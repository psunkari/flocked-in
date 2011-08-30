<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>
<%! from pytz import common_timezones %>
<%! from twisted.python import log %>
<%! import re, datetime %>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

##
## Profile is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        %if editProfile:
            ${self.edit_profile_nav_menu()}
        %else:
            ${self.nav_menu()}
        %endif
      </div>
    </div>
    <div id="center-right">
      <div id="right">
        <div id="user-me">
          %if not script:
            ${self.user_me()}
          %endif
        </div>
        <div id="user-groups">
          %if not script:
            ${self.user_groups()}
          %endif
        </div>
        <div id="user-subscriptions">
          %if not script:
            ${self.user_subscriptions()}
          %endif
        </div>
        <div id="user-followers">
          %if not script:
            ${self.user_followers()}
          %endif
        </div>
        <div id="user-subactions">
          %if not script:
            ${self.user_subactions(userKey)}
          %endif
        </div>
      </div>
      <div id="center">
        <div id="profile-summary" class="center-header">
          %if not script:
            ${self.summary()}
          %endif
        </div>
        <div class="center-contents">
          <div id="profile-tabs" class="tabs busy-indicator">
          %if not script:
            ${self.tabs()}
          %endif
          </div>
          <div id="profile-content">
          %if not script:
            ${self.content()}
          %endif
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>


##
## Functions for rendering content
##
<%def name="user_me()">
  %if myKey != userKey:
  %if len(commonFriends) > 0:
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Common Friends")}</div>
    <ul class="v-links">
    %for user in commonFriends:
      <li><a class="ajax" href="/profile?id=${user}">${rawUserData[user]['name']}</a></li>
    %endfor
    </ul>
  </div>
  %endif
  %endif
</%def>

<%def name="user_subscriptions()">
  %if len(subscriptions) > 0:
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Following")}</div>
    <ul class="v-links">
    %for user in subscriptions:
      <li><a class="ajax" href="/profile?id=${user}">${rawUserData[user]['name']}</a></li>
    %endfor
    </ul>
  </div>
  %endif
</%def>

<%def name="user_followers()">
  %if len(followers) > 0:
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Followers")}</div>
    <ul class="v-links">
    %for user in followers:
      <li><a class="ajax" href="/profile?id=${user}">${rawUserData[user]['name']}</a></li>
    %endfor
    </ul>
  </div>
  %endif
</%def>

<%def name="user_groups()">
  %if len(userGroups) > 0:
  <div class="sidebar-chunk">
    <div class="sidebar-title">${_("Groups")}</div>
    <ul class="v-links">
    %for group in userGroups:
      <li><a class="ajax" href="/feed?id=${group}">${rawGroupData[group]['name']}</a></li>
    %endfor
    </ul>
  </div>
  %endif
</%def>

<%def name="user_subactions(userKey, renderWrapper=True)">
  %if myKey != userKey:
    %if renderWrapper:
      <div class="sidebar-chunk">
      <ul id="user-subactions-${userKey}" class="middle user-subactions v-links">
    %endif
    %if relations.pending.get(userKey) == 0:
      <li><a href="/profile/friend?id=${userKey}&action=cancel"
             onclick="$.post('/ajax/profile/friend', 'id=${userKey}&action=cancel'); $.event.fix(event).preventDefault();">
            ${_("Cancel Friend Request")}
          </a>
      </li>
    %endif
    <li><a href="/profile/block?id=${userKey}"
           onclick="$.post('/ajax/profile/block', 'id=${userKey}'); $.event.fix(event).preventDefault();">
          ${_("Block User")}
        </a>
    </li>
    <li><a href="/profile/review?id=${userKey}"
           onclick="$.post('/ajax/profile/review', 'id=${userKey}'); $.event.fix(event).preventDefault();">
          ${_("Request Admin Review")}
        </a>
    </li>
    %if renderWrapper:
      </ul>
      </div>
    %endif
  %endif
</%def>

