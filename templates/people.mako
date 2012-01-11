<!DOCTYPE HTML>

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
      <div class="titlebar center-header">
        <span class="middle title">${_('People')}</span>
          %if script:
            <button onclick="$$.users.invite();" class="button title-button">${_('Invite People')}</button>
          %endif
      </div>
      <div id="right"></div>
      <div id="center">
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
      <div class="clear"></div>
      </div>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
 <%
    tabs = [('all', _('All users'))]
    if showInvitationsTab:
        tabs.append(('invitations', _('Invitations')))
 %>
  <ul class="h-links view-options">
    %for item, display in tabs:
      %if selected == item:
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
      <img src="${avatarURI}" style="max-height:48px; max-width:48px"></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
    <div class="user-details-actions">
      <ul id="user-actions-${userId}" class="middle user-actions h-links">
        ## XXX: showBlocked should not be the basis for displaying admin actions.
        ## take a parameter to indicate which actions should be displayed - admin or user.
        %if showBlocked:
          %if userId not in blockedUsers:
            <li><button class="button" onclick="$.post('/ajax/admin/block', 'id=${userId}')">${_("Block")}</button></li>
          %else:
            <li><button class="button" onclick="$.post('/ajax/admin/block', 'id=${userId}')">${_("Unblock")}</button></li>
          %endif
          <li><button class="button" onclick="$$.users.remove('${userId}')">${_("Remove")}</button></li>
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
  <div class='ui-dlg-title'>${_('Invite People')}</div>
  <div>
    <form id="invite-people-form" method="post" action="/people/invite" class="ajax">
      <input type="hidden" name="from" value="people"/>
      <ul class="dlgform" id="invite-people">
        <li class="form-row">
            <label class="dlgform-label" for="msgcompose-rcpts">${_('Email Address')}</label>
            <input type="email" name="email" placeholder="" autofocus required="" title="${_("Colleague&#39;s email address")}"/>
        </li>
        <li class="form-row">
            <label class="dlgform-label" for="msgcompose-rcpts">${_('Email Address')}</label>
            <input type="email" name="email" title="${_("Colleague&#39;s email address")}"/>
        </li>
        <li class="form-row">
            <label class="dlgform-label" for="msgcompose-rcpts">${_('Email Address')}</label>
            <input type="email" name="email" title="${_("Colleague&#39;s email address")}"/>
        </li>
      </ul>
      <input id="invite-people-form-submit" type="submit" style="visibility:hidden" />
    </form>
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
      <img style="max-width:48px; max-height:48px" src="/rsrcs/img/avatar_m_m.png">
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
