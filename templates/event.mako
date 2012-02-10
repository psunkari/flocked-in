<%! from social import utils, _, __, constants %>
<%! import pytz, datetime, time %>
<%! from pytz import timezone %>
<%! from dateutil.relativedelta import relativedelta, weekday, MO, TU, WE, TH, \
                                        FR, SA, SU
%>
<%! from dateutil.rrule import rrule, rruleset, rrulestr, \
                                YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, \
                                MINUTELY, SECONDLY, MO, TU, WE, TH, FR, SA, SU
%>
<!DOCTYPE HTML>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
          <%self.nav_menu()%>
      </div>
    </div>
    <div id="center-right">
      <div class="titlebar center-header">
        <span class="middle title">Events</span>
      </div>
      <div id="right">
        <div class="right-contents"></div>
      </div>
      <div id="center">
            %if not script:
                <%self.render_events()%>
            %endif
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="event_layout(convId, classes='')">
  <div id="conv-${convId}" class="conv-item ${classes}">
      <%
        convMeta = items[convId]['meta']
        utc = pytz.utc
        start = convMeta.get("event_startTime")
        end = convMeta.get("event_endTime")
        start = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
        end = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)
        now = datetime.datetime.utcfromtimestamp(time.time()).replace(tzinfo=utc)
        present = now <= end #This event is either in progress or has not started yet.
        iamOwner = myId == items[convId]["meta"]["owner"]

      %>
    ##<div class="conv-data">
      <%
        convType = convMeta["type"]
        convOwner = convMeta["owner"]
      %>
      <div id="conv-root-${convId}" class="conv-root">
        <div class="conv-summary">
          <%self.conv_root(convId, hasReason)%>
        </div>
      </div>
    ##</div>
    <div class="event-details">
      <div class="event-people-attending">
        <%
          reason = ""
          if myId in yes_people[convId]:
              if len(yes_people[convId]) == 2:
                  other_person_id = list(set(yes_people[convId]) - set([myId]))[0]
                  if present:
                    reason = _("You and %s are attending this event") % (utils.userName(other_person_id, entities[other_person_id]))
                  else:
                    reason = _("You and %s went to this event") % (utils.userName(other_person_id, entities[other_person_id]))
              elif len(yes_people[convId]) > 2:
                  if present:
                    reason = _("You and %d others are attending this event") % (len(yes_people[convId]) - 1)
                  else:
                    reason = _("You and %d others went to this event") % (len(yes_people[convId]) - 1)
              else:
                  if present:
                    reason = _("You are attending this event")
                  else:
                    reason = _("You went to this event")
          else:
              if present:
                  if len(yes_people[convId]) == 1:
                    reason = "%s is attending" % (utils.userName(yes_people[convId][0],
                                                  entities[yes_people[convId][0]]))
                  elif len(yes_people[convId]) == 2:
                    reason = "%s and %s are attending" % (utils.userName(yes_people[convId][0], entities[yes_people[convId][0]]),
                                                        utils.userName(yes_people[convId][1], entities[yes_people[convId][1]]))
                  elif len(yes_people[convId]) == 3:
                    reason = "%s, %s and %s are attending" % (utils.userName(yes_people[convId][0], entities[yes_people[convId][0]]),
                                                        utils.userName(yes_people[convId][1], entities[yes_people[convId][1]]),
                                                        utils.userName(yes_people[convId][2], entities[yes_people[convId][2]]))
                  elif len(yes_people[convId]) > 3:
                    reason = "%s, %s and %d others are attending" % (utils.userName(yes_people[convId][0], entities[yes_people[convId][0]]),
                                                        utils.userName(yes_people[convId][1], entities[yes_people[convId][1]]),
                                                        len(yes_people[convId]) - 3)
              else:
                  if len(yes_people[convId]) > 1:
                    reason = "%d people went to this event" % (len(yes_people[convId]))
                  else:
                    reason = ""
        %>
        ${reason}
      </div>
      <div class="event-who-invited">
        <%
          reason = ""
          if not iamOwner:
            if myId in invited_people[convId]:
                invited_by = invited_people[convId][myId]
                reason = _("%s invited you to this event") % (utils.userName(invited_by, entities[invited_by]))
            else:
                if len(invited_people[convId]) > 1:
                    reason = _("You invited %d people to this event") % (len(invited_people[convId]) - 1)
                else:
                    reason = _("You have not invited anyone to this event")
          else:
              target = convMeta.get("target", None)
              if target:
                  groupId = target.split(',')[0]
                  reason = _("Anyone in %s can attend this event") % (utils.groupName(groupId, entities[groupId]))
              else:pass
        %>
        <span>${reason}</span>
      </div>
      <div class="event-join-decline">
        %if present:
          %if my_response[convId] != "yes":
            <button class="button-link" onclick="$$.events.RSVP('${convId}', 'yes')">${_("Join")}</button>&nbsp;&#183;
            <button class="button-link" onclick="$$.events.RSVP('${convId}', 'no')">${_("Decline")}</button>
          %endif
        %else:
            <span>${_("This event has passed")}</span>
        %endif
      </div>
    </div>
    <div class="clear"></div>
  </div>
