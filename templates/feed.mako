<!DOCTYPE HTML>
<%! from social import utils, _, __, plugins %>
<%! from social.logging import log %>

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
      <div class="titlebar center-header">
        <div id="title">${self.feed_title()}</div>
      </div>
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
        <div id="invite-people-block">
          ${self.invitePeopleBlock()}
        </div>
        <div id ="group-links" >
        </div>
        <div id="suggestions" >
            %if not script:
                ${self._suggestions()}
            %endif
        </div>
        <div id="feed-side-block-container"></div>
      </div>
      <div id="center">
        %if script:
        <div id="share-block">
          ${self.share_block()}
        </div>
        %endif
        <div id="feed-filter-bar" class="feed-filter-bar">
          %if not script:
            ${self.feedFilterBar(itemType)}
          %endif
        </div>
        <div id="user-feed" class="center-contents">
          %if not script or tmp_files:
            ${self.feed()}
          %endif
          <div id="foot-loader"></div>
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="feed_title()">
  <span class="middle title">${feedTitle}</span>
</%def>


<%def name="feedFilterBar(curItemType)">
  <%
    selectedPluginName = 'All Items'
    if curItemType in plugins and plugins[curItemType].hasIndex:
      selectedPluginName = plugins[curItemType].displayNames[1]
  %>
  <span class="feed-filter" onclick="$$.convs.showFilterMenu(event);">${_('Showing %s') % selectedPluginName} &#9660;</span>
  <ul style="display:none;">
    <%
      sortedItemTypes = sorted(plugins.values(), key=lambda x: x.position)
      indexed = [(plugin.displayNames[1], plugin.itemType) for plugin in sortedItemTypes if plugin.hasIndex]
    %>
    <li><a class="ff-item" data-ff="">
      <span class="icon feed-icon"></span>
      ${_('All Items')}
    </a></li>
    %for displayName, itemType in indexed:
      <li><a class="ff-item" data-ff="${itemType}">
        <span class="icon ${itemType}-icon"></span>
        ${displayName}
      </a></li>
    %endfor
  </ul>
</%def>


<%def name="invitePeopleBlock()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Invite people")}</div>
    <form id="invite-form" method="post" action="/people/invite" class="ajax" autocomplete="off" >
      <div class="input-wrap">
        <% domain = me.basic["emailId"].split('@')[1] %>
        <input type="email" name="email" id="invite-others" placeholder="someone@${domain}" required title="${_('Email')}"/>
      </div>
      <input type="hidden" name="from" value="sidebar"/>
      <input class="button" type="submit" id="submit" value="${_('Invite')}"/>
    </form>
  </div>
</%def>


<%def name="groupLinks()">
  %if groupId:
    <div class="sidebar-chunk">
    %if myId in groupAdmins:
      <div class="sidebar-title">${_("Manage")}</div>
    %else:
      <div class="sidebar-title">${_("Group")}</div>
    %endif
      <ul class="v-links">
        %if myId in groupAdmins:
          <li><a class="ajax" href="/groups/pending?id=${groupId}">${_('Pending Requests')}</a></li>
        %endif
        <li><a class="ajax" href="/groups/members?id=${groupId}">${_('Members List')}</a></li>
      </ul>
    </div>
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Invite your colleague to this group")}</div>
      <div class="invite-input-block">
        <form method="post" action="/groups/invite" class="ajax" autocomplete="off">
          <input type="hidden" name="user" id="group_invitee"/>
          <input type="hidden" value = ${groupId} name="id" />
          <div class="input-wrap">
            <input type="text" id="group_add_invitee" placeHolder="${_("Your colleague&#39;s name")}"/>
          </div>
          <input type="hidden" name="from" value="sidebar"/>
        </form>
      </div>
    </div>
  %endif
</%def>


## acl_button can initialize its default value through a select event, using hard-coded values until then
<%def name="acl_button(id, defaultVal, defaultLabel, defaultTooltip)">
  <input type="hidden" id="${id}" name="acl" value='${defaultVal}'/>
  %if script:
    <div id="${id}-wrapper">
      <button type="button" class="acl-button acl-text-button has-tooltip" id="${id}-button" onclick="$$.acl.showACL(event, '${id}');">
        <span>${_("With")}</span>
        <span class="acl-label" id="${id}-label">${defaultLabel}</span>
        <span class="acl-down-arrow">&#9660;</span>
        <div class="tooltip top-right"><span id="${id}-tooltip" class="tooltip-content">${defaultTooltip}</span></div>
      </button>
      <ul id="${id}-menu" class="acl-menu" style="display:none;">
        <li>
          <a class="acl-item" data-acl="org:${orgId}">
            <span class="acl-title">${_("Company")}</span>
            <div class="acltip">${_("Sent to your followers and company's feed")}</div>
          </a>
        </li>
        <li id="sharebar-acl-groups-sep" class="ui-menu-separator"></li>
      </ul>
    </div>
  %endif
</%def>

