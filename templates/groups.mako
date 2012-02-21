<!DOCTYPE HTML>
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="profile" file="profile.mako"/>
<%namespace name="people" file="people.mako"/>
<%namespace name="group_feed" file="group-feed.mako"/>

##
##
<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="titlebar" class="titlebar center-header">
        %if not script:
          <% titlebar() %>
        %endif
      </div>
      <div id="right"></div>
      <div id="center">
        <div class="center-contents" id="center-content">
          <div id="groups-view" class="viewbar">
            %if not script:
              ${viewOptions(viewType)}
            %endif
          </div>
          <div id="groups-wrapper" class="paged-container">
            %if not script:
              ${self.listGroups()}
            %endif
          </div>
          <div id="groups-paging" class="pagingbar">
            %if not script:
              ${self.paging()}
            %endif
          </div>
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="titlebar()">
    %if heading:
      <span class="middle title">${heading}</span>
    %else:
      <button onclick="$$.ui.addGroup();" class="button title-button">${_('New Group')}</button>
      <span class="middle title">${_('Groups')}</span>
    %endif
</%def>

<%def name="listGroups()">
  <%
    counter = 0
    firstRow = True
  %>
  %for groupId in groupIds:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayGroup(groupId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="_displayGroup(groupId)">
  <% button_class = 'default' %>
  <div class="users-avatar">
    <% avatarURI = utils.groupAvatar(groupId, entities[groupId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" style="max-height:48px; max-width:48px"></img>
    %endif
  </div>
  <div class="users-details">
    <%
      groupName = entities[groupId]["basic"].get("name", "-")
      groupDesc = entities[groupId]["basic"].get("desc", None)
    %>
    ${utils.groupName(groupId, entities[groupId], "user-details-name", "div")}
    <div class="group-details-title">${entities[groupId]["basic"]["access"].capitalize()}</div>
    %if groupDesc:
        <div class="group-details-desc">&nbsp;&ndash;&nbsp;${groupDesc}</div>
    %else:
        <div class="group-details-desc">&nbsp;</div>
    %endif
    <div class="user-details-actions">
      <ul id="group-actions-${groupId}" class="middle user-actions h-links">
        ${group_feed.group_actions(groupId)}
      </ul>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
  <%
    options = [('myGroups', 'My Groups'), ('allGroups', 'All Groups'), ('adminGroups', 'Groups managed by Me')]
    if showInvitationsTab:
      options.append(('invitations', 'Group Invitations'))
    if showPendingRequestsTab:
        options.append(("pendingRequests", "Pending Requests"))
    group_request_count = groupRequestCount if groupRequestCount else ''
    %>
  <ul class="h-links view-options">
    %for item, display in options:
      %if item == "pendingRequests":
        %if selected == item:
          <li class="selected">${_(display)}<span id="pending-group-requests-count" class="view-options-count" >${group_request_count}</span></li>
        %else:
          <li><a href="/groups?type=${item}" class="ajax">${_(display)}</a><span id="pending-group-requests-count" class="view-options-count">${group_request_count}</span></li>
        %endif
      %elif selected == item:
        <li class="selected">${_(display)}</li>
      %else:
        <li><a href="/groups?type=${item}" class="ajax">${_(display)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/groups?type=${viewType}&start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/groups?type=${viewType}&start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="createGroup()">
  <div class='ui-dlg-title'>${_('Create a New Group')}</div>
  <div class="ui-dlg-center" style="max-height: 300px;">
    <form id="add-group-form" action="/ajax/groups/create" method="post" enctype="multipart/form-data">
      <ul class="dlgform">
        <li class="form-row">
            <label class="styled-label" for="groupName">${_('Group Name')}</label>
            <input type="text" id="groupName" name="name" required
                   title="${_('Group Name')}"/>
        </li>
        <li class="form-row">
            <label class="styled-label" for="desc">${_('Description')}</label>
            <textarea class="input-wrap" id="desc" name="desc"></textarea>
        </li>
        <li class="form-row">
            <label class="styled-label">&nbsp;</label>
            <input type="checkbox" id="access" name="access" value="closed"/>
            <label for="access">${_("Membership requires administrator approval")}</label>
        </li>
        <li class="form-row">
            <label class="styled-label" for="dp">${_("Group Logo")}</label>
            <input type="file" id="dp" size="13" name="dp"/>
      </ul>
      <input id="add-group-form-submit" type="submit" style="display:none;"/>
      %if myKey:
        <input type="hidden" value = ${myKey} name="id" />
      %endif
    </form>
  </div>
</%def>

<%def name="allPendingRequests()">
  <%
    counter = 0
    firstRow = True
  %>
  %for userId, groupId in userIds:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayUser(userId, groupId, True)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="groupRequestActions(groupId, userId, action='')">
  %if action == 'accept':
    <button class="button disabled"><span class="button-text">${_("Accepted")}</span></button>
  %elif action == 'reject':
    <button class="button disabled"><span class="button-text">${_("Rejected")}</span></button>
  %elif action == 'block':
    <button class="button disabled"><span class="button-text">${_("Blocked")}</span></button>
  %elif action == 'unblock':
    <button class="button disabled"><span class="button-text">${_("Unblocked")}</span></button>
  %elif action == 'removed':
    <button class="button disabled"><span class="button-text">${_("Removed")}</span></button>
  %elif action == 'show_blocked':
    <button class="button" onclick="$.post('/ajax/groups/unblock', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Unblock")}</span></button>
  %elif action == 'show_manage':
    <button class="button" onclick="$.post('/ajax/groups/remove', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Remove")}</span></button>
    %if userId not in entities[groupId]['admins']:
      <button class="button" onclick="$.post('/ajax/groups/makeadmin', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Make Admin")}</span></button>
    %else:
      <button class="button" onclick="$.post('/ajax/groups/removeadmin', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Remove Admin")}</span></button>
    %endif

  %else:
    <button class="button default" onclick="$.post('/ajax/groups/approve', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Accept")}</span></button>
    <button class="button" onclick="$.post('/ajax/groups/reject', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Reject")}</span></button>
    <button class="button" onclick="$.post('/ajax/groups/block', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Block")}</span></button>
  %endif

