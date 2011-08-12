import os
import hashlib
import uuid
import json
import cgi
import traceback
import mimetypes
from base64     import urlsafe_b64encode, urlsafe_b64decode
from email.header import Header

import boto
from telephus.cassandra import ttypes
from txaws.credentials import AWSCredentials
from txaws.s3 import client as s3Client
from boto.s3.connection import S3Connection
from boto.s3.connection import VHostCallingFormat, SubdomainCallingFormat

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer, threads
from twisted.python     import log
from twisted.web        import static, server

from social             import db, utils, errors, base, feed, _, config
from social.relations   import Relation
from social             import constants
from social.isocial     import IItemType, IAuthInfo
from social.template    import render, renderScriptBlock, getBlock


def _getFileId(data):
    return hashlib.sha1(data).hexdigest()

def _getFilePath(fileId):
    dirs = ['data', fileId[0:2], fileId[2:4], fileId[4:6]]
    return os.path.join(dirpath, fileId)

def _getFileInfo(fs):
    if fs.filename  is None:
        return (None, None, None, None)
    data = fs.file.read()
    size = len(data)
    name = fs.filename.replace('/', '\/').replace(':', '_')
    fileType = fs.type
    return (data, name, size, fileType)

def _get_tmpfile_location(fileId):
    return os.path.join('/tmp/social/data', fileId)

def _createDirs(dirpath):
    try:
        os.makedirs(dirpath, 0700)
    except OSError:
        pass

def _writeToFile(filepath, data):

    dirpath, filename = os.path.split(filepath)
    _createDirs(dirpath)

    if not os.path.lexists(filepath):
        try:
            with open(filepath, 'wb') as f:
                f.write(data)
        except IOError as e:
            traceback.print_exc()
            log.msg(e)
            raise e


