import uuid
import pickle
import re
import pytz, time, datetime



from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import db, utils, base, errors
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

        recipients = utils.getRequestArg(request, "recipients", sanitize=False)
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
        notifications = {}
        rm_notifications = {'latestNotifications':[]}
        conv = yield db.get_slice(convId, "mConversations", ['meta'])
        conv = utils.supercolumnsToDict(conv)

        oldTimeUUID = conv['meta']['uuid']
        unread = "u:%s"%(convId)
        read = "r:%s"%(convId)

        cols = yield db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in recipients:
            deliverToInbox = True
            # for a new message, mConvFolders will be empty
            # so recipient may not necessarily be present in cols
            if recipient != owner:
                notifications[recipient]= {'latestNotifications': {'messages':{timeUUID: convId }}}
                rm_notifications['latestNotifications'].append(recipient)

            for folder in cols.get(recipient, []):
                cf = self._folders[folder] if folder in self._folders else folder
                yield db.remove(recipient, cf, oldTimeUUID)
                if cf == 'mDeletedConversations':
                    #don't add to recipient's inbox if the conv is deleted.
                    deliverToInbox = False
                else:
                    yield db.remove(convId, 'mConvFolders', folder, recipient)
            if deliverToInbox:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mAllConversations':{timeUUID:val}}
                userFolderMap[recipient]= {'mAllConversations':''}
                if recipient != owner:
                    convFolderMap[recipient]['mUnreadConversations'] = {timeUUID:unread}
                    userFolderMap[recipient]['mUnreadConversations'] = ''

            else:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mDeletedConversations':{timeUUID:val}}


        yield db.batch_mutate(convFolderMap)
        yield db.batch_insert(convId, "mConvFolders", userFolderMap)
        if rm_notifications and oldTimeUUID != timeUUID:
            yield db.batch_remove(rm_notifications, names=[oldTimeUUID], supercolumn="messages")
        if notifications:
            yield db.batch_mutate(notifications)

    @defer.inlineCallbacks
    def _newMessage(self, ownerId, timeUUID, body, epoch):
        messageId = utils.getUniqueKey()
        meta =  { "owner": ownerId,
                 "timestamp": str(int(time.time())),
                 'date_epoch': str(epoch),
                 "body": body,
                 "uuid": timeUUID
                }
        yield db.batch_insert(messageId, "messages", {'meta':meta})
        defer.returnValue(messageId)

    @defer.inlineCallbacks
    def _newConversation(self, ownerId, participants, timeUUID, subject, epoch):
        participants = dict ([(userId, '') for userId in participants])
        conv_meta = {"owner":ownerId,
                     "timestamp": str(int(time.time())),
                     "uuid": timeUUID,
                     "date_epoch" : str(epoch),
                     "subject": subject}
        convId = utils.getUniqueKey()
        yield db.batch_insert(convId, "mConversations", {"meta": conv_meta,
                                                "participants": participants})
        defer.returnValue(convId)

    @defer.inlineCallbacks
    def _reply(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        convId = utils.getRequestArg(request, 'id')
        landing = not self._ajax

        myId = request.getSession(IAuthInfo).username
        recipients, body, subject, convId = self._parseComposerArgs(request)
        epoch = int(time.time())

        if not convId:
            raise errors.MissingParams()

        cols = yield db.get_slice(convId, "mConversations", ['participants'])
        cols = utils.supercolumnsToDict(cols)
        if not cols:
            raise errors.InvalidRequest()

        participants = cols['participants'].keys()
        if myId not in participants:
            raise errors.AccessDenied()

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet":snippet}

        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield db.batch_insert(convId, "mConversations", {'meta':meta})

        #XXX:We currently only fetch the message we inserted. Later we may fetch
        # all messages delivered since we last rendered the conversation
        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv['participants'])
        mids = [messageId]
        messages = yield db.multiget_slice(mids, "messages", ["meta"])
        messages = utils.multiSuperColumnsToDict(messages)
        participants.update([messages[mid]['meta']['owner'] for mid in messages])

        people = yield db.multiget_slice(participants, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)

        args.update({"people":people})
        args.update({"messageIds": mids})
        args.update({'messages': messages})
        if script:
            onload = """
                        $('.conversation-reply').attr('value', '');
                    """
            yield renderScriptBlock(request, "message.mako",
                                            "render_conversation_messages",
                                            landing,
                                            ".conversation-messages-wrapper",
                                            "append", True,
                                            handlers={"onload":onload}, **args)
        else:
            request.redirect('/messages')
            request.finish()

    @defer.inlineCallbacks
    def _createConversation(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        recipients, body, subject, parent = self._parseComposerArgs(request)
        epoch = int(time.time())
        filterType = utils.getRequestArg(request, "filterType") or None

        if not parent and not recipients:
            raise errors.MissingParams()

        cols = yield db.multiget_slice(recipients, "entities", ['basic'])
        recipients = utils.multiSuperColumnsToDict(cols)
        recipients = set([userId for userId in recipients if recipients[userId]])

        if not recipients:
            raise errors.MissingParams()
        recipients.add(myId)
        participants = list(recipients)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet": snippet}
        convId = yield self._newConversation(myId, participants, timeUUID,
                                             subject, epoch)
        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)
        #XXX:Is this a duplicate batch insert ?
        yield db.batch_insert(convId, "mConversations", {'meta':meta})

        if script and filterType is not None and filterType == "all":
            col = yield db.get_slice(convId, 'mConversations')
            conversation = utils.supercolumnsToDict(col)
            args.update({"convId":convId})

            conv = {"people":participants, "read":1, "count":1,
                    "meta":conversation['meta']}
            args.update({"conv":conv})

            users = participants
            users = yield db.multiget_slice(users, 'entities', ['basic'])
            users = utils.multiSuperColumnsToDict(users)
            args.update({"people":users})

            args.update({"filterType":"all"})
            yield renderScriptBlock(request, "message.mako",
                                    "render_conversation_row", landing,
                                    ".conversation-layout-container",
                                    "prepend", **args)

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        parent = utils.getRequestArg(request, "parent") or None
        if parent:
            yield self._reply(request)
        else:
            yield self._createConversation(request)

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

        cols = yield db.get_slice(myKey, folder, reverse=True, start=start, count=fetchCount)
        for col in cols:
            x, convId = col.column.value.split(':')
            convs.append(convId)
            if x == 'u':
                unread.append(convId)
        if len(cols) == fetchCount:
            nextPageStart = utils.encodeKey(col.column.name)
            convs = convs[:count]

        ###XXX: try to avoid extra fetch
        cols = yield db.get_slice(myKey, folder, count=fetchCount, start=start)
        if cols and len(cols)>1 and start:
            prevPageStart = utils.encodeKey(cols[-1].column.name)


        cols = yield db.multiget_slice(convs, 'mConversations')
        conversations = utils.multiSuperColumnsToDict(cols)
        m={}
        for convId in conversations:
            if not conversations[convId]:
                continue
            participants = conversations[convId]['participants'].keys()
            users.update(participants)
            conversations[convId]['people'] = participants
            conversations[convId]['read'] = str(int(convId not in unread))
            messageCount = yield db.get_count(convId, "mConvMessages")
            conversations[convId]['count'] = messageCount
            m[convId]=conversations[convId]

        users = yield db.multiget_slice(users, 'entities', ['basic'])
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
            cols = yield db.get_slice(convId, "mConversations")
            conv = utils.supercolumnsToDict(cols)
            participants = set(conv['participants'])
            people = yield db.multiget_slice(participants, "entities", ['basic'])
            people = utils.multiSuperColumnsToDict(people)

            args.update({"people":people})
            args.update({"conv":conv})
            args.update({"id":convId})
            args.update({"view":"message"})
            if script:
                onload = """
                         $('#conversation_add_member').autocomplete({
                               source: '/auto/users',
                               minLength: 2,
                               select: function( event, ui ) {
                                   $('#conversation_recipients').attr('value', ui.item.uid)
                               }
                          });
                         """
                yield renderScriptBlock(request, "message.mako", "right",
                                        landing, ".right-contents", "set", True,
                                        handlers={"onload":onload}, **args)
        else:
            print "none"

    @defer.inlineCallbacks
    def _addMembers(self, request):
        myId = request.getSession(IAuthInfo).username
        newMembers, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and newMembers):
            raise errors.MissingParams()

        conv = yield db.get_slice(convId, "mConversations")
        if not conv:
            raise errors.MissingParams()
        conv = utils.supercolumnsToDict(conv)
        participants =  set(conv['participants'].keys())

        if myId not in participants:
            raise errors.AccessDenied()

        cols = yield db.multiget_slice(newMembers, "entities", ['basic'])
        newMembers = set([userId for userId in cols if cols[userId]])
        newMembers = newMembers - participants

        if newMembers:
            newMembers = dict([(userId, '') for userId in newMembers])
            yield db.batch_insert(convId, "mConversations", {'participants':newMembers})
            yield self._deliverMessage(convId, newMembers, conv['meta']['uuid'], conv['meta']['owner'])

    @defer.inlineCallbacks
    def _removeMembers(self, request):
        myId = request.getSession(IAuthInfo).username
        members, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and  members):
            raise errors.MissingParams()

        conv = yield db.get_slice(convId, "mConversations")
        if not conv:
            raise errors.MissingParams()

        conv = utils.supercolumnsToDict(conv)
        participants = conv['participants'].keys()

        if myId not in participants:
            raise errors.Unauthorized()

        cols = yield db.multiget_slice(members, "entities", ['basic'])
        members = set([userId for userId in cols if cols[userId]])
        members = members.intersection(participants)

        if len(members) == len(participants):
            members.remove(conv['meta']['owner'])

        deferreds = []
        if members:
            d =  db.batch_remove({"mConversations":[convId]},
                                    names=members,
                                    supercolumn='participants')
            deferreds.append(d)

            cols = yield db.get_slice(convId, 'mConvFolders', members)
            cols = utils.supercolumnsToDict(cols)
            for recipient in cols:
                for folder in cols[recipient]:
                    cf = self._folders[folder] if folder in self._folders else folder
                    d = db.remove(recipient, cf, conv['meta']['uuid'])
                    deferreds.append(d)
            if deferreds:
                yield deferreds

    @defer.inlineCallbacks
    def _actions(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        convIds = utils.getRequestArg(request, 'selected', multiValued=True) or []
        filterType = utils.getRequestArg(request, "filterType") or "all"
        trash = utils.getRequestArg(request, "trash") or None
        archive = utils.getRequestArg(request, "archive") or None
        unread = utils.getRequestArg(request, "unread") or None
        inbox = utils.getRequestArg(request, "inbox") or None

        if trash:action = "trash"
        elif archive:action = "archive"
        elif unread:action = "unread"
        elif inbox:action = "inbox"
        else:action = utils.getRequestArg(request, "action")

        if convIds:
            if action in self._folders.keys():
                yield self._moveConversation(request, convIds, action)
            elif action == "read":
                #Remove it from unreadIndex and mark it as unread in all other
                # folders
                convId = convIds[0]
                cols = yield db.get_slice(convId, "mConversations")
                conv = utils.supercolumnsToDict(cols)
                timeUUID = conv['meta']['uuid']
                participants = conv['participants'].keys()
                if myId not in participants:
                    raise errors.Unauthorized()

                yield db.remove(myId, "mUnreadConversations", timeUUID)
                yield db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
                cols = yield db.get_slice(convId, "mConvFolders", [myId])
                cols = utils.supercolumnsToDict(cols)
                for folder in cols[myId]:
                    if folder in self._folders:
                        folder = self._folders[folder]
                    yield db.insert(myId, folder, "r:%s"%(convId), timeUUID)

        if not self._ajax:
            #Not all actions on message(s) happen over ajax, for them do a redirect
            request.redirect("/messages?type=%s" %filterType)
            request.finish()
        elif self._ajax and len(convIds) > 0:
            #For all actions other than read/unread, since the action won't be
            # available to the user in same view; i.e, archive won't be on
            # archive view, we can simply remove the conv.
            # We are assuming action is always on a single thread
            if action == "inbox":
                request.write("$('#thread-%s').remove()" %convIds[0])
            elif action == "archive":
                request.write("$('#thread-%s').remove()" %convIds[0])
            elif action == "trash":
                request.write("$('#thread-%s').remove()" %convIds[0])
            elif action == "unread":
                request.write("""
                              $('#thread-%s').removeClass('row-read').addClass('row-unread');
                              $('#thread-%s .messaging-read-icon').removeClass('messaging-read-icon').addClass('messaging-unread-icon');
                              $('#thread-%s .messaging-unread-icon').attr("title", "Mark this conversation as read")
                              $('#thread-%s .messaging-unread-icon')[0].onclick = function(event) { $.post('/ajax/messages/thread', 'action=read&selected=%s&filterType=%s', null, 'script') }
                              """ % (convIds[0], convIds[0], convIds[0], convIds[0], convIds[0], filterType))
                #request.finish()
            elif action == "read":
                # If we are in unread view, remove the conv else swap the styles
                if filterType != "unread":
                    request.write("""
                                  $('#thread-%s').removeClass('row-unread').addClass('row-read');
                                  $('#thread-%s .messaging-unread-icon').removeClass('messaging-unread-icon').addClass('messaging-read-icon');
                                  $('#thread-%s .messaging-read-icon').attr("title", "Mark this conversation as unread")
                                  $('#thread-%s .messaging-read-icon')[0].onclick = function(event) { $.post('/ajax/messages/thread', 'action=unread&selected=%s&filterType=%s', null, 'script') }
                                  """ % (convIds[0], convIds[0], convIds[0], convIds[0], convIds[0], filterType))
                else:
                    request.write("$('#thread-%s').remove()" %convIds[0])

    @defer.inlineCallbacks
    def _moveConversation(self, request, convIds, toFolder):
        myId = request.getSession(IAuthInfo).username

        for convId in convIds:
            conv = yield db.get_slice(convId, "mConversations")
            if not conv:
                raise errors.InvalidRequest()
            conv = utils.supercolumnsToDict(conv)
            timeUUID = conv['meta']['uuid']
            participants = conv['participants'].keys()
            if myId not in participants:
                raise errors.Unauthorized()

            val = "%s:%s"%( 'u' if toFolder == 'unread' else 'r', convId)

            cols = yield db.get_slice(convId, 'mConvFolders', [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                cf = self._folders[folder] if folder in self._folders else folder
                if toFolder!='unread':
                    if folder!= 'mUnreadConversations':
                        col = yield db.get(myId, cf, timeUUID)
                        val = col.column.value
                        yield db.remove(myId, cf, timeUUID)
                        yield db.remove(convId, "mConvFolders", cf, myId)
                else:
                        yield db.insert(myId, cf, "u:%s"%(convId), timeUUID)


            if toFolder == 'unread':
                val = "u:%s"%(convId)
                yield db.insert(convId, 'mConvFolders', '', 'mUnreadConversations', myId)
                yield db.insert(myId, 'mUnreadConversations', val, timeUUID)
            else:
                folder = self._folders[toFolder]
                yield db.insert(myId, folder, val, timeUUID)
                yield db.insert(convId, 'mConvFolders', '', folder, myId)

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
            cols = yield db.get_slice(convId, "mConversations")
            conv = utils.supercolumnsToDict(cols)
            participants = set(conv['participants'])

            if myId not in participants:
                raise errors.Unauthorized()

            timeUUID = conv['meta']['uuid']
            yield db.remove(myId, "mUnreadConversations", timeUUID)
            yield db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
            yield db.remove(myId, "latestNotifications", timeUUID, "messages")
            cols = yield db.get_slice(convId, "mConvFolders", [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                if folder in self._folders:
                    folder = self._folders[folder]
                yield db.insert(myId, folder, "r:%s"%(convId), timeUUID)

            #FIX: make sure that there will be an entry of convId in mConvFolders
            cols = yield db.get_slice(convId, "mConvMessages")
            mids = []
            for col in cols:
                mids.append(col.column.value)
            messages = yield db.multiget_slice(mids, "messages", ["meta"])
            messages = utils.multiSuperColumnsToDict(messages)
            participants.update([messages[mid]['meta']['owner'] for mid in messages])

            people = yield db.multiget_slice(participants, "entities", ['basic'])
            people = utils.multiSuperColumnsToDict(people)

            args.update({"people":people})
            args.update({"conv":conv})
            args.update({"messageIds": mids})
            args.update({'messages': messages})
            args.update({"id":convId})
            args.update({"flags":{}})
            args.update({"view":"message"})
            args.update({"menuId": "messages"})

            if script:
                onload = """
                         $$.menu.selectItem("messages");
                         $('#mainbar .contents').addClass("has-right");
                         $('.conversation-reply').autogrow();
                         """
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", True,
                                        handlers={"onload":onload}, **args)

                onload = """
                         $('#conversation_add_member').autocomplete({
                               source: '/auto/users',
                               minLength: 2,
                               select: function( event, ui ) {
                                   $('#conversation_recipients').attr('value', ui.item.uid)
                               }
                          });
                        """
                yield renderScriptBlock(request, "message.mako", "right",
                                        landing, ".right-contents", "set", True,
                                        handlers={"onload":onload}, **args)
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
                    $('.conversation-composer-field-recipient').autocomplete({
                        source: '/auto/users',
                        minLength: 2,
                        select: function( event, ui ) {
                            $('.conversation-composer-recipients').append($$.messaging.formatUser(ui.item.value, ui.item.uid))
                            var rcpts = $('.conversation-composer-recipients').data('recipients')
                            if (jQuery.isArray(rcpts)){
                                rcpts.push(ui.item.uid)
                            }else{
                                rcpts = [ui.item.uid]
                            }
                            $('.conversation-composer-recipients').data('recipients', rcpts)
                            this.value = ""
                            return false;
                    }
                    });
                    $('.conversation-composer-field-body').autogrow();
                     """
            yield renderScriptBlock(request, "message.mako", "render_composer",
                                    landing, "#composer", "set", True,
                                    handlers={"onload":onload}, **args)
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
