<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="profile" file="profile.mako"/>

##
## People page is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <span class="middle title">${_('People')}</span>
            <span class="button title-button">
              <a class="ajax" href="/people/invite" data-ref="/people/invite">${_('Invite more people')}</a>
            </span>
          </div>
          <div id="invite-people-wrapper">
          </div>
        </div>
        <div class="center-contents">
          <div id="people-view" class="viewbar">
            %if not script:
              ${viewOptions(viewType)}
            %endif
          </div>
          <div id="users-wrapper" class="paged-container">
            %if not script:
              ${listPeople()}
            %endif
          </div>
          <div id="people-paging" class="pagingbar">
            %if not script:
              ${paging()}
            %endif
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
 <%
    tabs = [('friends', _('My friends')), ('all', _('All users')), ('pendingRequests', _('Friend Requests'))]
    if showInvitationsTab:
        tabs.append(('invitations', _('Invitations')))
    people_count = pendingRequestsCount if pendingRequestsCount else ''
 %>
  <ul class="h-links view-options">
    %for item, display in tabs:
      %if item == "pendingRequests":
        %if selected == item:
          <li class="selected">${_(display)}<span id="pending-requests-count" class="view-options-count" >${people_count}</span></li>
        %else:
          <li><a href="/people?type=${item}" class="ajax">${_(display)}</a><span id="pending-requests-count" class="view-options-count">${people_count}</span></li>
        %endif
      %elif selected == item:
        <li class="selected">${_(display)}</li>
      %else:
        <li><a href="/people?type=${item}" class="ajax">${_(display)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/people?type=${viewType}&start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/people?type=${viewType}&start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="_displayUser(userId, showBlocked=False)">
  <% button_class = 'default' %>
  <div class="users-avatar">
    <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" height='48' width='48'></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
    <div class="user-details-actions">
      <ul id="user-actions-${userId}" class="middle user-actions h-links">
        %if showBlocked:
          %if userId not in blockedUsers:
            <li><button class="button default" onclick="$.post('/ajax/admin/block', 'id=${userId}')">Block</button></li>
          %endif
          <li><button class="button default" onclick="$.post('/ajax/admin/delete', 'id=${userId}')">Remove</button></li>
        %else:
          ${profile.user_actions(userId, True)}
        %endif
      </ul>
    </div>
  </div>
</%def>

<%def name="listPeople()">
  %if viewType and viewType == 'invitations':
    ${listInvitations()}
  %else:
    ${listUsers()}
  %endif
</%def>


<%def name="listUsers(showBlocked=False)">
  <%
    counter = 0
    firstRow = True
  %>
  %for userId in people:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayUser(userId, showBlocked)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="invitePeople()">
  <div class="header-form">
    <form id="invite-people-form" method="post" action="/people/invite" class="ajax">
      <input type="hidden" name="from" value="people"/>
      <div id="invite-people">
        <div class="input-wrap">
          <span class="icon invite-people-entry">&nbsp;</span>
          <input type="text" name="email" placeholder="${_("Enter your colleague&#39;s email address")}" autofocus required title="${_("Colleague's email address")}"/>
        </div>
        <div class="input-wrap">
          <span class="icon invite-people-entry">&nbsp;</span>
          <input type="text" name="email" placeholder="${_("Enter your colleague&#39;s email address")}"/>
        </div>
        <div class="input-wrap">
          <span class="icon invite-people-entry">&nbsp;</span>
          <input type="text" name="email" placeholder="${_("Enter your colleague&#39;s email address")}"/>
        </div>
      </div>
      <div class="header-form-buttons">
        <button type="submit" class="button default">${_("Invite")}</button>
        <button type="button" class="button" onclick="$('#invite-people-wrapper').empty()">${'Cancel'}</button>
      </div>
    </form>
    <script type="text/javascript">$('#invite-people-form').html5form({messages: 'en'});</script>
  </div>
</%def>

<%def name="listInvitations()">
  <%
    counter = 0
    firstRow = True
  %>
  %for emailId in emailIds:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayInvitation(emailId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="_displayInvitation(emailId)">
  <% button_class = 'default' %>
  <div class="users-avatar">
      <img width="48" height="48" src="/rsrcs/img/avatar_m_m.png">
  </div>
  <div class="users-details">
    <div class="user-details-name">${emailId}</div>
    <div class="user-details-actions">
      <ul id="user-actions-${emailId}" class="middle user-actions h-links">
        ##<li><button class="button disabled" onclick="$.post('/ajax/people/invite/resend', 'id=${emailId}')"><span class="button-text">Invite Again</span></button></li>
      </ul>
    </div>
  </div>
</%def>
