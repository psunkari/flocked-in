import os
import hashlib
import uuid
import json
import cgi
import traceback
from base64     import urlsafe_b64encode
from telephus.cassandra import ttypes

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer, threads
from twisted.python     import log
from twisted.web        import static, server

from social             import db, utils, errors, base, feed, _
from social.relations   import Relation
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
    filetype = fs.type
    return (data, name, size, filetype)

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
                log.msg(cols[attachmentId][tuuid].split(':'))
                tuuid, fileId, name, size, ftype = cols[attachmentId][tuuid].split(':')
                files.append([itemId, attachmentId, tuuid, name, size, ftype])
        ##TODO: use some widget to list the files
        request.write(json.dumps(files))


    @defer.inlineCallbacks
    def _getFileInfo(self, request):

        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        relation = Relation(myId, [])

        itemId, item = yield utils.getValidItemId(request, 'id')
        attachmentId = utils.getRequestArg(request, "fid", sanitize=False)
        version = utils.getRequestArg(request, "ver", sanitize=False)

        if not attachmentId or not version:
            raise errors.MissingParams()

        # Check if the attachmentId belong to item
        if attachmentId not in item['attachments'].keys():
            raise errors.AccessDenied()

        version = utils.decodeKey(version)
        fileId, filetype, name = None, 'text/plain', 'file'
        cols = yield db.get(itemId, "item_files", version, attachmentId)
        cols = utils.columnsToDict([cols])
        if not cols or version not in cols:
            raise errors.InvalidRequest()

        tuuid, fileId, name, size, filetype = cols[version].split(':')

        files = yield db.get_slice(fileId, "files", ["meta"])
        files = utils.supercolumnsToDict(files)

        url = files['meta']['uri']
        defer.returnValue([url, filetype, size, name])

    def _renderFile(self, request):
        d = self._getFileInfo(request)
        def renderFile(fileInfo):
            url, filetype, size, name = fileInfo
            fileObj = static.File(url, filetype)
            request.setHeader('Cache-control', 'no-cache')
            request.setHeader('Content-Disposition', 'attachment;filename = \"%s\"' %(name))
            fileObj.render(request)

        d.addCallback(renderFile)


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
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        itemType = utils.getRequestArg(request, 'type')
        feedId = myId
        args["feedTitle"] = _("News Feed")
        args["menuId"] = "feed"
        args["feedId"] = feedId
        args['itemType']=itemType
        start = utils.getRequestArg(request, "start") or ''
        feedItems = yield feed.getFeedItems(request, feedId=feedId, start=start)
        args.update(feedItems)

        fs = cgi.FieldStorage(request.content,
                              request.getAllHeaders(),
                              environ={'REQUEST_METHOD':'POST'})
        if 'file' in fs:
            tmp_files = []
            tmp_files_info = {}
            files = fs['file'] if len(fs.getlist('file')) >1 else [fs['file']]
            for fsi in files:
                data, name, size, filetype = yield threads.deferToThread(_getFileInfo, fsi)
                if data:
                    fileId = _getFileId(data)
                    tmpFileId = utils.getUniqueKey()
                    location = _get_tmpfile_location(fileId)
                    try:
                        yield threads.deferToThread(_writeToFile, location, data)
                        val = "%s:%s:%s:%s"%(location, name, size, filetype)
                        tmp_files.append((tmpFileId, val))
                        tmp_files_info[tmpFileId] = [location, name, size, filetype]
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

    def render_GET(self, request):
        d = None
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            self._renderFile(request)
            return server.NOT_DONE_YET
        if segmentCount == 1:
            d = self._listFileVersions(request)
        return self._epilogue(request, d)

    def render_POST(self, request):
        d = None
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self.upload(request)
        if segmentCount == 1 and request.postpath[0]=="new_version":
            d = self._upload_new_version(request)
        return self._epilogue(request, d)
