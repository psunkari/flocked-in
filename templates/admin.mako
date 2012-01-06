<%! from social import utils, _, __, plugins %>
<%! from pytz import common_timezones %>
<!DOCTYPE HTML>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="people" file="people.mako"/>
<%inherit file="base.mako"/>

<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, id):
      cls = "sidemenu-selected" if id == menuId else ''
      return """<li>
                  <a href="%(link)s" class="ajax busy-indicator %(id)s-sideitem %(cls)s">
                    <span class="sidemenu-icon icon %(id)s-icon"></span>
                    <span class="sidemenu-text">%(text)s</span>
                  </a>
                </li>
              """ % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
       ${navMenuItem("/feed", _("Back to Home"), "back")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/admin/people", _("Users"), "users")}
      ${navMenuItem("admin/groups", _("Groups"), "groups")}
      ${navMenuItem("/admin/org", _("Organization"), "org")}
    </ul>
  </div>
</%def>

<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="center-header">
        <div class="titlebar">
          %if title:
            <span class="middle title">${_(title)}</span>
          %else:
            <span class="middle title">${_("Admin Console")}</span>
          %endif
          <span class="button title-button">
            <a class="ajax" href="/admin/add" data-ref="/admin/add">${_('Add Users')}</a>
          </span>
        </div>
        <div id="add-user-wrapper"></div>
      </div>
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
      </div>
      <div id="center">
        <div class="center-contents">
          <div id="users-view" class="viewbar">
            %if not script:
              ${viewOptions()}
            %endif
          </div>
          <div id="list-users" class="paged-container">
            %if not script:
              ${self.list_users()}
            %endif
          </div>
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="_displayUser(userId)">
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
        ${admin_actions(userId, 'blocked')}
      </ul>
    </div>
  </div>
</%def>

<%def name="list_blocked()">
  % if not entities:
    <div id="next-load-wrapper">${_("No blocked users")}</div>
  % else:
    <%
      counter = 0
      firstRow = True
    %>
    %for userId in entities:
      %if counter % 2 == 0:
        %if firstRow:
          <div class="users-row users-row-first">
          <% firstRow = False %>
        %else:
          <div class="users-row">
        %endif
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

    <div id="people-paging" class="pagingbar">
      ${paging(type='blocked')}
  %endif
</%def>

<%def name="viewOptions(viewType)">
  <ul class="h-links view-options">
    %for item, display in [('all', 'All users'), ('blocked', 'Blocked Users')]:
      %if viewType == item:
        <li class="selected">${_(display)}</li>
      %else:
        <li><a href="/admin/people?type=${item}" class="ajax">${_(display)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="paging(type='')">
  <%
    typeFilter = ''
    if type and type == 'blocked':
      typeFilter = '&type=blocked'
  %>
  <ul class="h-links">
    %if prevPageStart:
      <li class="button">
        <a class="ajax" href="/admin/people?start=${prevPageStart}${typeFilter}">${_("&#9666; Previous")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button">
        <a class="ajax" href="/admin/people?&start=${nextPageStart}${typeFilter}">${_("Next &#9656;")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="list_users()" >
  ${people.listUsers(showBlocked=True)}
  <div id="people-paging" class="pagingbar">
    ${paging()}
  </div>
</%def>


<%def name="addUsers()">
  <% myTimezone  = me.get("basic", {}).get("timezone", "") %>
  <div class="tabs">
    <ul class="tablinks h-links">
      <li><a style="cursor:pointer" class="selected"
             onclick="$('#add-user-block').toggle();
                      $('#add-users-block').toggle();
                      $(this).toggleClass('selected');
                      $(this).parent().siblings().children().toggleClass('selected')">
            ${_("New User")}
          </a>
      </li>
      <li><a style="cursor:pointer" class=""
             onclick="$('#add-users-block').toggle();
                      $('#add-user-block').toggle();
                      $(this).toggleClass('selected');
                      $(this).parent().siblings().children().toggleClass('selected')">
            ${_("Multiple Users")}
          </a>
      </li>
  </div>
  <div id="add-user-block">
    <form action="/admin/add" method="POST" enctype="multipart/form-data" autocomplete="off">
      <ul class="styledform">
        <li class="form-row">
          <label class="styled-label" for="name">${_("Display Name")}</label>
          <input type="text" name="name" />
        </li>
        <li class="form-row">
          <label class="styled-label" for="email">${_("Email Address")}</label>
          <input type="text" name="email" />
        </li>
        <li class="form-row">
          <label class="styled-label" for="jobTitle">${_("Job Title")}</label>
          <input type="text" name="jobTitle" />
        </li>
        <li class="form-row">
          <label class="styled-label" for="timezone">${_("Timezone")}</label>
          <select name="timezone" class="single-row">
            %for timezone in common_timezones:
              %if timezone == myTimezone:
                <option value = "${timezone}" selected="">${timezone}</option>
              %else:
                <option value = "${timezone}" >${timezone}</option>
              %endif
            %endfor
          </select>
        </li>
        <li class="form-row">
          <label class="styled-label" for="passwd">${_("Password")}</label>
          <input type="password" name="passwd" />
        </li>
      </ul>
      <div class="styledform-buttons">
        <button type="submit" class="button default">${_("Add")}</button>
        <button type="button" class="button default" onclick="$('#add-user-wrapper').empty()">${_("Cancel")}</button>
      </div>
    </form>
  </div>
  <div id="add-users-block" style="display:none">
    <form action="/admin/add" method="POST" enctype="multipart/form-data" autocomplete="off">
      <!-- fileupload doesn't work with ajax request.
           TODO: find workaround to submit file in ajax request-->
      <div class="alert alert-info">
        ${_("Please upload a comma or tab separated file containing list of users in the following fields")}
        <div><b>
          <span>Name</span>&nbsp;&nbsp;
          <span>Email Address</span>&nbsp;&nbsp;
          <span>Job Title</span>&nbsp;&nbsp;
          <span>Timezone</span>&nbsp;&nbsp;
          <span>Password</span>
        </b></div>
      </div>
      <ul class="styledform">
        <li class="form-row">
          <label class="styled-label" for="format">${_("File Type")}</label>
          <input type="radio" name="format" value="csv" checked=True/>CSV
          <input type="radio" name="format" value="tsv"/>TSV
        </li>
        <li class="form-row">
          <label class="styled-label" for="data">${_("Upload File")}</label>
          <input type="file" name="data" accept="csv" />
        </li>
      </ul>
      <div class="styledform-buttons">
        <button type="submit" class="button default">${_("Add")}</button>
        <button type="button" class="button default" onclick="$('#add-user-wrapper').empty()">${_("Cancel")}</button>
      </div>
    </form>
  </div>
</%def>

<%def name="orgInfo()">
  <%
    name = org.get("basic", {}).get("name", '')
  %>
  <form id='orginfo-form' class='ajax' action="/admin/org" method="POST" enctype="multipart/form-data">
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label" for="name">${_("Name")}</label>
        <input type="text" name="name"  value="${name}"/>
      </li>
      <li class="form-row">
        <label class="styled-label" for="dp">${_("Logo")}</label>
        <input type="file" name="dp" />
      </li>
    </ul>
    <div class="styledform-buttons">
        <button type="submit" class="button default">${_("Save")}</button>
    </div>
  </form>
</%def>

<%def name="admin_actions(userId, action='')">
  %if not action or action == 'unblocked':
    <li><button class="button default" onclick="$.post('/ajax/admin/block', 'id=${userId}')">${_("Block")}</button></li>
    <li><button class="button default" onclick="$$.removeUser.showRemoveUser('${userId}')">${_("Remove")}</button></li>
  %elif action == 'blocked':
    <li><button class="button" onclick="$.post('/ajax/admin/unblock', 'id=${userId}')">${_("Unblock")}</button></li>
    <li><button class="button default" onclick="$$.removeUser.showRemoveUser('${userId}')">${_("Remove")}</button></li>
  %elif action == 'deleted':
    <li>${_('User deleted from the network')}</li>
  %endif

</%def>

<%def name="confirm_remove_user()">
  <div class="ui-dialog-titlebar ui-widget-header ui-corner-all ui-helper-clearfix">
    <span class="ui-dialog-title" id="ui-dialog-title-dialog-form">Remove user</span>
  </div>
  <div style="color:red;font-size:12px;"> Caution! removing an user is irreversible process.
  User will not be able to login again. Access to apps created by the user will be revoked.
  </div>
  %if affectedGroups:
    <div class=''> User will be removed from following groups</div>
    % for groupId, name in affectedGroups:
      <span> <a href='/group?id=${groupId}'>${name}</a></span>
    %endfor
  %endif
  %if orgAdminNewGroups:
    <div class=''> This User is the only administrator for the following groups.  You will be made the administrator for these groups. </div>
    % for groupId, name in orgAdminNewGroups:
      <span> <a href='/group?id=${groupId}'>${name}</a></span>
    %endfor
  %endif
  %if apps:
    <div class=''> The following apps will be removed from the network.</div>
    % for appId in apps:
      <span> <a href='/apps?id=${appId}'>${apps[appId]['meta']['name']}</a></span>
    % endfor
  %endif
</%def>