<%def name="share_block()">
  %if script:
    <div id="sharebar-disabler" class="sharebar-disabler"></div>
    <div id="sharebar-tabs" class="busy-indicator">
      <ul id="sharebar-links" class="h-links">
        <li>${_("Share:")}</li>
        <%
          sortedList  = sorted(plugins.values(), key=lambda x: x.position)
          supported = [(plugin.displayNames[0], plugin.itemType) for plugin in sortedList if plugin.position > 0]
          itemName, itemType = supported[0]
        %>
        <li><a data-ref="/feed/ui/share/${itemType}" id="publisher-${itemType}" class="ajax selected"><span class="sharebar-icon icon ${itemType}-icon"></span><span class="sharebar-text">${_(itemName)}</span></a></li>
        %for itemName, itemType in supported[1:]:
          <li><a data-ref="/feed/ui/share/${itemType}" id="publisher-${itemType}" class="ajax"><span class="sharebar-icon icon ${itemType}-icon"></span><span class="sharebar-text">${_(itemName)}</span></a></li>
        %endfor
      </ul>
    </div>
    <div id="sharebar-container">
      <form id="share-form" autocomplete="off" method="post" action="/item/new" class="ajax">
        <div id="sharebar"><%share_status()%></div>
        <div id="sharebar-attach-uploaded" class="uploaded-filelist"></div>
        <div id="sharebar-actions-wrapper">
          <ul id="sharebar-actions" class="h-links">
            <li>${acl_button("sharebar-acl", '{"accept":{"orgs":["%s"]}}'%orgId, "Company", "Sent to your followers and company's feed")}</li>
            <li>${widgets.button("sharebar-submit", "submit", "default", "Share", "Share")}</li>
          </ul>
          <span class="clear" style="display:block"></span>
        </div>
      </form>
      <div class="file-attach-wrapper">
        ${widgets.fileUploadButton('sharebar-attach')}
      </div>
      <div class="clear"></div>
    </div>
  %endif
</%def>

<%def name="share_status()">
  <textarea class="sb-input last" name="comment" placeholder="${_('What are you working on?')}" required title="${_('Status')}"></textarea>
  <input type="hidden" name="type" value="status"/>
</%def>

<%def name="share_question()">
  <textarea class="sb-input last" name="comment" placeholder="${_('What is your question?')}" required title="${_('Question')}"></textarea>
  <input type="hidden" name="type" value="question"/>
</%def>

<%def name="share_link()">
  <input type="text" class="sb-input" name="url" placeholder="${_('http://')}" required title="${_('URL')}"/>
  <textarea class="sb-input last" name="comment" placeholder="${_('Say something about the link')}"></textarea>
  <input type="hidden" name="type" value="link"/>
</%def>

<%def name="feed()">
  <%
    for convId in conversations:
      try:
        item.item_layout(convId)
      except Exception, e:
        log.err(e)
  %>
  %if not conversations:
    <span id="welcome-message">
      ${_("Welcome to ")}<a href='/'>Flocked.in</a>
      <ul >
        <li>${_("Share status updates, files, Ask questions, Create polls")}</li>
        <li><a href="#" onclick='$$.users.invite();'>${_("Invite")}</a>${_(" your colleagues")}</li>
        <li><a href='/people?type=all'>${_("Follow")}</a>${_(" your colleagues")}</li>
        <li><a href='#' onclick='$$.messaging.compose();'>${_("Send")}</a>${_(" private messages")}</li>
        <li><a href='#' onclick='$$.ui.addGroup();'>${_("Create")}</a>${_(" new groups. ")}<a href='/groups?type=allGroups'>${_("Join")}</a>${_(" Groups ")}</li>
        <li><a href='/settings'>${_("Update")}</a>${_(" your profile")}</li>
      </ul>
    </span>
  %endif
  %if nextPageStart:
    <% typ_filter = '&type=%s' %(itemType) if itemType else '' %>
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/feed/${feedId}/?start=${nextPageStart}${typ_filter}" data-ref="/feed/${feedId}?start=${nextPageStart}&more=1${typ_filter}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">${_("No more posts to show")}</div>
  %endif
</%def>

<%def name="customAudience()">
  <div class="ui-dlg-title">${_("Select your audience")}</div>
   <div class="" style="width:auto;background-color:#E8EEFA;padding:10px">
    <form>
      <input type="text" id="custom-audience-dlg-search" style="display:inline-block;font-size:11px;width:20em" class="input-wrap" placeholder="${_("Search among my friends and groups.")}"/>
      <input type="checkbox" id="allfriends" style="position:relative;top:3px"/><label for="allfriends">${_("Add all my friends")}</label>
      <div class="ui-list-meta" id="footer-info" style="padding-left: 0;"></div>
    </form>
   </div>
  <div class="ui-list ui-dlg-center">
    <div class="ui-listitem empty">
      <div class="ui-list-title"></div>
      <div class="ui-list-meta"></div>
    </div>
  </div>
</%def>

<%def name="_suggestions()">
    %if suggestions:
      <div class="sidebar-chunk">
        <div class="sidebar-title">${_("People you may know")}</div>
        %for userId in suggestions:
          <div class="suggestions-user">
            <div class="users-avatar">
              <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
              % if avatarURI:
                <img src="${avatarURI}" style="max-height:32px; max-width:32px"></img>
              % endif
            </div>
            <div class="users-details" style="margin-left:36px">
              <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
              <div class="user-details-title">${entities[userId].basic.get("jobTitle", '')}</div>
              <div >
                <ul id="user-actions-${userId}" class="middle user-actions h-links">
                  <li><button class="button" onclick="$.post('/ajax/profile/follow', 'id=${userId}')"><span class="button-text" style="font-size:11px;">${_("Follow")}</span></button></li>
                </ul>
              </div>
            </div>
          </div>
        %endfor
      </div>
    %endif
</%def>
