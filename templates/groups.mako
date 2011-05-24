
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
          <div id="titlebar" class="titlebar">
            ${self.titlebar()}
          </div>
        </div>
        <div id="groups-wrapper" class="center-contents">
          %if not script:
            ${self.displayGroups()}
          %endif
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
      <a class="ajax">${_('New Group')}</a>
    </span>
  %endif
</%def>

<%def name="displayGroupMembers()">
  <% counter = 0 %>
  %for userId in userIds:
    %if counter % 2 == 0:
      <div class="users-row">
    %endif
    <div class="users-user">${_displayUser(userId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" _ref="/groups/members?id=${groupId}&start=${nextPageStart}">${_("Fetch More People")}</a></div>
  %else:
    <div id="next-load-wrapper"> </div>
  %endif
</%def>


<%def name="_displayUser(userId)">
  <% button_class = 'default' %>

    <div class="users-avatar">
    <% avatarURI = utils.userAvatar(userId, users[userId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" height='48' width='48'></img>
    %endif
    </div>
    <div class="users-details">
      <div class="user-details-name">${utils.userName(userId, users[userId])}</div>
      <div class="user-details-title">${users[userId]["basic"].get("jobTitle", '')}</div>
      <div class="user-details-actions">
        <ul id="user-actions-${userId}" class="middle user-actions h-links">
          ${profile.user_actions(userId, True)}
        </ul>
      </div>
    </div>
</%def>

<%def name="pendingRequests()">
  <%
    counter = 0
  %>
  %for userId in entities:


    <div class="users-user">

      <div class="users-avatar">
      <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
      %if avatarURI:
        <img src="${avatarURI}" height='48' width='48'></img>
      %endif
      </div>
      <div class="users-details">
        <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
        <div class="user-details-actions">
          <ul id="user-actions-${userId}" class="middle user-actions h-links">
            <button class="button default" onclick="$.post('/ajax/groups/approve', 'id=${groupId}&uid=${userId}', null, 'script')"><span class="button-text">Accept</span></button>
            <button class="button default" onclick="$.post('/ajax/groups/reject', 'id=${groupId}&uid=${userId}', null, 'script')"><span class="button-text">Reject</span></button>
            <button class="button default" onclick="$.post('/ajax/groups/block', 'id=${groupId}&uid=${userId}', null, 'script')"><span class="button-text">Block</span></button>
          </ul>
        </div>
      </div>
    </div>

  %endfor

</%def>

<%def name="userActions(groupId)">


        <ul id="user-actions-${groupId}" class="middle user-actions h-links">
        %if groupId in pendingConnections:
          <button class="button disabled"><span class="button-text">Request Pending</span></button>
        % elif groupId not in myGroups:
          <button class="button default" onclick="$.post('/ajax/groups/subscribe', 'id=${groupId}', null, 'script')"><span class="button-text">Subscribe</span></button>
        %else:
          <button class="button" onclick="$.post('/ajax/groups/unsubscribe', 'id=${groupId}', null, 'script')"><span class="button-text">Unsubscribe</span></button>
          %if myKey in groupFollowers[groupId]:
            <button class="button" onclick="$.post('/ajax/groups/unfollow', 'id=${groupId}', null, 'script')"><span class="button-text">UnFollow</span></button>
          %else:
            <button class="button default" onclick="$.post('/ajax/groups/follow', 'id=${groupId}', null, 'script')"><span class="button-text">Follow</span></button>
          %endif
        %endif
        </ul>


</%def>

<%def name="displayGroups()">

  % for groupId in groups:

    <div class="user-avatar">
      <% avatarURI = utils.userAvatar(groupId, groups[groupId], "large") %>
      %if avatarURI:
        <!--<img src="${avatarURI}" width=64 height=64/>-->
      %endif
    </div>
    <div class="user-details">
      <%
        groupName = groups[groupId]["basic"].get("name", "no name")
      %>
      <div class="user-details-name"><a href ="/feed?id=${groupId}">${groupName}</a></div>
      <div class="user-details-actions" id=${groupId}-user-actions>
        ${self.userActions(groupId)}
      </div>


    </div>
  %endfor
</%def>


<%def name="createGroup()">
  <form action="/groups/create" method="post"  enctype="multipart/form-data">
    <div class="edit-profile">
      <ul>
        <li><label for="name"> Group Name: </label></li>
        <li><input type="text" id="name" name="name" value= "" /></li>
      </ul>
      <ul>
        <li><label for="desc"> Description: </label></li>
        <li><textarea id="desc" name="desc" /></li>
      </ul>
      <ul>
        <li><label for="access"> Group Type : </label></li>
        <li><input type="radio" id="access" name="access" value= "public" > Public</input></li>
        <li><input type="radio" id="access" name="access" value= "private" > Private</input></li>
      </ul>

      <ul>
        <li><label for="external"> external users allowed: </label></li>
        <li><input type="radio" id="external" name="external" value= "open"> Yes</input>  </li>
        <li><input type="radio" id="external" name="external" value= "closed"> No </input></li>
      </ul>
      <ul><li></li></ul>

      <ul>
        <li><label for="dp"> Photo </label> </li>
        <li><input type="file" id="dp" name="dp" accept="image/jpx, image/png, image/gif" />
      </ul>
      <ul>
        % if myKey:
        <li><input type="hidden" value = ${myKey} name="id" /></li>
        %endif
      </ul>
      <ul>
        <li></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
      </ul>
    </div>
  </form>
</%def>

<%def name="inviteMembers()">
  <form action="/groups/invite" class="ajax" method="post"  >
    <div class="edit-profile">
      <ul>
        <li><label for="name"> EmailId: </label></li>
        <li><input type="text" id="uid" name="uid" /></li>
      </ul>
      <ul>
        <li><input type="hidden" value = ${groupId} name="id" /></li>
      </ul>
      <ul>
        <li></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
      </ul>
    </div>
  </form>
</%def>
