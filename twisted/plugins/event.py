import datetime
import pytz
import calendar
import json
from pytz import timezone
from dateutil.relativedelta import relativedelta
try:
    import cPickle as pickle
except:
    import pickle
from operator import itemgetter, attrgetter

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer

from social             import db, utils, base, errors, _
from social             import template as t
from social             import constants
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import dump_args, profile, log


class EventResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _inviteUsers(self, request, convId=None):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args['orgId']

        if not convId:
            convId = utils.getRequestArg(request, 'id')
        acl = utils.getRequestArg(request, 'acl', False)
        invitees = yield utils.expandAcl(myKey, orgId, pickle.dumps(json.loads(acl)), convId)
        #invitees = utils.getRequestArg(request, 'invitees')
        #invitees = invitees.split(',') if invitees else None
        #myKey = request.getSession(IAuthInfo).username
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
                value = ":".join([responseType, myKey, convId, convType, convOwner])
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
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

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
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convs = []
        invitations = []
        toFetchEntities = set()

        if script and landing:
            t.render(request, "event.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "event.mako", "layout",
                                landing, "#mainbar", "set", **args)

        myEvents = yield db.get_slice(myKey, "userEvents", reverse=True)
        myInvitations = yield db.get_slice(myKey, "userEventInvitations", reverse=True)

        for item in myEvents:
            convs.append(item.column.value)

        for item in myInvitations:
            if item.column.value not in invitations:
                invitations.append(item.column.value)

        events = yield db.multiget_slice(convs + invitations, "items", ["meta", "rsvp"])
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
    monitorFields = {'meta': set(['event_desc', 'event_location', 'event_title'])}

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
        reasons = {1: "%s invited you to the event: %s",
                   2: "%s and %s invited you to the event: %s",
                   3: "%s, %s and 1 other invited you to the event: %s",
                   4: "%s, %s and %s others invited you to the event: %s"}
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
        orgId = authinfo.organization

        cols = yield db.multiget_slice([myId, orgId], "entities", ["basic"])
        cols = utils.multiSuperColumnsToDict(cols)

        me = cols.get(myId, None)
        org = cols.get(orgId, None)
        args = {"myId": myId, "orgId": orgId, "me": me, "org": org}

        my_tz = timezone(me["basic"]["timezone"])
        utc_now = datetime.datetime.now(pytz.utc)
        mytz_now = utc_now.astimezone(my_tz)
        tzoffset = int(mytz_now.utcoffset().total_seconds())
        args.update({"my_tz": my_tz, "utc_now":utc_now, "mytz_now":mytz_now})

        onload = """
                (function(obj){
                    $$.publisher.load(obj);
                    $$.events.prepareDateTimePickers();
                    $$.events.autoFillUsers();
                })(this);
                """
        t.renderScriptBlock(request, "event.mako", "share_event",
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "event"},
                                handlers={"onload": onload}, **args)


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("event.mako", "event_root", **args)
        else:
            return t.getBlock("event.mako", "event_root",
                              args=[convId, isQuoted], **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        myId = args["myId"]
        myResponse = ""
        userResponses = {}
        yesPeople, noPeople, maybePeople = [], [], []

        # List of invited people
        invitees = yield db.get_slice(convId, "items", ["invitees"])
        invitees = utils.supercolumnsToDict(invitees)
        args.setdefault("invitedPeople", {})[convId] = \
                                                    invitees["invitees"]

        # Status of others
        cols = yield db.get_slice(convId, "eventResponses")
        res = utils.columnsToDict(cols).keys()
        for x in res:
            resp, userId = x.split(":")
            userResponses[userId] = resp
            if resp == "yes":
                yesPeople.append(userId)
            elif resp == "no":
                noPeople.append(userId)
            elif resp == "maybe":
                maybePeople.append(userId)

        args.setdefault("userResponses", {})[convId] = userResponses
        args.setdefault("yesPeople", {})[convId] = yesPeople
        args.setdefault("noPeople", {})[convId] = noPeople
        args.setdefault("maybePeople", {})[convId] = maybePeople

        args.setdefault("myResponse", {})[convId] = userResponses[myId] \
                                            if myId in userResponses else ""

        defer.returnValue(invitees["invitees"].keys()+\
                            yesPeople+noPeople+maybePeople)


    @profile
    @defer.inlineCallbacks
    def create(self, request, myId, myOrgId, convId, richText=False):
        startDate = utils.getRequestArg(request, 'startDate')
        endDate = utils.getRequestArg(request, 'endDate')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        allDay = utils.getRequestArg(request, "allDay")
        acl = utils.getRequestArg(request, "acl", sanitize=False)
        isPrivate = utils.getRequestArg(request, "isPrivate")

        if not ((title or desc) and startDate and endDate):
            raise errors.MissingParams([_('Title'), _('Start date'), _('End date')])

        if startDate.isdigit() and endDate.isdigit():
            startDate = int(startDate)/1000
            endDate = int(endDate)/1000
        else:
            raise error.InvalidRequest("Invalid start or end dates")

        if endDate < startDate:
            raise errors.InvalidRequest("Event end date is set in the past")

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

        meta = {"event_startTime": str(startDate), "event_endTime": str(endDate)}

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

        # Check if the invited user ids are valid
        res = yield db.multiget_slice(invitees, "entities", ['basic'])
        res = utils.multiSuperColumnsToDict(res)
        invitees = [x for x in res.keys() if res[x]["basic"]["org"] == myOrgId]

        # Modify the received ACL to include those who were invited including
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

        starttimeUUID = utils.uuid1(timestamp=startDate)
        starttimeUUID = starttimeUUID.bytes

        endtimeUUID = utils.uuid1(timestamp=endDate)
        endtimeUUID = endtimeUUID.bytes

        yield self.inviteUsers(request, starttimeUUID, endtimeUUID, convId,
                                    myId, myOrgId, invitees, acl)

        defer.returnValue((item, attachments))


    @defer.inlineCallbacks
    def delete(self, myId, convId, conv):
        log.debug("plugin:delete", convId)
        user_tuids = {}

        # Get the list of every user who responded to this event
        res = yield db.get_slice(convId, "eventResponses")
        attendees = [x.column.name.split(":", 1)[1] for x in res]

        # Add all the invited people of the item
        res = yield db.get_slice(convId, "items", ['invitees'])
        res = utils.supercolumnsToDict(res)
        attendees.extend(res["invitees"].keys())
        invitedPeople = res["invitees"].keys()

        log.debug("Maps", ["%s:%s"%(uId, convId) for \
                                       uId in attendees])

        # Get the Org and GroupIds if any.
        convMeta = conv["meta"]
        groupIds = convMeta["target"].split(",") if "target" in convMeta else []
        attendees.extend(groupIds+[convMeta["org"]])

        log.debug("Attendees", attendees)

        # Get the timeuuids that were inserted for this user
        res = yield db.multiget_slice(["%s:%s"%(uId, convId) for \
                                       uId in attendees], "userAgendaMap")
        res = utils.multiColumnsToDict(res)

        for k, v in res.iteritems():
            uid = k.split(":", 1)[0]
            tuids = v.keys()
            if tuids:
                user_tuids[uid] = tuids

        log.debug("userAgenda Removal", user_tuids)
        # Delete their entries in the user's list of event entries
        for attendee in user_tuids:
            yield db.batch_remove({'userAgenda': [attendee]},
                                    names=user_tuids[attendee])

        # Delete invitation entries for invited people
        invited_tuids = dict([[x, user_tuids[x]] for x in invitedPeople])
        log.debug("userAgenda Invitation Removal", invited_tuids)
        for attendee in invited_tuids:
            yield db.batch_remove({'userAgenda': ['%s:%s' %(attendee, 'I')]},
                                    names=invited_tuids[attendee])

        log.debug("eventResponses Removal", convId)
        # Delete the event's entry in eventResponses
        yield db.remove(convId, "eventResponses")

        log.debug("userAgendaMap Removal", user_tuids)
        # Delete their entries in userAgendaMap
        for attendee in user_tuids:
            yield db.batch_remove({'userAgendaMap': ["%s:%s"%(attendee, convId)]},
                                    names=user_tuids[attendee])


    @defer.inlineCallbacks
    def inviteUsers(self, request, starttimeUUID, endtimeUUID, convId, ownerId,
                     myOrgId, invitees, acl=None):
        deferreds = []
        toNotify = {}
        toRemove = {'latest':[]}
        entitiesToUpdate = []

        #TODO:Send notifications to each one of these people
        for invitee in invitees:
            # Add to each user's agenda
            entitiesToUpdate.append(invitee)
            if invitee == ownerId:
                # The organizer auto accepts an event
                d = db.insert(convId, "eventResponses", "", "yes:%s" %(ownerId))
                deferreds.append(d)

            # Add to an additional column for invited users(not the owner)
            if invitee != ownerId:
                d1 = db.insert("%s:I" % (invitee), "userAgenda",
                               convId, starttimeUUID)
                d2 = db.insert("%s:I" % (invitee), "userAgenda",
                               convId, endtimeUUID)
                deferreds.extend([d1, d2])

        if acl:
            # Based on the ACL, if company or groups were included, then add an
            # Extra entry for the company agenda and group agenda.
            # FIXME: Praveen: technically acl can have a dont-allow list.
            # we dont want to add event to entities in dont-allow list.
            acl = json.loads(acl)
            extra_entities = []
            if "groups" in acl["accept"]:
                res = yield db.multiget_slice(acl["accept"]["groups"],
                                              "entities", ['basic'])
                groups = utils.multiSuperColumnsToDict(res)
                for groupId, group in groups.iteritems():
                    #Check if group is really a group and belongs to the same
                    # org that I belong to.
                    if group["basic"]["type"] == 'group' and \
                      group["basic"]["org"] == myOrgId:
                        extra_entities.append(groupId)

            if "orgs" in acl["accept"]:
                extra_entities.extend([myOrgId])

            entitiesToUpdate.extend(extra_entities)

        for invitee in entitiesToUpdate:
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


    def renderItemSideBlock(self, request, landing, args):

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
        startdatetime = datetime.datetime.utcfromtimestamp(float(start)).\
                                                            replace(tzinfo=utc)
        enddatetime = datetime.datetime.utcfromtimestamp(float(end)).\
                                                            replace(tzinfo=utc)

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

        t.renderScriptBlock(request, "event.mako", "event_meta", landing,
                                "#item-meta", "set", **args)
        t.renderScriptBlock(request, "event.mako", "event_me", landing,
                                "#item-me", "set", **args)

        onload = """
                $$.events.autoFillUsers();
                """
        t.renderScriptBlock(request, "event.mako", "event_actions", landing,
                                "#item-subactions", "set", True,
                                handlers={"onload": onload}, **args)


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
