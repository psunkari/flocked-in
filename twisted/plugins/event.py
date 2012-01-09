import time
import uuid
import datetime
import pytz
import calendar
import json
import re
from pytz import timezone
from twisted.internet   import defer
from telephus.cassandra import ttypes
#from dateutil.relativedelta import relativedelta, weekday, MO, TU, WE, TH, \
#                                        FR, SA, SU
#
#from dateutil.rrule import rrule, rruleset, rrulestr, \
#                                YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, \
#                                MINUTELY, SECONDLY, MO, TU, WE, TH, FR, SA, SU
try:
    import cPickle as pickle
except:
    import pickle

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, errors, _
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import dump_args, profile, log


class EventResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    #TODO
    def _invite(self, request, convId=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args['orgId']
        pass

    @defer.inlineCallbacks
    #TODO
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

            yield renderScriptBlock(request, "item.mako", "userListDialog", False,
                                    "#invitee-dlg-%s"%(itemId), "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _rsvp(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        response = utils.getRequestArg(request, 'response')
        deferreds = []
        prevResponse = ""

        if not response or response not in ('yes', 'maybe', 'no'):
            raise errors.InvalidRequest()

        convId, conv = yield utils.getValidItemId(request, "id", columns=["invitees"])

        if not conv:
            raise errors.MissingParams([_("Event ID")])

        if (conv["meta"].has_key("type") and conv["meta"]["type"] != "event"):
            raise errors.InvalidRequest("Not a valid event")

        #Find out if already stored response is the same as this one. Saves
        # quite a few queries
        rsvp_names = ["%s:%s" %(x, myId) for x in ['yes', 'no', 'maybe']]
        cols = yield db.get_slice(convId, "eventResponses", names=rsvp_names)
        if cols:
            prevResponse = cols[0].column.name.split(":", 1)[0]

        if prevResponse == response:
            defer.returnValue(0)

        print ("Setting New RSVP")
        starttime = int(conv["meta"]["event_startTime"])
        endtime = int(conv["meta"]["event_endTime"])
        starttimeUUID = utils.uuid1(timestamp=starttime)
        starttimeUUID = starttimeUUID.bytes
        endtimeUUID = utils.uuid1(timestamp=endtime)
        endtimeUUID = endtimeUUID.bytes

        #If I was invited, then update the invited status in convs scf
        if myId in conv["invitees"].keys():
            conv["invitees"] = {myId:response}
            d = db.batch_insert(convId, "items", conv)
            deferreds.append(d)

        #Now insert the event in the user's agenda list if the user has
        # never responded to this event or the user is not in the invited list.
        #In the second case the agenda was already updated when creating the
        # event

        # To get a match of all events occuring in a timeframe, including
        # overlapping and multiday events, both start time and endtime are
        # required.
        # Also update the reverse map, so it is easy to delete an event's
        # reference later
        if prevResponse == "" and myId not in conv["invitees"].keys():
            d1 = db.insert(myId, "userAgenda", convId, starttimeUUID)
            d2 = db.insert(myId, "userAgenda", convId, endtimeUUID)
            d3 = db.insert("%s:%s" %(myId, convId), "userAgendaMap", "",
                          starttimeUUID)
            d4 = db.insert("%s:%s" %(myId, convId), "userAgendaMap", "",
                          endtimeUUID)
            deferreds.extend([d1, d3, d2, d4])

        #Now insert this user in the list of people who responded to this event
        # Map of user to a response
        d = db.insert(convId, "eventAttendees", response, myId)
        deferreds.append(d)

        #Remove the old response to this event by this user.
        yield db.batch_remove({'eventResponses': [convId]},
                                names=rsvp_names)

        #Now insert the user's new response.
        d = db.insert(convId, "eventResponses", "", "%s:%s" %(response, myId))
        deferreds.append(d)

        if script:
            #Update the inline status of the rsvp status
            if response == "yes":
              rsp = _("You are attending")
            elif response == "no":
              rsp = _("You are not attending")
            elif response == "maybe":
              rsp = _("You may attend")

            request.write("$('#event-rsvp-status-%s').text('%s')" %(convId, rsp))

        if deferreds:
            res = yield defer.DeferredList(deferreds)

        #TODO:Update the UI for changes
        #TODO:Remove the eventAttendees CF as per wiki
        #TODO:Once a user who has not been invited responds, add the item to his
        # feed

    @profile
    @defer.inlineCallbacks
    @dump_args
    #TODO
    def _events(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convs = []
        invitations = []
        toFetchEntities = set()

        if script and landing:
            yield render(request, "event.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "event.mako", "layout",
                                    landing, "#mainbar", "set", **args)


        # Get the next 5 matching events for today
        # since we store times in UTC, find out the utc time for the user's
        # 00:00 hours instead of utc 00:00.
        my_tz = timezone(args["me"]["basic"]["timezone"])
        utc_now = datetime.datetime.now(pytz.utc)
        mytz_now = utc_now.astimezone(my_tz)
        mytz_start = datetime.datetime(mytz_now.year, mytz_now.month,
                                       mytz_now.day+2, 0, 0, 0).replace(tzinfo=my_tz)

        mytz_end = datetime.datetime(mytz_now.year, mytz_now.month,
                                       mytz_now.day+20, 23, 59, 59).replace(tzinfo=my_tz)

        print mytz_start.strftime('%a %b %d, %I:%M %p %Z')
        timestamp = calendar.timegm(mytz_start.utctimetuple())
        timeUUID = utils.uuid1(timestamp=timestamp)
        stimeUUID = timeUUID.bytes

        print mytz_end.strftime('%a %b %d, %I:%M %p %Z')
        timestamp = calendar.timegm(mytz_end.utctimetuple())
        timeUUID = utils.uuid1(timestamp=timestamp)
        etimeUUID = timeUUID.bytes

        events = yield db.get_slice(myId, "userAgenda", start=stimeUUID, finish=etimeUUID)
        matched_events = []
        matched_tids = []
        for event in events:
            matched_events.append(event.column.value)
            matched_tids.append(uuid.UUID(bytes=event.column.name))

        #print str(matched_tids)
        #print str(matched_tids)
        matched_tids.sort()
        #print str(matched_tids)
        #print str(matched_events)

        mevents = []
        for x in matched_events:
            if x not in mevents:
                mevents.append(x)


        #matched_events = set(matched_events)
        print str(mevents)
        res = yield db.multiget_slice(mevents, "items", ["meta"])
        events = utils.multiSuperColumnsToDict(res, ordered=True)

        myResponses = dict([(x, "yes") for x in matched_events])

        #
        toFetchEntities.update([events[id]["meta"]["owner"] for id in events])
        #
        args["items"] = events
        #args["myResponse"] = myResponses
        args["conversations"] = mevents
        #args["inviItems"] = invitations
        args["my_response"] = myResponses
        args["invited_status"] = {}
        invitees = yield db.multiget_slice(matched_events, "items", ["invitees"])
        invitees = utils.multiSuperColumnsToDict(invitees)
        for convId in matched_events:
            args["invited_status"][convId] = invitees[convId]["invitees"]
            toFetchEntities.update(invitees[convId]["invitees"])
        #
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        args["entities"] = entities

        if script:
            yield renderScriptBlock(request, "event.mako", "events", landing,
                                    "#events", "set", **args)
        #if script:
        #    yield renderScriptBlock(request, "event.mako", "invitations", landing,
        #                            "#invitations", "set", **args)


    @profile
    @dump_args
    def render_POST(self, request):

        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == 'rsvp':
            d = self._rsvp(request)
        if segmentCount == 1 and request.postpath[0] == "invite":
            d = self._invite(request)

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
    disabled = False
    hasIndex = True
    indexFields = {'meta':set(['event_desc','event_location','event_title'])}

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


    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        orgKey = authinfo.organization

        cols = yield db.multiget_slice([myId, orgKey], "entities", ["basic"])
        cols = utils.multiSuperColumnsToDict(cols)

        me = cols.get(myId, None)
        org = cols.get(orgKey, None)
        args = {"myId": myId, "orgKey": orgKey, "me": me, "org": org}

        templateFile = "event.mako"
        renderDef = "share_event"

        onload = """
                (function(obj){$$.publisher.load(obj)})(this);
                $$.events.prepareDateTimePickers();
                $$.events.autoFillUsers();
                """
        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "event"},
                                handlers={"onload": onload}, **args)


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
        myId = args["myKey"]
        response = ""

        invitees = yield db.multiget_slice([convId], "items", ["invitees"])
        invitees = utils.multiSuperColumnsToDict(invitees)
        args.setdefault("invited_status", {})[convId] = invitees[convId]["invitees"]

        try:
            d = yield db.get(convId, "eventAttendees", myId)
        except ttypes.NotFoundException:
            pass
        else:
            response = d.column.value

        args.setdefault("my_response", {})[convId] = response

        defer.returnValue(invitees[convId]["invitees"].keys())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request, myId, myOrgId, richText=False):
        startDate = utils.getRequestArg(request, 'startDate')
        endDate = utils.getRequestArg(request, 'endDate')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        allDay = utils.getRequestArg(request, "allDay")
        acl = utils.getRequestArg(request, "acl", sanitize=False)
        invitees = utils.getRequestArg(request, "invitees", sanitize=False)
        if invitees:
            invitees = re.sub(',\s+', ',', invitees).split(",")
        else:
            invitees = []
        # The owner is always invited to the event
        invitees.append(myId)

        isPrivate = utils.getRequestArg(request, "isPrivate")

        if not ((title or desc) and startDate and endDate):
            raise errors.InvalidRequest()

        #TODO input sanitization
        utc = pytz.utc
        startDate = datetime.datetime.utcfromtimestamp(float(startDate)/1000).replace(tzinfo=utc)
        endDate = datetime.datetime.utcfromtimestamp(float(endDate)/1000).replace(tzinfo=utc)

        if not allDay:
            startDateTime = datetime.datetime(startDate.year, startDate.month,
                                              startDate.day, startDate.hour,
                                              startDate.minute, startDate.second).\
                                                replace(tzinfo=utc)
            endDateTime = datetime.datetime(endDate.year, endDate.month,
                                              endDate.day, endDate.hour,
                                              endDate.minute, endDate.second).\
                                                replace(tzinfo=utc)

        else:
            startDateTime = datetime.datetime(startDate.year, startDate.month,
                                              startDate.day, 0, 0, 0).\
                                                replace(tzinfo=utc)
            endDateTime = datetime.datetime(endDate.year, endDate.month,
                                              endDate.day, 23,
                                              59, 59).replace(tzinfo=utc)

        meta = {"event_startTime": str(
                                        calendar.timegm(
                                            startDateTime.utctimetuple())),
                "event_endTime": str(calendar.timegm(
                                        endDateTime.utctimetuple()))
                }
        if title:
            meta["event_title"] = title
        if desc:
            meta["event_desc"] = desc
        if location:
            meta["event_location"] = location
        if allDay:
            meta["event_allDay"] = '1'
        else:
            meta["event_allDay"] = '0'

        convId = utils.getUniqueKey()
        starttime = int(meta["event_startTime"])
        starttimeUUID = utils.uuid1(timestamp=starttime)
        starttimeUUID = starttimeUUID.bytes

        endtime = int(meta["event_endTime"])
        endtimeUUID = utils.uuid1(timestamp=endtime)
        endtimeUUID = endtimeUUID.bytes

        print "isgreater"
        print starttimeUUID > endtimeUUID
        print starttime > endtime

        invitedUsers = yield self._inviteUsers(request, starttimeUUID,
                                               endtimeUUID, convId, myId,
                                               invitees)

        acl = json.loads(acl)
        acl.setdefault("accept", {})
        acl["accept"].setdefault("users", [])
        acl["accept"]["users"].extend(invitedUsers)
        acl = json.dumps(acl)
        item, attachments = yield utils.createNewItem(request, self.itemType,
                                                      myId, myOrgId,
                                                      richText=richText,
                                                      acl=acl)

        item["meta"].update(meta)
        item["invitees"] = invitedUsers

        yield db.batch_insert(convId, "items", item)

        for attachmentId in attachments:
            timeuuid, fid, name, size, ftype  = attachments[attachmentId]
            val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
            yield db.insert(convId, "item_files", val, timeuuid, attachmentId)

        from social import search
        d = search.solr.updateItem(convId, item, myOrgId)
        defer.returnValue((convId, item))


    @defer.inlineCallbacks
    def delete(self, myId, convId):
        log.debug("plugin:delete", convId)
        user_tuids = {}

        #Get the list of every user who responded to this event
        res = yield db.get_slice(convId, "eventResponses")
        attendees = [x.column.name.split(":",1)[1] for x in res]

        # Add all the invited people of the item
        res = yield db.get_slice(convId, "items", ['invitees'])
        res = utils.supercolumnsToDict(res)
        attendees.extend(res["invitees"].keys())

        #Get the timeuuids that were inserted for this user
        res = yield db.multiget_slice(["%s:%s"%(uId, convId) for \
                                       uId in attendees], "userAgendaMap")
        res = utils.multiColumnsToDict(res)

        for k,v in res.iteritems():
            uid = k.split(":",1)[0]
            tuids = v.keys()
            user_tuids[uid] = tuids

        #Delete their entries in the user's list of event entries
        for attendee in user_tuids:
            yield db.batch_remove({'userAgenda': [attendee]},
                                    names=user_tuids[attendee])

        #Delete the event's entry in eventResponses
        yield db.remove(convId, "eventResponses")

        #Delete their entries in userAgendaMap
        for attendee in user_tuids:
            yield db.batch_remove({'userAgendaMap': ["%s:%s"%(attendee, convId)]},
                                    names=user_tuids[attendee])


    @defer.inlineCallbacks
    def _inviteUsers(self, request, starttimeUUID, endtimeUUID, convId, myId,
                     invitees):
        #Return a dict of users who were explicitly invited and their current
        # RSVP set to ""
        people = yield db.multiget_slice(invitees, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)
        deferreds = []
        #TODO:Send notifications to each one of these people
        for invitee in people.keys():
            #Add to the user's agenda
            d1 = db.insert(invitee, "userAgenda", convId, starttimeUUID)
            d2 = db.insert(invitee, "userAgenda", convId, endtimeUUID)
            d3 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                          starttimeUUID)
            d4 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                          endtimeUUID)
            deferreds.extend([d1, d3, d2, d4])

        if deferreds:
            res = yield defer.DeferredList(deferreds)
            print res

        defer.returnValue(dict([(x, "") for x in people.keys()]))


    @defer.inlineCallbacks
    def renderSideBlock(self, request, landing, args):
        d1 = renderScriptBlock(request, "event.mako", "event_me", landing,
                                "#item-me", "set", **args)
        d2 = renderScriptBlock(request, "event.mako", "event_meta", landing,
                                "#item-meta", "set", **args)
        d3 = renderScriptBlock(request, "event.mako", "event_actions", landing,
                                "#item-subactions", "set", **args)

        yield defer.DeferredList([d1, d2, d3])
        defer.returnValue([])


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
