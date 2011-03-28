
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
            %if heading:
              <div id="title"><span class="middle title">${heading}</span></div>
            %else:
              <div id="title"><span class="middle title">${_('People')}</span></div>
            %endif
          </div>
        </div>
        <div id="users-wrapper" class="center-contents">
          %if not script:
            ${self.content()}
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="_displayUser(userId)">
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
      ${profile.user_actions(userId, True, True)}
    </div>
  </div>
</%def>

<%def name="content()">
  <% counter = 0 %>
  %for userId in people:
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
