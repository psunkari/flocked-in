<%! from social import utils, _, __, plugins %>
<%! from pytz import common_timezones %>
<!DOCTYPE HTML>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="people" file="people.mako"/>
<%namespace name="tagsmako" file="tags.mako"/>
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
      ${navMenuItem("/admin/org", _("Organization"), "org")}
      ${navMenuItem("/admin/tags", _("Preset Tags"), "tags")}
      ${navMenuItem('/admin/keywords', _("Monitored Keywords"), "keywords")}
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
      <div class="titlebar center-header">
          %if title:
            <span class="middle title">${_(title)}</span>
          %else:
            <span class="middle title">${_("Admin Console")}</span>
          %endif
          %if script:
            %if not menuId or menuId == 'users':
              <button onclick="$$.users.add();" class="button title-button">${_('Add Users')}</button>
            %endif
          %endif
      </div>
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
      </div>
      <div id="center">
        <div class="center-contents">
          %if not menuId or menuId == 'users':
            <div id="users-view" class="viewbar">
              %if not script:
                <% option = 'all' if not viewType else viewType %>
                ${viewOptions(option)}
              %endif
            </div>
          %endif
          <div id="content">
            %if not script and viewType:
              %if viewType == "org":
                <% self.orgInfo() %>
              %elif viewType == "tags":
                <% self.list_tags() %>
              %else:
                <% self.list_users() %>
              %endif
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
  <div id='list-users' class="paged-container">
    %if viewType == 'blocked':
      ${list_blocked()}
    %else:
      ${people.listUsers(showBlocked=True)}
    %endif
  </div>
  <div id="people-paging" class="pagingbar">
    %if viewType == 'all':
      ${paging()}
    %elif viewType == 'blocked' and entities:
      ${paging(viewType)}
    %endif
  </div>
</%def>


<%def name="addUsers()">
  <% myTimezone  = me.get("basic", {}).get("timezone", "") %>
  <div class='ui-dlg-title'>${_('Add Users')}</div>
  <div class="tabs" style="margin:auto">
    <ul class="tablinks h-links">
      <li><a style="cursor:pointer" class="selected"
             onclick="$('#add-user-block').toggle();
                      $('#add-users-block').toggle();
                      $(this).toggleClass('selected');
                      $('#add-user-form-id').val('add-user-form');
                      $(this).parent().siblings().children().toggleClass('selected')">
            ${_("New User")}
          </a>
      </li>
      <li><a style="cursor:pointer" class=""
             onclick="$('#add-users-block').toggle();
                      $('#add-user-block').toggle();
                      $(this).toggleClass('selected');
                      $('#add-user-form-id').val('add-users-form');
                      $(this).parent().siblings().children().toggleClass('selected')">
            ${_("Multiple Users")}
          </a>
      </li>
  </div>
  <input id="add-user-form-id" type="hidden" value="add-user-form" />
  <div id="add-user-block">
    <form id="add-user-form" class="ajax" action="/admin/add" method="POST" enctype="multipart/form-data" autocomplete="off">
      <ul class="dlgform">
        <li class="form-row">
          <label class="styled-label" for="name">${_("Display Name")}</label>
          <input type="text" name="name" required="" title="${_("Display Name")}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="email">${_("Email Address")}</label>
          <input type="email" name="email" required="" title="${_("Email Address")}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="jobTitle">${_("Job Title")}</label>
          <input type="text" name="jobTitle" required="" title="${_("Job Title")}"/>
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
          <input type="password" name="passwd" required="" title="${_("Password")}"/>
        </li>
      </ul>
      <input id="add-user-form-submit" type="submit" style="display:none;" />
    </form>
  </div>
  <div id="add-users-block" style="display:none">
    <form id="add-users-form" action="/admin/add" method="POST" enctype="multipart/form-data" autocomplete="off">
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
      <ul class="dlgform">
        <li class="form-row">
          <label class="styled-label" for="format">${_("File Type")}</label>
          <input type="radio" name="format" value="csv" checked=True/>CSV
          <input type="radio" name="format" value="tsv"/>TSV
        </li>
        <li class="form-row">
          <label class="styled-label" for="data">${_("Upload File")}</label>
          <input type="file" name="data" accept="csv" size="15" required=""/>
        </li>
      </ul>
      <input id="add-users-form-submit" type="submit" style="display:none;" />
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
    <li><button class="button" onclick="$.post('/ajax/admin/block', 'id=${userId}')">${_("Block")}</button></li>
    <li><button class="button" onclick="$$.users.remove('${userId}')">${_("Remove")}</button></li>
  %elif action == 'blocked':
    <li><button class="button" onclick="$.post('/ajax/admin/unblock', 'id=${userId}')">${_("Unblock")}</button></li>
    <li><button class="button" onclick="$$.users.remove('${userId}')">${_("Remove")}</button></li>
  %elif action == 'deleted':
    <li>${_('User deleted from the network')}</li>
  %endif

