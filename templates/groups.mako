
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
    <div id="title"><span class="middle title">${heading}</span></div>
  %else:
    <div id="title"><span class="middle title">${_('Group')}</span></div>
  %endif
</%def>

<%def name="displayGroupMembers()">
  <% counter = 0 %>
  %for userId in users:
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
        ${profile.user_actions(userId, True, True)}
      </div>
    </div>
</%def>

<%def name="displayGroups()">

  % for groupId in groups:

    <div class="user-avatar">

    </div>
    <div class="user-details">
      <%
        groupName = groups[groupId]["basic"].get("name", "no name")
      %>
      <div class="user-details-name"><a href ="/feed?id=${groupId}">${groupName}</a></div>
      <div class="user-details-actions">
        <ul id="user-actions-${myKey}" class="middle user-actions h-links">
        % if groupId not in myGroups:
          <li class="button default" onclick="$.post('/ajax/groups/subscribe', 'id=${groupId}', null, 'script')"><span class="button-text">Subscribe</span></li>
        %else:
          <li class="button" onclick="$.post('/ajax/groups/unsubscribe', 'id=${groupId}', null, 'script')"><span class="button-text">Unsubscribe</span></li>
          %if myKey in groupFollowers[groupId]:
            <li class="button" onclick="$.post('/ajax/groups/unfollow', 'id=${groupId}', null, 'script')"><span class="button-text">UnFollow</span></li>
          %else:
            <li class="button" onclick="$.post('/ajax/groups/follow', 'id=${groupId}', null, 'script')"><span class="button-text">Follow</span></li>
          %endif
        %endif
        </ul>
      </div>
    </div>
  %endfor
</%def>

