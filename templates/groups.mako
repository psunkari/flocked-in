
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="profile" file="profile.mako"/>
<%namespace name="people" file="people.mako"/>

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
          <div id="titlebar" class="titlebar">
            ${self.titlebar()}
          </div>
          <div id="add-user-wrapper"></div>
        </div>
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
    </div>
  </div>
</%def>

<%def name="titlebar()" >
  %if heading:
    <span class="middle title">${heading}</span>
  %else:
    <span class="middle title">${_('Groups')}</span>
    <span class="button title-button">
      <a class="ajax" href="/groups/create" _ref="/groups/create">${_('New Group')}</a>
    </span>
  %endif
</%def>

<%def name="listGroupMembers()">
  <% counter = 0 %>
  %for userId in userIds:
    %if counter % 2 == 0:
      <div class="users-row">
    %endif
    <div class="users-user">${people._displayUser(userId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>



<%def name="group_actions(groupId)">
  %if groupId in pendingConnections:
    <button class="button disabled"><span class="button-text">${_('Request Pending')}</span></button>
  %elif groupId not in myGroups:
    <button class="button default" onclick="$.post('/ajax/groups/subscribe', 'id=${groupId}')"><span class="button-text">${('Join')}</span></button>
  %else:
    <button class="button" onclick="$.post('/ajax/groups/unsubscribe', 'id=${groupId}')"><span class="button-text">${('Leave')}</span></button>
    %if myKey in groupFollowers[groupId]:
      <button class="button" onclick="$.post('/ajax/groups/unfollow', 'id=${groupId}')"><span class="button-text">${('Stop Following')}</span></button>
    %else:
      <button class="button default" onclick="$.post('/ajax/groups/follow', 'id=${groupId}')"><span class="button-text">${('Follow')}</span></button>
    %endif
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
    <% avatarURI = utils.groupAvatar(groupId, groups[groupId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" height='48' width='48'></img>
    %endif
  </div>
  <div class="users-details">
    <%
      groupName = groups[groupId]["basic"].get("name", "-")
      groupDesc = groups[groupId]["basic"].get("desc", None)
    %>
    <div class="user-details-name"><a href ="/feed?id=${groupId}">${groupName}</a></div>
    <div class="group-details-title">${groups[groupId]["basic"]["access"].capitalize()}</div>
    %if groupDesc:
        <div class="group-details-desc">&nbsp;&ndash;&nbsp;${groupDesc}</div>
    %else:
        <div class="group-details-desc">&nbsp;</div>
    %endif
    <div class="user-details-actions">
      <ul id="group-actions-${groupId}" class="middle user-actions h-links">
        ${group_actions(groupId)}
      </ul>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
  <%
    options = [('myGroups', 'My Groups'), ('allGroups', 'All Groups'), ('adminGroups', 'Groups managed by Me')]
    if showPendingRequestsTab:
        options.append(("pendingRequests", "Pending Requests"))
    %>
  <ul class="h-links view-options">
    %for item, display in options:
      %if selected == item:
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
  <form id="group_form" action="/ajax/groups/create" method="post" enctype="multipart/form-data">
    <div class="styledform">
      <ul>
        <li>
            <label for="name">Group Name</label>
            <input type="text" id="groupname" name="name" value= ""/>
        </li>
        <li>
            <label for="desc">Description</label>
            <textarea class="input-wrap" id="desc" name="desc"></textarea>
        </li>
        <li>
            <label>Group Visibility</label>
            <input type="radio" id="access" name="access" value="public">Public</input>
            <input type="radio" id="access" name="access" value="private">Private</input>
        </li>
        <li>
            <label for="dp">Group Logo</label>
            <input type="file" id="dp" name="dp" accept="image/jpx, image/png, image/gif"/>
      </ul>
    <div class="styledform-buttons">
        <input type="submit" name="userInfo_submit" value="Save" class="button default"/>
        <button type="button" class="button default" onclick="$('#add-user-wrapper').empty()">Cancel</button>
    </div>
    </div>
    % if myKey:
    <input type="hidden" value = ${myKey} name="id" />
    %endif
  </form>
</%def>

<%def name="inviteMembers()">
  <form action="/groups/invite" class="ajax" method="post"  >
    <div class="styledform">
      <ul>
        <li><label for="name"> EmailId: </label></li>
        <li><input type="text" id="invitee" name="invitee" /></li>
        <li><input type="hidden" value = ${groupId} name="id" /></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
      </ul>
    </div>
  </form>
</%def>


<%def name="pendingRequests()">
  <%
    counter = 0
    firstRow = True
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
    <div class="users-user">${_pendingRequestUser(userId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
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
    <div class="users-user">${_pendingRequestUser(userId, groupId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>


<%def name="_pendingRequestUser(userId, groupId=None)">
  <div class="users-avatar">
    <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
    %if avatarURI:
        <img src="${avatarURI}" height='48' width='48'></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    % if groupId:
      <div class="user-details-name">${_("Group:")} ${utils.groupName(groupId, entities[groupId])}</div>
    %endif
    <div class="user-details-actions">
      <ul id="user-actions-${userId}" class="middle user-actions h-links">
        <button class="button default" onclick="$.post('/ajax/groups/approve', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Accept")}</span></button>
        <button class="button default" onclick="$.post('/ajax/groups/reject', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Reject")}</span></button>
        <button class="button default" onclick="$.post('/ajax/groups/block', 'id=${groupId}&uid=${userId}')"><span class="button-text">${_("Block")}</span></button>
      </ul>
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
