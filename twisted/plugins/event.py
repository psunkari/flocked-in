import datetime
import pytz
import calendar
import json
from pytz import timezone
from dateutil.relativedelta import relativedelta
import uuid
try:
    import cPickle as pickle
except:
    import pickle
from operator import itemgetter, attrgetter

from telephus.cassandra import ttypes
from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer

from social             import db, utils, base, errors, _, constants
from social             import template as t
from social             import rootUrl
from social.relations   import Relation
from social.isocial     import IAuthInfo, IItemType, IFeedUpdateType
from social.isocial     import INotificationType
from social.logging     import dump_args, profile, log

# Taken from social.item
@defer.inlineCallbacks
def _notify(notifyType, convId, timeUUID, **kwargs):
    convOwnerId = kwargs["convOwnerId"]
    convType = kwargs["convType"]
    myId = kwargs["myId"]
    toFetchEntities = set()
    notifyId = ":".join([convId, convType, convOwnerId, notifyType])

    # List of people who will get the notification about current action
    if notifyType == "EI":
        recipients = kwargs["new_invitees"]
    else:
        recipients = [convOwnerId]

    toFetchEntities = set(recipients + [myId, convOwnerId])
    recipients = [userId for userId in recipients if userId != myId]

    from social import notifications

    entities = base.EntitySet(toFetchEntities)
    if recipients:
        def _gotEntities(cols):
            kwargs.setdefault('entities', {}).update(entities)
            kwargs["me"] = entities[myId]
        def _sendNotifications(ignored):
            return notifications.notify(recipients, notifyId,
                                        myId, timeUUID, **kwargs)

        notify_d = entities.fetchData()
        notify_d.addCallback(_gotEntities)
        notify_d.addCallback(_sendNotifications)

        yield notify_d