class FilesResource(base.BaseResource):
    isLeaf = True

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
            raise errors.AccessDenied()

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

        headers={'response-content-type':fileType,
                 'response-content-disposition':'attachment;filename=\"%s\"'%filename,
                 'response-expires':'0'}

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        domain = config.get('CloudFiles', 'Domain')
        bucket = config.get('CloudFiles', 'Bucket')
        if domain == "":
            calling_format = SubdomainCallingFormat()
            domain = "s3.amazonaws.com"
        else:
            calling_format = VHostCallingFormat()
        conn = S3Connection(AKey, SKey, host=domain,
                            calling_format=calling_format)

        Location = conn.generate_url(600, 'GET', bucket,
                                     '%s/%s/%s' %(myOrgId, owner, url),
                                     response_headers=headers,
                                     force_http=True)

        request.setResponseCode(307)
        request.setHeader('Location', Location)

    @defer.inlineCallbacks
    def _upload_new_version(self, request):

        attachmentId = utils.getRequestArg(request, 'fid')
        itemId, item = yield utils.getValidItemId(request, 'id')

        if attachmentId not in item.get('attachments', {}).keys():
            raise errors.uploadFailed()

        fs = cgi.FieldStorage(request.content,
                              request.getAllHeaders(),
                              environ={'REQUEST_METHOD':'POST'})

        if 'file' in fs:
            fsi = fs['file'][0] if len(fs.getlist('file')) >1 else fs['file']
            data, name, size, ftype = yield threads.deferToThread(_getFileInfo, fsi)
            if data:
                fileId = _getFileId(data)
                location = _getFilePath(fileId)
                timeuuid = uuid.uuid1().bytes
                try:
                    yield threads.deferToThread(_writeToFile, location, data)
                    val = "%s:%s:%s:%s" %(utils.encodeKey(timeuuid), name, size, ftype)
                    val1= "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fileId, name, size, ftype)
                    yield db.insert(itemId, "items", val, attachmentId, "attachments")
                    yield db.insert(itemId, "item_files", val1, timeuuid, attachmentId)
                    #args = [itemId, attachmentId, utils.encodeKey(timeuuid),name, size]
                    #yield renderScriptBlock(request, 'item.mako', 'set_attachment', False,
                    #                        "#%s"%(attachmentId), "set", args = args)
                except OSError:
                    raise errors.uploadFailed()


    @defer.inlineCallbacks
    def upload(self, request):
        fs = cgi.FieldStorage(request.content,
                              request.getAllHeaders(),
                              environ={'REQUEST_METHOD':'POST'})
        if 'file' in fs:
            tmp_files = []
            tmp_files_info = {}
            files = fs['file'] if len(fs.getlist('file')) >1 else [fs['file']]
            for fsi in files:
                data, name, size, fileType = yield threads.deferToThread(_getFileInfo, fsi)
                if data:
                    fileId = _getFileId(data)
                    tmpFileId = utils.getUniqueKey()
                    location = _get_tmpfile_location(fileId)
                    try:
                        yield threads.deferToThread(_writeToFile, location, data)
                        val = "%s:%s:%s:%s"%(location, name, size, fileType)
                        tmp_files.append((tmpFileId, val))
                        tmp_files_info[tmpFileId] = [location, name, size, fileType]
                    except Exception as e:
                        raise errors.uploadFailed()

            for tmp_file, val in tmp_files:
                yield db.insert(tmp_file, "tmp_files", val, "fileId")

            response = """
                            <textarea data-type="application/json">
                              {"ok": true, "files": %s}
                            </textarea>
                       """ % (json.dumps(tmp_files_info))
            request.write(response)

    @defer.inlineCallbacks
    def _s3Update(self, request):
        pass

    @defer.inlineCallbacks
    def _S3FormData(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        landing = not self._ajax
        myOrgId = args["orgKey"]

        log.msg("-------- S3 from ------------")

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        domain = config.get('CloudFiles', 'Domain')
        bucket = config.get('CloudFiles', 'Bucket')
        if domain == "":
            calling_format = SubdomainCallingFormat()
            domain = "s3.amazonaws.com"
        else:
            calling_format = VHostCallingFormat()
        conn = S3Connection(AKey, SKey, host=domain,
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
        key = '%s/%s/%s' %(myOrgId, myId, fileId)
        attachment_filename = 'attachment;filename=\"%s\"' %(filename)
        x_conds = ['{"x-amz-meta-uid":"%s"}' %myId,
                   '{"x-amz-meta-filename":"%s"}' %filename,
                   '{"x-amz-meta-fileId":"%s"}' %fileId,
                   '{"content-type":"%s"}' %mime]

        x_fields = [{"name":"x-amz-meta-uid","value":"%s" %myId},
                    {"name":"x-amz-meta-filename","value":"%s" %filename},
                    {"name":"content-type","value":"%s" %mime},
                    {"name":"x-amz-meta-fileId","value":"%s" %fileId}]

        max_content_length = constants.MAX_FILE_SIZE
        x_conds.append('["content-length-range", 0, %i]' % max_content_length)

        redirect_url = config.get('General', 'URL') + "/file/update"
        form_data = conn.build_post_form_args(bucket,
                                  key,
                                  http_method="http",
                                  fields=x_fields,
                                  conditions=x_conds,
                                  success_action_redirect=redirect_url)
        log.msg("--------- form data ---------", form_data)
        request.write(json.dumps([form_data]));
        defer.returnValue(0)

    def _enqueueMessage(self, bucket, key, filename, content_type):
        SKey =  config.get('CloudFiles', 'SecretKey')
        AKey =  config.get('CloudFiles', 'AccessKey')

        thumbnailsBucket = config.get('CloudFiles', 'ThumbnailsBucket')
        thumbnailsQueue = config.get('CloudFiles', 'ThumbnailsQueue')

        sqsConn = boto.connect_sqs(AKey, SKey)
        queue = sqsConn.get_queue(thumbnailsQueue)
        if not queue:
            queue = sqsConn.create_queue(thumbnailsQueue)

        data = {'bucket': bucket, 'filename': filename,
                 'key': key, 'content-type': content_type}
        message = queue.new_message(body= json.dumps(data))
        queue.write(message)



    @defer.inlineCallbacks
    def _uploadDone(self, request):
        SKey =  config.get('CloudFiles', 'SecretKey')
        AKey =  config.get('CloudFiles', 'AccessKey')

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
        val = "%s:%s:%s:%s"%(fileId, name, size, fileType)
        filename = urlsafe_b64decode(name)
        tmp_files_info[fileId] = [fileId, filename, size, fileType]

        yield threads.deferToThread(self._enqueueMessage, bucket, key, name, fileType)
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
        myOrgId = args["orgKey"]

        SKey =  config.get('CloudFiles', 'SecretKey')
        AKey =  config.get('CloudFiles', 'AccessKey')
        bucket = config.get('CloudFiles', 'Bucket')
        creds = AWSCredentials(AKey, SKey)

        client = s3Client.S3Client(creds)
        fileId = utils.getRequestArg(request, "id")
        key = "%s/%s/%s" %(myOrgId, myId, fileId)

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
    def _deleteFile(request):
        pass

    def render_GET(self, request):
        d = None
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self._renderFile(request)
        elif  segmentCount == 1 and request.postpath[0]=="update":
            d = self._uploadDone(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        d = None
        segmentCount = len(request.postpath)
        if  segmentCount == 1 and request.postpath[0]=="form":
            d = self._S3FormData(request)
        elif  segmentCount == 1 and request.postpath[0]=="remove":
            d = self._removeTempFile(request)
        #elif  segmentCount == 1 and request.postpath[0]=="delete":
        #    d = self._deleteFile(request)
        return self._epilogue(request, d)
