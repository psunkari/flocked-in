import time
import uuid
import datetime
import pytz
import calendar

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
    disabled = False
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

        onload = """
                (function(obj){$$.publisher.load(obj)})(this);
                var currentTime = new Date();
                var currentMinutes = currentTime.getMinutes();
                var currentHours = currentTime.getHours();

                if (currentMinutes < 30){
                    //We set the start time at :30 mins
                    startTime = currentTime.setMinutes(30);
                    endTime = currentTime.setHours(currentTime.getHours()+1)
                }else{
                    //else we set the start at the next hour
                    startTime = currentTime.setHours(currentTime.getHours()+1);
                    startTime = currentTime.setMinutes(0);
                    endTime = currentTime.setHours(currentTime.getHours()+1)
                    endTime = currentTime.setMinutes(0);
                }

                startTimeString = $$.events.formatTimein12(new Date(startTime));
                endTimeString = $$.events.formatTimein12(new Date(endTime));

                // Set the Display Strings
                $('#eventstarttime').attr('value', startTimeString);
                $('#eventendtime').attr('value', endTimeString);
                // Set the hidden attrs
                $('#startTime').attr('value', startTime);
                $('#endTime').attr('value', endTime);
                // Set the Display Strings
                $('#eventstartdate').datepicker();
                $('#eventenddate').datepicker();
                $('#eventstartdate').datepicker('setDate', new Date());
                $('#eventenddate').datepicker('setDate', new Date());
                // Set the hidden attrs.  When a user picks a date from the
                // calendar, the corresponding epoch value is stored in
                // the hidden field. To the server; only the date component is
                // important, since the time component is fetched from the startTime
                // and endTime respectively.
                $('#startDate').attr('value', startTime);
                $('#endDate').attr('value', endTime);
                $("#eventstartdate").datepicker("option", "altField", '#startDate');
                $("#eventenddate").datepicker("option", "altField", '#endDate');
                $("#eventstartdate").datepicker("option", "altFormat", '@');
                $("#eventenddate").datepicker("option", "altFormat", '@');

                //Generate 30 minute timeslots in a day. When a user filters
                // and picks a slot, the corresponding epoch value is stored in
                // the hidden field. To the server; only the time component is
                // important, since the date component is fetched from the startDate
                // and endDate respectively.
                var timeslots = [];
                var dtnow = new Date();
                var hourslots = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
                $.each(hourslots, function(index, slot) {
                    if (slot < 12){
                        var dtlabel = ( slot < 10 ? "0" : "" ) + slot;
                        dtvalue = dtnow.setHours(slot)
                        dtvalue = dtnow.setMinutes(0);
                        dtvalue = dtnow.setSeconds(0);
                        timeslots.push({label:dtlabel+":00"+"AM", value: dtvalue});
                        dtvalue = dtnow.setMinutes(30);
                        timeslots.push({label:dtlabel+":30"+"AM", value: dtvalue});
                    }else{
                        var dtlabel = slot-12;
                        dtvalue = dtnow.setHours(slot)
                        dtvalue = dtnow.setMinutes(0);
                        dtvalue = dtnow.setSeconds(0);
                        timeslots.push({label:dtlabel+":00"+"PM", value: dtvalue})
                        dtvalue = dtnow.setMinutes(30);
                        timeslots.push({label:dtlabel+":30"+"PM", value: dtvalue})
                    }
                });
                console.info(timeslots);

                $( "#eventstarttime" ).autocomplete({
                    minLength: 0,
                    source: timeslots,
                    focus: function( event, ui ) {
                        $("#eventstarttime").attr('value', ui.item.label);
                        return false;
                    },
                    select: function( event, ui ) {
                        $("#eventstarttime").attr('value', ui.item.label);
                        $("#startTime").attr('value', ui.item.value);
                        return false;
                    },
                    change: function(event, ui){
                    }
                })
                $( "#eventendtime" ).autocomplete({
                    minLength: 0,
                    source: timeslots,
                    focus: function( event, ui ) {
                        $("#eventendtime").attr('value', ui.item.label);
                        return false;
                    },
                    select: function( event, ui ) {
                        $("#eventendtime").attr('value', ui.item.label);
                        $("#endTime").attr('value', ui.item.value);
                        return false;
                    }
                })
                $('#eventInvitees').autocomplete({
                      source: '/auto/users',
                      minLength: 2,
                      select: function( event, ui ) {
                        $('#invitees').append($$.events.formatUser(ui.item.value, ui.item.uid))
                        var rcpts = $('#inviteeList').val().trim();
                        rcpts = (rcpts == "") ? ui.item.uid: rcpts+","+ui.item.uid
                        $('#inviteeList').val(rcpts)
                        this.value = ""
                        return false;
                      }
                 });
                """
        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "event"},
                                handlers={"onload": onload})


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
        startDate = utils.getRequestArg(request, 'startDate')
        startTime = utils.getRequestArg(request, 'startTime')
        endDate = utils.getRequestArg(request, 'endDate') or startDate
        endTime = utils.getRequestArg(request, 'endTime') #or all day event
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')
        invitees = utils.getRequestArg(request, "invitees")
        invitees = invitees.split(',') if invitees else None

        if not ((title or desc) and startTime and startDate):
            raise errors.InvalidRequest()

        #TODO
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

        convId = utils.getUniqueKey()
        item, attachments = yield utils.createNewItem(request, self.itemType)

        options = dict([('yes', '0'), ('maybe', '0'), ('no', '0')])
        meta = {"startTime": str(calendar.timegm(startDateTime.utctimetuple()))}
        if title:
            meta["title"] = title
        if desc:
            meta["desc"] = desc
        if endTime:
            meta["endTime"] = str(calendar.timegm(endDateTime.utctimetuple()))
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