</%def>

<%def name="conv_root(convId, isQuoted=False)">
  <%self.event_root(convId, isQuoted, context.kwargs)%>
</%def>

<%def name="render_events()">
  <div class="center-contents">
    <div class="viewbar">
      <%print entityId%>
      %if entityId == myId:
        <ul class="h-links view-options">
          %for item, display in [('agenda', _('Agenda')), ('invitations', _('Invitations'))]:
            %if view == item:
              <li class="selected">${_(display)}</li>
            %else:
              <li><a href="/event?view=${item}" class="ajax">${_(display)}</a></li>
            %endif
          %endfor
        </ul>
      %else:
        <ul class="h-links view-options">
          <li class="selected">${_("Agenda")}</li>
        </ul>
      %endif
    </div>
    <div class="paged-container" id="events-container">
      <%events()%>
      <div id="next-page-loader">
        %if nextPage:
          <div id="next-load-wrapper" class="busy-indicator">
            <a id="next-page-load" class="ajax" data-ref="/event?page=${nextPage}">${_("Fetch more events")}</a>
          </div>
        %endif
      </div>
    </div>
  </div>
</%def>

<%def name="events()">
    %if conversations:
      %for convId in conversations:
        <%event_layout(convId, "concise")%>
      %endfor
    %endif
</%def>

<%def name="share_event()">
  <div class="input-wrap">
    <textarea type="text" name="title" placeholder="${_('Title of your event?')}" required=""></textarea>
  </div>
  <div>
    <div style="display:inline-block;width:12em">
      <div class="input-wrap">
        <input type="text" id="startdate"/>
        <input type="hidden" name="startDate" id="startDate" required=""/>
      </div>
    </div>
    <div style="display:inline-block;width:9em" class="time-picker">
      <div class="input-wrap">
            <select id="starttime">
                <%
                    my_tz = timezone(me["basic"]["timezone"])
                    utc_now = datetime.datetime.now(pytz.utc)
                    mytz_now = utc_now.astimezone(my_tz)
                    hoursNow = mytz_now.hour
                %>
                %for slot in range(0, 48):
                    <%
                        seconds = 1800 * slot
                        ampm = "PM" if slot > 24 else "AM"
                        hours = "%02d" % ((slot/2) % 12)
                        minutes = "30" if (slot % 2) else "00"
                        if hoursNow == (slot/2) and minutes != "30":
                            selected=True
                        else:
                            selected=False
                    %>
                    <option value="${seconds}" ${'selected' if selected else ''}>${hours}:${minutes} ${ampm}</option>
                %endfor
            </select>
        <input type="hidden" name="startTime" id="startTime" required=""/>
        ##<button class="event-time-button" type='button' onclick="$$.events.showTimePicker('starttime')">&#9650;</button>
      </div>
    </div>
    <span><strong>to</strong></span>
    <div style="display:inline-block;width:9em" class="time-picker">
      <div class="input-wrap">
            <select id="endtime">
                <%
                    my_tz = timezone(me["basic"]["timezone"])
                    utc_now = datetime.datetime.now(pytz.utc)
                    mytz_now = utc_now.astimezone(my_tz)
                    if mytz_now.hour < 23:
                        hoursNow = mytz_now.hour + 1
                    else:
                        hoursNow = 0
                %>
                %for slot in range(0, 48):
                    <%
                        seconds = 1800 * slot
                        ampm = "PM" if slot > 24 else "AM"
                        hours = "%02d" % ((slot/2) % 12)
                        minutes = "30" if (slot % 2) else "00"
                        if hoursNow == (slot/2) and minutes != "30":
                            selected=True
                        else:
                            selected=False
                    %>
                    <option value="${seconds}" ${'selected' if selected else ''}>${hours}:${minutes} ${ampm}</option>
                %endfor
            </select>
        <input type="hidden" id="endTime" name="endTime" required=""/>
        ##<button class="event-time-button" type='button' onclick="$$.events.showTimePicker('endtime')">&#9650;</button>
      </div>
    </div>
    <div style="display:inline-block;width:12em">
      <div class="input-wrap">
        <input type="text" id="enddate"/>
        <input type="hidden" id="endDate" name="endDate" required=""/>
      </div>
    </div>
    <div style="display:inline-block">
      ##${timezone(me['basic']['timezone'])}
    </div>
    <div style="display:inline-block;float:right;padding: 4px 0px">
        <input type="checkbox" name="allDay" id="allDay" style="vertical-align: middle"/>
        <label for="allDay">${_("All day")}</label>
    </div>
  </div>
  <div style="margin-bottom: 4px">
    <div class="alert-info" style="padding: 4px;text-align: center">Your timezone is not in order</div>
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

