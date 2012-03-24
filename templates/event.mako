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
<%namespace name="emails" file="emails.mako"/>

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
        <div class="center-contents">
            %if not script:
                <%self.render_events()%>
            %endif
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="event_layout(convId, isConcise)">
  <div id="conv-${convId}" class="conv-item">
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
      <%
        convType = convMeta["type"]
        convOwner = convMeta["owner"]
        if isConcise:
            convClass = "agenda-root"
        else:
            convClass = "conv-root"
      %>
      <div id="conv-root-${convId}" class="${convClass}">
        <div class="conv-summary">
          <%self.conv_root(convId, hasReason)%>
        </div>
      </div>
    <div class="event-details">
      <div class="event-people-attending">
        <%
          reason = ""
          if myId in yesPeople[convId]:
              if len(yesPeople[convId]) == 2:
                  other_person_id = list(set(yesPeople[convId]) - set([myId]))[0]
                  if present:
                    reason = _("You and %s are attending this event") % (utils.userName(other_person_id, entities[other_person_id]))
                  else:
                    reason = _("You and %s attended this event") % (utils.userName(other_person_id, entities[other_person_id]))
              elif len(yesPeople[convId]) > 2:
                  if present:
                    reason = _("You and %d others are attending this event") % (len(yesPeople[convId]) - 1)
                  else:
                    reason = _("You and %d others attended this event") % (len(yesPeople[convId]) - 1)
              else:
                  if present:
                    reason = _("You are attending this event")
                  else:
                    reason = _("You attended this event")
          else:
              if present:
                  if len(yesPeople[convId]) == 1:
                    reason = "%s is attending" % (utils.userName(yesPeople[convId][0],
                                                  entities[yesPeople[convId][0]]))
                  elif len(yesPeople[convId]) == 2:
                    reason = "%s and %s are attending" % (utils.userName(yesPeople[convId][0], entities[yesPeople[convId][0]]),
                                                        utils.userName(yesPeople[convId][1], entities[yesPeople[convId][1]]))
                  elif len(yesPeople[convId]) == 3:
                    reason = "%s, %s and %s are attending" % (utils.userName(yesPeople[convId][0], entities[yesPeople[convId][0]]),
                                                        utils.userName(yesPeople[convId][1], entities[yesPeople[convId][1]]),
                                                        utils.userName(yesPeople[convId][2], entities[yesPeople[convId][2]]))
                  elif len(yesPeople[convId]) > 3:
                    reason = "%s, %s and %d others are attending" % (utils.userName(yesPeople[convId][0], entities[yesPeople[convId][0]]),
                                                        utils.userName(yesPeople[convId][1], entities[yesPeople[convId][1]]),
                                                        len(yesPeople[convId]) - 3)
              else:
                  if len(yesPeople[convId]) > 1:
                    reason = "%d people attended this event" % (len(yesPeople[convId]))
                  else:
                    reason = ""
        %>
        ${reason}
      </div>
      <div class="event-who-invited">
        <%
          reason = ""
          if not iamOwner:
            if myId in invitedPeople[convId]:
                invited_by = invitedPeople[convId][myId]
                reason = _("%s invited you to this event") % (utils.userName(invited_by, entities[invited_by]))
            else:
                if len(invitedPeople[convId]) > 1:
                    reason = _("You invited %d people to this event") % (len(invitedPeople[convId]) - 1)
                else:
                    reason = _("You have not invited anyone to this event")
          else:
              target = convMeta.get("target", None)
              if target:
                  groupId = target.split(',')[0]
                  reason = _("Anyone in %s can attend this event") % (utils.groupName(groupId, entities[groupId]))
        %>
        <span>${reason}</span>
      </div>
      <div class="event-join-decline">
        %if present:
          %if myResponse[convId] != "yes":
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
  <div class="viewbar">
    <ul class="h-links view-options">
      %for item, display in [('agenda', _('Agenda')), ('invitations', _('Invitations'))]:
        %if view == item:
          <li class="selected">${_(display)}</li>
        %else:
          <li><a href="/event?view=${item}" class="ajax">${_(display)}</a></li>
        %endif
      %endfor
    </ul>
    <div class="input-wrap" id="agenda-start-wrapper">
      <input id="agenda-start" type="text" disabled/>
      <input type="hidden" id="agenda-start-date" />
      <input type="hidden" id="agenda-view" value="${view}" />
    </div>
  </div>
  <div class="paged-container" id="events-container">
    <%events()%>
  </div>
  <div class="pagingbar">
    <%paging()%>
  </div>
