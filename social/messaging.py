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

class MessagingResource(base.BaseResource):
    isLeaf = True
    _folders = {'inbox': 'mAllConversations',
                'archive': 'mArchivedConversations',
                'trash': 'mDeletedConversations',
                'unread': 'mUnreadConversations'}

    def _parseComposerArgs(self, request):
        #Since we will deal with composer related forms. Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        if body:
            body = body.decode('utf-8').encode('utf-8', "replace")
        parent = utils.getRequestArg(request, "parent") #TODO
        subject = utils.getRequestArg(request, "subject") or None
        if subject: subject.decode('utf-8').encode('utf-8', "replace")

        recipients = utils.getRequestArg(request, "recipients")
        if recipients:
            recipients = re.sub(',\s+', ',', recipients).split(",")
        return recipients, body, subject, parent

    def _fetchSnippet(self, body):
        #XXX:obviously we need a better regex than matching ":wrote"
        lines = body.split("\n")
        snippet = ""
        for line in lines:
            if not line.startswith(">") or not "wrote:" in line:
                snippet = line[:120]
                break
            else:
                continue
        return snippet

    @defer.inlineCallbacks
    def _deliverMessage(self, convId, recipients, timeUUID, owner):

        convFolderMap = {}
        userFolderMap = {}
        conv = yield Db.get_slice(convId, "mConversations", ['meta'])
        conv = utils.supercolumnsToDict(conv)

        oldTimeUUID = conv['meta']['uuid']
        unread = "u:%s"%(convId)
        read = "r:%s"%(convId)

        cols = yield Db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in recipients:
            deliverToInbox = True
            # for a new message, mConvFolders will be empty
            # so recipient may not necessarily be present in cols
            for folder in cols.get(recipient, []):
                cf = self._folders[folder] if folder in self._folders else folder
                yield Db.remove(recipient, cf, oldTimeUUID)
                if cf == 'mDeletedConversations':
                    #don't add to recipient's inbox if the conv is deleted.
                    deliverToInbox = False
                else:
                    yield Db.remove(convId, 'mConvFolders', folder, recipient)
            if deliverToInbox:
                convFolderMap[recipient] = {'mAllConversations':{timeUUID:unread}}
                userFolderMap[recipient]= {'mAllConversations':''}
                if recipient != owner:
                    convFolderMap[recipient]['mUnreadConversations'] = {timeUUID:read}
                    userFolderMap[recipient]['mUnreadConversations'] = ''
            else:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mDeletedConversations':{timeUUID:val}}


        yield Db.batch_mutate(convFolderMap)
        yield Db.batch_insert(convId, "mConvFolders", userFolderMap)

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
    def _newConversation(self, ownerId, participants, timeUUID,
                         subject, dateHeader, epoch):

        participants = dict ([(userId, '') for userId in participants])
        conv_meta = {"owner":ownerId,
                     "timestamp": str(int(time.time())),
                     "uuid": timeUUID,
                     "Date": dateHeader,
                     "date_epoch" : str(epoch),
                     "subject": subject}
        convId = utils.getUniqueKey()
        yield Db.batch_insert(convId, "mConversations", {"meta": conv_meta,
                                                "participants": participants})
        defer.returnValue(convId)

    @defer.inlineCallbacks
    def _reply(self, request):

        myId = request.getSession(IAuthInfo).username
        recipients, body, subject, convId = self._parseComposerArgs(request)
        dateHeader, epoch = self._createDateHeader()

        if not convId:
            raise errors.MissingParams()

        cols = yield Db.get_slice(convId, "mConversations", ['participants'])
        cols = utils.supercolumnsToDict(cols)
        if not cols:
            raise errors.InvalidRequest()

        participants = cols['participants'].keys()
        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'Date': dateHeader, 'date_epoch': str(epoch),
                "snippet":snippet}

        messageId = yield self._newMessage(myId, timeUUID, body, dateHeader, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield Db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield Db.batch_insert(convId, "mConversations", {'meta':meta})
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
        participants = list(recipients)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        print "snippet is %s" %snippet
        meta = {'uuid': timeUUID, 'Date': dateHeader, 'date_epoch': str(epoch),
                "snippet":snippet}
        convId = yield self._newConversation(myId, participants, timeUUID,
                                             subject, dateHeader, epoch)
        messageId = yield self._newMessage(myId, timeUUID, body, dateHeader, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield Db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield Db.batch_insert(convId, "mConversations", {'meta':meta})

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        parent = utils.getRequestArg(request, "parent") or None
        if parent:
            yield self._reply(request)
        else:
            yield self._createConveration(request)

    @defer.inlineCallbacks
    def _listConversations(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        filterType = utils.getRequestArg(request, 'type')
        folder = self._folders[filterType] if filterType in self._folders else\
                                                         self._folders['inbox']
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        unread = []
        convs = []
        users = set()
        count = 10
        fetchCount = count + 1
        nextPageStart = ''
        prevPageStart = ''

        cols = yield Db.get_slice(myKey, folder, reverse=True, start=start, count=fetchCount)
        for col in cols:
            x, convId = col.column.value.split(':')
            convs.append(convId)
            if x == 'u':
                unread.append(convId)
        if len(cols) == fetchCount:
            nextPageStart = utils.encodeKey(col.column.name)
            convs = convs[:count]

        ###XXX: try to avoid extra fetch
        cols = yield Db.get_slice(myKey, folder, count=fetchCount, start=start)
        if cols and len(cols)>1 and start:
            prevPageStart = utils.encodeKey(cols[-1].column.name)


        cols = yield Db.multiget_slice(convs, 'mConversations')
        conversations = utils.multiSuperColumnsToDict(cols)
        m={}
        for convId in conversations:
            if not conversations[convId]:
                continue
            participants = conversations[convId]['participants'].keys()
            users.update(participants)
            conversations[convId]['people'] = participants
            conversations[convId]['read'] = str(int(convId not in unread))
            messageCount = yield Db.get_count(convId, "mConvMessages")
            conversations[convId]['count'] = messageCount
            m[convId]=conversations[convId]

        users = yield Db.multiget_slice(users, 'entities', ['basic'])
        users = utils.multiSuperColumnsToDict(users)


        args.update({"view":"messages"})
        args.update({"messages":m})
        args.update({"people":users})
        args.update({"mids": convs})
        args.update({"menuId": "messages"})

        args.update({"filterType": filterType or "all"})
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            onload = """
                     $$.menu.selectItem('%s');
                     $('#mainbar .contents').removeClass("has-right");
                     """ %args["menuId"]
            yield renderScriptBlock(request, "message.mako", "center", landing,
                                    ".center-contents", "set", True,
                                    handlers={"onload": onload}, **args)
        else:
            yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _members(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        action = utils.getRequestArg(request, "action")
        convId = utils.getRequestArg(request, 'parent') or None

        if action == "add":
            yield self._addMembers(request)
        elif action == "remove":
            yield self._removeMembers(request)

        if convId:
            cols = yield Db.get_slice(convId, "mConversations")
            conv = utils.supercolumnsToDict(cols)
            participants = set(conv['participants'])
            people = yield Db.multiget_slice(participants, "entities", ['basic'])
            people = utils.multiSuperColumnsToDict(people)

            args.update({"people":people})
            args.update({"conv":conv})
            args.update({"id":convId})
            args.update({"view":"message"})
            if script:
                yield renderScriptBlock(request, "message.mako", "right",
                                        landing, ".right-contents", "set", **args)
        else:
            print "none"

    @defer.inlineCallbacks
    def _addMembers(self, request):
        myId = request.getSession(IAuthInfo).username
        newMembers, body, subject, convId = self._parseComposerArgs(request)
        if not (convId and newMembers):
            raise errors.MissingParams()
        conv = yield Db.get_slice(convId, "mConversations")
        if not conv:
            raise errors.MissingParams()

        conv = utils.supercolumnsToDict(conv)
        participants =  set(conv['participants'].keys())

        if myId not in participants:
            raise errors.AccessDenied()

        cols = yield Db.multiget_slice(newMembers, "entities", ['basic'])
        newMembers = set([userId for userId in cols if cols[userId]])
        newMembers = newMembers - participants

        if newMembers:
            newMembers = dict([(userId, '') for userId in newMembers])
            yield Db.batch_insert(convId, "mConversations", {'participants':newMembers})
            yield self._deliverMessage(convId, newMembers, conv['meta']['uuid'], conv['meta']['owner'])

    @defer.inlineCallbacks
    def _removeMembers(self, request):

        myId = request.getSession(IAuthInfo).username
        members, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and  members):
            raise errors.MissingParams()

        conv = yield Db.get_slice(convId, "mConversations")
        if not conv:
            raise errors.MissingParams()

        conv = utils.supercolumnsToDict(conv)
        participants = conv['participants'].keys()

        if myId not in participants:
            raise errors.UnAuthorized()

        cols = yield Db.multiget_slice(members, "entities", ['basic'])
        members = set([userId for userId in cols if cols[userId]])
        members = members.intersection(participants)

        if len(members) == len(participants):
            members.remove(conv['meta']['owner'])

        deferreds = []
        if members:
            d =  Db.batch_remove({"mConversations":[convId]},
                                    names=members,
                                    supercolumn='participants')
            deferreds.append(d)

            cols = yield Db.get_slice(convId, 'mConvFolders', members)
            cols = utils.supercolumnsToDict(cols)
            for recipient in cols:
                for folder in cols[recipient]:
                    cf = self._folders[folder] if folder in self._folders else folder
                    d = Db.remove(recipient, cf, conv['meta']['uuid'])
                    deferreds.append(d)
            if deferreds:
                yield deferreds

    @defer.inlineCallbacks
    def _actions(self, request):

        convIds = request.args.get('selected', [])

        trash = utils.getRequestArg(request, "trash")
        archive = utils.getRequestArg(request, "archive")
        unread = utils.getRequestArg(request, "unread")
        unArchive = utils.getRequestArg(request, "inbox")
        if not convIds:
            raise errors.MissingParams()
        if trash:
            yield self._moveConversation(request, convIds, 'trash')
        if archive:
            yield self._moveConversation(request, convIds, 'archive')
        if unread:
            yield self._moveConversation(request, convIds, 'unread')
        if unArchive:
            yield self._moveConversation(request, convIds, 'inbox')

    @defer.inlineCallbacks
    def _moveConversation(self, request, convIds, toFolder):


        myId = request.getSession(IAuthInfo).username

        for convId in convIds:
            conv = yield Db.get_slice(convId, "mConversations")
            if not conv:
                raise errors.InvalidRequest()
            conv = utils.supercolumnsToDict(conv)
            timeUUID = conv['meta']['uuid']

            val = "%s:%s"%( 'u' if toFolder == 'unread' else 'r', convId)

            cols = yield Db.get_slice(convId, 'mConvFolders', [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                cf = self._folders[folder] if folder in self._folders else folder
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
                folder = self._folders[toFolder]
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
            conv = utils.supercolumnsToDict(cols)
            participants = set(conv['participants'])

            if myId not in participants:
                raise errors.UnAuthorized()

            timeUUID = conv['meta']['uuid']
            yield Db.remove(myId, "mUnreadConversations", timeUUID)
            yield Db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
            cols = yield Db.get_slice(convId, "mConvFolders", [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                if folder in self._folders:
                    folder = self._folders[folder]
                yield Db.insert(myId, folder, "r:%s"%(convId), timeUUID)

            #FIX: make sure that there will be an entry of convId in mConvFolders
            cols = yield Db.get_slice(convId, "mConvMessages")
            mids = []
            for col in cols:
                mids.append(col.column.value)
            messages = yield Db.multiget_slice(mids, "messages", ["meta"])
            messages = utils.multiSuperColumnsToDict(messages)
            participants.update([messages[mid]['meta']['owner'] for mid in messages])

            people = yield Db.multiget_slice(participants, "entities", ['basic'])
            people = utils.multiSuperColumnsToDict(people)

            args.update({"people":people})
            args.update({"conv":conv})
            args.update({"messageIds": mids})
            args.update({'messages': messages})
            args.update({"id":convId})
            args.update({"flags":{}})
            args.update({"view":"message"})
            if script:
                onload = """
                         $('#mainbar .contents').addClass("has-right");
                         $('.conversation-reply').autogrow();
                         """
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", True,
                                        handlers={"onload":onload}, **args)
                yield renderScriptBlock(request, "message.mako", "right",
                                        landing, ".right-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        args.update({"view":"compose"})

        if script and landing:
            yield render(request, "message.mako", **args)

        if script:
            onload = """

                     $('#mainbar .contents').removeClass("has-right");
                     """
            yield renderScriptBlock(request, "message.mako", "viewComposer",
                                    landing, "#composer", "set", **args)
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
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._actions(request)
        elif segmentCount == 1 and request.postpath[0] == "members":
            d = self._members(request)

        return self._epilogue(request, d)
