<%! from social import utils, _, __ %>

<%inherit file="layout.mako"/>

<%def name="summary()">
  <div id="profile-block">
    <div id="useravatar"></div>
    <div id="userprofile">
      <div id="titlebar">
        <div id="title">${userinfo['basic']['name']}</div>
        %if userinfo['basic'].has_key('jobTitle'):
          ${'<div id="subtitle">' + userinfo['basic']['jobTitle'] + '</div>'}
        %endif
      </div>
      <div id="summary-block">
        %if userinfo.has_key('work'):
          <%
            keys = [x.split(':')[2] for x in userinfo['work'].keys()]
            length = len(keys)
          %>
          ${'<span id="summary-work" class="summary-item">' + __('Worked on %s', 'Worked on %s and %s', length) % ((keys[0]) if length == 1 else (keys[1], keys[0])) + '</span>'}
        %endif
        %if userinfo.has_key('education'):
          <%
            keys = [x.split(':')[1] for x in userinfo['education'].keys()]
            length = len(keys)
          %>
          ${'<span id="summary-education" class="summary-item">' + __('Studied at %s', 'Studied at %s and %s', length) % ((keys[0]) if length == 1 else (keys[1], keys[0])) + '</span>'}
        %endif
        %if userinfo['personal'].has_key('currentCity'):
          ${'<span id="summary-lives" class="summary-item">' + _('Lives in %s') % userinfo['personal']['currentCity'] + '</span>'}
        %endif
        %if userinfo['personal'].has_key('birthday'):
          <%
            stamp = userinfo['personal']['birthday']  ## YYYYMMDD
            formatmap = {"year": stamp[0:4], "month": utils.monthName(int(stamp[4:6])), "day": stamp[6:]}
          %>
          ${'<span id="summary-born" class="summary-item">' + _('Born on %(month)s %(day)s, %(year)s') % formatmap + '</span>'}
        %endif
        %if userinfo['contact'].has_key('mail'):
          ${'<span id="summary-workmail" class="summary-item">' + userinfo['contact']['mail'] + '</span>'}
        %endif
        %if userinfo['contact'].has_key('phone'):
          ${'<span id="summary-phone" class="summary-item">' + userinfo['contact']['phone'] + '</span>'}
        %endif
        %if userinfo['contact'].has_key('mobile'):
          ${'<span id="summary-mobile" class="summary-item">' + userinfo['contact']['mobile'] + '</span>'}
        %endif
      </div>
    </div>
  </div>
</%def>

<%def name="tabs()">
  <div id="profile-tabs">
    <ul id="profile-tablinks">
      <li><a href="?d=notes" class="ajax">${_('Notes')}</a></li>
      <li><a href="?d=info"  class="ajax">${_('Info')}</a></li>
      <li><a href="?d=docs"  class="ajax">${_('Documents')}</a></li>
    </ul>
  </div>
</%def>

<%def name="contentInfo()">
  %if userinfo.has_key('work'):
    <%
      keys = sorted(userinfo['work'].keys(), reverse=True)
    %>
    <div class="content-title"><h4>${_('Work at %s') % ('Synovel')}</h4></div>
    <dl id="content-workhere">
      %for key in keys:
        <%
          end, start, title = key.split(':')
          sy, sm = int(start[0:4]), int(start[4:6])
          args = {'sm': utils.monthName(sm, True), 'sy': sy}
          duration = ''
          if len(end) == 0:
            duration = _('Started in %(sm)s %(sy)s') % args
          else:
            ey, em = int(end[0:4]), int(end[4:6])
            args['em'] = utils.monthName(em, True)
            args['ey'] = ey
            duration = _('%(sm)s %(sy)s &mdash; %(em)s %(ey)s') % args
        %>
        <dt>${title}</dt>
        <dd>
          <ul>
            <li class="light">${duration}</li>
            <li>${userinfo['work'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  <div class="content-title"><h4>${_('Recommendations for %s') % userinfo['basic']['name']}</h4></div>
  %if userinfo.has_key('employers'):
    <%
      keys = sorted(userinfo['employers'].keys(), reverse=True)
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
            <li>${userinfo['employers'][key]}</li>
          </ul>
        </dd>
      %endfor
    </dl>
  %endif
  %if userinfo.has_key('education'):
    <%
      keys = sorted(userinfo['education'].keys(), reverse=True)
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
            <li>${userinfo['education'][key]}</li>
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
      ${contentInfo()}
    %endif
  </div>
</%def>

<%def name="title()">
</%def>

<%def name="rightBar()">
</%def>

<%def name="centerBar()">
  ${summary()}
  ${tabs()}
  ${content(detail)}
</%def>
