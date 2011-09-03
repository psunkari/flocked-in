<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from twisted.python import log %>

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
        <div id="suggestions" >
            %if not script:
                ${self._suggestions()}
            %endif
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
          %if not script or tmp_files:
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
    <form id="invite-form" method="post" action="/people/invite" class="ajax" autocomplete="off" >
      <div class="input-wrap">
        <% domain = me["basic"]["emailId"].split('@')[1] %>
        <input type="email" name="email" id="invite-others" placeholder="someone@${domain}" required title="${_('Email')}"/>
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
      <div class="sidebar-title">${_("Manage")}</div>
    %else:
      <div class="sidebar-title">${_("Group")}</div>
    %endif
      <ul class="v-links">
        %if myKey in groupAdmins:
          <li><a class="ajax" href="/groups/pending?id=${groupId}">${_('Pending Requests')}</a></li>
        %endif
        <li><a class="ajax" href="/groups/members?id=${groupId}">${_('Members List')}</a></li>
      </ul>
    </div>
    <div class="invite-input-block">
        <div class="sidebar-chunk">
            <div class="sidebar-title">${_("Invite your colleague to this group")}</div>
            <form method="post" action="/groups/invite" class="ajax" autocomplete="off">
              <input type="hidden" name="invitee" id="group_invitee"/>
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
      <button class="acl-button acl-text-button has-tooltip" id="${id}-button" onclick="$$.acl.showACL(event, '${id}');">
        <span>${_("With")}</span>
        <span id="${id}-label">${defaultLabel}</span>
        <span class="acl-down-arrow">&#9660;</span>
        <div class="tooltip bottom-right"><span id="${id}-tooltip" class="tooltip-content">${defaultTooltip}</span></div>
      </button>
      <ul id="${id}-menu" class="acl-menu" style="display:none;">
        <li>
          <a class="acl-item has-tooltip" _acl="org:${orgKey}">
            <div class="icon"></div>
            <span class="acl-title">${_("Company")}</span>
            <div class="tooltip left"><span class="tooltip-content">${_("Notifies only your friends and followers")}</span></div>
          </a>
        </li>
        <li>
          <a class="acl-item has-tooltip" _acl="friends">
            <div class="icon"></div>
            <span class="acl-title">${_("Friends")}</span>
            <div class="tooltip left"><span class="tooltip-content">${_("Notifies all your friends")}</span></div>
          </a>
        </li>
        <li id="sharebar-acl-groups-sep" class="ui-menu-separator"></li>
        <li id="sharebar-acl-custom-sep" class="ui-menu-separator"></li>
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
    <form id="share-form" autocomplete="off" method="post" action="/item/new" class="ajax" >
      <div id="sharebar">
            <div class="input-wrap">
            <textarea name="comment" placeholder="${_('What are you working on?')}" required title="${_('Comment')}"></textarea>
           </div>
          <input type="hidden" name="type" value="status"/>
      </div>
      <div id="sharebar-attach-uploaded" class="uploaded-filelist"></div>
      <div id="sharebar-actions-wrapper">
        <ul id="sharebar-actions" class="h-links">
          <li>${acl_button("sharebar-acl", '{"accept":{"orgs":["%s"]}}'%orgKey, "Company", "Notifies only your friends and followers")}</li>
          <li>${widgets.button("sharebar-submit", "submit", "default", "Share", "Share")}</li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
    <div class="file-attach-wrapper">
      ${widgets.fileUploadButton('sharebar-attach')}
    </div>
    <div class="clear"></div>
  %endif
</%def>

<%def name="share_status()">
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('What are you working on?')}" required title="${_('Status')}"/>
  </div>
  <input type="hidden" name="type" value="status"/>
</%def>

<%def name="share_question()">
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('What is your question?')}" required title="${_('Question')}"/>
  </div>
  <input type="hidden" name="type" value="question"/>
</%def>

<%def name="share_link()">
  <div class="input-wrap">
    <textarea name="url" placeholder="${_('http://')}" required title="${_('URL')}"/>
    </div>
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('Say something about the link')}" />
  </div>
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
      ${_("Welcome to ")}<a href='/'>Flocked.in.</a>
      <ul >
        <li>${_("Share status updates, files, Ask questions, Create polls")}</li>
        <li><a href='/people/invite'>${_("Invite")}</a>${_(" your colleagues.")}</li>
        <li><a href='/people?type=all'>${_("Follow")}</a>${_(" your colleagues, ")}<a href='/people?type=all'>${_("Add")}</a>${_(" them as Friends")}</li>
        <li><a href='/messages'>${_("Send")}</a>${_(" private messages")}</li>
        <li><a href='/groups/create'>${_("Create")}</a>${_(" new groups. ")}<a href='/groups?type=allGroups'>${_("Join")}</a>${_(" Groups ")}</li>
        <li><a href='/settings'>${_("Update")}</a>${_(" your profile")}</li>
      </ul>
    </span>
  %endif
  %if nextPageStart:
    <% typ_filter = '&type=%s' %(itemType) if itemType else '' %>
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/feed?start=${nextPageStart}&id=${feedId}" _ref="/feed/more?start=${nextPageStart}&id=${feedId}${typ_filter}">${_("Fetch older posts")}</a></div>
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
          <div style="margin-top: 5px">
            <div class="users-avatar">
              <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
              % if avatarURI:
                <img src="${avatarURI}" height='32' width='32'></img>
              % endif
            </div>
            <div class="users-details" style="margin-left:36px">
              <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
              <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
              <div >
                <ul id="user-actions-${userId}" class="middle user-actions h-links">
                %if userId not in relations.friends:
                  %if not relations.pending or userId not in relations.pending:
                    <button class="button" onclick="$.post('/ajax/profile/friend', 'id=${userId}&action=add')"><span class="button-text" style="font-size:11px">${_("Add as Friend")}</span></button>
                  %endif
                %endif
                %if userId not in relations.subscriptions and userId not in relations.friends:
                  <button class="button" onclick="$.post('/ajax/profile/follow', 'id=${userId}')"><span class="button-text" style="font-size:11px;">${_("Follow")}</span></button>
                %endif
                </ul>
              </div>
            </div>
          </div>
        %endfor
      </div>
    %endif
</%def>
