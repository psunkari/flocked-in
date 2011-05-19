import uuid
import pickle
import re
import pytz, time, datetime



from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock

folders = {'inbox':'mAllConversations',
           'archive':'mArchivedConversations',
           'delete':'mDeletedConversations',
           'unread':'mUnreadConversations'}


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
        if recipients:
            recipients = re.sub(',\s+', ',', recipients).split(",")
        return recipients, body, subject, parent

    @defer.inlineCallbacks
    def _deliverMessage(self, convId, recipients, timeUUID):

        oldTimeUUID = None
        cols = yield Db.get_slice(convId, "mConversations", ['uuid'])
        cols = utils.columnsToDict(cols)

        oldTimeUUID = cols.get('uuid', None)
        oldTimeUUID = None if timeUUID == oldTimeUUID else oldTimeUUID
        val = "u:%s"%(convId)

        cols = yield Db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in cols:
            deliver = True
            if oldTimeUUID:
                for folder in cols[recipient]:
                    if folder == 'delete':
                        #don't add to recipient's inbox if the conv is deleted.
                        deliver = False
                    else:
                        cf = folders[folder] if folder in folders else folder
                        yield Db.remove(recipient, cf, oldTimeUUID)
            if deliver:
                yield Db.insert(recipient, 'mUnreadConversations',  val, timeUUID)
                yield Db.insert(recipient, 'mAllConversations',  val, timeUUID)
                yield Db.insert(convId, "mConvFolders", '', 'mAllConversations', recipient)
                yield Db.insert(convId, "mConvFolders", '', 'mUnreadConversations', recipient)


    def _createDateHeader(self, timezone='Asia/Kolkata'):
        #FIX: get the timezone from userInfo
        tz = pytz.timezone(timezone)
        dt = tz.localize(datetime.datetime.now())
        fmt_2822 = "%a, %d %b %Y %H:%M:%S %Z%z"
        date = dt.strftime(fmt_2822)
        epoch = time.mktime(dt.timetuple())
        return date, epoch


    @defer.inlineCallbacks
    def _createConveration(self, request):

        myId = request.getSession(IAuthInfo).username

        recipients, body, subject, parent = self._parseComposerArgs(request)

        dateHeader, epoch = self._createDateHeader()

        messageId = utils.getUniqueKey()
        convId = utils.getUniqueKey() if not parent else parent

        if not parent and not recipients:
            raise errors.MissingParams()

        if not parent:
            cols = yield Db.multiget_slice(recipients, "entities", ['basic'])
            recipients = utils.multiSuperColumnsToDict(cols)
            recipients = [userId for userId in recipients if recipients[userId]]
            if not recipients:
                raise errors.MissingParams()
            recipients.append(myId)

        if parent:
            cols = yield Db.get_slice(parent, "mConversations", ['acl'])
            if not cols:
                raise errors.InvalidRequest()

            recipients = pickle.loads(cols[0].column.value)['accept']['users']



        timeUUID = uuid.uuid1().bytes
        if not parent:
            acl = pickle.dumps({'accept':{'users':recipients}})
            conv_meta = {"acl": acl,
                         "owner":myId,
                         "timestamp": str(int(time.time())),
                         "uuid": timeUUID,
                         "subject": subject}
            yield Db.batch_insert(convId, "mConversations", conv_meta)

        meta = { "owner": myId,
                 "timestamp": str(int(time.time())),
                 'Date':dateHeader,
                 'date_epoch': str(epoch),
                 "body": body,
                 "uuid": timeUUID
                }
        yield Db.batch_insert(messageId, "messages", {'meta':meta})
        yield self._deliverMessage(convId, recipients, timeUUID)
        yield Db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield Db.insert(convId, "mConversations", timeUUID, "uuid")

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
        cols = yield Db.multiget_slice(convs, 'mConversations')
        messages = utils.multiColumnsToDict(cols)
        m={}
        for mid in messages:
            if not messages[mid]:
                continue
            acl = pickle.loads(messages[mid]['acl'])
            users.update(acl['accept']['users'])
            users.add(messages[mid]['owner'])
            messages[mid]['people'] = acl['accept']['users']
            messages[mid]['read'] = str(int(mid not in unread))
            m[mid]=messages[mid]

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
    def _renderConversation(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convId = utils.getRequestArg(request, 'id')

        if script and landing:
            yield render(request, "message.mako", **args)


        if appchange and script:
            renderScriptBlock(request, "message.mako", "layout",
                              landing, "#mainbar", "set", **args)

        if convId:
            cols = yield Db.get_slice(convId, "mConversations")
            conv = utils.columnsToDict(cols)

            timeUUID = conv['uuid']
            yield Db.remove(myId, "mUnreadConversations", timeUUID)
            cols = yield Db.get_slice(myId, "mConvFolders", convId)
            #FIX: make sure that there will be an entry of convId in mConvFolders

            relation = Relation(myId, [])
            if not utils.checkAcl(myId, conv['acl'], conv['owner'], relation):
                errors.AccessDenied()

            acl = pickle.loads(conv['acl'])
            recipients = set(acl['accept']['users'] + [myId, conv['owner']])
            people = yield Db.multiget_slice(recipients, "entities", ['basic'])
            people = utils.multiSuperColumnsToDict(people)

            cols = yield Db.get_slice(convId, "mConvMessages")
            mids = []
            for col in cols:
                mids.append(col.column.value)
            messages = yield Db.multiget_slice(mids, "messages", ["meta"])
            messages = utils.multiSuperColumnsToDict(messages)


            args.update({"people":people})
            args.update({"conv":conv})
            args.update({"messageIds": mids})
            args.update({'messages': messages})
            args.update({"id":convId})
            args.update({"fid":None})
            args.update({"flags":{}})
            args.update({"view":"message"})
            if script:
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)




    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        parent = utils.getRequestArg(request, "parent")
        action = utils.getRequestArg(request, "action") or "reply"
        folderId = utils.getRequestArg(request, "fid") or None

        args["folders"] = folders
        args.update({"fid":folderId})

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if parent:
            hasAccess = True
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
