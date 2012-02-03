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
        <div class="right-contents"></div>
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
    <div id="title"> <span class = "middle title">${_("Events")}</span> ${start} -- ${end}</div>
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
    <textarea type="text" name="title" placeholder="${_('Title of your event?')}" required=""></textarea>
  </div>
  <div>
    <div style="display:inline-block;width:16em">
      <div class="input-wrap">
        <input type="text" id="eventstartdate"/>
        <input type="hidden" name="startDate" id="startDate" required=""/>
      </div>
    </div>
    <span><strong>to</strong></span>
    <div style="display:inline-block;width:16em">
      <div class="input-wrap">
        <input type="text" id="eventenddate"/>
        <input type="hidden" id="endDate" name="endDate" required=""/>
      </div>
    </div>
    <div style="display:inline-block">
      ${timezone(me['basic']['timezone'])}
    </div>
    <div style="display:inline-block;float:right">
        <input type="checkbox" name="allDay" id="allDay"/>
        <label for="allDay">${_("All Day")}</label>
    </div>
  </div>
  <div class="input-wrap">
    <textarea type="text" name="location" placeholder="${_('Where is the event being hosted?')}"></textarea>
  </div>
  <div class="input-wrap">
      <textarea name="desc" placeholder="${_('Write something about your event')}"></textarea>
  </div>
  <div class="input-wrap">
    <input type="text" id="event-invitee" name="invitee[]"
           placeholder="${_('Invite people to this event')}"/>
  </div>
  <input type="hidden" name="type" value="event"/>
</%def>

<%def name="event_root(convId, isQuoted=False)">
  <%
    response = my_response[convId]
    conv = items[convId]
    convMeta = conv["meta"]
    title = convMeta.get("event_title", '')
    location = convMeta.get("event_location", '')
    desc = convMeta.get("event_desc", "")
    start = convMeta.get("event_startTime")
    end   = convMeta.get("event_endTime")
    owner = convMeta["owner"]
    ownerName = entities[owner]["basic"]["name"]

    my_tz = timezone(me['basic']['timezone'])
    owner_tz = timezone(entities[owner]['basic']['timezone'])
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

    #If start and end on the same day then don't show end date
    today = datetime.datetime.now().replace(tzinfo=my_tz)
    startrdelta = relativedelta(startdatetime, today)
    startsToday = False
    endsToday = False
    allDay = True if convMeta.get("allDay", "0") == "1" else False

    if not allDay:
      event_start_fmt = "%a %b %d, %I:%M %p"
    else:
      event_start_fmt = "%a %b %d"
    event_start = start_dt.strftime(event_start_fmt)

    endrdelta = relativedelta(start_dt, end_dt)
    if not allDay:
      event_end_fmt = "%a %b %d, %I:%M %p"
    else:
      event_end_fmt = "%a %b %d"
    event_end = end_dt.strftime(event_end_fmt)
    normalize = utils.normalizeText

    target = convMeta.get('target', '')
    target = target.split(',') if target else ''
    richText = convMeta.get('richText', 'False') == 'True'
    if target:
      target = [x for x in target if x in relations.groups]

  %>
  <div class="conv-reason">
    %if not target:
      ${utils.userName(owner, entities[owner], "conv-user-cause")}
    %else:
      ${utils.userName(owner, entities[owner], "conv-user-cause")}  &#9656; ${utils.groupName(target[0], entities[target[0]])}
    %endif
  </div>
  <div class="item-title has-icon">
    <span class="event-date-icon">
      <div>
        <div class="event-date-month">${start_dt.strftime("%b")}</div>
        <div class="event-date-day">${start_dt.strftime("%d")}</div>
        <div class="event-date-year"></div>
      </div>
    </span>

    <div class="item-title-text event-title-text">
      <span>${title}</span>
    </div>

    <div class="event-contents">
      %if not allDay:
        % if startsToday:
          <span class="event-duration-text">${_("today from")} ${event_start}</span>
        % else:
          <span class="event-duration-text">${_("")} ${event_start}</span>
        % endif
        % if endsToday:
          <span class="event-duration-text">to ${event_end}</span>
        % else:
          <span class="event-duration-text">-- ${event_end}</span>
        % endif
      %else:
        % if startsToday:
          <span class="event-duration-text">${_("")} ${event_start}</span>
        % else:
          <span class="event-duration-text">${_("")} ${event_start}</span>
        % endif
        % if endsToday:
          <span class="event-duration-text">${_("All Day")}</span>
        % else:
          <span class="event-duration-text">-- ${event_end}</span>
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
          <span id="event-rsvp-status-${convId}">${_("You have not responded to this event")}</span>
        %endif
        <button class="button-link" onclick="$$.ui.showPopup(event)">${_("RSVP to this event")}</button>
        <ul class="acl-menu" style="display:none;">
            <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'yes')">${_("Yes, I will attend")}</a></li>
            <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'no')">${_("No")}</a></li>
            <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'maybe')">${_("Maybe")}</a></li>
        </ul>
        ##<a class="ajax" onclick="$$.events.showEventInvitees('${convId}')">${len(invited_status[convId].keys())}</a>
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

