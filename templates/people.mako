
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

##
## Profile is displayed in a 3-column layout.
##
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
        ${self.content()}
      </div>
    </div>
  </div>
</%def>

<%def name="content()">
  <%
    fmtUser = lambda x: ("<span class='user comment-author'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (x, users[x]["basic"]["name"]))
    button_class = "default"
  %>
  %if heading:
    <h3> ${heading} </h3>
  %endif
  <div class="user-info">
    %for userId in users:
      <% button_class = "default" %>
      <ul>
        <li>
          <div class="conv-avatar">
            <% avatarURI = utils.userAvatar(userId, users[userId], "medium") %>
            %if avatarURI:
              <img src="${avatarURI}" height='48' width='48'/>
            %endif
          </div>
        </li>
        <li>${fmtUser(userId)} </li>
        <li>${users[userId]["basic"].get("jobTitle", '')} </li>
        <li>
          % if myKey != userId:
            % if not myFriends or (userId not in myFriends):
              <a onclick="$.post('/ajax/profile/friend', 'id=${userId}')"><span class="button ${button_class}"><span> Add as Friend</span></span></a>
              <% button_class = "" if button_class else "default" %>
            %else:
              <a onclick="$.post('/ajax/profile/unfriend', 'id=${userId}')"><span class="button ${button_class} "><span> UnFriend</span></span></a>
              <% button_class = "" if button_class else "default" %>
            %endif
          % endif
        </li>
        <li>
          % if myKey != userId:
            % if myFriends and userId in myFriends:
              <!-- -->
            % elif mySubscriptions and (userId in mySubscriptions):
                <a onclick="$.post('/ajax/profile/unfollow', 'id=${userId}')"><span class="button ${button_class} "> <span> UnFollow </span></span></a>
                <% button_class = "" if button_class else "default" %>
            % else:
                <a onclick="$.post('/ajax/profile/follow', 'id=${userId}')"><span class="button ${button_class} "><span>Follow User </span> </span></a>
            %endif
          % endif
        </li>
      </ul>
    %endfor
  </div>
</%def>
