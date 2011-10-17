<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins, settings %>
<%! from social import relations as r %>
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
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="settings-title" class="center-header">
        %if not script:
          ${self.settingsTitle()}
        %endif
      </div>
      <div id="right">
        <div class="right-contents">
          %if not script:
            ${right()}
          %endif
        </div>
      </div>
      <div id="center">
        <div class="center-contents" id="settings-content"></div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>


##
## Functions for rendering content
##
<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, id):
      cls = "sidemenu-selected" if id == detail else ''
      return """<li>
                  <a href="%(link)s" id="%(id)s-sideitem" class="ajax busy-indicator %(cls)s">
                    <span class="sidemenu-icon %(id)s-icon"></span>
                    <span class="sidemenu-text">%(text)s</span>
                  </a>
                </li>
              """ % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul class="v-links sidemenu">
       ${navMenuItem("/feed", _("Back to Home"), "back")}
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("/settings?dt=basic", _("Basic"), "basic")}
      ${navMenuItem("/settings?dt=contact", _("Contact"), "contact")}
      ${navMenuItem("/settings?dt=personal", _("Personal Info"), "personal")}
##      ${navMenuItem("/settings?dt=work", _("Work &amp; Education"), "work")}
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("/settings?dt=passwd", _("Change Password"), "passwd")}
      ${navMenuItem("/settings?dt=notify", _("Notifications"), "notify")}
    </ul>
 </div>
</%def>

<%def name="settingsTitle()">
  <%
    detail_name_map = {'basic':_('Basic'), 'contact': _('Contact'),
                       'work':_('Work and Education'), 'personal':_('Personal'),
                       'passwd':_('Change Password'),
                       'notify': _('Notifications')}
    name = detail_name_map.get(detail, '')
  %>
  <span class="middle title"> ${_(name)} </span>
</%def>

<%def name="editBasicInfo()">
  <%
    name = me.get("basic", {}).get("name", '')
    firstname = me.get("basic", {}).get("firstname", '')
    lastname = me.get("basic", {}).get("lastname", '')
    jobTitle = me.get("basic", {}).get("jobTitle", '')
    myTimezone = me.get("basic", {}).get("timezone", '')
  %>
  <form id="settings-form" action="/ajax/settings" method="post" enctype="multipart/form-data">
    <div class="styledform">
      <ul>
        <li>
          <label for="displayname">${_('Display Name')}</label>
          <input type="text" id="displayname" name="name" value="${name}" autofocus />
        </li>
        <li>
          <label for="firstname">${_('First Name')}</label>
          <input type="text" id="firstname" name="firstname" value="${firstname}"/>
        </li>
        <li>
          <label for="lastname">${_('Last Name')}</label>
          <input type="text" id="lastname" name="lastname" value="${lastname}"/>
        </li>
        <li>
          <label for="jobTitle">${_('Job Title')}</label>
          <input type="text" id="jobTitle" name="jobTitle" value="${jobTitle}"/>
        </li>
        <li>
          <label for="timezone">${_('Timezone')}</label>
          <select name="timezone" class="single-row">
            %for timezone in common_timezones:
              %if timezone == myTimezone:
                <option value="${timezone}" selected="">${timezone}</option>
              %else:
                <option value="${timezone}">${timezone}</option>
              %endif
            %endfor
          </select>
        </li>
        <li>
          <label for="dp">${_('Photo')}</label>
          <input type="file" id="dp" name="dp" accept="image/jpeg,image/png,image/gif"/>
        </li>

        %if emailId and emailId[0]:
          <input type="hidden" value=${emailId[0]} name="emailId"/>
        %endif
        % if myKey:
          <input type="hidden" value=${myKey} name="id"/>
        %endif
      </ul>
    </div>
    <div class="styledform-buttons">
      <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>

<%def name="changePasswd()">
  <form class="ajax" id="settings-form" action="/settings/passwd"
        method="post" enctype="multipart/form-data">
    <div class="styledform">
      <ul>
        <li>
          <label for="curr_passwd">${_('Current Password')}</label>
          <input type="password" name="curr_passwd" id="curr_passwd" required autofocus />
        </li>
        <li>
          <label for="passwd1">${_('New Password')}</label>
          <input type="password" name="passwd1" id="passwd1" required />
        </li>
        <li>
          <label for="passwd2">${_('Confirm Password')}</label>
          <input type="password" name="passwd2" id="passwd2" required />
        </li>
      </ul>
      <input type="hidden" id = 'dt' name="dt" value="passwd"/>
    </div>
    <div class="styledform-buttons">
      <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>

