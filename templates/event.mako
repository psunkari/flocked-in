<%! from social import utils, _, __, constants %>
<!DOCTYPE HTML>

<%! import pytz, datetime, calendar %>
<%! from pytz import timezone %>
<%! from dateutil.relativedelta import relativedelta, weekday, MO, TU, WE, TH, \
                                        FR, SA, SU
%>
<%! from dateutil.rrule import rrule, rruleset, rrulestr, \
                                YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, \
                                MINUTELY, SECONDLY, MO, TU, WE, TH, FR, SA, SU
%>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%inherit file="base.mako"/>


<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
      </div>
      <div id="center">
        <div class="">
          <div id= "events">
            ${self.events()}
          </div>
        </div>
        <div >
          <div id="invitations">
            ${self.invitations()}
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="events()">
  %if conversations:
    <div id="title"> <span class = "middle title">${_("Events")}</span> </div>
    %for convId in conversations:
      ${item.item_layout(convId)}
    %endfor
  %endif
</%def>

<%def name="invitations()">
 %if inviItems:
    <div id="title"> <span class = "middle title">${_("Invitations")}</span> </div>
    %for convId in inviItems:
      ${item.item_layout(convId)}
    %endfor
  %endif
</%def>

<%def name="share_event()">
  <div class="input-wrap">
    <input type="text" name="title" placeholder="${_('Title of your event?')}"/>
  </div>
  <div>
    <div style="display:inline-block;width:8em">
      <div class="input-wrap">
        <input type="text" id="eventstartdate"/>
        <input type="hidden" name="startDate" id="startDate"/>
      </div>
    </div>
    <div style="display:inline-block;width:8em;border:1px solid #C3D9FF" id="startTimeWrapper" class="styledform">
      <!--<div class="input-wrap">-->
        <!--<input type="text" id="eventstarttime"/>-->
        ${self.selectTime("startTime", "Start Time",)}

      <!--</div>-->
    </div>
    <span> to </span>
    <div style="display:inline-block;width:8em;border:1px solid #C3D9FF" id="endTimeWrapper" class="styledform">
      <!--<div class="input-wrap">-->
        <!--<input type="text" id="eventendtime"/>-->
        ${self.selectTime("endTime", "End Time",)}

      <!--</div>-->
    </div>
    <div style="display:inline-block;width:8em">
      <div class="input-wrap">
        <input type="text" id="eventenddate"/>
        <input type="hidden" id="endDate" name="endDate"/>
      </div>
    </div>
    <div style="display:inline-block">
      ${timezone(me['basic']['timezone'])}
    </div>
    <div style="display:inline-block;float:right">
      <!--<div class="input-wrap">-->
        <input type="checkbox" name="allDay" id="allDay"/><label for="allDay">${_("All Day")}</label>
      <!--</div>-->
    </div>
  </div>
  <div class="input-wrap">
    <input type="text" name="location" placeholder="${_('Where is the event being hosted?')}"/>
  </div>
  <div class="input-wrap">
      <textarea name="desc" placeholder="${_('Write something about your event')}"></textarea>
  </div>
  <div class="input-wrap">
    <div style="float:left" id="invitees" name="invitees"></div>
    <div>To invite a specific group of people or groups, select the custom option from the Audience option below</div>
  </div>
  <input type="hidden" name="type" value="event"/>
</%def>

