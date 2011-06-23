<%! from social import utils, _, __, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! import pytz, datetime %>
<%! from pytz import timezone %>
<%! from dateutil.relativedelta import relativedelta %>
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
    <div id="title"> <span class = "middle title"> Events </span> </div>
    %for convId in conversations:
      ${item.item_layout(convId)}
    %endfor
  %endif
</%def>

<%def name="invitations()">
 %if inviItems:
    <div id="title"> <span class = "middle title"> Invitations </span> </div>
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
    <div style="display:inline-block;width:10em">
      <div class="input-wrap">
        <input type="text" id="eventstartdate"/>
        <input type="hidden" name="startDate" id="startDate"/>
      </div>
    </div>
    <div style="display:inline-block;width:10em" id="startTimeWrapper">
      <div class="input-wrap">
        <input type="text" id="eventstarttime"/>
        <input type="hidden" name="startTime" id="startTime"/>
      </div>
    </div>
    <span> to </span>
    <div style="display:inline-block;width:10em" id="endTimeWrapper">
      <div class="input-wrap">
        <input type="text" id="eventendtime"/>
        <input type="hidden" id="endTime" name="endTime"/>
      </div>
    </div>
    <div style="display:inline-block;width:10em">
      <div class="input-wrap">
        <input type="text" id="eventenddate"/>
        <input type="hidden" id="endDate" name="endDate"/>
      </div>
    </div>
    <div style="display:inline-block;float:right">
      <!--<div class="input-wrap">-->
        <input type="checkbox" name="allDay" id="allDay" onchange="$('#startTimeWrapper, #endTimeWrapper').toggle()"/><label for="allDay">All Day</label>
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
    <input name="invitees" id="inviteeList" type="hidden"/>
    <div>
      <input type="text" id="eventInvitees" placeholder="${_('List of Invitees')}"/>
    </div>
  </div>
  <input type="hidden" name="type" value="event"/>
</%def>

<%def name="event_root(convId, isQuoted=False)">
  <%
    conv = items[convId]
    title = items[convId]["meta"].get("title", '')
    location = items[convId]["meta"].get("location", '')
    desc = items[convId]["meta"].get("desc", "")
    start = items[convId]["meta"].get("startTime")
    end   = items[convId]["meta"].get("endTime", '')
    options = items[convId]["options"] or ["yes", "maybe", "no"]
    #response = myResponse[convId] if convId in myResponse else False
    owner = items[convId]["meta"]["owner"]
    ownerName = entities[owner]["basic"]["name"]
    my_tz = timezone(entities[owner]["basic"]["timezone"])
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
    if startrdelta.days == 0:
      event_start_fmt = "%I:%M %p"
      startsToday = True
    else:
      event_start_fmt = "%a %b %d, %I:%M %p"
    event_start = start_dt.strftime(event_start_fmt)

    endrdelta = relativedelta(start_dt, end_dt)
    if endrdelta.days == 0:
      event_end_fmt = "%I:%M %p"
      endsToday = True
    else:
      event_end_fmt = "%a %b %d, %I:%M %p"
    event_end = end_dt.strftime(event_end_fmt)
  %>
  <div class="conv-item">
    <span>
      <a class='ajax' href='/profile?id=${owner}'>${ownerName}</a> has invited you to <a href="/item?id=${convId}">${title} </a>
    </span>
    <div class="item-title has-icon">
      <span class="event-date-icon button">
        <div>
          <div class="event-date-month">${start_dt.strftime("%b")}</div>
          <div class="event-date-day">${start_dt.strftime("%d")}</div>
          <div class="event-date-year"></div>
        </div>
      </span>
      <div class="item-title-text" style="margin-top:10px;">
        <div style="display:inline-block;padding-left:8px">
          <div>${desc}</div>
          <div>Venue: ${location}</div>
          % if startsToday:
            <span>Event starts today from ${event_start}</span>
          % else:
            <span>Event starts on ${event_start}</span>
          % endif
          % if endsToday:
            <span>to ${event_end}</span>
          % else:
            <span>till ${event_end}</span>
          % endif
        </div>
      </div>
    </div>
  </div>
<!--      <form action="/event/rsvp" method="POST" class="ajax">
          % for option in options:
            <% checked = "checked" if response and response == option else "" %>
            % if checked:
              <input type="radio" name="response" checked="${checked}" value="${option}">${option}</input>
            % else:
              <input type="radio" name="response" value= "${option}">${option}</input>
            %endif
          % endfor
          <input type="hidden" name="id" value="${convId}" />
          <input type="hidden" name="type" value="event" />
          <input type="submit" id="submit" value="${_('RSVP')}" class="button"/>
      </form>-->

<!--    <div >
      <form action="/event/invite"  method=POST class="ajax">
        <label for="invitees"> Invite </label>
        <input type="text" name="invitees" placeholder="${_('List of Invitees')}"/>
        <input type="hidden" name="id" value= "${convId}" />
        <input type="submit" id="submit" value="${_('Invite')}"/>
      </form>
    </div>
-->
</%def>