<%def name="event_root(convId, isQuoted=False, isConcise=False)">
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

    # Determine if start date and end date are on the same day
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

    normalize = utils.normalizeText
    richText = convMeta.get('richText', 'False') == 'True'
    short_desc = desc.split("\n").pop()

    target = convMeta.get('target')
    if target:
      target = target.split(',')
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
      <a href="/item?id=${convId}">${title}</a>
      ##<span>${start_dt}</span>
    </div>

    <div class="event-contents">
      %if not allDay:
        <span class="event-duration-text">${event_start}</span>
        % if sameDay:
          <span class="event-duration-text">to ${event_end}</span>
        % else:
          <span class="event-duration-text">-- ${event_end}</span>
        % endif
      %else:
        <span class="event-duration-text">${event_start}</span>
        % if sameDay:
          <span class="event-duration-text">${_("All Day")}</span>
        % else:
          <span class="event-duration-text">-- ${event_end}</span>
        % endif
      %endif
      <div class="event-description">${desc|normalize}</div>
      %if location.strip() != "" and not isConcise:
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
      </div>
    </div>
  </div>
</%def>

<%def name="event_me()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("About this event")}</div>
    <div class="conversation-people-add-wrapper">
      <ul class="v-links">
        %if myId != items[convId]["meta"]["owner"] and myId in invited_people[convId]:
          <%
            invited_by = invited_people[convId][myId]
          %>
          <li>
            <span>${entities[invited_by]["basic"]["name"]}</span>&nbsp;<span>${_("invited you to this event")} &nbsp; </span>
          </li>
        %endif
        <li>
            <%
                delta = eventDueIn(items, convId, True)
                if delta == 0:
                    reason = _("This event has already started")
                elif delta == -1:
                    reason = _("This event has passed")
                else:
                    if delta.days:
                        eventDueInStr = "%s days" %delta.days
                    elif delta.hours:
                        eventDueInStr = "%s hours" %delta.hours
                    elif delta.minutes:
                        eventDueInStr = "%s minutes" %delta.minutes
                    else:
                        eventDueInStr = "a few moments"

                    reason = _("Event starts in %s") %(eventDueInStr)
            %>
          <span>${reason}</span>
        </li>
      </ul>
    </div>
  </div>
</%def>

<%def name="event_actions()">
  %if myId in invited_people[convId].keys():
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
  %endif
</%def>

<%def name="event_meta()">
  <%
    iamOwner = myId == items[convId]["meta"]["owner"]
  %>
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Who are attending (%d)") % (len(yes_people[convId]))}</div>
    %if yes_people[convId]:
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in yes_people[convId]:
            <li>
              %if u in invited_people[convId].keys():
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
  %if maybe_people[convId] and iamOwner:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who may attend (%d)") % (len(maybe_people[convId]))}</div>
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in maybe_people[convId]:
            <li>
              %if u in invited_people[convId].keys():
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
  %if no_people[convId] and iamOwner:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who are not attending (%d)") % (len(no_people[convId]))}</div>
      <div class="conversation-attachments-wrapper">
        <ul class="v-links peoplemenu">
          %for u in no_people[convId]:
            <li>
              %if u in invited_people[convId].keys():
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

<%def name="side_agenda()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${title}</div>
    <ul class="v-links" style="margin-right: 20px;">
      %for convId in conversations:
        <li>
          <a class="event-agenda-link${'-expired' if expired else ''}" href="/item?id=${convId}">${items[convId]['meta']['event_title']}</a>
          <span class="event-agenda-due-in">${eventDueIn(items, convId)}</span>
        </li>
      %endfor
    </ul>
  </div>
</%def>

<%!
  def eventDueIn(items, convId, deltaOnly=False):
    convMeta = items[convId]['meta']
    utc = pytz.utc
    expired, inProgress = False, False
    start = convMeta.get("event_startTime")
    end = convMeta.get("event_endTime")
    start = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
    end = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)
    now = datetime.datetime.utcfromtimestamp(time.time()).replace(tzinfo=utc)

    if now > end:
        expired = True
        eventDueInStr = "Over"
    elif now > start and now < end:
        inProgress = True
        eventDueInStr = "In progress"
    else:
      delta = relativedelta(start, now)

      if delta.days:
          eventDueInStr = "%sd" %delta.days
      elif delta.hours:
          eventDueInStr = "%sh" %delta.hours
      elif delta.minutes:
          eventDueInStr = "%sm" %delta.minutes
      else:
          eventDueInStr = "now"

    if deltaOnly:
        if expired:
            return -1
        elif inProgress:
            return 0
        else:
            return relativedelta(start, now)
    else:
        return eventDueInStr
%>