class EventResource(base.BaseResource):
    isLeaf = True
    _templates = ['event.mako']

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

        res = base.EntitySet(invitees)
        yield res.fetchData()
        invitees = [x for x in res.keys() if res[x].basic["org"] == myOrgId]
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
                                    convId, conv["meta"], myId,
                                    myOrgId, new_invitees)
            request.write("""$$.alerts.info('%s');""" \
                            %("%d people invited to this event" %len(new_invitees)))
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
            owner = item["meta"].get("owner")

            entities = base.EntitySet(invited+[owner])
            yield entities.fetchData()

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
        orgId = args['orgId']

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
            entities = base.EntitySet(entityIds)
            yield entities.fetchData()
            args["entities"] = entities

            t.renderScriptBlock(request, "event.mako", "event_meta",
                                landing, "#item-meta", "set", **args)

        # Push Feed Updates
        responseType = "E"
        convMeta = conv["meta"]
        convType = convMeta["type"]
        convOwnerId = convMeta["owner"]
        commentSnippet = convMeta["event_title"]
        itemId = convId
        convACL = convMeta["acl"]
        extraEntities = [convMeta["owner"]]
        # Importing social.feed at the beginning of the module leads to
        # a cyclic dependency as feed in turn imports plugins.
        from social.core import Feed

        if response == "yes":
            timeUUID = uuid.uuid1().bytes

            # Add user to the followers list of parent item
            yield db.insert(convId, "items", "", myId, "followers")

            # Update user's feed, feedItems, feed_*
            userItemValue = ":".join([responseType, itemId, convId, convType,
                                      convOwnerId, commentSnippet])
            yield db.insert(myId, "userItems", userItemValue, timeUUID)
            yield db.insert(myId, "userItems_event", userItemValue, timeUUID)

            # Push to feed
            feedItemVal = "%s:%s:%s:%s" % (responseType, myId, itemId,
                                            ','.join(extraEntities))
            yield Feed.push(myId, orgId, convId, conv, timeUUID, feedItemVal)
        elif prevResponse != "":
            rsvpTimeUUID = None
            cols = yield db.get_slice(myId, "userItems")
            cols = utils.columnsToDict(cols)
            for k, v in cols.iteritems():
                if v.startswith("E"):
                    rsvpTimeUUID = k

            if rsvpTimeUUID:
                # Remove update if user changes RSVP to no/maybe from yes.
                # Do not update if user had RSVPed to this event.
                feedUpdateVal = "%s:%s:%s:%s" % (responseType, myId, itemId,
                                                 convOwnerId)
                yield Feed.unpush(myId, orgId, convId, conv, feedUpdateVal)

                # FIX: if user updates more than one item at exactly same time,
                #      one of the updates will overwrite the other. Fix it.
                yield db.remove(myId, "userItems", rsvpTimeUUID)
                yield db.remove(myId, "userItems_event", rsvpTimeUUID)

        if myId != convOwnerId and response == "yes":
            timeUUID = uuid.uuid1().bytes
            yield _notify("EA", convId, timeUUID, convType=convType,
                              convOwnerId=convOwnerId, myId=myId, me=args["me"])


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
    displayNames = ('Event', 'Events')


    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        orgId = authinfo.organization

        entities = base.EntitySet([myId, orgId])
        yield entities.fetchData()

        me = entities[myId]
        org = entities[orgId]
        args = {"myId": myId, "orgId": orgId, "me": me, "org": org}

        my_tz = timezone(me.basic["timezone"])
        utc_now = datetime.datetime.now(pytz.utc)
        mytz_now = utc_now.astimezone(my_tz)
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
    def create(self, request, me, convId, richText=False):
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
            raise errors.InvalidRequest("Invalid start or end dates")

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
        invitees.append(me.id)

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
        res = base.EntitySet(invitees)
        yield res.fetchData()
        invitees = [x for x in res.keys() if res[x].basic["org"] == me.basic['org']]

        # Modify the received ACL to include those who were invited including
        # the owner of this item.
        acl = json.loads(acl)
        acl.setdefault("accept", {})
        acl["accept"].setdefault("users", [])
        acl["accept"]["users"].extend(invitees)
        acl = json.dumps(acl)
        item = yield utils.createNewItem(request, self.itemType, me,
                                         richText=richText, acl=acl)

        item["meta"].update(meta)
        item["invitees"] = dict([(x, me.id) for x in invitees])

        starttimeUUID = utils.uuid1(timestamp=startDate)
        starttimeUUID = starttimeUUID.bytes

        endtimeUUID = utils.uuid1(timestamp=endDate)
        endtimeUUID = endtimeUUID.bytes

        yield self.inviteUsers(request, starttimeUUID, endtimeUUID, convId,
                                        item["meta"], me.id, me.basic['org'],
                                                                invitees, acl)
        defer.returnValue(item)


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
    def inviteUsers(self, request, starttimeUUID, endtimeUUID, convId, convMeta,
                     myId, myOrgId, invitees, acl=None):
        deferreds = []
        toNotify = {}
        toRemove = {'latest':[]}
        entitiesToUpdate = []
        convOwnerId = convMeta["owner"]

        for invitee in invitees:
            # Add to each user's agenda
            entitiesToUpdate.append(invitee)
            if invitee == convOwnerId:
                # The organizer auto accepts an event
                d = db.insert(convId, "eventResponses", "", "yes:%s" %(convOwnerId))
                deferreds.append(d)

            # Add to an additional column for invited users(not the owner)
            if invitee != convOwnerId:
                d1 = db.insert("%s:I" % (invitee), "userAgenda",
                               convId, starttimeUUID)
                d2 = db.insert("%s:I" % (invitee), "userAgenda",
                               convId, endtimeUUID)
                deferreds.extend([d1, d2])

        # Send notifications to each of the invited people
        timeUUID = uuid.uuid1().bytes
        convType = "event"
        yield _notify("EI", convId, timeUUID, convType=convType,
                          convOwnerId=convOwnerId, myId=myId,
                          convMeta=convMeta, new_invitees=invitees)

        if acl:
            # Based on the ACL, if company or groups were included, then add an
            # Extra entry for the company agenda and group agenda.
            # FIXME: Praveen: technically acl can have a dont-allow list.
            # we dont want to add event to entities in dont-allow list.
            acl = json.loads(acl)
            extra_entities = []
            if "groups" in acl["accept"]:
                groups = base.EntitySet(acl['accept']['groups'])
                yield groups.fetchData()
                for groupId, group in groups.items():
                    #Check if group is really a group and belongs to the same
                    # org that I belong to.
                    if group.basic["type"] == 'group' and \
                      group.basic["org"] == myOrgId:
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
        ownerName = args["entities"][owner].basic["name"]

        my_tz = timezone(args["me"].basic['timezone'])
        owner_tz = timezone(args["entities"][owner].basic['timezone'])
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
        my_tz = timezone(args["me"].basic["timezone"])

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

        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
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