</%def>

<%def name="events()">
    %if conversations:
      %for convId in conversations:
        <%event_layout(convId, True)%>
      %endfor
    %else:
        <div id="empty-message" >${_("No Events")}</div>
    %endif
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPage:
      <li class="button">
        <a class="ajax" data-ref="/event?page=${prevPage}&view=${view}&start=${start}">${_("&#9666; Previous")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPage:
      <li class="button">
        <a class="ajax" data-ref="/event?page=${nextPage}&view=${view}&start=${start}">${_("Next &#9656;")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="share_event()">
  <div class="input-wrap">
    <textarea type="text" name="title" placeholder="${_('Title of your event?')}" required=""></textarea>
  </div>
  <div>
    <div class="date-picker-wrapper">
      <div class="input-wrap">
        <input type="text" id="startdate"/>
        <input type="hidden" name="startDate" id="startDate" required=""/>
      </div>
    </div>
    <div class="time-picker">
      <div class="input-wrap">
            <select id="starttime">
                <%
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
      </div>
    </div>
    <span><strong>to</strong></span>
    <div class="time-picker">
      <div class="input-wrap">
            <select id="endtime">
                <%
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
      </div>
    </div>
    <div class="date-picker-wrapper">
      <div class="input-wrap">
        <input type="text" id="enddate"/>
        <input type="hidden" id="endDate" name="endDate" required=""/>
      </div>
    </div>
    <div id="allDay-wrapper">
        <input type="checkbox" name="allDay" id="allDay"/>
        <label for="allDay">${_("All day")}</label>
    </div>
  </div>
  ##TODO:Yet to find a good way of determining the timezone differences between browser and profile
  ##<div style="margin-bottom: 4px">
    ##<div class="alert-info" style="padding: 4px;text-align: center">Your timezone is not in order</div>
  ##</div>
  <div class="input-wrap">
    <textarea type="text" name="location" placeholder="${_('Where is the event being hosted?')}"></textarea>
  </div>
  <div class="input-wrap">
      <textarea name="desc" placeholder="${_('Write something about your event')}"></textarea>
  </div>
  <div class="input-wrap">
    <input type="text" disabled="disabled" value="${_('Invite people')}"
           id="placeholder-hidden" style="position: absolute;top: -9999px;left: -9999px"/>
    <input type="text" id="event-invitee" name="invitee[]"
           placeholder="${_('Invite people')}"/>
  </div>
  <input type="hidden" name="type" value="event"/>
</%def>

<%def name="event_root(convId, isQuoted=False, isConcise=False)">
  <%
    response = myResponse[convId]
    conv = items[convId]
    convMeta = conv["meta"]
    title = convMeta.get("event_title", '')
    location = convMeta.get("event_location", '')
    desc = convMeta.get("event_desc", "")
    start = convMeta.get("event_startTime")
    end   = convMeta.get("event_endTime")
    owner = convMeta["owner"]
    ownerName = entities[owner].basic["name"]

    my_tz = timezone(me.basic['timezone'])
    owner_tz = timezone(entities[owner].basic['timezone'])
    utc = pytz.utc
    startdatetime = datetime.datetime.utcfromtimestamp(float(start)).replace(tzinfo=utc)
    enddatetime = datetime.datetime.utcfromtimestamp(float(end)).replace(tzinfo=utc)

    utc_dt = utc.normalize(startdatetime)
    #In my timezone
    start_dt = my_tz.normalize(startdatetime.astimezone(my_tz))
    end_dt = my_tz.normalize(enddatetime.astimezone(my_tz))

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
  %if not isConcise:
    %if not target:
      ${utils.userName(owner, entities[owner], "conv-user-cause")}
    %else:
      ${utils.userName(owner, entities[owner], "conv-user-cause")}
        <span class="conv-target">&#9656;</span>
      ${utils.groupName(target[0], entities[target[0]])}
    %endif
  %endif
  <div class="item-title has-icon">
    <span class="event-date-icon">
      <div>
        <div class="event-date-month">${start_dt.strftime("%b")}</div>
        <div class="event-date-day">${start_dt.strftime("%d")}</div>
        <div class="event-date-year"></div>
      </div>
    </span>

    <div class="event-title-text">
      <a href="/item?id=${convId}">${title}</a>
    </div>

    <div class="${'agenda-contents' if isConcise else 'event-contents'}">
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
      %if not isConcise:
        <div class="event-description">${desc|normalize}</div>
      %endif
      %if location.strip() != "" and not isConcise:
        <div><b>Venue</b> ${location}</div>
      %endif
      %if not isConcise:
        <div class="item-subactions">
          % if response == "yes":
            <span id="event-rsvp-status-${convId}">${_("You are attending.")}</span>
          % elif response == "no":
            <span id="event-rsvp-status-${convId}">${_("You are not attending.")}</span>
          % elif response == "maybe":
            <span id="event-rsvp-status-${convId}">${_("You may attend.")}</span>
          %else:
            <span id="event-rsvp-status-${convId}">${_("You have not responded to this event.")}</span>
          %endif
          % if response:
            <button class="button-link" onclick="$$.ui.showPopup(event)">${_("Change RSVP")}</button>
          % else:
            <button class="button-link" onclick="$$.ui.showPopup(event)">${_("RSVP now")}</button>
          % endif
          <ul class="acl-menu" style="display:none;">
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'yes')">${_("Yes, I will attend")}</a></li>
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'no')">${_("No")}</a></li>
              <li><a class="acl-item" onclick="$$.events.RSVP('${convId}', 'maybe')">${_("Maybe")}</a></li>
          </ul>
        </div>
      %endif
    </div>
  </div>
