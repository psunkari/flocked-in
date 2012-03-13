import json
import mimetypes
from base64         import urlsafe_b64encode, urlsafe_b64decode
from email.header   import Header
try:
    import cPickle as pickle
except:
    import pickle

import boto
from telephus.cassandra     import ttypes
from txaws.credentials      import AWSCredentials
from txaws.s3               import client as s3Client
from boto.s3.connection     import S3Connection
from boto.s3.connection     import VHostCallingFormat, SubdomainCallingFormat

from twisted.internet       import defer, threads

from social                 import db, utils, errors, base,  _, config
from social                 import constants, template as t
from social.relations       import Relation
from social.isocial         import IAuthInfo
from social.logging         import profile, dump_args


@defer.inlineCallbacks
def pushfileinfo(myId, orgId, convId, conv):
    acl = pickle.loads(conv['meta']['acl'])

    allowedGroups = acl.get('accept', {}).get('groups', [])
    deniedGroups = acl.get('deny', {}).get('groups', [])
    groups = [x for x in allowedGroups if x not in deniedGroups]
    allowedOrgs = acl.get('accept', {}).get('orgs', [])
    ownerId = conv['meta']['owner']

    entityIds = [myId]
    entityIds.extend(groups)
    entityIds.extend(allowedOrgs)
    entityIds_ = yield utils.expandAcl(myId, orgId, conv['meta']['acl'], convId, ownerId, True)
    entityIds.extend(entityIds_)

    for attachmentId in conv.get('attachments', {}):
        tuuid, name, size, ftype = conv['attachments'][attachmentId].split(':')
        tuuid = utils.decodeKey(tuuid)
        value = '%s:%s:%s:%s' % (attachmentId, name, convId, ownerId)
        #TODO: use batch remove/batch mutate
        yield db.insert(myId, "user_files", value, tuuid)
        for entityId in entityIds:
            yield db.insert(entityId, "entityFeed_files", value, tuuid)


@defer.inlineCallbacks
def deleteFileInfo(myId, orgId, convId, conv):
    acl = pickle.loads(conv['meta']['acl'])

    allowedGroups = acl.get('accept', {}).get('groups', [])
    deniedGroups = acl.get('deny', {}).get('groups', [])
    groups = [x for x in allowedGroups if x not in deniedGroups]
    allowedOrgs = acl.get('accept', {}).get('orgs', [])
    ownerId = conv['meta']['owner']

    entityIds = [myId]
    entityIds.extend(groups)
    entityIds.extend(allowedOrgs)
    entityIds_ = yield utils.expandAcl(myId, orgId, conv['meta']['acl'], convId, ownerId, True)
    entityIds.extend(entityIds_)
    deferreds = []
    for attachmentId in conv.get('attachments', {}):
        tuuid, name, size, ftype = conv['attachments'][attachmentId].split(':')
        tuuid = utils.decodeKey(tuuid)
        deferreds.append(db.remove(myId, "user_files", tuuid))
        #TODO: use batch remove/batch mutate
        for entityId in entityIds:
            deferreds.append(db.remove(entityId, "entityFeed_files", tuuid))
    if deferreds:
        yield defer.DeferredList(deferreds)

