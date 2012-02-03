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
from dateutil.relativedelta import relativedelta, weekday, MO, TU, WE, TH, \
                                        FR, SA, SU
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
        myOrgId = args['orgId']
        convId, conv = yield utils.getValidItemId(request, "id", columns=["invitees"])

        # Parse invitees from the tag edit plugin values
        arg_keys = request.args.keys()
        invitees = []
        for arg in arg_keys:
            if arg.startswith("invitee[") and arg.endswith("-a]"):
                rcpt = arg.replace("invitee[", "").replace("-a]", "")
                if rcpt != "":
                    invitees.append(rcpt)

        #Check if they are valid uids
        res = yield db.multiget_slice(invitees, "entities", ['basic'])
        res = utils.multiSuperColumnsToDict(res)
        invitees = [x for x in res.keys() if res[x]["basic"]["org"] == myOrgId]
        new_invitees = [x for x in invitees if x not in conv["invitees"].keys()]
        print new_invitees

        #TODO: Make sure the invited user is within the ACL limits.

        if new_invitees:
            convMeta = conv["meta"]
            starttime = int(convMeta["event_startTime"])
            starttimeUUID = utils.uuid1(timestamp=starttime)
            starttimeUUID = starttimeUUID.bytes

            endtime = int(convMeta["event_endTime"])
            endtimeUUID = utils.uuid1(timestamp=endtime)
            endtimeUUID = endtimeUUID.bytes

            conv["invitees"] = dict([(x, myId) for x in new_invitees])
            d = yield db.batch_insert(convId, "items", conv)

            yield event.inviteUsers(request, starttimeUUID, endtimeUUID,
                                        convId, myId, myOrgId, new_invitees)
            request.write("""$$.alerts.info('%s');""" \
                            %("%d people invited to this event" %len(new_invitees)))
            #XXX: Push to the invited user's feed.
        else:
            request.write("""$$.alerts.info('%s');""" \
                            %("Invited persons are already on the invitation list"))

        request.write("$('#item-subactions .tagedit-listelement-old').remove();")


    @defer.inlineCallbacks
    def _attendance(self, request):
        itemId, item = yield utils.getValidItemId(request, "id", columns=["invitees"])
        list_type = utils.getRequestArg(request, 'type') or "yes"
        user_list = []

        if itemId and list_type in ["yes", "no", "maybe"]:
            cols = yield db.get_slice(itemId, "eventResponses")
            res = utils.columnsToDict(cols)
            for rsvp in res.keys():
                resp = rsvp.split(":")[0]
                uid = rsvp.split(":")[1]
                if resp == list_type:
                    if uid in item["invitees"] and item["invitees"][uid] == list_type:
                        user_list.insert(0, uid)
                    else:
                        user_list.append(uid)

            invited = user_list

            entities = {}
            owner = item["meta"].get("owner")
            cols = yield db.multiget_slice(invited+[owner], "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(cols)

            args = {"users": invited, "entities": entities}
            args['title'] = {"yes":_("People attending this event"),
                             "no": _("People not attending this event"),
                             "maybe": _("People who may attend this event")
                             }[list_type]

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

        if ("type" in conv["meta"] and conv["meta"]["type"] != "event"):
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
        #if myId in conv["invitees"].keys():
        #    conv["invitees"] = {myId: response}
            #d = db.batch_insert(convId, "items", conv)
            #deferreds.append(d)

        #Now insert the event in the user's agenda list if the user has
        # never responded to this event or the user is not in the invited list.
        #In the second case the agenda was already updated when creating the
        # event
        if prevResponse == "" and myId not in conv["invitees"].keys():
            d1 = db.insert(myId, "userAgenda", convId, starttimeUUID)
            d2 = db.insert(myId, "userAgenda", convId, endtimeUUID)
            d3 = db.insert("%s:%s" %(myId, convId), "userAgendaMap", "",
                          starttimeUUID)
            d4 = db.insert("%s:%s" %(myId, convId), "userAgendaMap", "",
                          endtimeUUID)
            deferreds.extend([d1, d3, d2, d4])

        #Remove any old responses to this event by this user.
        yield db.batch_remove({'eventResponses': [convId]}, names=rsvp_names)

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

        #TODO:Update the UI for changes.
        #TODO:Once a user who has not been invited responds, add the item to his
        # feed.

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _events(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "event.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "event.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        yield event.fetchMatchingEvents(request, args, myId)

        if script:
            yield renderScriptBlock(request, "event.mako", "events", landing,
                                    "#events", "set", **args)


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
        if segmentCount == 1 and request.postpath[0] == "attendance":
            d = self._attendance(request)

        return self._epilogue(request, d)


class Event(object):
    implements(IPlugin, IItemType)
    itemType = "event"
    position = 4
    disabled = False
    hasIndex = True
    indexFields = {'meta': set(['event_desc', 'event_location', 'event_title'])}
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
        reasons = {1: "%s invited you to the event: %s ",
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
        my_response = ""
        responses = {}
        yes_people, no_people, maybe_people = [], [], []

        #Status of invited people
        invitees = yield db.multiget_slice([convId], "items", ["invitees"])
        invitees = utils.multiSuperColumnsToDict(invitees)
        args.setdefault("invited_status", {})[convId] = invitees[convId]["invitees"]
        #responses.update(invitees[convId]["invitees"])

        #Status of others
        cols = yield db.get_slice(convId, "eventResponses")
        res = utils.columnsToDict(cols).keys()
        for x in res:
            resp, userId = x.split(":")
            responses[userId] = resp
            {'yes':lambda id: yes_people.append(id),
             'no':lambda id: no_people.append(id),
             'maybe':lambda id: maybe_people.append(id)}[resp](userId)

        args.setdefault("responses", {})[convId] = responses
        args.setdefault("yes_people", {})[convId] = yes_people
        args.setdefault("no_people", {})[convId] = no_people
        args.setdefault("maybe_people", {})[convId] = maybe_people

        args.setdefault("my_response", {})[convId] = responses[myId] if myId in responses else ""

        defer.returnValue(invitees[convId]["invitees"].keys()+yes_people+no_people+maybe_people)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request, myId, myOrgId, convId, richText=False):

        startDate = utils.getRequestArg(request, 'startDate')
        endDate = utils.getRequestArg(request, 'endDate')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        allDay = utils.getRequestArg(request, "allDay")
        acl = utils.getRequestArg(request, "acl", sanitize=False)
        isPrivate = utils.getRequestArg(request, "isPrivate")

        # Parse invitees from the tag edit plugin values
        arg_keys = request.args.keys()
        invitees = []
        for arg in arg_keys:
            if arg.startswith("invitee[") and arg.endswith("-a]"):
                rcpt = arg.replace("invitee[", "").replace("-a]", "")
                if rcpt != "":
                    invitees.append(rcpt)
        # The owner is always invited to the event
        invitees.append(myId)

        if not ((title or desc) and startDate and endDate):
            raise errors.MissingParams([_('Title, Start date and End date are required to create an event')])

        utc = pytz.utc
        startDate = datetime.datetime.utcfromtimestamp(float(startDate)/1000).replace(tzinfo=utc)
        endDate = datetime.datetime.utcfromtimestamp(float(endDate)/1000).replace(tzinfo=utc)

        if endDate < startDate:
            raise errors.InvalidRequest("Event end date is set in the past")

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

        #Check if the invited user ids are valid
        res = yield db.multiget_slice(invitees, "entities", ['basic'])
        res = utils.multiSuperColumnsToDict(res)
        invitees = [x for x in res.keys() if res[x]["basic"]["org"] == myOrgId]

        #Modify the received ACL to include those who were invited including
        # the owner of this item.
        acl = json.loads(acl)
        acl.setdefault("accept", {})
        acl["accept"].setdefault("users", [])
        acl["accept"]["users"].extend(invitees)
        acl = json.dumps(acl)
        item, attachments = yield utils.createNewItem(request, self.itemType,
                                                      myId, myOrgId,
                                                      richText=richText,
                                                      acl=acl)

        item["meta"].update(meta)
        item["invitees"] = dict([(x, myId) for x in invitees])

        starttime = int(meta["event_startTime"])
        starttimeUUID = utils.uuid1(timestamp=starttime)
        starttimeUUID = starttimeUUID.bytes

        endtime = int(meta["event_endTime"])
        endtimeUUID = utils.uuid1(timestamp=endtime)
        endtimeUUID = endtimeUUID.bytes

        yield self.inviteUsers(request, starttimeUUID, endtimeUUID, convId,
                                    myId, myOrgId, invitees, acl)

        # XXX: We should find a way to make things like this work.
        defer.returnValue((item, attachments))


    @defer.inlineCallbacks
    def delete(self, myId, convId):
        log.debug("plugin:delete", convId)
        user_tuids = {}

        #Get the list of every user who responded to this event
        res = yield db.get_slice(convId, "eventResponses")
        attendees = [x.column.name.split(":", 1)[1] for x in res]

        # Add all the invited people of the item
        res = yield db.get_slice(convId, "items", ['invitees'])
        res = utils.supercolumnsToDict(res)
        attendees.extend(res["invitees"].keys())

        log.debug("Attendees", attendees)
        log.debug("Maps", ["%s:%s"%(uId, convId) for \
                                       uId in attendees])

        # TODO:Add the orgId in case, the event was posted to the company.
        # TODO:Add the groups, if the event was posted to groups.

        #Get the timeuuids that were inserted for this user
        res = yield db.multiget_slice(["%s:%s"%(uId, convId) for \
                                       uId in attendees], "userAgendaMap")
        res = utils.multiColumnsToDict(res)

        for k, v in res.iteritems():
            uid = k.split(":", 1)[0]
            tuids = v.keys()
            user_tuids[uid] = tuids

        log.debug("userAgenda Removal", user_tuids)
        #Delete their entries in the user's list of event entries
        for attendee in user_tuids:
            yield db.batch_remove({'userAgenda': [attendee]},
                                    names=user_tuids[attendee])

        log.debug("eventResponses Removal", convId)
        #Delete the event's entry in eventResponses
        yield db.remove(convId, "eventResponses")

        log.debug("userAgendaMap Removal", user_tuids)
        #Delete their entries in userAgendaMap
        for attendee in user_tuids:
            yield db.batch_remove({'userAgendaMap': ["%s:%s"%(attendee, convId)]},
                                    names=user_tuids[attendee])


    @defer.inlineCallbacks
    def inviteUsers(self, request, starttimeUUID, endtimeUUID, convId, myId,
                     myOrgId, invitees, acl=None):
        #Return a dict of users who were explicitly invited and their current
        # RSVP set to ""
        deferreds = []
        #TODO:Send notifications to each one of these people
        for invitee in invitees:
            #Add to the user's agenda
            d1 = db.insert(invitee, "userAgenda", convId, starttimeUUID)
            d2 = db.insert(invitee, "userAgenda", convId, endtimeUUID)
            d3 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                          starttimeUUID)
            d4 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                          endtimeUUID)
            deferreds.extend([d1, d3, d2, d4])

        if acl:
            # Based on the ACL, if company or groups were included, then add an
            # Extra entry for the company aganda and group agenda.
            acl = json.loads(acl)
            extra_entities = []
            if "groups" in acl["accept"]:
                res = yield db.multiget_slice(acl["accept"]["groups"], "entities", ['basic'])
                res = utils.multiSuperColumnsToDict(res)
                extra_entities.extend([x for x in res.keys() if res[x]['basic']['type'] == 'group'])
            if "orgs" in acl["accept"]:
                extra_entities.extend([myOrgId])

            for invitee in extra_entities:
                #Add to the entity's agenda
                d1 = db.insert(invitee, "userAgenda", convId, starttimeUUID)
                d2 = db.insert(invitee, "userAgenda", convId, endtimeUUID)
                d3 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                              starttimeUUID)
                d4 = db.insert("%s:%s" %(invitee, convId), "userAgendaMap", "",
                              endtimeUUID)
                deferreds.extend([d1, d3, d2, d4])

        if deferreds:
            res = yield defer.DeferredList(deferreds)

        defer.returnValue([])


    @defer.inlineCallbacks
    def renderSideBlock(self, request, landing, args):

        convId = args["convId"]
        conv = args["items"][convId]
        convMeta = conv["meta"]
        title = convMeta.get("event_title", '')
        location = convMeta.get("event_location", '')
        desc = convMeta.get("event_desc", "")
        start = convMeta.get("event_startTime")
        end   = convMeta.get("event_endTime")
        owner = convMeta["owner"]
        ownerName = args["entities"][owner]["basic"]["name"]

        my_tz = timezone(args["me"]['basic']['timezone'])
        owner_tz = timezone(args["entities"][owner]['basic']['timezone'])
        utc = pytz.utc
        startdatetime = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
        enddatetime = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)

        utc_dt = utc.normalize(startdatetime)
        #In my timezone
        start_dt = my_tz.normalize(startdatetime.astimezone(my_tz))
        end_dt = my_tz.normalize(enddatetime.astimezone(my_tz))

        #In owner's timezone
        owner_start_dt = owner_tz.normalize(startdatetime.astimezone(owner_tz))
        owner_end_dt = owner_tz.normalize(enddatetime.astimezone(owner_tz))

        args.update({"start_dt":start_dt, "end_dt":end_dt,
                     "owner_start_dt":owner_start_dt,
                     "owner_end_dt":owner_end_dt})

        d1 = renderScriptBlock(request, "event.mako", "event_meta", landing,
                                "#item-meta", "set", **args)
        d2 = renderScriptBlock(request, "event.mako", "event_me", landing,
                                "#item-me", "set", **args)

        onload = """
                $$.events.autoFillUsers();
                """
        d3 = renderScriptBlock(request, "event.mako", "event_actions", landing,
                                "#item-subactions", "set", True,
                                handlers={"onload": onload}, **args)

        yield defer.DeferredList([d1, d2, d3])

    @defer.inlineCallbacks
    def renderSideAgendaBlock(self, request, landing, blockType, args):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        if blockType == "org":
            yield event.fetchMatchingEvents(request, args, myOrgId)
            yield renderScriptBlock(request, "event.mako", "company_agenda",
                                   landing, "#agenda", "set", **args)
        elif blockType == "group":
            groupId = args["groupId"]
            yield event.fetchMatchingEvents(request, args, groupId)
            yield renderScriptBlock(request, "event.mako", "group_agenda",
                                   landing, "#group-agenda", "set", **args)
        else:
            yield event.fetchMatchingEvents(request, args, myId)
            yield renderScriptBlock(request, "event.mako", "quick_agenda",
                                   landing, "#agenda", "set", **args)


    @defer.inlineCallbacks
    def fetchMatchingEvents(self, request, args, entityId, count=5,
                            start=None, end=None):
        """Find matching events for the user, org or group for a given time
        range.

        """
        # since we store times in UTC, find out the utc time for the user's
        # 00:00 hours instead of utc 00:00.
        my_tz = timezone(args["me"]["basic"]["timezone"])
        utc_now = datetime.datetime.now(pytz.utc)
        mytz_now = utc_now.astimezone(my_tz)
        myId = args["myId"]
        convs = []
        invitations = []
        toFetchEntities = set()

        if not start:
            mytz_start = mytz_now+relativedelta(hour=0, minute=0, second=0)

        if not end:
            mytz_end = mytz_now+relativedelta(days=7, hour=23, minute=59, second=59)

        print mytz_start.strftime('%a %b %d, %I:%M %p %Z')
        timestamp = calendar.timegm(mytz_start.utctimetuple())
        timeUUID = utils.uuid1(timestamp=timestamp)
        stimeUUID = timeUUID.bytes

        print mytz_end.strftime('%a %b %d, %I:%M %p %Z')
        args["start"] = mytz_start.strftime('%a %b %d, %I:%M %p %Z')
        args["end"] = mytz_end.strftime('%a %b %d, %I:%M %p %Z')
        timestamp = calendar.timegm(mytz_end.utctimetuple())
        timeUUID = utils.uuid1(timestamp=timestamp)
        etimeUUID = timeUUID.bytes

        myevents = yield db.get_slice(entityId, "userAgenda", start=stimeUUID,
                                      count=count, finish=etimeUUID)
        matched_events = []
        matched_tids = []
        for event in myevents:
            matched_events.append(event.column.value)
            matched_tids.append(uuid.UUID(bytes=event.column.name))

        matched_tids.sort()
        mevents = []
        for x in matched_events:
            if x not in mevents:
                mevents.append(x)

        res = yield db.multiget_slice(mevents, "items", ["meta"])
        events = utils.multiSuperColumnsToDict(res, ordered=True)

        #Get this user's response for each of these events.
        rsvp_names = ["%s:%s" %(x, myId) for x in ['yes', 'no', 'maybe']]
        myResponses = {}
        cols = yield db.multiget_slice(mevents, "eventResponses", rsvp_names)
        res = utils.multiColumnsToDict(cols)
        for event, resp in res.iteritems():
            if resp.keys():
                myResponses[event] = resp.keys()[0].split(":", 1)[0]
            else:
                myResponses[event] = ""

        args["items"] = events
        args["conversations"] = mevents
        args["my_response"] = myResponses
        args["invited_status"] = {}

        toFetchEntities.update([events[id]["meta"]["owner"] for id in events])
        invitees = yield db.multiget_slice(matched_events, "items", ["invitees"])
        invitees = utils.multiSuperColumnsToDict(invitees)
        for convId in matched_events:
            #args["invited_status"][convId] = invitees[convId]["invitees"]
            toFetchEntities.update(invitees[convId]["invitees"])
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        args["entities"] = entities


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
