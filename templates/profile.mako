<%! from social import utils, _, __ %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>

##
## Profile is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
        <div id="user-me"></div>
        <div id="user-groups"></div>
        <div id="user-subscriptions"></div>
        <div id="user-followers"></div>
        <div id="user-actions"></div>
      </div>
      <div id="center">
        <div id="summary" class="center-header">
          %if not script:
            ${self.summary()}
          %endif
        </div>
        <div class="center-contents">
          <div id="profile-tabs">
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

<%def name="summary()">
  <div id="useravatar"></div>
  <div id="userprofile">
    <div class="titlebar">
      <div>
        <span class="middle title">${user['basic']['name']}</span>
        ${user_actions()}
      </div>
      %if user['basic'].has_key('jobTitle'):
        <div class="subtitle">${user['basic']['jobTitle']}</div>
      %endif
    </div>
    <div id="summary-block">
      %if user.has_key('work'):
        <%
          keys = [x.split(':')[2] for x in user['work'].keys()]
          length = len(keys)
        %>
        ${'<span id="summary-work" class="summary-item">' + __('Worked on %s', 'Worked on %s and %s', length) % ((keys[0]) if length == 1 else (keys[1], keys[0])) + '</span>'}
      %endif
      %if user.has_key('education'):
        <%
          keys = [x.split(':')[1] for x in user['education'].keys()]
          length = len(keys)
        %>
        ${'<span id="summary-education" class="summary-item">' + __('Studied at %s', 'Studied at %s and %s', length) % ((keys[0]) if length == 1 else (keys[1], keys[0])) + '</span>'}
      %endif
      %if user['personal'].has_key('currentCity'):
        ${'<span id="summary-lives" class="summary-item">' + _('Lives in %s') % user['personal']['currentCity'] + '</span>'}
      %endif
      %if user['personal'].has_key('birthday'):
        <%
          stamp = user['personal']['birthday']  ## YYYYMMDD
          formatmap = {"year": stamp[0:4], "month": utils.monthName(int(stamp[4:6])), "day": stamp[6:]}
        %>
        ${'<span id="summary-born" class="summary-item">' + _('Born on %(month)s %(day)s, %(year)s') % formatmap + '</span>'}
      %endif
      %if user['contact'].has_key('mail'):
        ${'<span id="summary-workmail" class="summary-item">' + user['contact']['mail'] + '</span>'}
      %endif
      %if user['contact'].has_key('phone'):
        ${'<span id="summary-phone" class="summary-item">' + user['contact']['phone'] + '</span>'}
      %endif
      %if user['contact'].has_key('mobile'):
        ${'<span id="summary-mobile" class="summary-item">' + user['contact']['mobile'] + '</span>'}
      %endif
    </div>
  </div>
  <div class="clear"></div>
</%def>

<%def name="tabs()">
  <ul id="profile-tablinks" class="h-links">
    <%
      path = "/profile?id=%s&" % encodedUserKey
    %>
    %for item, name in [('notes', 'Notes'), ('info', 'Info'), ('docs', 'Documents')]:
      %if detail == item:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax selected">${_(name)}</a></li>
      %else:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax">${_(name)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="user_actions()">
  %if myKey != userKey:
  <%
    respond_cls = " hidden" if relation.isFriend != r.REL_REMOTE_PENDING else ""
    add_cls     = " hidden" if relation.isFriend != r.REL_UNRELATED else ""
    follow_cls  = " hidden" if relation.isFriend != r.REL_UNRELATED or relation.isSubscribed != r.REL_UNRELATED else ""
    sent_cls    = " hidden" if relation.isFriend != r.REL_LOCAL_PENDING else ""
  %>
  <ul id="user-actions-${encodedUserKey}" class="middle user-actions h-links">
    <li><button class="button default${respond_cls}" onclick="$.post('/ajax/profile/connect', 'target=${encodedUserKey}')">Respond to Friend Request</button></li>
    <li><button class="button disabled${sent_cls}">Friend request sent</button></li>
    <li><button class="button default${add_cls}" onclick="$.post('/ajax/profile/connect', 'target=${encodedUserKey}')">Add as Friend</button></li>
    <li><button class="button${follow_cls}" onclick="$.post('/ajax/profile/follow', 'target=${encodedUserKey}')">Follow User</button></li>
  </ul>
  %endif
</%def>

<%def name="content_info()">
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
  <div class="content-title"><h4>${_('Recommendations for %s') % user['basic']['name']}</h4></div>
  %if user.has_key('employers'):
    <%
      keys = sorted(user['employers'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Past Employment')}</h4></div>
    <dl id="content-workex">
      %for key in keys:
        <%
          end, start, org = key.split(':')
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
  <div class="content-title"><h4>${_('Interests')}</h4></div>
  <dl id="content-interests">
  </dl>
  <div class="content-title"><h4>${_('Contact Information')}</h4></div>
  <dl id="content-contact">
  </dl>
  <div class="content-title"><h4>${_('Other Details')}</h4></div>
  <dl id="content-other">
  </dl>
</%def>

<%def name="content()">
  %if detail == 'info':
    ${content_info()}
  %endif
</%def>