@profile
@defer.inlineCallbacks
@dump_args
def userFiles(myId, entityId, myOrgId, start='', end='', fromFeed=True):
    allItems = {}
    hasPrevPage = False     # Do we have another page before the current one.
    nextPageStart = ''      # Start item for the next page
    accessibleFiles = []
    accessibleItems = []
    toFetchEntities = set()

    count = constants.FILES_PER_PAGE
    toFetchCount = count + 1

    relation = Relation(myId, [])
    yield relation.initGroupsList()

    # Fetching files owned by entityId or files that were part of entityId's feed.
    cf = 'entityFeed_files' if fromFeed else 'user_files'

    # End is actually the start item of next page.
    # If @end is set, we have to display @count items before @end.  For that
    # we fetch @count + 2 items before (and including) @end. Of the extra items
    # fetched, one item helps us determine if there is another page before this
    # and the other one is the start of next page.
    if end:
        start = end
        reverse = False
        toFetchCount += 1
    else:
        reverse = True

    while 1:
        files = yield db.get_slice(entityId, cf, count=toFetchCount, start=start, reverse=reverse)
        files = utils.columnsToDict(files, True)
        toFetchItems = []
        for tuuid in files:
            if len(files[tuuid].split(':')) == 4:
                fid, name, itemId, attachmentId = files[tuuid].split(':')
                toFetchItems.append(itemId)

        toFetchItems = [itemId for itemId in toFetchItems if itemId not in accessibleItems]
        if toFetchItems:
            items = yield db.multiget_slice(toFetchItems, "items", ["meta"])
            items = utils.multiSuperColumnsToDict(items)
            for itemId in items:
                acl = items[itemId]['meta']['acl']
                if utils.checkAcl(myId, myOrgId, False, relation, items[itemId]['meta']):
                    accessibleItems.append(itemId)
            allItems.update(items)

        for tuuid in files:
            if len(files[tuuid].split(':')) == 4:
                fid, name, itemId, ownerId = files[tuuid].split(':')
                if itemId in accessibleItems:
                    accessibleFiles.append((tuuid,
                                            (fid, urlsafe_b64decode(name),
                                             itemId, ownerId, allItems[itemId])))
                    toFetchEntities.add(ownerId)

        if len(files) < toFetchCount or len(accessibleFiles) > count:
            break
        else:
            start = files.keys()[-1]

    if end:
        # We have enough items to have another page before this.
        if len(accessibleFiles) > count + 1:
            hasPrevPage = True
            accessibleFiles = accessibleFiles[:count + 1]

        # Revert the list to get most recent items first.
        accessibleFiles.reverse()

        # The last item is actually the first item of next page.
        nextPageStart = accessibleFiles[-1][0]
        accessibleFiles = accessibleFiles[:-1]

    elif start:
        hasPrevPage = True  # XXX: may not always be true, but the edge case is OK

    if len(accessibleFiles) > count:
        nextPageStart = accessibleFiles[count][0]
        accessibleFiles = accessibleFiles[:count]

    defer.returnValue((accessibleFiles, hasPrevPage, nextPageStart, toFetchEntities))