</%def>

<%def name="displayUsers()">
  <%
    counter = 0
    firstRow = True
    showUserActions = tab not in ['pending', 'banned', 'manage']
  %>
  %for userId in userIds:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayUser(userId, groupId, showUserActions=showUserActions)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="_displayUser(userId, groupId, showGroupName=False, showUserActions=False)">
  <div class="users-avatar">
    <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" style="max-height:48px; max-width:48px"></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
    % if groupId and showGroupName:
      <div class="user-details-name">${_("Group:")} ${utils.groupName(groupId, entities[groupId])}</div>
    %endif
    <div class="user-details-actions">
      %if showUserActions:
        <ul id="user-actions-${userId}" class="middle user-actions h-links">
          ${profile.user_actions(userId, True)}
        </ul>
      %else:
        <ul id="group-request-actions-${userId}-${groupId}" class="middle user-actions h-links">
          %if tab == 'pending':
            ${self.groupRequestActions(groupId, userId)}
          %elif tab == 'banned':
            ${self.groupRequestActions(groupId, userId, action="show_blocked")}
          % elif tab == 'manage':
            ${self.groupRequestActions(groupId, userId, action="show_manage")}
          %endif
        </ul>
      %endif
    </div>
  </div>
</%def>

<%def name="pendingRequestsPaging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/groups/pending?start=${prevPageStart}&id=${groupId}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/groups/pending?start=${nextPageStart}&id=${groupId}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="bannedUsersPaging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/groups/banned?start=${prevPageStart}&id=${groupId}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/groups/banned?start=${nextPageStart}&id=${groupId}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>
