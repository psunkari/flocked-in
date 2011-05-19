import uuid
import pickle
import re
import pytz, time, datetime



from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base, errors
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
    def _deliverMessage(self, convId, recipients, timeUUID, owner):

        dontDeliver = set()
        cols = yield Db.get_slice(convId, "mConversations", ['uuid'])
        cols = utils.columnsToDict(cols)

        oldTimeUUID = cols['uuid']
        val = "u:%s" %(convId)

        cols = yield Db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in cols:
            for folder in cols[recipient]:
                cf = folders[folder] if folder in folders else folder
                yield Db.remove(recipient, cf, oldTimeUUID)
                if cf == 'mDeletedConversations':
                    yield Db.insert(recipient, cf,  val, timeUUID)
                    #don't add to recipient's inbox if the conv is deleted.
                    dontDeliver.add(recipient)

        for recipient in recipients:
            if recipient not in dontDeliver:
                val = "u:%s"%(convId) if recipient!= owner else 'r:%s'%(convId)
                if recipient != owner:
                    yield Db.insert(recipient, 'mUnreadConversations',  val, timeUUID)
                    yield Db.insert(convId, "mConvFolders", '', 'mUnreadConversations', recipient)
                yield Db.insert(recipient, 'mAllConversations',  val, timeUUID)
                yield Db.insert(convId, "mConvFolders", '', 'mAllConversations', recipient)


    def _createDateHeader(self, timezone='Asia/Kolkata'):
        #FIX: get the timezone from userInfo
        tz = pytz.timezone(timezone)
        dt = tz.localize(datetime.datetime.now())
        fmt_2822 = "%a, %d %b %Y %H:%M:%S %Z%z"
        date = dt.strftime(fmt_2822)
        epoch = time.mktime(dt.timetuple())
        return date, epoch

    @defer.inlineCallbacks
    def _newMessage(self, ownerId, timeUUID, body, dateHeader, epoch):

        messageId = utils.getUniqueKey()
        meta =  { "owner": ownerId,
                 "timestamp": str(int(time.time())),
                 'Date':dateHeader,
                 'date_epoch': str(epoch),
                 "body": body,
                 "uuid": timeUUID
                }
        yield Db.batch_insert(messageId, "messages", {'meta':meta})
        defer.returnValue(messageId)

    @defer.inlineCallbacks
    def _newConversation(self, ownerId, recipients, timeUUID,
                         subject, dateHeader, epoch):

        acl = pickle.dumps({'accept':{'users':recipients}})
        conv_meta = {"acl": acl,
                     "owner":ownerId,
                     "timestamp": str(int(time.time())),
                     "uuid": timeUUID,
                     "Date": dateHeader,
                     "date_epoch" : str(epoch),
                     "subject": subject}
        convId = utils.getUniqueKey()
        yield Db.batch_insert(convId, "mConversations", conv_meta)
        defer.returnValue(convId)

    @defer.inlineCallbacks
    def _reply(self, request):

        myId = request.getSession(IAuthInfo).username
        recipients, body, subject, convId = self._parseComposerArgs(request)
        dateHeader, epoch = self._createDateHeader()

        if not convId and not recipients:
            raise errors.MissingParams()

        cols = yield Db.get_slice(convId, "mConversations", ['acl'])
        if not cols:
            raise errors.InvalidRequest()

        recipients = pickle.loads(cols[0].column.value)['accept']['users']
        timeUUID = uuid.uuid1().bytes

        messageId = yield self._newMessage(myId, timeUUID, body, dateHeader, epoch)
        yield self._deliverMessage(convId, recipients, timeUUID, myId)
        yield Db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield Db.batch_insert(convId, "mConversations", {'uuid': timeUUID,
                                                         'Date': dateHeader,
                                                         'date_epoch': str(epoch)})
        request.redirect('/messages')


    @defer.inlineCallbacks
    def _createConveration(self, request):

        myId = request.getSession(IAuthInfo).username
        recipients, body, subject, parent = self._parseComposerArgs(request)
        dateHeader, epoch = self._createDateHeader()

        if not parent and not recipients:
            raise errors.MissingParams()

        cols = yield Db.multiget_slice(recipients, "entities", ['basic'])
        recipients = utils.multiSuperColumnsToDict(cols)
        recipients = set([userId for userId in recipients if recipients[userId]])

        if not recipients:
            raise errors.MissingParams()
        recipients.add(myId)
        recipients = list(recipients)

        timeUUID = uuid.uuid1().bytes
        convId = yield self._newConversation(myId, recipients, timeUUID,
                                             subject, dateHeader, epoch)
        messageId = yield self._newMessage(myId, timeUUID, body, dateHeader, epoch)
        yield self._deliverMessage(convId, recipients, timeUUID, myId)
        yield Db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield Db.batch_insert(convId, "mConversations", {'uuid': timeUUID,
                                                         'Date': dateHeader,
                                                         'date_epoch': str(epoch)})

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
        folder = utils.getRequestArg(request, 'filter')
        folder = folders[folder] if folder in folders else folders['inbox']

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        unread = []
        convs = []
        users = set()

        cols = yield Db.get_slice(myKey, folder, reverse=True)
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
    def _addMembers(self, request):

        newMembers, body, subject, convId = self._parseComposerArgs(request)
        if not (convId or  recipients):
            raise errors.MissingParams()
        conv = yield Db.get_slice(convId, "mConversations")
        if not conv:
            raise errors.MissingParams()
        conv = utils.columnsToDict(conv)

        cols = yield Db.multiget_slice(newMembers, "entities", ['basic'])
        newMembers = set([userId for userId in cols if cols[userId]])
        recipients =  set(pickle.loads(conv['acl'])['accept']['users'])
        newMembers = newMembers - recipients
        recipients.update(newMembers)
        acl = pickle.dumps({"accept":{"users":list(recipients)}})
        yield Db.insert(convId, "mConversations", acl, 'acl')
        yield self._deliverMessage(convId, newMembers, conv['uuid'], conv['owner'])


    @defer.inlineCallbacks
    def _deleteMembers(self, request):
        members, body, subject, convId = self._parseComposerArgs(request)
        if not (convId or  recipients):
            raise errors.MissingParams()
        if not conv:
            raise errors.MissingParams()
        conv = utils.columnsToDict(conv)
        cols = yield Db.multiget_slice(members, "entities", ['basic'])
        members = set([userId for userId in cols if cols[userId]])
        recipients =  set(pickle.loads(conv['acl'])['accept']['users'])
        members = members.intersection(recipients)
        new_recipients = list(recipients - members)

        cols = yield Db.multiget_slice(newMembers, "entities", ['basic'])
        acl = pickle.dumps({"accept":{"users":new_recipients}})
        yield Db.insert(convId, "mConversations", acl, 'acl')

        cols = yield Db.get_slice(convId, 'mConvFolders', members)
        cols = utils.supercolumnsToDict(cols)
        for recipient in cols:
            for folder in cols[recipient]:
                cf = folders[folder] if folder in folders else folder
                yield Db.remove(recipient, cf, conv['uuid'])

    @defer.inlineCallbacks
    def _actions(self, request):

        convIds = request.args.get('selected', [])

        delete = utils.getRequestArg(request, "delete")
        archive = utils.getRequestArg(request, "archive")
        unread = utils.getRequestArg(request, "unread")
        unArchive = utils.getRequestArg(request, "inbox")
        if not convIds:
            raise errors.MissingParams()
        if delete:
            yield self._markAsDelete(request)
        if archive:
            yield self._moveConversation(request, convIds, 'archive')
        if unread:
            yield self._moveConversation(request, convIds, 'unread')
        if unArchive:
            yield self._moveConversation(request, convIds, 'inbox')



    @defer.inlineCallbacks
    def _markAsDelete(self, request):
        defer.returnValue(True)

    @defer.inlineCallbacks
    def _moveConversation(self, request, convIds, toFolder):


        myId = request.getSession(IAuthInfo).username

        for convId in convIds:
            conv = yield Db.get_slice(convId, "mConversations")
            if not conv:
                raise errors.InvalidRequest()
            conv = utils.columnsToDict(conv)
            timeUUID = conv['uuid']

            val = "%s:%s"%( 'u' if toFolder == 'unread' else 'r', convId)

            cols = yield Db.get_slice(convId, 'mConvFolders', [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                cf = folders[folder] if folder in folders else folder
                if toFolder!='unread':
                    if folder!= 'mUnreadConversations':
                        col = yield Db.get(myId, cf, timeUUID)
                        val = col.column.value
                        yield Db.remove(myId, cf, timeUUID)
                        yield Db.remove(convId, "mConvFolders", cf, myId)
                else:
                        yield Db.insert(myId, cf, "u:%s"%(convId), timeUUID)


            if toFolder == 'unread':
                val = "u:%s"%(convId)
                yield Db.insert(convId, 'mConvFolders', '', 'mUnreadConversations', myId)
                yield Db.insert(myId, 'mUnreadConversations', val, timeUUID)
            else:
                folder = folders[toFolder]
                yield Db.insert(myId, folder, val, timeUUID)
                yield Db.insert(convId, 'mConvFolders', '', folder, myId)
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
            yield Db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
            cols = yield Db.get_slice(convId, "mConvFolders", [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                if folder in folders:
                    folder = folders[folder]
                yield Db.insert(myId, folder, "r:%s"%(convId), timeUUID)

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
            d = self._actions(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._actions(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._composeMessage(request)
        elif segmentCount == 1 and request.postpath[0] == "reply":
            d = self._reply(request)

        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._actions(request)

        return self._epilogue(request, d)