<%def name="event_root(convId, isQuoted=False)">
  <%
    conv = items[convId]
    title = items[convId]["meta"].get("event_title", '')
    location = items[convId]["meta"].get("event_location", '')
    desc = items[convId]["meta"].get("desc", "")
    start = items[convId]["meta"].get("event_startTime")
    end   = items[convId]["meta"].get("event_endTime", '')

    options = items[convId]["rsvp"] or ["yes", "maybe", "no"]
    owner = items[convId]["meta"]["owner"]
    ownerName = entities[owner]["basic"]["name"]
    my_tz = timezone(me['basic']['timezone'])
    if "invitees" in context.kwargs:
      invited = invitees[convId]
    else:
      invited = []
    response = myResponse[convId] if "myResponse" in context.kwargs else ""

    utc = pytz.utc
    startdatetime = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
    enddatetime = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)

    utc_dt = utc.normalize(startdatetime)
    start_dt = my_tz.normalize(startdatetime.astimezone(my_tz))
    end_dt = my_tz.normalize(enddatetime.astimezone(my_tz))

    #If start and end on the same day then don't show end date
    today = datetime.datetime.now().replace(tzinfo=my_tz)
    startrdelta = relativedelta(startdatetime, today)
    startsToday = False
    endsToday = False
    allDay = True if items[convId]["meta"].get("allDay", "0") == "1" else False

    if startrdelta.days == 0:
      if not allDay:
        event_start_fmt = "%I:%M %p"
      else:
        event_start_fmt = ""
      startsToday = True
    else:
      if not allDay:
        event_start_fmt = "%a %b %d, %I:%M %p"
      else:
        event_start_fmt = "%a %b %d"
    event_start = start_dt.strftime(event_start_fmt)

    endrdelta = relativedelta(start_dt, end_dt)
    if endrdelta.days == 0:
      if not allDay:
        event_end_fmt = "%I:%M %p"
      else:
        event_end_fmt = ""
      endsToday = True
    else:
      if not allDay:
        event_end_fmt = "%a %b %d, %I:%M %p"
      else:
        event_end_fmt = "%a %b %d"
    event_end = end_dt.strftime(event_end_fmt)
    normalize = utils.normalizeText
  %>
  <div class="">
    <span class="conv-reason">
      %if myKey == owner:
        <span class="item">
          <a href="/item?id=${convId}">${title} </a>
        </span>
      %else:
        <span class="item">
          <a href="/item?id=${convId}">${title} </a>
        </span>
        <span class=""> -- ${_("Invitation from")}</span>
        <span class="user">
          <a class='ajax' href='/profile?id=${owner}'>${ownerName}</a>
        </span>
      %endif
    </span>
    <div class="item-title has-icon">
      <span class="event-date-icon">
        <div>
          <div class="event-date-month">${start_dt.strftime("%b")}</div>
          <div class="event-date-day">${start_dt.strftime("%d")}</div>
          <div class="event-date-year"></div>
        </div>
      </span>
      <div class="item-contents has-icon event-contents">
        %if not allDay:
          % if startsToday:
            <span>${_("Event starts today from")} ${event_start}</span>
          % else:
            <span>${_("Event starts on")} ${event_start}</span>
          % endif
          % if endsToday:
            <span>to ${event_end}</span>
          % else:
            <span>untill ${event_end}</span>
          % endif
        %else:
          % if startsToday:
            <span>${_("Event starts today")} ${event_start}</span>
          % else:
            <span>${_("Event starts on")} ${event_start}</span>
          % endif
          % if endsToday:
            <span>for the entire day</span>
          % else:
            <span>untill ${event_end}</span>
          % endif
        %endif
        <div class="event-description">${desc|normalize}</div>
        %if location.strip() != "":
          <div><b>Venue</b> ${location}</div>
        %endif
        <div class="item-subactions">
          % if response == "yes":
            <span id="event-rsvp-status-${convId}">${_("You are attending")}</span>
          % elif response == "no":
            <span id="event-rsvp-status-${convId}">${_("You are not attending")}</span>
          % elif response == "maybe":
            <span id="event-rsvp-status-${convId}">${_("You may attend")}</span>
          %else:
            <span id="event-rsvp-status-${convId}">&nbsp;</span>
          %endif
          <button class="button-link" onclick="$$.ui.showPopup(event)">${_("RSVP to this event")}</button>
          <ul class="acl-menu" style="display:none;">
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'yes')">${_("Yes, I will attend")}</a></li>
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'no')">${_("No")}</a></li>
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'maybe')">${_("Maybe")}</a></li>
          </ul>
          <a class="ajax" onclick="$$.events.showEventInvitees('${convId}')">${len(invited)}</a>
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="update_rsvp(response, convId)">
  % if response == "yes":
    <span id="event-rsvp-status-${convId}">${_("You are attending")}</span>
  % elif response == "no":
    <span id="event-rsvp-status-${convId}">${_("You are not attending")}</span>
  % elif response == "maybe":
    <span id="event-rsvp-status-${convId}">${_("You may attend")}</span>
  %endif
</%def>

<%def name="selectTime(name, label)">
  <select id="${name}" name="${name}" class="inline-select" style="border:none;width:100% !important">
    <option value="">${label}</option>
      <%
        TODAY = datetime.date.today()
        TOMORROW = TODAY+relativedelta(days=+1)
        my_tz = timezone(me['basic']['timezone'])
        NOW = datetime.datetime.now(my_tz)
        dts = list(rrule(MINUTELY, dtstart=TODAY, interval=30, until=TOMORROW))
        dtslabels = [a.strftime('%I:%M %p') for a in dts]
        dtsvalues = [str(calendar.timegm(a.utctimetuple())) for a in dts]
      %>
      %for i in range(len(dts)):
        <%
          #
          #
          selected = False
          h = relativedelta(my_tz.normalize(dts[i].replace(tzinfo=my_tz)),NOW).hours
          if h == 0:
            m = relativedelta(my_tz.normalize(dts[i].replace(tzinfo=my_tz)),NOW).minutes
            if m:
              selected = True
            else:
              selected = False
        %>
        %if selected:
          <option selected value="${dtsvalues[i]}000">${dtslabels[i]}</option>
        %else:
          <option value="${dtsvalues[i]}000">${dtslabels[i]}</option>
        %endif
      %endfor
  </select>
  <input type="hidden" id="time${name}" value="${dtsvalues[0]}000"/>
</%def>
