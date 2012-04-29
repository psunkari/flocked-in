<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social.logging import log %>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%namespace name="feed_mako" file="feed.mako"/>
<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="group-summary">
        %if not script:
          ${self.summary()}
        %endif
      </div>
      <div id='profile-center-right'>
        <div id="right">
          <div id ="group-admins">
            %if not script:
              ${self.groupAdmins()}
            %endif
          </div>
          <div id ="group-links" >
            %if not script:
              ${self.groupLinks()}
            %endif
          </div>
          <div id ="group-files" ></div>
          <div id ="group-events" ></div>
          <div id ="feed-side-block-container"></div>
        </div>
        <div id="center">
          <div id='feed-filter-bar' class='feed-filter-bar'>
            %if not script:
              ${feed_mako.feedFilterBar(itemType)}
            %endif
          </div>
          <div class='center-contents' id="user-feed">
            %if not script or tmp_files:
              ${self.feed()}
            %endif
            <div id="foot-loader"></div>
          </div>
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="group_actions(groupId)">
  %if entities and ('GI:%s'%(groupId) in pendingConnections and entities[groupId].basic["access"]=="open"):
    <button class="acl-button button" onclick="$$.ui.showPopup(event)">${_("Respond to Group Invitation")}</button>
    <ul class="acl-menu" style="display:none;">
        <li>
          <a class="acl-item" _acl="public" onclick="$.post('/ajax/groups/subscribe', 'id=${groupId}&action=accept')">${_("Accept")}</a>
        </li>
        <li>
          <a class="acl-item" _acl="friends" onclick="$.post('/ajax/groups/cancel', 'id=${groupId}&action=reject')">${_("Reject")}</a>
        </li>
    </ul>
  %elif 'GO:%s'%(groupId) in pendingConnections:
    <button class="button disabled"><span class="button-text">${_('Request Pending')}</span></button>
  %elif groupId not in myGroups:
    <button class="button default" onclick="$.post('/ajax/groups/subscribe', 'id=${groupId}')"><span class="button-text">${('Join')}</span></button>
  %else:
    <button class="button" onclick="$.post('/ajax/groups/unsubscribe', 'id=${groupId}')"><span class="button-text">${('Leave')}</span></button>
    %if me.id in groupFollowers[groupId]:
      <button class="button" onclick="$.post('/ajax/groups/unfollow', 'id=${groupId}')"><span class="button-text">${('Stop Following')}</span></button>
    %else:
      <button class="button default" onclick="$.post('/ajax/groups/follow', 'id=${groupId}')"><span class="button-text">${('Follow')}</span></button>
    %endif
  %endif
</%def>

<%def name="summary()">
  <% avatarURI = utils.groupAvatar(groupId, entities[groupId], "large") %>
  <div class="titlebar center-header">
    %if avatarURI:
      <div id="useravatar" class="avatar" style="background-image:url('${avatarURI}')"></div>
    %endif
    <div id="title">
      <span class="middle title" id="group-name">${entities[groupId].basic['name']}</span>
      <ul id="group-actions-${groupId}" class="middle user-actions h-links">
        ${self.group_actions(groupId)}
      </ul>
    </div>
  </div>
  <div id='userprofile'>
    <div class="summary-block">
      <div class='subtitle summary-line' >
        <%
          basic = entities[groupId].basic
          membership = "Membership requires approval, " if basic["access"] == "closed" else ""
          posting = "Non-members can post, " if basic.get("writable", '') == "open" else "Only members can post, "
          readable = "Non-members can access." if basic.get("readable", '') == "open" else "Only members can access."
        %>
        <span id="group-type">${"%s&nbsp;%s&nbsp;%s" % (membership, posting, readable)}</span>
      </div>
      %if entities[groupId].basic.has_key('desc'):
        <span class="summary-item" id="group-desc">${entities[groupId].basic['desc']}</span>
      %endif
      <div id="group-share-block"></div>
    </div>
  </div>
</%def>

<%def name="groupFiles()">
</%def>

<%def name="groupLinks()">
  %if groupId:
    <div class="sidebar-chunk">
      %if myId in getattr(entities[groupId], "admins", {}):
        <div class="sidebar-title">${_("Manage Group")}</div>
      %else:
        <div class="sidebar-title">${_("Group")}</div>
      %endif
      <ul class="v-links">
        %if myId in getattr(entities[groupId], "admins", {}):
          %if entities[groupId].basic['access'] == 'closed':
            <li><a class="ajax" href="/groups/pending?id=${groupId}">${_('Pending Requests')}</a></li>
          %endif
          <li><a class="ajax" href="/groups/edit?id=${groupId}">${_('Edit Group Settings')}</a></li>
          <li><a class="ajax" href="/groups/members?id=${groupId}&managed=manage">${_('Manage Members')}</a></li>
        %else:
          <li><a class="ajax" href="/groups/members?id=${groupId}">${_('Members')}</a></li>
        %endif
      </ul>
    </div>
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Invite your colleague to this group")}</div>
      <div class="invite-input-block">
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


<%def name="feed()">
  %if not isMember:
    <span id="welcome-message">
      <%
        basic = entities[groupId].basic
        writable = True if basic.get("writable", '') == "open" else False
        readable = True if basic.get("readable", '') == "open" else False
      %>
      <div style="padding:20px; border:1px solid #c40000; margin: 40px 0;border-radius: 10px;">
        ${_("The contents on this group are visible only to it's members.")}
      </div>
    </span>
  %elif conversations:
    <%
      for convId in conversations:
        try:
          item.item_layout(convId)
        except Exception, e:
          log.err(e)
    %>
    %if nextPageStart:
      <% typ_filter = '&type=%s' %(itemType) if itemType else '' %>
      <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" data-ref="/group/more?start=${nextPageStart}&id=${groupId}${typ_filter}">${_("Fetch older posts")}</a></div>
    %else:
      <div id="next-load-wrapper">${_("No more posts to show")}</div>
    %endif

  %elif not conversations:
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
</%def>

<%def name="groupAdmins()">
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Administrators")}</div>
      <ul class="v-links">
        % if getattr(entities[groupId], 'admins', {}):
          % for admin in entities[groupId].admins.keys()[:4]:
            <li>${utils.userName(admin, entities[admin])}</li>
          %endfor
        %endif
      </ul>
  </div>
</%def>