<%def name="summary()">
  <% avatarURI = utils.userAvatar(userKey, user, "large") %>
  %if avatarURI:
     <div id="useravatar" class="avatar" style="background-image:url('${avatarURI}')"></div>
  %endif
  <div id="userprofile">
    <div class="titlebar">
      <div>
        <span class="middle title">${user['basic']['name']}</span>
        <ul id="user-actions-${userKey}" class="middle user-actions h-links">
          ${user_actions(userKey, True)}
        </ul>
      </div>

      <div class="subtitle" class="summary-line">
      %if (user['basic'].has_key('firstname') and user['basic'].has_key('lastname')):
        <span class="summary-item">${user['basic']['firstname']} ${user['basic']['lastname']}</span>
      %endif
      </div>

      %if user['basic'].has_key('jobTitle'):
        <div class="subtitle">${user['basic']['jobTitle']}</div>
      %endif
    </div>
    <div id="summary-block">
      <div id="summary-work-contact" class="summary-line">
        <span class="summary-item"><a href="${'mailto:' + user['basic']['emailId']}">${user['basic']['emailId']}</a></span>
        %if user.get('contact', {}).has_key('phone'):
          <span class="summary-icon landline-icon"/>
          <span class="summary-item" title="${_('Work Phone')}">${user['contact']['phone']}</span>
        %endif
        %if user.get('contact',{}).has_key('mobile'):
          <span class="summary-icon mobile-icon"/>
          <span class="summary-item" title="${_('Work Mobile')}">${user['contact']['mobile']}</span>
        %endif
      </div>
    </div>
  </div>
  <div class="clear"></div>
</%def>

<%def name="tabs()">
  <ul id="profile-tablinks" class="tablinks h-links">
    <%
      path = "/profile?id=%s&" % userKey
    %>
    %for item, name in [('activity', 'Activity'), ('info', 'More Info')]:
      %if detail == item:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax selected">${_(name)}</a></li>
      %else:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax">${_(name)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="user_actions(userKey, showRemove=False)">
  %if myKey != userKey:
    %if userKey not in relations.friends:
      %if not relations.pending or userKey not in relations.pending:
        <button class="button default" onclick="$.post('/ajax/profile/friend', 'id=${userKey}&action=add')">
          <span class="button-text">${_("Add as Friend")}</span>
        </button>
      %elif relations.pending.get(userKey) == 1:
        <button class="acl-button button" onclick="$$.ui.showPopup(event)">${_("Respond to Friend Request")}</button>
        <ul class="acl-menu" style="display:none;">
            <li>
              <a class="acl-item" _acl="public" onclick="$.post('/ajax/profile/friend', 'id=${userKey}&action=accept')">${_("Accept")}</a>
            </li>
            <li>
              <a class="acl-item" _acl="friends" onclick="$.post('/ajax/profile/friend', 'id=${userKey}&action=reject')">${_("Reject")}</a>
            </li>
        </ul>
      %else:
        <button class="button disabled"><span class="button-text">${_("Friend request sent")}</span></button>
      %endif
      %if userKey not in relations.subscriptions and userKey not in relations.friends:
        <button class="button" onclick="$.post('/ajax/profile/follow', 'id=${userKey}')">
          <span class="button-text">${_("Follow User")}</span>
        </button>
      %elif showRemove:
        <button class="button" onclick="$.post('/ajax/profile/unfollow', 'id=${userKey}')">
          <span class="button-text">${_("Unfollow User")}</span>
        </button>
      %endif
    %elif showRemove:
      <button class="button" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}')">
        <span class="button-text">${_("Unfriend User")}</span>
      </button>
    %endif
  %else:
    <button class="button" onclick="location.href = '/settings'">
      <span class="button-text">${_("Edit Profile")}</span>
    </button>
  %endif
</%def>

