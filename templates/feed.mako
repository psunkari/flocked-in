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
        <div id="invite-people-block">
          ${self.invitePeopleBlock()}
        </div>
        <div id ="group-links" >
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <div id="title">${self.feed_title()}</div>
          </div>
          %if script:
          <div id="share-block">
            ${self.share_block()}
          </div>
          %endif
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


<%def name="invitePeopleBlock()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Invite people")}</div>
    <form method="post" action="/people/invite" class="ajax" autocomplete="off" >
      <div class="input-wrap">
        <input type="text" name="email"/>
      </div>
      <input type="hidden" name="from" value="sidebar"/>
      <input class="button" type="submit" id="submit" value="${_('Submit')}"/>
    </form>
  </div>
</%def>


<%def name="groupLinks()">
  %if groupId:
    <div class="sidebar-chunk">
    %if myKey in groupAdmins:
      <div class="sidebar-title">${_("Manage group")}</div>
    %else:
      <div class="sidebar-title">${_("Group")}</div>
    %endif
      <ul class="v-links">
        %if myKey in groupAdmins:
          <li><a class="ajax" href="/groups/pending?id=${groupId}">${_('Pending requests')}</a></li>
          <li><a class="ajax" href="/groups/invite?id=${groupId}">${_('Invite more people')}</a></li>
        %endif
        <li><a class="ajax" href="/groups/members?id=${groupId}">${_('Members list')}</a></li>
      </ul>
    </div>
  %endif
</%def>


<%def name="acl_button(id, defaultVal, defaultLabel)">
  <input type="hidden" id="${id}" name="acl" value="${defaultVal}"/>
  %if script:
    <div id="${id}-wrapper">
      <button class="acl-button button" id="${id}-label" onclick="$$.acl.showACL(event, '${id}');">${defaultLabel}</button>
      <ul id="${id}-menu" class="acl-menu" style="display:none;">
##      <li><a class="acl-item" _acl="public"><div class="icon"></div>${_("Public")}</a></li>
        <li><a class="acl-item" _acl="org:${orgKey}"><div class="icon"></div>${_("Company")}</a></li>
        <li><a class="acl-item" _acl="friends"><div class="icon"></div>${_("Friends")}</a></li>
##      <li class="ui-menu-separator" id="${id}-groups-sep"></li>
##      <li class="ui-menu-separator"></li>
##      <li><a class="acl-item" _acl="custom"><div class="icon"></div>${_("Custom")}</a></li>
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
          sortedList  = sorted(plugins.values(), key=lambda x: x.position)
          supported = [(plugin.itemType.capitalize(), plugin.itemType) for plugin in sortedList if plugin.position > 0]
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

<%def name="share_question()">
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('What is your question?')}"/>
  </div>
  <input type="hidden" name="type" value="question"/>
</%def>

<%def name="share_link()">
  <div class="input-wrap">
    <textarea name="url" placeholder="${_('http://')}"/>
    </div>
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('Say something about the link')}"/>
  </div>
  <input type="hidden" name="type" value="link"/>
</%def>

<%def name="feed()">
  %for convId in conversations:
    ${item.item_layout(convId)}
  %endfor
  %if nextPageStart:
    <% typ_filter = '&type=%s' %(itemType) if itemType else '' %>
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/feed?start=${nextPageStart}&id=${feedId}" _ref="/feed/more?start=${nextPageStart}&id=${feedId}${typ_filter}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
  %endif
</%def>
