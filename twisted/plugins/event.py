import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import db, utils, base, errors, _
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import dump_args, profile


class EventResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _inviteUsers(self, request, convId=None):
        invitees = utils.getRequestArg(request, 'invitees')
        invitees = invitees.split(',') if invitees else None
        myKey = request.getSession(IAuthInfo).username

        if not convId:
            convId = utils.getRequestArg(request, 'id')

        if not convId or not invitees:
            raise errors.MissingParams()

        conv = yield db.get_slice(convId, "items")
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

        invitees = yield db.multiget_slice(invitees, "userAuth")
        invitees = utils.multiColumnsToDict(invitees)

        responses = yield db.get_slice(convId, "eventResponses")
        responses = utils.supercolumnsToDict(responses)
        attendees = responses.get("yes", {}).keys() + \
                     responses.get("maybe", {}).keys() + \
                     responses.get("no", {}).keys()

        for mailId in invitees:
            userKey = invitees[mailId].get("user", None)
            if not userKey:
                raise errors.InvalidUserId()
            if userKey not in attendees:
                yield db.batch_insert(convId, "eventInvitations", {userKey:{timeUUID:''}})
                yield db.insert(userKey, "userEventInvitations", convId, timeUUID)
                yield db.insert(userKey, "notifications", convId, timeUUID)
                value = ":".join([responseType, myKey, convId, convType, convOwner])
                yield db.batch_insert(userKey, "notificationItems", {convId:{timeUUID:value}})


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _rsvp(self, request):
        convId = utils.getRequestArg(request, 'id')
        response = utils.getRequestArg(request, 'response')
        myKey = request.getSession(IAuthInfo).username
        optionCounts = {}

        if not response or response not in ('yes', 'maybe', 'no'):
            raise errors.InvalidRequest()

        item = yield db.get_slice(convId, "items")
        item = utils.supercolumnsToDict(item)

        if not item  :
            raise errors.MissingParams()

        if (item["meta"].has_key("type") and item["meta"]["type"] != "event"):
            raise errors.InvalidRequest()

        starttime = int(item["meta"]["startTime"])
        timeUUID = utils.uuid1(timestamp=starttime)
        timeUUID = timeUUID.bytes
        prevResponse, responseUUID = None, None

        cols = yield db.get_slice(myKey, "userEventResponse", [convId])
        if cols:
            prevResponse, responseUUID = cols[0].column.value.split(":")

        if prevResponse == response:
            return

        if prevResponse:
            yield db.remove(convId, "eventResponses", myKey, prevResponse)
            prevOptionCount = yield db.get_count(convId, "eventResponses", prevResponse)
            optionCounts[prevResponse] = str(prevOptionCount)
            yield db.remove(myKey, "userEvents", responseUUID)

        if not prevResponse:
            invitations = yield  db.get_slice(convId, "eventInvitations",
                                              super_column =myKey)
            for invitation in invitations:
                tuuid = invitation.column.name
                yield db.remove(myKey, "userEventInvitations", tuuid)
            yield db.remove(convId, "eventInvitations", super_column=myKey)

        yield db.insert(myKey, "userEventResponse", response+":"+timeUUID, convId)
        yield db.insert(convId, "eventResponses",  '', myKey, response)

        if response in ("yes", "maybe"):
            yield db.insert(myKey, "userEvents", convId, timeUUID)

        responseCount = yield db.get_count(convId, "eventResponses", response)
        optionCounts[response] = str(responseCount)

        yield db.batch_insert(convId, "items", {"options":optionCounts})


    @profile
    @defer.inlineCallbacks
    @dump_args
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

        myEvents = yield db.get_slice(myKey, "userEvents", reverse=True)
        myInvitations = yield db.get_slice(myKey, "userEventInvitations", reverse=True)

        for item in myEvents:
            convs.append(item.column.value)

        for item in myInvitations:
            if item.column.value not in invitations:
                invitations.append(item.column.value)

        events = yield db.multiget_slice(convs + invitations, "items", ["meta", "options"])
        events = utils.multiSuperColumnsToDict(events)
        myResponses = {}

        if convs:
            responses = yield db.get_slice(myKey, "userEventResponse", convs )
            for item in responses:
                convId = item.column.name
                value = item.column.value.split(":")[0]
                myResponses[convId] = value

        for convId in convs:
            if convId not in myResponses:
                myResponses[convId] = ''

        toFetchEntities.update([events[id]["meta"]["owner"] for id in events])
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
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


    @profile
    @dump_args
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


    @profile
    @dump_args
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
    disabled = True
    hasIndex = False

    @profile
    @defer.inlineCallbacks
    @dump_args
    def getReason(self, convId, requesters, users):
        conv = yield db.get_slice(convId, "items", ["meta"])
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


    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        templateFile = "event.mako"
        renderDef = "share_event"

        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "event"},
                                handlers={"onload": "(function(obj){$$.publisher.load(obj)})(this);"})


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("event.mako", "event_root", **args)
        else:
            return getBlock("event.mako", "event_root", args=[convId, isQuoted], **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        myKey = args["myKey"]

        conv = yield db.get_slice(convId, "items", ["options"])
        if not conv:
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv)
        conv.update(args.get("items", {}).get(convId, {}))

        myResponse = yield db.get_slice(myKey, "userEventResponse", [convId])
        myResponse = myResponse[0].column.value.split(":")[0] if myResponse else ''

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myResponse", {})[convId] = myResponse

        defer.returnValue(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
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
        item = utils.createNewItem(request, self.itemType)

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

        yield db.batch_insert(convId, "items", item)
        if invitees:
            event = self.getResource(False)
            yield event._inviteUsers(request, convId)

        defer.returnValue((convId, item))

    @defer.inlineCallbacks
    def delete(self, itemId):
        log.msg("plugin:delete", itemId)
        yield db.get_slice(itemId, "entities")




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