<%def name="event_me()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("About this event")}</div>
    <div class="conversation-people-add-wrapper">
      <ul class="v-links">
        %if myId != items[convId]["meta"]["owner"] and myId in invited_status[convId]:
          <%
            invited_by = invited_status[convId][myId]
          %>
          <li>
            <span>${entities[invited_by]["basic"]["name"]}</span>&nbsp;<span>${_("invited you to this event")} &nbsp; </span>
          </li>
        %endif
        <li>
          <span>${start_dt.strftime("%b %d, %H:%M")} - ${end_dt.strftime("%b %d, %H:%M %Z")}</span>
        </li>
        <li>
          <span>${owner_start_dt.strftime("%b %d, %H:%M")} - ${owner_end_dt.strftime("%b %d, %H:%M %Z")}</span>
        </li>
      </ul>
    </div>
  </div>
</%def>

<%def name="event_actions()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Invite Someone")}</div>
    <div class="conversation-people-add-wrapper">
      <form class="ajax" action="/event/invite">
        <input type="hidden" name="id" value="${convId}" />
        <div class="input-wrap">
              <input type="text" id="event-invitee" name="invitee[]"
                placeholder="${_('Invite someone')}"/>
        </div>
        <button type="submit" style="display:none"></button>
      </form>
    </div>
  </div>
</%def>

<%def name="event_meta()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Who are attending")}</div>
    %if yes_people[convId]:
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in yes_people[convId]:
            <li>
              %if u in invited_status[convId].keys():
                <strong>
                  ${utils.userName(u, entities[u])}
                </strong>
              %else:
                ${utils.userName(u, entities[u])}
              %endif
            </li>
          %endfor
        </ul>
      </div>
      %if len(yes_people[convId]) > 4:
        <div style="float:right; margin-right:10px"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'yes')">and ${len(yes_people[convId]) - 4} more</a></div>
      %endif
    %else:
      <p> No one has accepted your invite yet!</p>
    %endif
  </div>
  %if maybe_people[convId]:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who may attend")}</div>
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in maybe_people[convId]:
            <li>
              %if u in invited_status[convId].keys():
                <strong>
                  ${utils.userName(u, entities[u])}
                </strong>
              %else:
                ${utils.userName(u, entities[u])}
              %endif
            </li>
          %endfor
        </ul>
      </div>
      %if len(maybe_people[convId]) > 4:
        <div style="float:right; margin-right:10px"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'maybe')">and ${len(maybe_people[convId]) - 4} more</a></div>
      %endif
    </div>
  %endif
  %if no_people[convId]:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who are not attending")}</div>
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in no_people[convId]:
            <li>
              %if u in invited_status[convId].keys():
                <strong>
                  ${utils.userName(u, entities[u])}
                </strong>
              %else:
                ${utils.userName(u, entities[u])}
              %endif
            </li>
          %endfor
        </ul>
      </div>
      %if len(no_people[convId]) > 4:
        <div style="float:right; margin-right:10px;"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'no')">and ${len(no_people[convId]) - 4} more</a></div>
      %endif
    </div>
  %endif
</%def>

<%def name="quick_agenda()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("My Upcoming Agenda")}</div>
    <ul class="v-links">
      <% print items %>
      %for convId in conversations:
        <li>
          <a href="/item?id=${convId}">${items[convId]['meta']['event_title']}</a>
        </li>
      %endfor
    </ul>
  </div>
</%def>

<%def name="company_agenda()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Upcoming Events")}</div>
    <ul class="v-links">
      %for convId in conversations:
        <li>
          <a href="/item?id=${convId}">${items[convId]['meta']['event_title']}</a>
        </li>
      %endfor
    </ul>
  </div>
</%def>

<%def name="group_agenda()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Group Agenda")}</div>
    <ul class="v-links">
      %for convId in conversations:
        <li>
          <a href="/item?id=${convId}">${items[convId]['meta']['event_title']}</a>
        </li>
      %endfor
    </ul>
  </div>
</%def>
