import uuid
import pickle


from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock



class MessagingResource(base.BaseResource):

    isLeaf = True
    def _parseComposerArgs(self, request):
        #Since we will deal with composer related forms. Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        body = body.decode('utf-8').encode('utf-8', "replace")
        parent = utils.getRequestArg(request, "parent") #TODO
        subject = utils.getRequestArg(request, "subject") or None
        if subject: subject.decode('utf-8').encode('utf-8', "replace")
        recipients = utils.getRequestArg(request, "recipients")
        recipients = re.sub(',\s+', ',', recipients).split(",")
        return recipients, body, subject, parent

    @defer.inlineCallbacks
    def _deliverMessage(self, convId, recipients, timeUUID):

        folders = {'inbox':'mAllConversations',
                   'archive':'mArchivedConversations',
                   'delete':'mDeletedConversations',
                   'unread':'mUnreadConversations'}

        oldTimeUUID = None
        cols = yield Db.get_slice(convId, "messages", ["meta"])
        cols = utils.supercolumnsToDict(cols)
        oldTimeUUID = cols['meta'].get('uuid', None)
        oldTimeUUID = None if timeUUID == oldTimeUUID else oldTimeUUID
        val = "u:%s"%(convId)

        for recipient in recipients:
            cols = yield Db.get_slice(convId, 'mConvFolders', recipient)
            if oldTimeUUID:
                folder = cols.column.value
                if folder == 'delete':
                    #don't add to recipient's inbox if the conv is deleted.
                    pass
                else:
                    yield Db.remove(recipient, folders[folder], oldTimeUUID)
                    yield Db.remove(recipient, folders['unread'], oldTimeUUID)
                    yield Db.insert(recipient, 'mAllConversations',  val, timeUUID)
                    yield Db.insert(recipient, 'mUnreadConversations',  val, timeUUID)
            else:
                yield Db.insert(recipient, 'mUnreadConversations',  val, timeUUID)
                yield Db.insert(recipient, 'mAllConversations',  val, timeUUID)





    @defer.inlineCallbacks
    def _createConveration(self, request):

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        recipients, body, subject, parent = self._parseComposerArgs(request)
        dateHeader, epoch = self._createDateHeader()
        messageId = utils.getUniqueKey()
        convId = messageId if not parent else parent
        cols = yield Db.multiget_slice(recipients, "entities", ['basic'])
        recipients = utils.multiSuperColumnsToDict(cols)
        recipients = [userId for userId in recipients if recipients[userId]]
        if not recipients:
            raise errors.MissingParams()
        acl = pickle.dumps({'accept':{'users':recipients}})
        timeUUID = uuid.uuid1().bytes
        meta = { "acl": acl,
                 "owner": myId,
                 "timestamp": str(int(time.time())),
                 'Date':dateHeader,
                 'date_epoch': str(epoch),
                 "subject": subject,
                 "uuid": timeUUID
                }
        yield Db.batch_insert(messageId, "messages", {'meta':meta})
        yield self._deliverMessage(convId, recipients +[myId], timeUUID)


    @defer.inlineCallbacks
    def _composeMessage(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        yield self._createConveration(request)
        request.redirect('/messages')

    @defer.inlineCallbacks
    def _listConversations(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)




        unread = []
        convs = []
        users = set()

        cols = yield Db.get_slice(myKey, 'mAllConversations', reverse=True)
        for col in cols:
            x, convId = col.column.value.split(':')
            convs.append(convId)
            if x == 'u':
                unread.append(convId)
        cols = yield Db.multiget_slice(convs, 'messages', ["meta"])
        messages = utils.multiSuperColumnsToDict(cols)
        m={}
        for mid in messages:
            acl = pickle.loads(messages[mid]['meta']['acl'])
            users.update(acl['accept']['users'])
            messages[mid]['meta']['people'] = acl['accept']['users']
            messages[mid]['meta']['read'] = str(int(mid not in unread))
            m[mid]=messages[mid]['meta']

        users.add(myKey)


        users = yield Db.multiget_slice(users, 'entities', ['basic'])
        users = utils.multiSuperColumnsToDict(users)

        args.update({"view":"messages"})
        args.update({"messages":m})
        args.update({"people":users})
        args.update({"mids": convs})
        args.update({"fid": None})
        args['start']=''
        args['end']=''
        folderId=None

        if script:
            yield renderScriptBlock(request, "message.mako", "center", landing,
                                    ".center-contents", "set", True, **args)
        else:
            yield render(request, "message.mako", **args)


    @defer.inlineCallbacks
    def _renderConversation(self, request):
        request.redirect('/messages')

    @defer.inlineCallbacks
    def _reply(self, request):
        pass

    @defer.inlineCallbacks
    def _addMembers(self, request):
        pass

    @defer.inlineCallbacks
    def _deleteMembers(self, request):
        pass

    @defer.inlineCallbacks
    def deleteConversation(self, request):
        pass

    @defer.inlineCallbacks
    def _moveConversation(self, request):
        request.redirect('/messages')

    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        parent = utils.getRequestArg(request, "parent")
        action = utils.getRequestArg(request, "action") or "reply"
        folderId = utils.getRequestArg(request, "fid") or None

        folders = yield self._getFolders(myKey)
        if folderId is None:
            #Find the Inbox of this user and set it.
            folderId = self._getSpecialFolder(myKey, folders)
        else:
            # Make sure user has access to the folder
            res = yield self._checkUserFolderACL(myKey, folderId)
            if not res:
                request.redirect("/messages")

        args["folders"] = folders
        args.update({"fid":folderId})

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if parent:
            hasAccess = yield self._checkUserHasMessageAccess(myKey, parent)
            if not hasAccess:
                raise Unauthorized

            res = yield Db.multiget_slice(keys=[parent], column_family="messages")
            res = utils.multiColumnsToDict(res)
            if parent in res.keys():
                parent_msg = res[parent]
            else:
                parent_msg = None
            args.update({"parent_msg":parent_msg})
            if action == "forward":
                args.update({"view":"forward"})
            else:
                args.update({"view":"reply"})
            if script:
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)
        else:
            args.update({"view":"compose"})
            if script:
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)





    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listConversations(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._renderConversation(request)
        elif segmentCount == 1 and request.postpath[0] == "actions":
            d = self._threadActions(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._moveConversation(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._composeMessage(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._moveConversation(request)

        return self._epilogue(request, d)
        pass