</%def>

<%def name="confirm_remove_user()">
  <div class='ui-dlg-title'>${_('Remove user ')} &ndash; ${entities[userId]["basic"]["name"]}</div>
  <div class="dlgform ui-dlg-center" style="font-size: 12px;max-height:250px;">
    <p style="margin:0px">
      User removal is an irreversible process. Instead you can <strong>Block</strong> a user to disable login to the network temporarily.
    </p>
    <p>
      %if apps or orgAdminNewGroups:
        If you proceed with removing ${utils.userName(userId, entities[userId])}, the following actions will happen:
        <ol>
          %if apps:
            <li>
              Access to following applications created by ${utils.userName(userId, entities[userId])} will be revoked.
              </br>
              <%
                links = []
                for appId in apps:
                  links.append("""<a href='/apps?id=%s'>%s</a>""" %(appId, apps[appId]['meta']['name']))
              %>
              ${", ".join(links)}
            </li>
          %endif
          %if orgAdminNewGroups:
            <li>
              You will become the administrator for the following groups,
              for which ${utils.userName(userId, entities[userId])} is the only administrator:
              </br>
              <%
                links = []
                for groupId, name in orgAdminNewGroups:
                  links.append("""<a target="_blank" href='/group?id=%s'>%s</a>""" %(groupId, name))
              %>
              ${", ".join(links)}
            </li>
          %endif
        </ol>
      %endif
    </p>
    <p>
      <em>Note</em>: Content created by the user will not be removed in this process.
    </p>
  </div>
</%def>


<%def name="list_tags()">
  <ul class="styledform">
    <li class="form-row">
      <label class="styled-label">${_("Tags")}</label>
      <div class="styledform-helpwrap">
        <form method="post" action="/admin/tags/add" class="ajax" autocomplete="off">
          <div class="styledform-inputwrap" id="expertise-input">
            <input type="textarea" name="tag" id="expertise-textbox" value="" required title="Tags"  autofocus/>
            <input type="submit" id="expertise-add" class="button" value="Add" style="margin:0px;"/>
          </div>
        </form>
        <div>Enter comma separated tags. Each tag can only have alphabet, numerals or hyphen and cannot exceed 50 characters.</div>
      </div>
    </li>
  </ul>
  <div class='center-title'></div>
  <div  id='tags-container' class="tl-wrapper">
    %for tagId in tagsList:
      ${tagsmako._displayTag(tagId, False, True)}
    %endfor
  </div>
</%def>


<%def name="_displayKeyword(keyword)">
  <% encodedKeyword = utils.encodeKey(keyword) %>
  <div id='keyword-${encodedKeyword}'>
    <div class='tl-item' id='keyword-${encodedKeyword}'>
      <div class='tl-avatar large-icon large-keyword'></div>
      <div class='tl-details'>
        <div class='tl-name'><a href="/admin/keyword-matches?keyword=${keyword}">${keyword}</a></div>
        <button class='company-remove ajaxpost' title='' data-ref='/admin/keywords/delete?keyword=${encodedKeyword}' ></button>
      </div>
    </div>
  </div>
</%def>


<%def name="_keywords(keywords)">
  <%
    for item in keywords.keys():
      _displayKeyword(item)
  %>
</%def>

<%def name="listKeywords()">
  <ul class="styledform">
    <li class="form-row">
      <label class="styled-label">${_('Keywords')}</label>
      <div class="styledform-helpwrap">
        <form method="post" action="/admin/keywords/add" class="ajax" autocomplete="off">
          <div class="styledform-inputwrap" id='expertise-input'>
            <input type="textarea" name="keywords" id="expertise-textbox" value="" required title="Keywords" />
            <input type="submit" id="expertise-add" class="button" value="Add" style="margin:0px;"/>
          </div>
        </form>
        <div>Enter comma separated words to be monitored. Each word can only have alphabet, numerals or hyphen and cannot exceed 50 characters.</div>
      </div>
    </li>
  </ul>
  <div class='center-title'></div>
  <div  id='tags-container' class="tl-wrapper">
    <% _keywords(keywords) %>
  </div>
</%def>