</%def>

<%def name="event_me()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("About this event")}</div>
    <div class="conversation-people-add-wrapper">
      <ul class="v-links">
        %if myId != items[convId]["meta"]["owner"] and myId in invitedPeople[convId]:
          <%
            invited_by = invitedPeople[convId][myId]
          %>
          <li>
            <span>${entities[invited_by].basic["name"]}</span>&nbsp;<span>${_("invited you to this event")} &nbsp; </span>
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
  %if myId in invitedPeople[convId].keys():
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

<%def name="render_attendance(attendeeList, invitedPeople)">
  <div class="conversation-attachments-wrapper">
    <ul class="v-links peoplemenu">
      %for u in attendeeList[convId][:4]:
        <li>
          %if u in invitedPeople[convId].keys():
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
</%def>

<%def name="event_meta()">
  <%
    iamOwner = myId == items[convId]["meta"]["owner"]
  %>
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Who are attending (%d)") % (len(yesPeople[convId]))}</div>
    <%self.render_attendance(yesPeople, invitedPeople)%>
    %if yesPeople[convId]:
      %if len(yesPeople[convId]) > 4:
        <div class="event-show-more-attendees"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'yes')">and ${len(yesPeople[convId]) - 4} more</a></div>
      %endif
    %else:
      <p> No one has accepted your invite yet!</p>
    %endif
  </div>
  %if maybePeople[convId] and iamOwner:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who may attend (%d)") % (len(maybePeople[convId]))}</div>
      <%self.render_attendance(maybePeople, invitedPeople)%>
      %if len(maybePeople[convId]) > 4:
        <div class="event-show-more-attendees"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'maybe')">and ${len(maybePeople[convId]) - 4} more</a></div>
      %endif
    </div>
  %endif
  %if noPeople[convId] and iamOwner:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Who are not attending (%d)") % (len(noPeople[convId]))}</div>
      <%self.render_attendance(noPeople, invitedPeople)%>
      %if len(noPeople[convId]) > 4:
        <div class="event-show-more-attendees"><a class="ajax" onclick="$$.events.showEventAttendance('${convId}', 'no')">and ${len(noPeople[convId]) - 4} more</a></div>
      %endif
    </div>
  %endif
</%def>

<%def name="side_agenda()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${title}</div>
    <ul class="v-links">
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

<%def name="notifyOtherEI()">
  <% emails.header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> has invited you to ${convTitle}.
    <br/><br/>
    ${convTime}
    <br/>
    % if convLocation != "":
        <b>Venue</b> -- ${convLocation}
    %endif
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View event</div></a>
  </td>
  <% emails.footer() %>
</%def>

<%def name="notifyOwnerEA()">
  <% emails.header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> is attending your ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View event</div></a>
  </td>
  <% emails.footer() %>
</%def>
