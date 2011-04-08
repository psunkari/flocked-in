<%! from social import utils, _, __, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

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
      ${item.item_layout(convId, True, True)}
    %endfor
  %endif
</%def>

<%def name="invitations()">
 %if inviItems:
    <div id="title"> <span class = "middle title"> Invitations </span> </div>
    %for convId in inviItems:
      ${item.item_layout(convId, True, True)}
    %endfor
  %endif
</%def>

<%def name="share_event()">
  <div class="input-wrap">
    <input type="text" name="startTime" placeholder="${_('When?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="endTime" placeholder="${_('End Time?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="title" placeholder="${_('What?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="location" placeholder="${_('Where?')}"/>
  </div>
  <div class="input-wrap">
      <input type="text" name="desc" placeholder="${_('Description')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="invitees" placeholder="${_('List of Invitees')}"/>
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
    response = myResponse[convId] if convId in myResponse else False
    owner = items[convId]["meta"]["owner"]
    ownerName = entities[owner]["basic"]["name"]
  %>
  <div id="conv" class="conv-item">
    <div>

       <span><a href = "/item?id=${convId}" >${title} </a> </</span>

        <p>${desc}</p>
        <p>Location: ${location}</p>
        % if start:
          <p> Start: ${start} </p>
        %endif
        % if end:
          <p> End : ${end} </p>
        %endif
        <p class="user">Created by: <a class='ajax' href='/profile?id=${owner}'>${ownerName}</a></p>

    </div>
    <div>
      <form action="/event/rsvp" method="POST" class="ajax">
          % for option in options:
            <% checked = "checked" if response and response == option else "" %>
            % if checked:
            <input type="radio" name="response" checked="${checked}" value= "${option}"  > ${option} </input>
            % else:
              <input type="radio" name="response" value= "${option}"  > ${option} </input>
            %endif
          % endfor
          <input type="hidden" name="id" value="${convId}" />
          <input type="hidden" name="type" value="event" />
          <input type="submit" id="submit" value="${_('RSVP')}"/>
        </form>
    </div>
    <div >
      <form action="/event/invite"  method=POST class="ajax">
        <label for="invitees"> Invite </label>
        <input type="text" name="invitees" placeholder="${_('List of Invitees')}"/>
        <input type="hidden" name="id" value= "${convId}" />
        <input type="submit" id="submit" value="${_('Invite')}"/>
      </form>
    </div>
  </div>
</%def>
