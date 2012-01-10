<!DOCTYPE HTML>
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="profile" file="profile.mako"/>
<%namespace name="people" file="people.mako"/>
<%namespace name="group_feed" file="group-feed.mako"/>

##
##

<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, id):
      cls = "sidemenu-selected" if id == menuId else ''
      return """<li>
                  <a href="%(link)s" class="ajax busy-indicator %(id)s-sideitem %(cls)s">
                    <span class="sidemenu-icon %(id)s-icon"></span>
                    <span class="sidemenu-text">%(text)s</span>
                  </a>
                </li>
              """ % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
       ${navMenuItem("/group?id=%s"%(groupId), _("Back to Group"), "back")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      %if myId in entities[groupId]['admins']:
        ${navMenuItem("/groupsettings?id=%s"%(groupId), _("Settings"), "settings")}
        ${navMenuItem("/groups/members?id=%s"%(groupId), _("Manage Members"), "members")}
        ${navMenuItem("/groups/pending?id=%s"%(groupId), _("Pending Requests"), "pending")}
        ${navMenuItem("/groups/banned?id=%s"%(groupId), _("Banned Members"), "banned")}
      %else:
        ${navMenuItem("/groups/members?id=%s"%(groupId), _("Members"), "members")}
      %endif
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
        <div id="titlebar" class="titlebar">
          ${self.titlebar()}
        </div>
        <div id="add-user-wrapper"></div>
      </div>
      <div id="right">
      </div>
      <div id="center">
        <div class="center-contents" id="center-content">
          <div id="groups-wrapper" class="paged-container">
            %if not script:
              ${self.edit_group()}
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

<%def name="titlebar()" >
  %if heading:
    <span class="middle title">${heading}</span>
  %else:
    <span class="middle title">${_('Groups')}</span>
  %endif
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

<%def name="edit_group()">
  <%
    groupName = entities[groupId]["basic"].get("name", 'Group Name').replace('"', "&quot;")
    desc = entities[groupId]["basic"].get("desc", '')
    access = entities[groupId]["basic"].get("access", '')
  %>

  <form id="group-form" action="/ajax/groupsettings/edit" method="post" enctype="multipart/form-data">
    <ul class="styledform">
      <li class="form-row">
          <label class="styled-label" for="name">${_('Group Name')}</label>
          <input type="text" id="groupname" name="name" required title="${_('Group Name')}" value="${_(groupName)}"/>
      </li>
      <li class="form-row">
          <label class="styled-label" for="desc">${_('Description')}</label>
          <textarea class="input-wrap" id="desc" name="desc"> ${_(desc)}</textarea>
      </li>
      <li class="form-row">
          <label class="styled-label">&nbsp;</label>
          %if access == 'open':
            <label><input type="checkbox" id="access" name="access" value="closed"/>${_("Membership requires administrator approval")}</label>
          %else:
            <label><input type="checkbox" id="access" name="access" value="closed" checked="checked"/>${_("Membership requires administrator approval")}</label>
          %endif
      </li>
      <li class="form-row">
          <label class="styled-label" for="dp">${_("Group Logo")}</label>
          <input type="file" id="dp" name="dp" accept="image/jpx, image/png, image/gif"/>
    </ul>
    <div class="styledform-buttons">
      <input type="submit" name="groupEdit_submit" value="${_("Save")}" class="button default"/>
    </div>
    <input type="hidden" value = ${groupId} name="id" />
  </form>
</%def>
