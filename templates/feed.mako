<%! from social import utils, _, __, plugins %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%inherit file="base.mako"/>

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
        <div id="invite-ppl">
            <form method="post" action="/register" class="ajax">
                <input type="text" name="emailId"/><br/>
                <input type="submit" id="submit" value="${_('Submit')}"/>
            </form>
        </div>
        <div id ="admin" >
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <div id="title"><span class="middle title">${self.feed_title()}</span></div>
          </div>
          <div id="share-block">
            %if not script:
              ${self.share_block()}
            %endif
          </div>
        </div>
        <div id="user-feed" class="center-contents">
          %if not script:
            ${self.feed()}
          %endif
          <div id="foot-loader"></div>
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="feed_title()">
  <span class="middle title">${feedTitle}</span>
</%def>


<%def name="groupAdminLinks()">
  <div class="sidebar-title">${_("Manage")}</div>
    <ul class="v-links">
      <li><a class="ajax" href="/groups/invite?id=${groupId}">Invite</a></li>
      <li><a class="ajax" href="/groups/admin?id=${groupId}">Pending Requests</a></li>
      <li><a class="ajax" href="/groups/members?id=${groupId}">Members </a></li>
    </ul>
</%def>


<%def name="groupMembersLinks()">
  <div class="sidebar-title">${_("")}</div>
    <ul class="v-links">
      <li><a class="ajax" href="/groups/members?id=${groupId}">Members </a></li>
    </ul>
</%def>


<%def name="acl_button(id, defaultVal, defaultLabel)">
  <input type="hidden" id="${id}" name="acl" value="${defaultVal}"/>
  %if script:
    <div id="${id}-wrapper">
      <input type="button" class="acl-button" id="${id}-label"
             value="${defaultLabel}" onclick="$$.acl.showACL(event, '${id}');"/>
      <ul id="${id}-menu" class="acl-menu" style="display:none;">
        <li><a class="acl-item" _acl="public"><div class="icon"></div>${_("Public")}</a></li>
        <li><a class="acl-item" _acl="org:${orgKey}"><div class="icon"></div>${_("Company")}</a></li>
        <li><a class="acl-item" _acl="friends"><div class="icon"></div>${_("Friends")}</a></li>
        <li class="ui-menu-separator" id="${id}-groups-sep"></li>
        <li class="ui-menu-separator"></li>
        <li><a class="acl-item" _acl="custom"><div class="icon"></div>${_("Custom")}</a></li>
      </ul>
    </div>
  %endif
</%def>

<%def name="share_block()">
  %if script:
    <div id="sharebar-tabs" class="busy-indicator">
      <ul id="sharebar-links" class="h-links">
        <li>${_("Share:")}</li>
        <%
          supported = [(name.capitalize(), name) for name in plugins if plugins[name].position > 0]
          itemName, itemType = supported[0]
        %>
        <li><a _ref="/feed/share/${itemType}" id="publisher-${itemType}" class="ajax selected"><span class="sharebar-icon icon ${itemType}-icon"></span><span class="sharebar-text">${_(itemName)}</span></a></li>
        %for itemName, itemType in supported[1:]:
          <li><a _ref="/feed/share/${itemType}" id="publisher-${itemType}" class="ajax"><span class="sharebar-icon icon ${itemType}-icon"></span><span class="sharebar-text">${_(itemName)}</span></a></li>
        %endfor
      </ul>
    </div>
    <form id="share-form" class="ajax" autocomplete="off" method="post" action="/item/new">
      <div id="sharebar"></div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          <li>${acl_button("sharebar-acl", "{accept:{org:[%s]}}"%orgKey, "Company")}</li>
          <li>${widgets.button("sharebar-submit", "submit", "default", None, "Share")}</li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
  %endif
</%def>

<%def name="share_status()">
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('What are you currently working on?')}"/>
  </div>
  <input type="hidden" name="type" value="status"/>
</%def>

<%def name="feed()">
  %for convId in conversations:
    ${item.item_layout(convId)}
  %endfor
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" _ref="/feed?start=${nextPageStart}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
  %endif
</%def>