class EventUpdate(object):
    implements(IPlugin, IFeedUpdateType)
    updateType = "E"
    templates = [
        ["%(u0)s is attending your %(type)s",
         "%(u0)s is attending %(owner)s's %(type)s"],
        ["%(u0)s and %(u1)s are attending your %(type)s",
         "%(u0)s and %(u1)s are attending %(owner)s's %(type)s"],
        ["%(u0)s, %(u1)s and %(u2)s are attending your %(type)s",
         "%(u0)s, %(u1)s and %(u2)s are attending %(owner)s's %(type)s"]]

    def parse(self, convId, updates):
        items = []
        entities = []
        for update in updates:
            if len(update) >= 3:
                (x, user, item) = update[0:3]
                entities.append(user)
        return (items, entities)

    def reason(self, convId, updates, data):
        entities = data['entities']
        meta = data['items'][convId]['meta']
        ownerId = meta['owner']
        myId = data['myId']
        yesPeople = data['yesPeople']

        uname = lambda x: utils.userName(x, entities[x], "conv-user-cause")
        if convId in yesPeople:
            users = yesPeople[convId]
        else:
            return ('', [])
        if ownerId in users:
            users.remove(ownerId)
        users = users[0:3]

        vals = dict([('u'+str(i), uname(x)) for i,x in enumerate(users)])
        vals.update({'owner':uname(ownerId),
                     'type':utils.itemLink(convId, meta['type'])})

        if not users:
            return ('', [])

        template = self.templates[len(users)-1][1] if ownerId != myId\
                    else self.templates[len(users)-1][0]

        return (template % vals, users)


