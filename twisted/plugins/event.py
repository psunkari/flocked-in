import time
import uuid
import datetime
import pytz
import calendar
import json
try:
    import cPickle as pickle
except:
    import pickle

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, errors, _
from social             import template as t
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import dump_args, profile, log


class EventResource(base.BaseResource):
    isLeaf = True
    _templates = ['event.mako', 'item.mako']

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _inviteUsers(self, request, convId=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args['orgId']

        if not convId:
            convId = utils.getRequestArg(request, 'id')
        acl = utils.getRequestArg(request, 'acl', False)
        invitees = yield utils.expandAcl(myId, orgId, pickle.dumps(json.loads(acl)), convId)
        #invitees = utils.getRequestArg(request, 'invitees')
        #invitees = invitees.split(',') if invitees else None
        #myId = request.getSession(IAuthInfo).username
        #
        #
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

        responses = yield db.get_slice(convId, "eventResponses")
        responses = utils.supercolumnsToDict(responses)
        attendees = responses.get("yes", {}).keys() + \
                     responses.get("maybe", {}).keys() + \
                     responses.get("no", {}).keys()

        #Check if invitees are valid keys
        for userKey in invitees:
            if userKey not in attendees:
                yield db.batch_insert(convId, "eventInvitations", {userKey:{timeUUID:''}})
                yield db.insert(userKey, "userEventInvitations", convId, timeUUID)
                yield db.insert(userKey, "notifications", convId, timeUUID)
                value = ":".join([responseType, myId, convId, convType, convOwner])
                yield db.batch_insert(userKey, "notificationItems", {convId:{timeUUID:value}})

    @defer.inlineCallbacks
    def _invitees(self, request):
        itemId, item = yield utils.getValidItemId(request, "id")

        if itemId:
            response = yield db.get_slice(itemId, "eventInvitations")
            response = utils.supercolumnsToDict(response)
            invitees = response.keys()

            entities = {}
            owner = item["meta"].get("owner")
            cols = yield db.multiget_slice(invitees+[owner], "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(cols)

            args = {"users": invitees, "entities": entities}
            args['title'] = _("People invited to this event ")

            t.renderScriptBlock(request, "item.mako", "userListDialog", False,
                                "#invitee-dlg-%s"%(itemId), "set", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _rsvp(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        convId = utils.getRequestArg(request, 'id')
        response = utils.getRequestArg(request, 'response')
        myId = request.getSession(IAuthInfo).username
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

        cols = yield db.get_slice(myId, "userEventResponse", [convId])
        if cols:
            prevResponse, responseUUID = cols[0].column.value.split(":")

        if prevResponse == response:
            return

        if prevResponse:
            yield db.remove(convId, "eventResponses", myId, prevResponse)
            prevOptionCount = yield db.get_count(convId, "eventResponses", prevResponse)
            optionCounts[prevResponse] = str(prevOptionCount)
            yield db.remove(myId, "userEvents", responseUUID)

        if not prevResponse:
            invitations = yield  db.get_slice(convId, "eventInvitations",
                                              super_column =myId)
            for invitation in invitations:
                tuuid = invitation.column.name
                yield db.remove(myId, "userEventInvitations", tuuid)
            yield db.remove(convId, "eventInvitations", super_column=myId)

        yield db.insert(myId, "userEventResponse", response+":"+timeUUID, convId)
        yield db.insert(convId, "eventResponses",  '', myId, response)

        if response in ("yes", "maybe"):
            yield db.insert(myId, "userEvents", convId, timeUUID)

        responseCount = yield db.get_count(convId, "eventResponses", response)
        optionCounts[response] = str(responseCount)

        yield db.batch_insert(convId, "items", {"rsvp":optionCounts})

        if script:
            #Update the inline status of your rsvp
            if response == "yes":
              rsp = _("You are attending")
            elif response == "no":
              rsp = _("You are not attending")
            elif response == "maybe":
              rsp = _("You may attend")

            request.write("$('#event-rsvp-status-%s').text('%s')" %(convId, rsp))
            #TODO:Update the sidebar listing of people attending this event


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _events(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convs = []
        invitations = []
        toFetchEntities = set()

        if script and landing:
            t.render(request, "event.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "event.mako", "layout",
                                landing, "#mainbar", "set", **args)

        myEvents = yield db.get_slice(myId, "userEvents", reverse=True)
        myInvitations = yield db.get_slice(myId, "userEventInvitations", reverse=True)

        for item in myEvents:
            convs.append(item.column.value)

        for item in myInvitations:
            if item.column.value not in invitations:
                invitations.append(item.column.value)

        events = yield db.multiget_slice(convs + invitations, "items", ["meta", "rsvp"])
        events = utils.multiSuperColumnsToDict(events)
        myResponses = {}

        if convs:
            responses = yield db.get_slice(myId, "userEventResponse", convs )
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
            t.renderScriptBlock(request, "event.mako", "events", landing,
                                "#events", "set", **args)
        if script:
            t.renderScriptBlock(request, "event.mako", "invitations", landing,
                                "#invitations", "set", **args)


    @profile
    @dump_args
    def render_POST(self, request):

        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == 'rsvp':
            d = self._rsvp(request)
        if segmentCount == 1 and request.postpath[0] == "invitee":
            d = self._inviteUsers(request)

        return self._epilogue(request, d)

    @profile
    @dump_args
    def render_GET(self, request):

        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._events(request)
        if segmentCount == 1 and request.postpath[0] == "invitee":
            d = self._invitees(request)

        return self._epilogue(request, d)

#TODO: event Invitations.
#TODO: listing invitations chronologically.
class Event(object):
    implements(IPlugin, IItemType)
    itemType = "event"
    position = 4
    disabled = True
    hasIndex = True
    indexFields = {'meta':set(['event_desc','event_location','event_title'])}
    monitorFields = {}

    @profile
    @defer.inlineCallbacks
    @dump_args
    def getReason(self, convId, requesters, users):
        conv = yield db.get_slice(convId, "items", ["meta"])
        conv = utils.supercolumnsToDict(conv)

        title = conv["meta"].get("title", None)
        titleSnippet = utils.toSnippet(title, 80)
        if not title:
            desc = conv["meta"]["desc"]
            titleSnippet = utils.toSnippet(desc, 80)
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


    def renderShareBlock(self, request, isAjax):
        onload = """
                (function(obj){$$.publisher.load(obj)})(this);
                $$.events.prepareDateTimePickers();
                """
        t.renderScriptBlock(request, "event.mako", "share_event",
                            not isAjax, "#sharebar", "set", True,
                            attrs={"publisherName": "event"},
                            handlers={"onload": onload})


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("event.mako", "event_root", **args)
        else:
            return t.getBlock("event.mako", "event_root", args=[convId, isQuoted], **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        myId = args["myId"]

        conv = yield db.get_slice(convId, "items", ["rsvp"])
        if not conv:
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv)
        conv.update(args.get("items", {}).get(convId, {}))

        myResponse = yield db.get_slice(myId, "userEventResponse", [convId])
        myResponse = myResponse[0].column.value.split(":")[0] if myResponse else ''

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myResponse", {})[convId] = myResponse

        response = yield db.get_slice(convId, "eventInvitations")
        response = utils.supercolumnsToDict(response)
        invitees = response.keys()
        args.setdefault("invitees", {})[convId] = invitees
        defer.returnValue(set(invitees))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request, me, convId, richText=False):
        startDate = utils.getRequestArg(request, 'startDate')
        startTime = utils.getRequestArg(request, 'startTime')
        endDate = utils.getRequestArg(request, 'endDate') or startDate
        endTime = utils.getRequestArg(request, 'endTime') #or all day event
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        allDay = utils.getRequestArg(request, "allDay")

        if not ((title or desc) and startTime and startDate):
            raise errors.InvalidRequest()

        #TODO input sanitization
        utc = pytz.utc
        startDate = datetime.datetime.utcfromtimestamp(float(startDate)/1000).replace(tzinfo=utc)
        endDate = datetime.datetime.utcfromtimestamp(float(endDate)/1000).replace(tzinfo=utc)
        startTime = datetime.datetime.utcfromtimestamp(float(startTime)/1000).replace(tzinfo=utc)
        endTime = datetime.datetime.utcfromtimestamp(float(endTime)/1000).replace(tzinfo=utc)

        startDateTime = datetime.datetime(startDate.year, startDate.month,
                                          startDate.day, startTime.hour,
                                          startTime.minute, startTime.second).replace(tzinfo=utc)
        endDateTime = datetime.datetime(endDate.year, endDate.month,
                                          endDate.day, endTime.hour,
                                          endTime.minute, endTime.second).replace(tzinfo=utc)

        item = yield utils.createNewItem(request, self.itemType, me, richText=richText)

        rsvps = dict([('yes', '0'), ('maybe', '0'), ('no', '0')])
        meta = {"event_startTime": str(calendar.timegm(startDateTime.utctimetuple()))}
        if title:
            meta["event_title"] = title
        if desc:
            meta["event_desc"] = desc
        if endTime:
            meta["event_endTime"] = str(calendar.timegm(endDateTime.utctimetuple()))
        if location:
            meta["event_location"] = location
        if allDay:
            meta["event_allDay"] = '1'
        else:
            meta["event_allDay"] = '0'

        item["meta"].update(meta)
        item["rsvps"] = rsvps

        # XXX: We should find a way to make things like this work.
        #event = self.getResource(False)
        #yield event._inviteUsers(request, convId)
        defer.returnValue(item)


    @defer.inlineCallbacks
    def delete(self, itemId):
        log.debug("plugin:delete", itemId)
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
