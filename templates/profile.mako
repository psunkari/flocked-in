<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>
<%! from social.logging import log %>
<%! from pytz import common_timezones %>
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
      <div id="profile-summary">
        %if not script:
          ${self.summary()}
        %endif
      </div>
      <div id="profile-center-right">
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
              ${self.user_subactions(userId)}
            %endif
          </div>
        </div>
        <div id="center">
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
      <div class="clear"></div>
    </div>
  </div>
</%def>


##
## Functions for rendering content
##
<%def name="user_me()">
  %if myId != userId:
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
      <li><a class="ajax" href="/group?id=${group}">${rawGroupData[group]['name']}</a></li>
    %endfor
    </ul>
  </div>
  %endif
</%def>

<%def name="user_subactions(userId, renderWrapper=True)">
  %if myId != userId:
    ##%if renderWrapper:
    ##  <div class="sidebar-chunk">
    ##  <ul id="user-subactions-${userId}" class="middle user-subactions v-links">
    ##%endif
    ##<li><a href="/profile/block?id=${userId}"
    ##       onclick="$.post('/ajax/profile/block', 'id=${userId}'); $.event.fix(event).preventDefault();">
    ##      ${_("Block User")}
    ##    </a>
    ##</li>
    ##<li><a href="/profile/review?id=${userId}"
    ##       onclick="$.post('/ajax/profile/review', 'id=${userId}'); $.event.fix(event).preventDefault();">
    ##      ${_("Request Admin Review")}
    ##    </a>
    ##</li>
    ##%if renderWrapper:
    ##  </ul>
    ##  </div>
    ##%endif
  %endif
</%def>

<%def name="summary()">
  <% avatarURI = utils.userAvatar(userId, user, "large") %>
  <div class="titlebar center-header">
    %if avatarURI:
      <div id="useravatar" class="avatar" style="background-image:url('${avatarURI}')"></div>
    %endif
    <div id="title">
      <span class="middle title">${user['basic']['name']}</span>
      <ul id="user-actions-${userId}" class="middle user-actions h-links">
        ${user_actions(userId, True, True)}
      </ul>
    </div>
  </div>
  <div id="userprofile">
    <div id="summary-block">
      <div class="subtitle" class="summary-line">
        %if (user['basic'].has_key('firstname') and user['basic'].has_key('lastname')):
          <span>${user['basic']['firstname']} ${user['basic']['lastname']}</span>,
        %endif
        <span>${user['basic']['jobTitle']}</span>
      </div>
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
</%def>

<%def name="tabs()">
  <ul id="profile-tablinks" class="tablinks h-links">
    <%
      path = "/profile?id=%s&" % userId
    %>
    %for item, name in [('activity', 'Activity'), ('info', 'More Info'), ('files', 'Files')]:
      %if detail == item:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax selected">${_(name)}</a></li>
      %else:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax">${_(name)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="user_actions(userId, showRemove=False, showEditProfile=False)">
  %if myId != userId:
    %if userId not in relations.subscriptions:
      <li><button class="button default" onclick="$.post('/ajax/profile/follow', 'id=${userId}')">
        <span class="button-text">${_("Follow User")}</span>
      </button></li>
    %elif showRemove:
      <li><button class="button" onclick="$.post('/ajax/profile/unfollow', 'id=${userId}')">
        <span class="button-text">${_("Unfollow User")}</span>
      </button></li>
    %endif
  %elif showEditProfile:
    <li><button class="button ajax" data-href='/settings'>
      <span class="button-text">${_("Edit Profile")}</span>
    </button></li>
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
  %if user.has_key('companies'):
    <%
      keys = sorted(user['companies'].keys(), reverse=True)
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
            <li>${user['companies'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  %if user.has_key('schools'):
    <%
      keys = sorted(user['schools'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Education')}</h4></div>
    <dl id="content-education">
      %for key in keys:
        <%
          end, school = key.split(':')
          duration = _('%(ey)s') % {'ey': end}
        %>
        <dt>${school}</dt>
        <dd>
          <ul>
            <li class="light">${user['schools'][key]} - ${duration}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  %if user.has_key('expertise'):
    <div class="content-title"><h4>${_('Expertise')}</h4></div>
    <dl id="content-expertise">
      <dd><ul> <li> ${user['expertise']['expertise']}</li></ul></dd>
    </dl>
  %endif
</%def>

<%def name="activity_block(grp, tzone)">
  <%
    rTypeClasses = {"C": "comment", "Q": "answer", "L": "like"}
    simpleTimestamp = utils.simpleTimestamp
  %>
  <div class="conv-item">
    %for key in grp:
      <%
        rtype, itemId, convId, convType, convOwner, commentSnippet = key
        activity = reasonStr[key] % (utils.userName(convOwner, entities[convOwner]), utils.itemLink(convId, convType))
        rTypeClass = rTypeClasses.get(rtype, '')
      %>
      <div class="activity-item ${rTypeClass}">
        <div class="activity-icon icon"></div>
        <div class="activity-content">
          <span>${activity}</span>
          <div class="activity-footer">${simpleTimestamp(timestamps[key], tzone)}</div>
        </div>
      </div>
    %endfor
  </div>
</%def>

<%def name="content_activity()">
  <%
    block = []
    tzone = me["basic"]["timezone"]
    for key in userItems:
      try:
        rtype, itemId, convId, convType, convOwnerId, commentSnippet = key
        if not reasonStr.has_key(key):
          if len(block) > 0:
            self.activity_block(block, tzone)
            block = []
          item.item_layout(convId)
        elif convType in plugins:
          block.append(key)
      except Exception, e:
        log.err("Error when displaying UserItem:", key)
        log.err(e)
    if block:
      self.activity_block(block, tzone)
  %>
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator">
      <a id="next-page-load" class="ajax" data-ref="/profile?id=${userId}&start=${nextPageStart}">${_("Fetch older posts")}</a>
    </div>
  %else:
    <div id="next-load-wrapper">${_("No more posts to show")}</div>
  %endif
</%def>

<%def name="content()">
  %if detail == 'info':
    ${content_info()}
  % elif detail == 'activity':
    ${content_activity()}
  %endif

</%def>
