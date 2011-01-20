<%! from social import utils, _, __ %>
<%! from social import relations as r %>

<%inherit file="layout.mako"/>

##
## Functions for rendering content
##

<%def name="center_header()">
  <div id="profile-block">
    <div id="useravatar"></div>
    <div id="userprofile">
      <div id="titlebar">
        <div id="title">
          ${user['basic']['name']}
          %if myKey != userKey:
            %if relation._isFriend == r.REL_UNRELATED:
              <input type="button" value="+ Add as Friend" onclick="post('/ajax/profile/connect', 'target=${userKey}')"/>
            %elif relation._isFriend == r.REL_LOCAL_PENDING:
              <input type="button" value="- Cancel Friend Request" onclick="post('/ajax/profile/disconnect', 'target=${userKey}')"/>
            %elif relation._isFriend == r.REL_REMOTE_PENDING:
              <input type="button" value="+ Accept Friend Request" onclick="post('/ajax/profile/connect', 'target=${userKey}')"/>
            %endif
          %endif
        </div>
        %if user['basic'].has_key('jobTitle'):
          ${'<div id="subtitle">' + user['basic']['jobTitle'] + '</div>'}
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
  </div>
</%def>

<%def name="tabs()">
  <div id="profile-tabs">
    <ul id="profile-tablinks" class="h-links">
      <%
        profilePath = "/profile?"
        if myKey != userKey:
          profilePath = "/profile/%s?" % userKey
      %>
      %for item, name in [('notes', 'Notes'), ('info', 'Info'), ('docs', 'Documents')]:
        %if detail == item:
          <li><a href="${profilePath}dt=${item}" class="ajax selected">${_(name)}</a></li>
        %else:
          <li><a href="${profilePath}dt=${item}" class="ajax">${_(name)}</a></li>
        %endif
      %endfor
    </ul>
  </div>
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
  <div id="profile-detail">
    %if detail == 'info':
      ${content_info()}
    %endif
  </div>
</%def>






##
## Functions used for full page rendering
## Javascript is not available in the client browser
## Called from inside layout.mako
##

<%def name="center_contents()">
  ${tabs()}
  ${content()}
</%def>