<%def name="workitem(start, end, title, desc, id)">
  <div class="workitem" id="work-${id}">
    <span class="workitem-delete">&nbsp;</span>
    <div class="workitem-title">${title}</div>
    <div class="workitem-duration">${_('%(start)s &mdash; %(end)s') % locals()}</div>
    <div class="workitem-desc">${desc}</div>
  </div>
</%def>

<%def name="editWork()">
  <div id="work" class="styledform">
    <% orgName = org["basic"]["name"] %>
    <legend>${_("Work at %s")%orgName}</legend>
    <div id="worklist">
      <%
        work = me.get('work', {})
        for key, value in work.items():
          end, start, title = key.split(':')
          workitem(start, end, title, value, utils.encodeKey(key))
      %>
    </div>
    <div id="workadd">
      <button class="button-link ajax" data-ref="/settings/work">${_("+ Add Work")}</button>
    </div>
    <div class="styledform" id="workform" style="display:none;">
      <form id='settings-form' action='/settings/work' method='post' class='ajax'>
        <ul>
          <li>
            <label for="worktitle">${_('Title')}</label>
            <input type="text" id="worktitle" name="title"/>
          </li>
          <li>
            <label for="workdesc">${_('Description')}</label>
            <input type="text" id="workdesc" name="desc"/>
          </li>
          <li>
            <label for="workstart">${_('Duration')}</label>
            ${self.selectYear("startY", "Start year", id="workstart")}
            ${self.selectYear("endY", "End year", id="workstart")}
          </li>
          <li>
            <label/>
            <input type="submit" class="button default" name="submit" value="${_('Save')}"/>
          </li>
        </ul>
      </form>
    </div>
  </div>
</%def>

<%def name="editPersonal()">
  <form class="ajax" id="settings-form" action="/settings" method="post"  enctype="multipart/form-data">
    <% personal = me.get('personal', {}) %>
    <div class="styledform">
      <div id="personal">
        <ul>
          <li>
            <%
              rawstr = r"""(?P<doy>\d{4})(?P<dom>\d{2})(?P<dod>\d{1,2})"""
              matchstr = personal.get('birthday', '')
              compile_obj = re.compile(rawstr)
              match_obj = compile_obj.search(matchstr)
              if match_obj:
                doy = match_obj.group('doy')
                dom = match_obj.group('dom')
                dod = match_obj.group('dod')
              else:
                doy = dom = dod = None
            %>
            <label for ="bday">${_('Date of Birth')}</label>
            ${self.selectDay("dob_day", "Day", dod)}
            ${self.selectMonth("dob_mon", "Month", dom)}
            ${self.selectYear("dob_year", "Year", doy)}
          </li>
          <li>
            <label for="p_email">${_('Email')}</label>
            <input type="email" id="p_email" name="p_email" value="${personal.get('email', '')}"/>
          </li>
          <li>
            <label for="p_phone">${_('Phone')}</label>
            <input type="text" id="p_phone" name="p_phone" value="${personal.get('phone', '')}"/>
          </li>
          <li>
            <label for="p_mobile">${_('Mobile')}</label>
            <input type="text" id="p_mobile" name="p_mobile" value="${personal.get('mobile', '')}"/>
          </li>
          <li>
            <label for="hometown">${_('Hometown')}</label>
            <input type="text" id="hometown" name="hometown" value="${personal.get('hometown', '')}"/>
          </li>
          <li>
            <label for="currentCity">${_('Current City')}</label>
            <input type="text" id="currentCity" name="currentCity" value="${personal.get('currentCity', '')}"/>
          </li>
        </ul>
      </div>
        %if emailId and emailId[0]:
          <input type="hidden" value = ${emailId[0]} name="emailId" />
        %endif
        %if myKey:
          <input type="hidden" value = ${myKey} name="id" />
        %endif
    </div>
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>

<%def name="editContact()">
  <%
    contact = me.get('contact', {})
    emailId = me['basic']['emailId']
  %>
  <form class="ajax" id="settings-form" action="/settings" method="post"  enctype="multipart/form-data">
    <div class="styledform">
      <div id="contacts">
        <ul>
            <li>
                <label for="c_email">${_('Email')}</label>
                <input type="email" id="c_email" name="c_email" value="${emailId}" readonly='true' />
            </li>
            <li>
                <label for="c_im">${_('Chat Id')}</label>
                <input type="text" id="c_im" name="c_im" value="${contact.get('im', '')}" autofocus />
            </li>
            <li>
                <label for="c_phone">${_('Work Phone')}</label>
                <input type="text" id="c_phone" name="c_phone" value="${contact.get('phone', '')}"/>
            </li>
            <li>
                <label for="c_mobile">${_('Work Mobile')}</label>
                <input type="text" id="c_mobile" name="c_mobile" value="${contact.get('mobile', '')}"/>
            </li>
        </ul>
      </div>
      <div class="styledform-buttons">
          <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
      </div>
    </div>
    %if emailId and emailId[0]:
      <input type="hidden" value = ${emailId[0]} name="emailId" />
    %endif
    %if myKey:
      <input type="hidden" value = ${myKey} name="id" />
    %endif
  </form>
