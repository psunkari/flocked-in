<%! from gettext import gettext as _, ngettext as __ %>
<%! from social import utils %>

<%inherit file="layout.mako"/>

<%def name="userProfileBlock()">
  <div id="profile-block">
    <div id="useravatar"></div>
    <div id="userprofile">
      <div id="titlebar">
        <div id="title">${userinfo['basic']['Name']}</div>
        %if userinfo['basic'].has_key('Designation'):
          ${'<div id="subtitle">' + userinfo['basic']['Designation'] + '</div>'}
        %endif
      </div>
      <div id="summary-block">
        %if userinfo.has_key('work'):
          <%
            keys = [x.split(':')[1] for x in userinfo['work'].keys()]
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
        %if userinfo['contacts'].has_key('Address_City'):
          ${'<span id="summary-lives" class="summary-item">' + _('Lives in %s') % userinfo['contacts']['Address_City'] + '</span>'}
        %endif
        %if userinfo['basic'].has_key('Birthday'):
          <%
            stamp = userinfo['basic']['Birthday']  ## YYYYMMDD
            formatmap = {"year": stamp[0:4], "month": utils.monthName(int(stamp[4:6])), "day": stamp[6:]}
          %>
          ${'<span id="summary-born" class="summary-item">' + _('Born on %(month)s %(day)s, %(year)s') % formatmap + '</span>'}
        %endif
        %if userinfo['contacts']['WorkMail']:
          ${'<span id="summary-workmail" class="summary-item">' + userinfo['contacts']['WorkMail'] + '</span>'}
        %endif
        %if userinfo['contacts']['WorkPhone']:
          ${'<span id="summary-work" class="summary-item">' + userinfo['contacts']['WorkPhone'] + '</span>'}
        %endif
        %if userinfo['contacts']['MobilePhone']:
          ${'<span id="summary-mobile" class="summary-item">' + userinfo['contacts']['MobilePhone'] + '</span>'}
        %endif
      </div>
    </div>
  </div>
</%def>

<%def name="title()">
</%def>

<%def name="rightBar()">
</%def>

<%def name="centerBar()">
  ${userProfileBlock()}
</%def>