<%def name="content_info()">
  <div id="summary-personal">
      <div id="summary-personal-contact" class="summary-line">
      %if user.get('personal', {}).has_key('email'):
        <span class="summary-item" title="${_('Personal Email')}">${user['personal']['email']}</span>
      %endif
      %if user.get('personal', {}).has_key('phone'):
        <span class="summary-icon landline-icon"/>
        <span class="summary-item" title="${_('Personal Phone')}">${user['personal']['phone']}</span>
      %endif
      %if user.get('personal', {}).has_key('mobile'):
        <span class="summary-icon mobile-icon"/>
        <span class="summary-item" title="${_('Personal Mobile')}">${user['personal']['mobile']}</span>
      %endif
      </div>

      %if user.get('personal', {}).has_key('birthday'):
        <div id="summary-born" class="summary-line">
          <%
            stamp = user['personal']['birthday']  ## YYYYMMDD
            formatmap = {"year": stamp[0:4], "month": utils.monthName(int(stamp[4:6])), "day": stamp[6:]}
          %>
          ${'<span class="summary-item">' + _('Born on %(month)s %(day)s, %(year)s') % formatmap + '</span>'}
        </div>
      %endif

      %if user.get('personal', {}).has_key('currentCity'):
        <div id="summary-personal-location" class="summary-line">
          <span class="summary-item">${ _('Currently residing in ' + user['personal']['currentCity']) }</span>
        </div>
      %endif
  </div>
  %if user.has_key('work'):
    <%
      keys = sorted(user['work'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Work at %s') % ('Synovel')}</h4></div>
    <dl id="content-workhere">
      %for key in keys:
        <%
          end, start, title = key.split(':')
          sy, sm = start[0:4], start[4:6]
          args = {'sm': utils.monthName(int(sm), True), 'sy': sy}
          duration = ''
          if len(end) == 0:
            duration = _('Started in %(sm)s %(sy)s') % args
          else:
            ey, em = end[0:4], end[4:6]
            args['em'] = utils.monthName(int(em), True)
            args['ey'] = ey
            duration = _('%(sm)s %(sy)s &mdash; %(em)s %(ey)s') % args
        %>
        <dt>${title}</dt>
        <dd>
          <ul>
            <li class="light">${duration}</li>
            <li>${user['work'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  %if user.has_key('employers'):
    <%
      keys = sorted(user['employers'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Past Employment')}</h4></div>
    <dl id="content-workex">
      %for key in keys:
        <%
          end, start, org = key.split(':')[0:3]
          duration = _('%(sy)s &mdash; %(ey)s') % {'sy': start, 'ey': end}
        %>
        <dt>${org}</dt>
        <dd>
          <ul>
            <li class="light">${duration}</li>
            <li>${user['employers'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  %if user.has_key('education'):
    <%
      keys = sorted(user['education'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Education')}</h4></div>
    <dl id="content-education">
      %for key in keys:
        <%
          end, org = key.split(':')
          duration = _('%(ey)s') % {'ey': end}
        %>
        <dt>${org}</dt>
        <dd>
          <ul>
            <li class="light">${duration}</li>
            <li>${user['education'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
</%def>

<%def name="activity_block(grp)">
  <div class="conv-item">
    %for key in grp:
      <%
        rtype, itemId, convId, convType, convOwner, commentSnippet = key
        activity = reasonStr[key] % (utils.userName(convOwner, entities[convOwner]), utils.itemLink(convId, convType))
      %>
      <div class="conv-data">
        ${activity}
      </div>
    %endfor
  </div>
</%def>

<%def name="content_activity()">
  <%
    block = []
    for key in userItems:
      try:
        rtype, itemId, convId, convType, convOwnerId, commentSnippet = key
        if not reasonStr.has_key(key):
          if len(block) > 0:
            self.activity_block(block)
            block = []
          item.item_layout(convId)
        elif convType in plugins:
          block.append(key)
      except Exception, e:
        log.msg("Error when displaying UserItem:", key)
        log.err(e)
    if block:
      self.activity_block(block)
  %>
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator">
      <a id="next-page-load" class="ajax" _ref="/profile?id=${userKey}&start=${nextPageStart}">${_("Fetch older posts")}</a>
    </div>
  %else:
    <div id="next-load-wrapper">${_("No more posts to show")}</div>
  %endif
</%def>

<%def name="content()">
  %if detail == 'info':
    ${content_info()}
  %endif
  % if detail == 'activity':
    ${content_activity()}
  %endif
</%def>

