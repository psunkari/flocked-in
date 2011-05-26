<%! from social import utils, _, __, plugins %>
<%! from pytz import common_timezones %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="people" file="people.mako"/>
<%inherit file="base.mako"/>

<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, icon):
        return '<li><a href="%(link)s" class="ajax busy-indicator"><span class="sidemenu-icon admin-icon %(icon)s-icon"></span><span class="sidemenu-text">%(text)s</span></a></li>' % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
       ${navMenuItem("/feed", _("Back to Home"), "back")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/admin/add", _("Add Users"), "add-user")}
      ${navMenuItem("/admin/people", _("Manage Users"), "block-user")}
      ${navMenuItem("/admin/unblock", _("UnBlock Users "), "unblock-user")}
      ${navMenuItem("", _("Manage Admins"), "manage-admins")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("", _("Manage Groups"), "manage-groups")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/admin/org", _("Update OrgInfo"), "update-orgInfo")}
    </ul>
  </div>
</%def>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            %if title:
              <div id="title"><span class="middle title">${_(title)}</span></div>
            %else:
              <div id="title"><span class="middle title">${_("Admin Console")}</span></div>
            %endif
          </div>
        </div>
        <div id="add-users" class="center-contents">
          %if not script:
            ${self.addUsers()}
          %endif

        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="list_blocked()">
  % if not entities:
    <div id="next-load-wrapper">No blocked users</div>
  % else:
    % for userId in entities:
      <div class="users-user">
        <div class="users-avatar">
        <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
        %if avatarURI:
          <img src="${avatarURI}" height='48' width='48'></img>
        %endif
        </div>
        <div class="users-details">
          <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
          <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
          <ul id="user-actions-${userId}" class="middle user-actions h-links">
            <li class="button default" onclick="$.post('/ajax/admin/unblock', 'id=${userId}', null, 'script')"><span class="button-text">UnBlock</span></li>
          </ul>
        </div>
      </div>
    %endfor
  %endif
</%def>

<%def name="list_users()" >
  ${people.content(True)}
</%def>


<%def name="addUsers()">
  <% myTimezone  = me.get("basic", {}).get("timezone", "") %>
  <div class="edit-profile">
    <h4> Add User:</h4>
    <form action="/admin/add" method="POST" enctype="multipart/form-data" autocomplete="off">
    <!-- fileupload doesn't work with ajax request.
        TODO: find workaround to submit file in ajax request-->

      <ul>
        <li><label for="name"> Display Name: </label></li>
        <li><input type="text" name="name" /> </li>
      </ul>
      <ul>
        <li><label for="email"> EmailId: </label></li>
        <li><input type="text" name="email" /> </li>
      </ul>
      <ul>
        <li><label for="jobTitle"> JobTitle: </label></li>
        <li><input type="text" name="jobTitle" /> </li>
      </ul>
      <ul>
        <li> <label for="timezone">Timezone </label> </li>
        <li>
          <select name="timezone">
            % for timezone in common_timezones:
              % if timezone == myTimezone:
                <option value = "${timezone}" selected="">${timezone}</option>
              % else:
                <option value = "${timezone}" >${timezone}</option>
              % endif
            % endfor
          </select>
        </li>
      </ul>
      <ul>
        <li><label for="passwd">  Password: </label></li>
        <li><input type="password" name="passwd" /> </li>
      </ul>
      <ul>
        <li></li>
        <li> <input type="submit" value="Submit"/></li>
      </ul>
      <ul><li></li></ul>
      <ul><h4>Or Upload a File</h4></ul>
      <ul><li></li></ul>
      <ul>
        <li><label for="format"> File Type:</label></li>
        <li><input type="radio" name="format" value="csv" checked=True>CSV</input></li>
        <li><input type="radio" name="format" value="tsv">TSV</input></li>
      </ul>
      <ul>
        <li><label for="data"> Upload File: </label></li>
        <li><input type="file" name="data" accept="csv" /> </li>
      </ul>
      <ul>
        <li></li>
        <li> <input type="submit" value="Submit"/></li>
      </ul>
    </form>
  </div>
</%def>


<%def name="orgInfo()">
  <%
    name = org.get("basic", {}).get("name", '')
  %>
  <div class="edit-profile">
    <form action="/admin/org" method="POST" enctype="multipart/form-data">
    <!-- fileupload doesn't work with ajax request.
        TODO: find workaround to submit file in ajax request-->

      <ul>
        <li><label for="name"> Name: </label></li>
        <li><input type="text" name="name"  value="${name}"/> </li>
      </ul>
      <ul>
        <li><label for="dp"> Logo: </label></li>
        <li><input type="file" name="dp" /> </li>
      </ul>
      <ul>
        <li></li>
        <li> <input type="submit" value="Submit"/></li>
      </ul>
    </form>
  </div>
</%def>
