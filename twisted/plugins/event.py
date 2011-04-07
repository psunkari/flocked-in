import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base, errors, _
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
from social.isocial     import IItemType


class EventResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _inviteUsers(self, request, convId=None):
        invitees = utils.getRequestArg(request, 'invitees')
        invitees = invitees.split(',') if invitees else None
        myKey = request.getSession(IAuthInfo).username

        if not convId:
            convId = utils.getRequestArg(request, 'id')

        if not convId or not invitees:
            raise errors.MissingParams()

        conv = yield Db.get_slice(convId, "items")
        conv = utils.supercolumnsToDict(conv)

        if not conv:
            raise errors.MissingParams()

        if (conv["meta"].has_key("type") and conv["meta"]["type"] != "event"):
            raise errors.InvalidRequest()

        convType = conv["meta"]["type"]
        convOwner = conv["meta"]["owner"]
        starttime = int(conv["meta"]["startTime"])
        timeUUID = utils.uuid1(timestamp=starttime)
        timeUUID = timeUUID.bytes
        responseType = "I"

        invitees = yield Db.multiget_slice(invitees, "userAuth")
        invitees = utils.multiColumnsToDict(invitees)

        responses = yield Db.get_slice(convId, "eventResponses")
        responses = utils.supercolumnsToDict(responses)
        attendees = responses.get("yes", {}).keys() + \
                     responses.get("maybe", {}).keys() + \
                     responses.get("no", {}).keys()

        for mailId in invitees:
            userKey = invitees[mailId].get("user", None)
            if not userKey:
                raise errors.InvalidUserId()
            if userKey not in attendees:
                yield Db.batch_insert(convId, "eventInvitations", {userKey:{timeUUID:''}})
                yield Db.insert(userKey, "userEventInvitations", convId, timeUUID)
                yield Db.insert(userKey, "notifications", convId, timeUUID)
                value = ":".join([responseType, myKey, convId, convType, convOwner])
                yield Db.batch_insert(userKey, "notificationItems", {convId:{timeUUID:value}})


    @defer.inlineCallbacks
    def _rsvp(self, request):
        convId = utils.getRequestArg(request, 'id')
        response = utils.getRequestArg(request, 'response')
        myKey = request.getSession(IAuthInfo).username
        optionCounts = {}

        if not response or response not in ('yes', 'maybe', 'no'):
            raise errors.InvalidRequest()

        item = yield Db.get_slice(convId, "items")
        item = utils.supercolumnsToDict(item)

        if not item  :
            raise errors.MissingParams()

        if (item["meta"].has_key("type") and item["meta"]["type"] != "event"):
            raise errors.InvalidRequest()

        starttime = int(item["meta"]["startTime"])
        timeUUID = utils.uuid1(timestamp=starttime)
        timeUUID = timeUUID.bytes
        prevResponse, responseUUID = None, None

        cols = yield Db.get_slice(myKey, "userEventResponse", [convId])
        if cols:
            prevResponse, responseUUID = cols[0].column.value.split(":")

        if prevResponse == response:
            return

        if prevResponse:
            yield Db.remove(convId, "eventResponses", myKey, prevResponse)
            prevOptionCount = yield Db.get_count(convId, "eventResponses", prevResponse)
            optionCounts[prevResponse] = str(prevOptionCount)
            yield Db.remove(myKey, "userEvents", responseUUID)

        if not prevResponse:
            invitations = yield  Db.get_slice(convId, "eventInvitations",
                                              super_column =myKey)
            for invitation in invitations:
                tuuid = invitation.column.name
                yield Db.remove(myKey, "userEventInvitations", tuuid)
            yield Db.remove(convId, "eventInvitations", super_column=myKey)

        yield Db.insert(myKey, "userEventResponse", response+":"+timeUUID, convId)
        yield Db.insert(convId, "eventResponses",  '', myKey, response)

        if response in ("yes", "maybe"):
            yield Db.insert(myKey, "userEvents", convId, timeUUID)

        responseCount = yield Db.get_count(convId, "eventResponses", response)
        optionCounts[response] = str(responseCount)

        yield Db.batch_insert(convId, "items", {"options":optionCounts})


    @defer.inlineCallbacks
    def _events(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        convs = []
        invitations = []
        toFetchEntities = set()

        if script and landing:
            yield render(request, "event.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "event.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        myEvents = yield Db.get_slice(myKey, "userEvents", reverse=True)
        myInvitations = yield Db.get_slice(myKey, "userEventInvitations", reverse=True)

        for item in myEvents:
            convs.append(item.column.value)

        for item in myInvitations:
            if item.column.value not in invitations:
                invitations.append(item.column.value)

        events = yield Db.multiget_slice(convs + invitations, "items", ["meta", "options"])
        events = utils.multiSuperColumnsToDict(events)
        myResponses = {}

        if convs:
            responses = yield Db.get_slice(myKey, "userEventResponse", convs )
            for item in responses:
                convId = item.column.name
                value = item.column.value.split(":")[0]
                myResponses[convId] = value

        for convId in convs:
            if convId not in myResponses:
                myResponses[convId] = ''

        toFetchEntities.update([events[id]["meta"]["owner"] for id in events])
        entities = yield Db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)

        args["items"] = events
        args["myResponse"] = myResponses
        args["conversations"] = convs
        args["entities"] = entities
        args["inviItems"] = invitations

        if script:
            yield renderScriptBlock(request, "event.mako", "events", landing,
                                    "#events", "set", **args)
        if script:
            yield renderScriptBlock(request, "event.mako", "invitations", landing,
                                    "#invitations", "set", **args)


    def render_POST(self, request):
        def success(response):
            request.finish()
        def failure(err):
            log.msg(err)
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'rsvp':
            d = self._rsvp(request)
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET
        if segmentCount == 1 and request.postpath[0] == "invite":
            d = self._inviteUsers(request)
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET


    def render_GET(self, request):
        def success(response):
            request.finish()
        def failure(err):
            log.msg(err)
            request.finish()
        d = self._events(request)
        d.addCallbacks(success, failure)
        return server.NOT_DONE_YET



#TODO: event Invitations.
#TODO: listing invitations chronologically.
class Event(object):
    implements(IPlugin, IItemType)
    itemType = "event"
    position = 4
    hasIndex = False

    @defer.inlineCallbacks
    def getReason(self, convId, requesters, users):
        conv = yield Db.get_slice(convId, "items", ["meta"])
        conv = utils.supercolumnsToDict(conv)

        title = conv["meta"].get("title", None)
        titleSnippet = utils.toSnippet(title)
        if not title:
            desc = conv["meta"]["desc"]
            titleSnippet = utils.toSnippet(desc)
        noOfRequesters = len(set(requesters))
        reasons = { 1: "%s invited you to the event: %s ",
                    2: "%s and %s invited you to the event: %s ",
                    3: "%s, %s and 1 other invited you to the event: %s ",
                    4: "%s, %s and %s others invited you to the event: %s "}
        vals = []
        for userId in requesters:
            userName = utils.userName(userId, users[userId])
            if userName not in vals:
                vals.append(userName)
                if len(vals) == noOfRequesters or len(vals) == 2:
                    break
        if noOfRequesters > 3:
            vals.append(noOfRequesters-3)
        vals.append(utils.itemLink(convId, titleSnippet))
        defer.returnValue(_(reasons[noOfRequesters])%(tuple(vals)))


    def shareBlockProvider(self):
        return ("event.mako", "share_event")


    def rootHTML(self, convId, args):
        if "convId" in args:
            return getBlock("event.mako", "event_root", **args)
        else:
            return getBlock("event.mako", "event_root", args=[convId], **args)


    @defer.inlineCallbacks
    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        myKey = args["myKey"]

        conv = yield Db.get_slice(convId, "items", ["options"])
        if not conv:
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv)
        conv.update(args.get("items", {}).get(convId, {}))

        myResponse = yield Db.get_slice(myKey, "userEventResponse", [convId])
        myResponse = myResponse[0].column.value.split(":")[0] if myResponse else ''

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myResponse", {})[convId] = myResponse

        defer.returnValue(set())


    @defer.inlineCallbacks
    def renderRoot(self, request, convId, args):
        script = args['script']
        landing = not args['ajax']
        toFeed = args['toFeed'] if args.has_key('toFeed') else False
        if script:
            if not toFeed:
                yield renderScriptBlock(request, "item.mako", "conv_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)
            else:
                if 'convId' in args:
                    del args['convId']
                yield renderScriptBlock(request, "item.mako", "item_layout",
                                        landing, "#user-feed", "prepend",
                                        args=[convId, True], **args)
                args['convId'] = convId
        # TODO: handle no_script case


    @defer.inlineCallbacks
    def create(self, request):
        startTime = utils.getRequestArg(request, 'startTime')
        endTime = utils.getRequestArg(request, 'endTime')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        invitees = utils.getRequestArg(request, "invitees")
        invitees = invitees.split(',') if invitees else None

        if not ((title or desc) and startTime):
            raise errors.InvalidRequest()

        convId = utils.getUniqueKey()
        item = yield utils.createNewItem(request, self.itemType)

        options = dict([('yes', '0'), ('maybe', '0'), ('no', '0')])
        meta = {"startTime": startTime}
        if title:
            meta["title"] = title
        if desc:
            meta["desc"] = desc
        if endTime:
            meta["endTime"] = endTime
        if location:
            meta["location"] = location

        item["meta"].update(meta)
        item["options"] = options

        yield Db.batch_insert(convId, "items", item)
        if invitees:
            event = self.getResource(False)
            yield event._inviteUsers(request, convId)

        defer.returnValue((convId, item))


    _ajaxResource = None
    _resource = None
    def getResource(self, isAjax):
        if isAjax:
            if not self._ajaxResource:
                self._ajaxResource = EventResource(True)
            return self._ajaxResource
        else:
            if not self._resource:
                self._resource = EventResource()
            return self._resource


event = Event()
