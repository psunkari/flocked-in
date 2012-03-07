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
    def _invite(self, request, convId=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']
        convId, conv = yield utils.getValidItemId(request, "id", columns=["invitees"])

        # Parse invitees from the tag edit plugin values
        arg_keys = request.args.keys()
        invitees, new_invitees = [], []
        for arg in arg_keys:
            if arg.startswith("invitee[") and arg.endswith("-a]"):
                rcpt = arg.replace("invitee[", "").replace("-a]", "")
                if rcpt != "":
                    invitees.append(rcpt)

        if myId not in conv["invitees"].keys():
            raise errors.invalidRequest(_("Only those who are invited can invite others"))

        res = yield db.multiget_slice(invitees, "entities", ['basic'])
        res = utils.multiSuperColumnsToDict(res)
        invitees = [x for x in res.keys() if res[x]["basic"]["org"] == myOrgId]
        invitees = [x for x in invitees if x not in conv["invitees"].keys()]
        relation = Relation(myId, [])

        updateConv = {"meta":{}, "invitees":{}}
        if myId == conv["meta"]["owner"]:
            #If invited by owner, add the invitees to the ACL
            acl = conv["meta"]["acl"]
            acl = pickle.loads(acl)
            acl.setdefault("accept", {}).setdefault("users", [])
            acl["accept"]["users"].extend(invitees)
            updateConv["meta"]["acl"] = pickle.dumps(acl)
            new_invitees.extend(invitees)
        else:
            for invitee in invitees:
                relation = Relation(invitee, [])
                yield relation.initGroupsList()
                withinAcl = utils.checkAcl(invitee, myOrgId, False,
                                           relation, conv["meta"])
                if withinAcl:
                    new_invitees.append(invitee)

        if new_invitees:
            convMeta = conv["meta"]
            starttime = int(convMeta["event_startTime"])
            starttimeUUID = utils.uuid1(timestamp=starttime)
            starttimeUUID = starttimeUUID.bytes

            endtime = int(convMeta["event_endTime"])
            endtimeUUID = utils.uuid1(timestamp=endtime)
            endtimeUUID = endtimeUUID.bytes

            updateConv["invitees"] = dict([(x, myId) for x in new_invitees])
            d = yield db.batch_insert(convId, "items", updateConv)

            yield event.inviteUsers(request, starttimeUUID, endtimeUUID,
                                        convId, conv["meta"]["owner"],
                                        myOrgId, new_invitees)
            request.write("""$$.alerts.info('%s');""" \
                            %("%d people invited to this event" %len(new_invitees)))
            #XXX: Push to the invited user's feed.
        else:
            if not invitees:
                request.write("""$$.alerts.info('%s');""" \
                                %("Invited persons are already on the invitation list"))
            else:
                request.write("""$$.alerts.info('%s');""" \
                                %("Invited persons do not have access to this event"))

        request.write("$('#item-subactions .tagedit-listelement-old').remove();")


    @defer.inlineCallbacks
    def _attendance(self, request):
        itemId, item = yield utils.getValidItemId(request, "id",
                                                  columns=["invitees"])
        list_type = utils.getRequestArg(request, 'type') or "yes"
        user_list = []

        if itemId and list_type in ["yes", "no", "maybe"]:
            cols = yield db.get_slice(itemId, "eventResponses")
            res = utils.columnsToDict(cols)
            for rsvp in res.keys():
                resp = rsvp.split(":")[0]
                uid = rsvp.split(":")[1]
                if resp == list_type:
                    if uid in item["invitees"] and \
                      item["invitees"][uid] == list_type:
                        user_list.insert(0, uid)
                    else:
                        user_list.append(uid)

            invited = user_list

            entities = {}
            owner = item["meta"].get("owner")
            cols = yield db.multiget_slice(invited+[owner], "entities",
                                           ["basic"])
            entities = utils.multiSuperColumnsToDict(cols)

            args = {"users": invited, "entities": entities}
            args['title'] = {"yes":_("People attending this event"),
                             "no": _("People not attending this event"),
                             "maybe": _("People who may attend this event")
                             }[list_type]

            t.renderScriptBlock(request, "item.mako", "userListDialog", False,
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

        convId, conv = yield utils.getValidItemId(request, "id",
                                                  columns=["invitees"])

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

            request.write("$('#event-rsvp-status-%s').text('%s');"
                                                            %(convId, rsp))
            request.write("$('#conv-%s .event-join-decline').text('%s');"
                                                            %(convId, rsp))

        if deferreds:
            res = yield defer.DeferredList(deferreds)

        if script:
            args.update({"items":{convId:conv}, "convId":convId})
            entityIds = yield event.fetchData(args, convId)
            entities = yield db.multiget_slice(entityIds, "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(entities)
            args["entities"] = entities

            t.renderScriptBlock(request, "event.mako", "event_meta",
                                landing, "#item-meta", "set", **args)

        #TODO:Once a user who has not been invited responds, add the item to his
        # feed.

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _events(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        page = utils.getRequestArg(request, 'page') or '1'
        entityId = utils.getRequestArg(request, 'id') or myId
        view = utils.getRequestArg(request, 'view') or "agenda"
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization
        start = utils.getRequestArg(request, 'start') or ""

        #Check if entity Id is my Org or a group that I have access to.
        if entityId != myId and entityId != myOrgId:
            yield utils.getValidEntityId(request, "id", "group")

        if view == "invitations":
            entityId = "%s:%s" %(myId, "I")

        if page.isdigit():
            page = int(page)
        else:
            page = 1
        count = constants.EVENTS_PER_PAGE

        try:
            start = datetime.datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            start = None

        args.update({'view':view, 'menuId': 'events'})
        args.update({'page':page, 'entityId': entityId})

        if script and landing:
            t.render(request, "event.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "event.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        yield event.fetchMatchingEvents(request, args, entityId, count=count,
                                        start=start)

        if script:
            onload = """
                     $$.menu.selectItem('events');
                     $$.events.prepareAgendaDatePicker('%s')
                     """ % (args["start"])
            t.renderScriptBlock(request, 'event.mako', "render_events",
                                landing, ".center-contents", "set", True,
                                handlers={"onload": onload}, **args)
        else:
            t.render(request, "event.mako", **args)


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


    @defer.inlineCallbacks
    def renderFeedSideBlock(self, request, landing, entityId, args):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        groupId = args["groupId"] if "groupId" in args else None

        if entityId == myOrgId:
            args["title"] = _("Company Wide Events")
            yield event.fetchMatchingEvents(request, args, myOrgId)
            t.renderScriptBlock(request, "event.mako", "side_agenda",
                                   landing, "#feed-side-block-container",
                                   "append", **args)
        elif entityId == myId:
            args["title"] = _("My Upcoming Events")
            yield event.fetchMatchingEvents(request, args, myId)
            t.renderScriptBlock(request, "event.mako", "side_agenda",
                                   landing, "#feed-side-block-container",
                                   "append", **args)
        elif entityId == groupId:
            args["title"] = _("Group Agenda")
            groupId = args["groupId"]
            yield event.fetchMatchingEvents(request, args, groupId)
            t.renderScriptBlock(request, "event.mako", "side_agenda",
                                   landing, "#feed-side-block-container",
                                   "append", **args)

        #XXX: What if too many expired events come up in the search.

    @defer.inlineCallbacks
    def fetchMatchingEvents(self, request, args, entityId, count=5, start=None):
        """Find matching events for the user, org or group for a given time
        range. Events are sorted by their start time and then by their end time.

        """
        myId = args["myId"]
        convs = []
        invitations = []
        toFetchEntities = set()
        my_tz = timezone(args["me"]["basic"]["timezone"])

        if not start:
            # since we store times in UTC, find out the utc time for the user's
            # 00:00 hours instead of utc 00:00.
            utc_now = datetime.datetime.now(pytz.utc)
            mytz_now = utc_now.astimezone(my_tz)
            mytz_start = mytz_now+relativedelta(hour=0, minute=0, second=0)
        else:
            mytz_start = start.replace(tzinfo=my_tz)

        args["start"] = mytz_start.strftime("%Y-%m-%d")
        timestamp = calendar.timegm(mytz_start.utctimetuple())
        timeUUID = utils.uuid1(timestamp=timestamp)
        start = timeUUID.bytes

        page = args.get("page", 1)

        cols = yield db.get_slice(entityId, "userAgenda", start=start,
                                      count=(page*count)*2)
        matched_events = [col.column.value for col in cols]
        res = yield db.multiget_slice(matched_events, "items", ["meta"])
        matched_events = utils.multiSuperColumnsToDict(res)
        to_sort_time_tuples = [(x, y["meta"]["event_startTime"],
                                y["meta"]["event_endTime"]) \
                                    for x, y in matched_events.iteritems()]

        sorted_time_tuples = sorted(to_sort_time_tuples,
                                    key=itemgetter(int(1), int(2)))

        sorted_event_ids = [x[0] for x in sorted_time_tuples]
        events_in_this_page = sorted_event_ids[(page-1)*count:page*count]

        if len(events_in_this_page) >= count:
            nextPage = page + 1
            args.update({'nextPage': nextPage})
        else:
            args.update({'nextPage': 0})

        args["prevPage"] = page - 1
        args["items"] = matched_events
        args["conversations"] = events_in_this_page

        #Now fetch all related entities, participants, owners, attendees,
        # invitees, groups etc
        for convId in events_in_this_page:
            entityIds = yield self.fetchData(args, convId)
            toFetchEntities.update(entityIds)

        relation = Relation(myId, [])
        yield relation.initGroupsList()

        for event, event_meta in matched_events.iteritems():
            target = event_meta['meta'].get('target')
            if target:
                toFetchEntities.update(target.split(','))

        entities = yield db.multiget_slice(toFetchEntities, "entities",
                                           ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        args["entities"] = entities
        args["relations"] = relation


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
