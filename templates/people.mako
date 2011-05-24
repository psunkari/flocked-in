
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
              <a class="ajax">${_('Invite more people')}</a>
            </span>
          </div>
        </div>
        <div class="center-contents">
          <div id="people-view" class="viewbar">
            %if not script:
              ${viewOptions(viewType)}
            %endif
          </div>
          <div id="users-wrapper">
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
  <ul class="h-links view-options">
    %for item, display in [('friends', 'My friends'), ('all', 'All users')]:
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
      <img src="${avatarURI}" height='48' width='48'></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
    <div class="user-details-actions">
      <ul id="user-actions-${userId}" class="middle user-actions h-links">
        % if showBlocked:
          % if userId not in blockedUsers:
            <li class="button default" onclick="$.post('/ajax/admin/block', 'id=${userId}', null, 'script')"><span class="button-text">Block</span></li>
          %endif
          <li class="button default" onclick="$.post('/ajax/admin/delete', 'id=${userId}', null, 'script')"><span class="button-text">Remove</span></li>
        %else:
          ${profile.user_actions(userId, True)}
        %endif
      </ul>
    </div>
  </div>
</%def>

<%def name="listPeople(showBlocked=False)">
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
