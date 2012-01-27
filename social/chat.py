import json
import uuid
import time
from ordereddict        import OrderedDict
from telephus.cassandra import ttypes
from twisted.internet   import defer
from social.isocial     import IAuthInfo
from social.presence    import PresenceStates
from social             import base, utils, db, errors, constants
from social.comet       import pushToCometd
from social             import template as t
from social.logging     import log


class ChatResource(base.BaseResource):

    isLeaf=True
    _templates = ['chat.mako']

    @defer.inlineCallbacks
    def _postChat(self, request):
        comment = utils.getRequestArg(request, 'comment')
        channelId = utils.getRequestArg(request, 'channelId')
        authInfo = request.getSession(IAuthInfo)

        recipientId, recipient = yield utils.getValidEntityId(request, 'to')
        myId = authInfo.username
        timeuuid = uuid.uuid1().bytes
        chatId = utils.getUniqueKey()
        sessionId = request.getCookie('session')
        data = {'from': myId, 'to': recipientId, 'comment': comment,
                'channelId': channelId, 'time': time.time()}
        if not comment:
            return
        if channelId:
            channelSubscribers = yield db.get_slice(channelId, 'channelSubscribers')
            channelSubscribers = utils.columnsToDict(channelSubscribers)
            channelSubscribers = set([x.split(':', 1)[0] for x in channelSubscribers])
            if myId not in channelSubscribers:
                raise errors.ChatAccessDenied('')
            yield db.insert(channelId, 'channelSubscribers', '', '%s:%s'%(myId, sessionId))
            yield db.insert("%s:%s" %(myId, sessionId), "sessionChannelsMap", '', channelId)
            try:
                yield pushToCometd('/chat/%s'%(channelId), data)
                count = yield db.get_count(channelId, "channelSubscribers", start='%s:'%(recipientId))
                if not count:
                    yield pushToCometd('/notify/%s'%(recipientId), data)
            except:
                channelId = None
        if not channelId:
            channelId = utils.getUniqueKey()
            data['channelId'] = channelId
            try:
                yield pushToCometd('/notify/%s'%(myId), data)
                yield pushToCometd('/notify/%s'%(recipientId), data)
            except Exception as e:
                raise errors.RequestFailed()
            request.write('%s'%(channelId))
            yield db.insert(channelId, 'channelSubscribers', '', myId)
            yield db.insert(channelId, 'channelSubscribers', '', recipientId)
            channelSubscribers = set([myId, recipientId])

        start = utils.uuid1(timestamp = time.time() - 3600).bytes
        cols = yield db.get_slice(myId, 'chatArchiveList', start=start, )

        chatIds = [col.column.value for col in cols]
        participants = yield db.multiget_slice(chatIds, "chatParticipants")
        participants = utils.multiColumnsToDict(participants)
        oldTimeuuid = None
        chatId = None
        timeuuid = uuid.uuid1().bytes
        for col in cols:
            _participants = participants[col.column.value].keys()
            if not set(_participants).difference(channelSubscribers):
                chatId = col.column.value
                oldTimeuuid = col.column.name
        if not chatId:
            chatId = utils.getUniqueKey()
            for userId in channelSubscribers:
                yield db.insert(chatId, "chatParticipants", '', userId)
        for userId in channelSubscribers:
            yield db.insert(chatId, "chatLogs", '%s:%s'%(myId, comment), timeuuid)
            yield db.insert(userId, "chatArchiveList", chatId, timeuuid)
            if oldTimeuuid:
                yield db.remove(userId, "chatArchiveList", oldTimeuuid)

        #if channel:
        #   cols = yield db.get_slice(channelId, "chatChannels")
        #   if cols:
        #       chatId = cols[0].column.name
        #   else:
        #       channelId = None
        #
        #if not channel
        #   start = utils.uuid1(timestamp = time.time() - 3600)
        #   cols = yield db.get_slice(myId, 'chatArchiveList', start=start, reverse=True)
        #   chatIds = [col.columns.name for col in cols]
        #   participants = yield db.multiget_slice(chatIds, "chatParticipants")
        #   participants = utils.multiColumnsToDict(participants, True)
        #   for chatId in participants:
        #       _participants = participants[chatId]
        #       if len(_participants) == 2 and myId in _participants and recipientId in _participants:
        #           col = yield db.get(chatId, "chatParticipants", 'channelId')
        #           channelId = col.column.name
        #           break
        #   if not channelId:
        #       create channel
        #       chatId = utils.getUniqueKey()
        #       subscribe users to channel
        #       send channelId to me
        #       send comment, channelId, sender to recipient channel
        #       yield db.insert(chatId, "chatParticipants", '', myId)
        #       yield db.insert(chatId, "chatParticipants", '', recipientId)
        #   yield db.insert(channelId, "channelSubscribers",'', myId)
        #   yield db.insert(channelId, "channelSubscribers",'', recipientId)
        #   yield db.insert(channelId, "chatChannels", '', chatId)
        #
        #participants = yield db.get_slice(chatId, "chatParticipants")
        #participants = utils.columnsToDict(participants)
        #cols = yield db.get_slice(chatId, "chatLogs", reverse=True, count=1)
        #if cols:
        #    oldTimeuuid = cols[0].columns.colum_name
        #    for participant in participants:
        #        yield db.remove(participant, 'chatArchiveList', oldTimeuuid)
        #for participant in participants:
        #    yield db.insert(participant, "chatArchiveList", chatId, timeuuid)
        #yield db.insert(chatId, "chatLogs", "%s:%s" %(myId,comment), timeuuid)

    @defer.inlineCallbacks
    def _archives(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args['orgId']
        landing = not self._ajax
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        count = constants.CHATS_PER_PAGE

        if script and landing:
            t.render(request, "chat.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "chat.mako", "layout",
                                landing, "#mainbar", "set", **args)

        chats = {}
        chatParticipants = {}
        prevPageStart = ''
        nextPageStart = ''
        cols = yield db.get_slice(myId, "chatArchiveList", start=start, count=count+1, reverse=True)
        chatIds = [col.column.value for col in cols]
        if len(cols) == count+1:
            chatIds = chatIds[:count]
            nextPageStart = utils.encodeKey(cols[-1].column.name)
        cols = yield db.get_slice(myId, "chatArchiveList", start=start, count=count+1)
        if len(cols) > 1 and start:
            prevPageStart = utils.encodeKey(cols[-1].column.name)
        if chatIds:
            cols = yield db.multiget_slice(chatIds, "chatLogs", reverse=False)
            chats = OrderedDict()
            for chatId in cols:
                chats[chatId] = []
                for col in cols[chatId]:
                    entityId, comment = col.column.value.split(':', 1)
                    chats[chatId] = (entityId, comment, col.column.timestamp/1e6)
        #chats = utils.multiColumnsToDict(chats, True)
        participants = yield db.multiget_slice(chatIds, "chatParticipants")
        participants = utils.multiColumnsToDict(participants)
        entityIds = set([])
        for chatId in participants:
            entityIds.update(participants[chatId])
        entities = yield db.multiget_slice(entityIds, "entities", ['basic'])
        entities = utils.multiSuperColumnsToDict(entities)
        entities[myId] = args['me']
        args.update({'chatParticipants': participants,
                      'entities': entities,
                      'chats': chats,
                      'chatIds': chatIds,
                      'nextPageStart': nextPageStart,
                      'prevPageStart': prevPageStart})
        t.renderScriptBlock(request, "chat.mako", "render_chatList",
                          landing,'.center-contents', "set", **args )

    @defer.inlineCallbacks
    def _renderChatLog(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args['orgId']
        landing = not self._ajax


        if script and landing:
            t.render(request, "chat.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "chat.mako", "layout",
                                landing, "#mainbar", "set", **args)
        chatId = utils.getRequestArg(request, 'id')
        start= utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        count = 25
        if not chatId:
            return
        chatParticipants = yield db.get_slice(chatId, "chatParticipants")
        chatParticipants = utils.columnsToDict(chatParticipants).keys()
        if myId not in chatParticipants:
            raise errors.ChatAccessDenied(chatId)
        entityIds = set()
        chatLogs = []
        nextPageStart=''
        cols = yield db.get_slice(chatId, "chatLogs", start=start, count = count+1)
        for col in cols:
            timestamp = col.column.timestamp/1e6
            entityId, comment = col.column.value.split(':', 1)
            entityIds.add(entityId)
            chatLogs.append((entityId, comment, timestamp))
        if len(cols) == count+1:
            nextPageStart = utils.encodeKey(cols[-1].column.name)
            chatLogs = chatLogs[:count]
        entities = yield db.multiget_slice(chatParticipants, "entities", ['basic'])
        entities = utils.multiSuperColumnsToDict(entities)
        entities[myId] = args['me']
        title = "Chat with " + ",".join([entities[x]['basic']['name'] for x in chatParticipants if x != myId ])
        args.update({'chatLogs': chatLogs, "chatId": chatId, "entities": entities, "nextPageStart": nextPageStart})
        if not start:
            t.renderScriptBlock(request, 'chat.mako', "chat_title", landing,
                                "#title", "set", chatTitle=title)
            t.renderScriptBlock(request, "chat.mako", "render_chat",
                                landing, ".center-contents", "set", **args)
        else:
            t.renderScriptBlock(request, "chat.mako", "render_chatLog",
                                landing, "#next-page-loader", "replace", **args)
    @defer.inlineCallbacks
    def _post(self, request):

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args['orgId']
        landing = not self._ajax
        other = utils.getRequestArg(request, 'other')

        if script and landing:
            t.render(request, "chat.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "chat.mako", "layout",
                                landing, "#mainbar", "set", **args)
        args['to'] = 'tDM5JpfaEeCz1EBAhdLyVQ'
        if script and not other:
            t.renderScriptBlock(request, "chat.mako", "post",
                                landing, ".center-contents", "set", **args)
        else:
            t.renderScriptBlock(request, "chat.mako", "post_other",
                                landing, ".center-contents", "set", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._archives(request)
        elif segmentCount == 1 and request.postpath[0] == 'post':
            d = self._post(request)
        elif segmentCount == 1 and request.postpath[0] == 'log':
            d = self._renderChatLog(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._postChat(request)
        return self._epilogue(request, d)