class FilesResource(base.BaseResource):
    isLeaf = True
    _templates = ['files.mako']

    @defer.inlineCallbacks
    def _listFileVersions(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        relation = Relation(myId, [])

        attachmentId = utils.getRequestArg(request, "fid", sanitize=False)
        itemId, item = yield utils.getValidItemId(request, 'id')

        if not attachmentId:
            raise errors.MissingParams()

        # Check if the attachmentId belong to item
        if attachmentId not in item.get('attachments', {}).keys():
            version = None
            raise errors.AttachmentAccessDenied(itemId, attachmentId, version)

        #get the latest file
        files = []
        cols = yield db.get_slice(itemId, "item_files", [attachmentId], reverse=True)
        cols = utils.supercolumnsToDict(cols)
        for attachmentId in cols:
            fileId, ftype, name = None, 'text/plain', 'file'
            for tuuid in cols[attachmentId]:
                tuuid, fileId, name, size, ftype = cols[attachmentId][tuuid].split(':')
                files.append([itemId, attachmentId, tuuid, name, size, ftype])
        ##TODO: use some widget to list the files
        request.write(json.dumps(files))

    @defer.inlineCallbacks
    def _getFileInfo(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        itemId, item = yield utils.getValidItemId(request, 'id')
        attachmentId = utils.getRequestArg(request, "fid", sanitize=False)
        version = utils.getRequestArg(request, "ver", sanitize=False)

        if not attachmentId or not version:
            raise errors.MissingParams()

        # Check if the attachmentId belong to item
        if attachmentId not in item['attachments'].keys():
            raise errors.EntityAccessDenied("attachment", attachmentId)

        item = yield db.get_slice(itemId, "items", ["meta"])
        item = utils.supercolumnsToDict(item)
        owner = item["meta"]["owner"]

        version = utils.decodeKey(version)
        fileId, fileType, name = None, 'text/plain', 'file'
        cols = yield db.get(itemId, "item_files", version, attachmentId)
        cols = utils.columnsToDict([cols])
        if not cols or version not in cols:
            raise errors.InvalidRequest()

        tuuid, fileId, name, size, fileType = cols[version].split(':')

        files = yield db.get_slice(fileId, "files", ["meta"])
        files = utils.supercolumnsToDict(files)

        url = files['meta']['uri']
        defer.returnValue([owner, url, fileType, size, name])

    @defer.inlineCallbacks
    def _renderFile(self, request):
        fileInfo = yield self._getFileInfo(request)
        owner, url, fileType, size, name = fileInfo
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        filename = urlsafe_b64decode(name)
        try:
            filename.decode('ascii')
        except UnicodeDecodeError:
            filename = filename.decode('utf-8').encode('utf-8')
            filename = str(Header(filename, "UTF-8")).encode('string_escape')
        else:
            filename = filename.encode('string_escape')

        headers = {'response-content-type': fileType,
                   'response-content-disposition': 'attachment;filename=\"%s\"' % filename,
                   'response-expires': '0'}

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        domain = config.get('CloudFiles', 'Domain')
        bucket = config.get('CloudFiles', 'Bucket')
        if domain == "":
            calling_format = SubdomainCallingFormat()
            domain = "s3.amazonaws.com"
        else:
            calling_format = VHostCallingFormat()
        conn = S3Connection(AKey, SKey, host=domain, is_secure=True,
                            calling_format=calling_format)

        Location = conn.generate_url(600, 'GET', bucket,
                                     '%s/%s/%s' % (myOrgId, owner, url),
                                     response_headers=headers)

        request.setResponseCode(307)
        request.setHeader('Location', Location)

    @defer.inlineCallbacks
    def _s3Update(self, request):
        pass

    @defer.inlineCallbacks
    def _S3FormData(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        landing = not self._ajax
        myOrgId = args["orgId"]

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        domain = config.get('CloudFiles', 'Domain')
        bucket = config.get('CloudFiles', 'Bucket')
        if domain == "":
            calling_format = SubdomainCallingFormat()
            domain = "s3.amazonaws.com"
        else:
            calling_format = VHostCallingFormat()
        conn = S3Connection(AKey, SKey, host=domain, is_secure=True,
                            calling_format=calling_format)
        filename = utils.getRequestArg(request, "name") or None
        #TODO:If name is None raise an exception
        mime = utils.getRequestArg(request, "mime") or None
        if mime:
            if not mimetypes.guess_extension(mime):
                mime = mimetypes.guess_type(filename)[0]
        else:
            mime = mimetypes.guess_type(filename)[0]

        if not mime:
            mime = "text/plain"

        filename = urlsafe_b64encode(filename)
        fileId = utils.getUniqueKey()
        key = '%s/%s/%s' % (myOrgId, myId, fileId)
        attachment_filename = 'attachment;filename=\"%s\"' % (filename)
        x_conds = ['{"x-amz-meta-uid":"%s"}' % myId,
                   '{"x-amz-meta-filename":"%s"}' % filename,
                   '{"x-amz-meta-fileId":"%s"}' % fileId,
                   '{"content-type":"%s"}' % mime]

        x_fields = [{"name":"x-amz-meta-uid", "value":"%s" % myId},
                    {"name":"x-amz-meta-filename", "value":"%s" % filename},
                    {"name":"content-type", "value":"%s" % mime},
                    {"name":"x-amz-meta-fileId", "value":"%s" % fileId}]

        max_content_length = constants.MAX_FILE_SIZE
        x_conds.append('["content-length-range", 0, %i]' % max_content_length)

        redirect_url = config.get('General', 'URL') + "/files/update"
        form_data = conn.build_post_form_args(bucket,
                                  key,
                                  http_method="https",
                                  fields=x_fields,
                                  conditions=x_conds,
                                  success_action_redirect=redirect_url)
        request.write(json.dumps([form_data]))
        defer.returnValue(0)

    def _enqueueMessage(self, bucket, key, filename, content_type):
        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')

        thumbnailsBucket = config.get('CloudFiles', 'ThumbnailsBucket')
        thumbnailsQueue = config.get('CloudFiles', 'ThumbnailsQueue')

        sqsConn = boto.connect_sqs(AKey, SKey)
        queue = sqsConn.get_queue(thumbnailsQueue)
        if not queue:
            queue = sqsConn.create_queue(thumbnailsQueue)

        data = {'bucket': bucket, 'filename': filename,
                 'key': key, 'content-type': content_type}
        message = queue.new_message(body=json.dumps(data))
        queue.write(message)

    @defer.inlineCallbacks
    def _uploadDone(self, request):
        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')

        creds = AWSCredentials(AKey, SKey)
        client = s3Client.S3Client(creds)
        bucket = utils.getRequestArg(request, "bucket")
        key = utils.getRequestArg(request, "key")

        file_info = yield client.head_object(bucket, key)
        tmp_files_info = {}

        name = file_info['x-amz-meta-filename'][0]
        size = file_info['content-length'][0]
        fileType = file_info['content-type'][0]
        fileId = file_info['x-amz-meta-fileid'][0]
        val = "%s:%s:%s:%s" % (fileId, name, size, fileType)
        filename = urlsafe_b64decode(name)
        tmp_files_info[fileId] = [fileId, filename, size, fileType]

        # XXX: We currently don't generate any thumbnails!
        # yield threads.deferToThread(self._enqueueMessage, bucket, key, name, fileType)

        yield db.insert(fileId, "tmp_files", val, "fileId")

        response = """
                        <textarea data-type="application/json">
                          {"ok": true, "files": %s}
                        </textarea>
                   """ % (json.dumps(tmp_files_info))
        request.write(response)

    @defer.inlineCallbacks
    def _removeTempFile(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgId"]

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        bucket = config.get('CloudFiles', 'Bucket')
        creds = AWSCredentials(AKey, SKey)

        client = s3Client.S3Client(creds)
        fileId = utils.getRequestArg(request, "id")
        key = "%s/%s/%s" % (myOrgId, myId, fileId)

        #Check if the file is not in the "files" CF. In other words, it is not
        # attached to an existing item. Also check if I am the owner of the
        # file. Finally clear the existing entry in the "temp_files" CF
        res = yield db.get_slice(fileId, "tmp_files", ["fileId"])
        if len(res) == 1:
            try:
                res = yield db.get(fileId, "files", super_column="meta")
            except ttypes.NotFoundException:
                file_info = yield client.head_object(bucket, key)
                owner = file_info['x-amz-meta-uid'][0]
                if owner == myId:
                    yield client.delete_object(bucket, key)
                    yield db.remove(fileId, "tmp_files")
                else:
                    raise errors.EntityAccessDenied("attachment", fileId)
            else:
                raise errors.InvalidRequest()

    @defer.inlineCallbacks
    def _renderFileList(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgId"]

        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)
        end = utils.getRequestArg(request, "end") or ''
        end = utils.decodeKey(end)

        viewType = utils.getRequestArg(request, "type")
        viewType = viewType if viewType in ['myFiles', 'companyFiles', 'myFeedFiles'] else 'myFiles'

        args['menuId'] = 'files'
        if script and landing:
            t.render(request, "files.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "files.mako", 'layout',
                                landing, "#mainbar", "set", **args)

        args['viewType'] = viewType
        entityId = myId if viewType in ['myFiles', 'myFeedFiles'] else myOrgId
        fromFeed = viewType != 'myFiles'

        if script:
            t.renderScriptBlock(request, "files.mako", "viewOptions",
                                landing, "#file-view", "set", args=[viewType])

        files = yield userFiles(myId, entityId, args['orgId'], start, end, fromFeed)

        toFetchEntities = files[3]
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        args['entities'] = entities
        args['userfiles'] = files

        if script:
            t.renderScriptBlock(request, "files.mako", "listFiles",
                                landing, "#files-content", "set", **args)
            t.renderScriptBlock(request, "files.mako", "pagingBar",
                                landing, "#files-paging", "set", **args)

        else:
            t.render(request, "files.mako", **args)

    def render_GET(self, request):
        d = None
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self._renderFile(request)
        elif  segmentCount == 1 and request.postpath[0] == "update":
            d = self._uploadDone(request)
        elif segmentCount == 1 and request.postpath[0] == 'list':
            d = self._renderFileList(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        d = None
        segmentCount = len(request.postpath)
        if  segmentCount == 1 and request.postpath[0] == "form":
            d = self._S3FormData(request)
        elif  segmentCount == 1 and request.postpath[0] == "remove":
            d = self._removeTempFile(request)

        return self._epilogue(request, d)