class EventNotification(object):
    implements(IPlugin, INotificationType)
    notifyOnWeb = True

    # Notification of a person being invited to an event.
    _toOthers_EI = [
        "%(senderName)s invited you to an event",
        "Hi,\n\n"\
        "%(senderName)s has invited you to an event.\n"\
        "See the event at %(convUrl)s",
        "notifyOtherEI"
    ]

    _aggregation_EI = [
        ["%(user0)s invited you to an %(itemType)s",
         "%(user0)s invited you to %(owner)s's %(itemType)s"],
    ]

    # Notification of an event being RSVPed
    _toOwner_EA = [
        "%(senderName)s is attending your event",
        "Hi,\n\n"\
        "%(senderName)s is attending your event.\n"\
        "See the full event at %(convUrl)s",
        "notifyOwnerEA"
    ]

    # Aggregation of all attendees
    _aggregation_EA = [
        ["%(user0)s is attending your %(itemType)s",
         "%(user0)s is attending %(owner)s's %(itemType)s"],
        ["%(user0)s and %(user1)s are attending your %(itemType)s",
         "%(user0)s and %(user1)s are attending %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other are attending your %(itemType)s",
         "%(user0)s, %(user1)s and 1 other are attending %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others are attending your %(itemType)s",
         "%(user0)s, %(user1)s and %(count)s others are attending %(owner)s's %(itemType)s"]
    ]

    def __init__(self, notificationType):
        self.notificationType = notificationType

    def render(self, parts, value, toOwner=False, getTitle=True, getBody=True,
                                                                    data=None):
        convId, convType, convOwnerId, notifyType = parts
        convTitle, convLocation, convTime = "", "", ""
        if "convMeta" in data:
            convMeta = data["convMeta"]
            me = data['me']
            entities = data['entities']

            convTitle = convMeta["event_title"]
            convLocation = convMeta.get("event_location", "")
            start = convMeta["event_startTime"]
            end   = convMeta["event_endTime"]
            owner = convMeta["owner"]
            ownerName = entities[owner].basic["name"]

            my_tz = timezone(me.basic['timezone'])
            owner_tz = timezone(entities[owner].basic['timezone'])
            utc = pytz.utc
            startdatetime = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
            enddatetime = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)

            utc_dt = utc.normalize(startdatetime)
            start_dt = my_tz.normalize(startdatetime.astimezone(my_tz))
            end_dt = my_tz.normalize(enddatetime.astimezone(my_tz))

            if start_dt.date() == end_dt.date():
                sameDay = True
            else:
                sameDay = False

            allDay = True if convMeta.get("event_allDay", "0") == "1" else False

            if not allDay:
                event_start_fmt = "%a %b %d, %I:%M %p"
            else:
                event_start_fmt = "%a %b %d"
            event_start = start_dt.strftime(event_start_fmt)

            if allDay:
                event_end_fmt = "%a %b %d"
            elif sameDay:
                event_end_fmt = "%I:%M %p"
            else:
                event_end_fmt = "%a %b %d, %I:%M %p"
            event_end = end_dt.strftime(event_end_fmt)

            if not allDay:
                convTime += event_start
                if sameDay:
                    convTime += " to %s" % (event_end)
                else:
                    convTime += " -- %s" % (event_end)
            else:
                convTime += event_start
                if sameDay:
                    convTime += _("All Day")
                else:
                    convTime += " -- %s" % (event_end)

        if notifyType == "EI":
            templates = self._toOthers_EI
        else:
            templates = self._toOwner_EA

        title, body, html = '', '', ''
        senderName = data['me'].basic['name']
        convOwnerName = data['entities'][convOwnerId].basic['name']

        if getTitle:
            title = templates[0] % locals()

        if getBody:
            senderAvatarUrl = utils.userAvatar(data['myId'], data['me'], "medium")
            convUrl = "%s/item?id=%s" % (rootUrl, convId)
            body = templates[1] % locals()

            vals = locals().copy()
            del vals['self']
            html = t.getBlock("event.mako", templates[2], **vals)

        return (title, body, html)

    def fetchAggregationData(self, myId, orgId, parts, values):
        entityIds = [x.split(':')[0] for x in values]
        return (entityIds, entityIds, {})

    def aggregation(self, parts, values, data=None, fetched=None):
        convId, convType, convOwnerId, notifyType = parts

        entities = data['entities']
        userCount = len(values)

        templates = self._aggregation_EI if notifyType == "EI"\
                                         else self._aggregation_EA
        templatePair = templates[3 if userCount > 4 else userCount - 1]

        vals = dict([('user'+str(idx), utils.userName(uid, entities[uid]))\
                      for idx, uid in enumerate(values[0:2])])
        vals['count'] = userCount - 2
        vals['itemType'] = utils.itemLink(convId, convType)

        if notifyType == "EI":
            if convOwnerId == values[0]:
                notifyStr = templatePair[0] % vals
            else:
                vals['owner'] = utils.userName(convOwnerId, entities[convOwnerId])
                notifyStr = templatePair[1] % vals
        else:
            if convOwnerId == data['myId']:
                notifyStr = templatePair[0] % vals
            else:
                vals['owner'] = utils.userName(convOwnerId, entities[convOwnerId])
                notifyStr = templatePair[1] % vals

        return notifyStr


event = Event()
eventUpdates = EventUpdate()
eventInviteNotify = EventNotification("EI")
eventAttendNotify = EventNotification("EA")