</%def>

<%def name="selectMonth(name, label, dom=None)">
  <%
    months = [_("January"), _("February"), _("March"), _("April"),
                _("May"), _("June"), _("July"), _("August"),
                _("September"), _("October"), _("November"), _("December")]
  %>
  <select name="${name}" class="inline-select">
    <option value="">${label}</option>
    %for m in range(1, 13):
      <% value = "%02d" %m %>
      %if dom and int(dom) == m:
        <option selected value="${value}">${months[m-1]}</option>
      %else:
        <option value="${value}">${months[m-1]}</option>
      %endif
    %endfor
    </select>
</%def>

<%def name="selectDay(name, label, dod=None)">
  <select name="${name}" class="inline-select">
    <option value="">${label}</option>
      %for d in range(1, 32):
        <% value = "%d" %d %>
        %if dod and int(dod) == d:
          <option selected value="${value}">${d}</option>
        %else:
          <option value="${value}">${d}</option>
        %endif
      %endfor
  </select>
</%def>

<%def name="selectYear(name, label, doy=None, id=None)">
  <select name="${name}" class="inline-select">
    <option value="">${label}</option>
      %for d in reversed(range(1901, datetime.date.today().year)):
        <% value = "%d" %d %>
        %if doy and int(doy) == d:
          <option selected value="${value}">${d}</option>
        %else:
          <option value="${value}">${d}</option>
        %endif
      %endfor
  </select>
</%def>

<%def name="filterNotifications()">
  <%
    notify = me['basic'].get('notify', '')
    labels = [_('Someone adds you as a friend'),
              _('Your friend request is accepted'),
              _('Someone started following you'),
              _('New user joins your company network'),

              _('User wants to join a group you administer'),
              _('Your request to join a group is accepted'),
              _('You are invited to join a group'),
              _('New user joins a group you administer'),

              _('Someone tagged an item you shared'),
              _('Someone commented on an item you shared'),
              _('Someone liked an item you shared'),
              _('Someone liked your comment'),
              _('Someone commented on an item that you liked/commented on'),

              _('You are mentioned in a post or comment'),
              _('Other requests (event invitations etc;)'),

              _('New private conversation'),
              _('New message in an existing conversations'),
              _('Recipients of a conversation were changed')]
  %>
  <form class="ajax" id="settings-form" action="/settings/notify" method="post"  enctype="multipart/form-data">
    <table id='notify-setup' valign='middle' role='display'>
      <colgroup>
        <col class='notify-type'/>
        <col class='notify-medium'/>
      </colgroup>
      <tr class='notify-setup-header'>
        <th></th>
        <th class='notify-medium-mail'>${_('Mail')}</th>
      </tr>
      <% emailTemplate = _('E-mail notification when: %s') %>
      %for x in range(settings._notificationsCount):
        <%
          emailChecked = "checked='1'"\
            if settings.getNotifyPref(notify, x, settings.notifyByMail)\
            else '' %>
        <tr>
          <td>${_(labels[x])}</td>
          <td>
            <input type='checkbox' name='${settings._notifyNames[x]}'
                   title='${emailTemplate % labels[x]}'
                   value='1' ${emailChecked}/>
          </td>
        </tr>
      %endfor
    </table>
    <div class="styledform-buttons">
      <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>

<%def name="right()">
  %if len(suggested_sections.keys()) > 0:
    <div class="sidebar-chunk">
      <div class="sidebar-title">${_("Complete your profile")}</div>
      <ul class="v-links">
        <%
          suggestions = []
          for k,v in suggested_sections.iteritems():
            suggestions.append([v[0],k])
        %>
        %for suggestion in suggestions:
          %if suggestion[1] == detail:
            <li>${suggestion[0]}</li>
          %else:
            <li><a class="ajax" href="/settings?dt=${suggestion[1]}">${suggestion[0]}</a></li>
          %endif
        %endfor
      </ul>
    </div>
  %endif
</%def>
