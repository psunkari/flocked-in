<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins, settings , location_tz_map %>
<%! from social import relations as r %>
<%! from base64 import b64encode, b64decode %>
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
                    <span class="sidemenu-icon %(id)s-icon icon"></span>
                    <span class="sidemenu-text">%(text)s</span>
                  </a>
                </li>
              """ % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul class="v-links sidemenu">
      <li><button class="button ajax" data-href="/profile?id=${myId}&dt=info"><span class="sidemenu-icon icon back-icon" style="position: relative; top: -1px;"></span>${_('View Profile')}</button></li>
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("/settings?dt=basic", _("Basic"), "basic")}
      ${navMenuItem("/settings?dt=work", _("Work Profile"), "work")}
      ${navMenuItem("/settings?dt=personal", _("Personal Profile"), "personal")}
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("/settings?dt=passwd", _("Change Password"), "passwd")}
      ${navMenuItem("/settings?dt=notify", _("Notifications"), "notify")}
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("/apps", _("Applications"), "apps")}
    </ul>
 </div>
</%def>


<%def name="settingsTitle()">
  <%
    detail_name_map = {'basic':_('Basic'), 'work':_('Work Information'),
                       'personal':_('Personal Information'),
                       'passwd':_('Change Password'), 'notify': _('Notifications')}
    name = detail_name_map.get(detail, '')
  %>
  <span class="middle title"> ${_(name)} </span>
</%def>


<%def name="editBasicInfo()">
  <%
    name = me.get("basic", {}).get("name", '')
    firstname = me.get("basic", {}).get("firstname", '').replace('"', '&quot;')
    lastname = me.get("basic", {}).get("lastname", '').replace('"', '&quot;')
    jobTitle = me.get("basic", {}).get("jobTitle", '')
    myTimezone = me.get("basic", {}).get("timezone", '')
  %>
  <form id="settings-form" action="/ajax/settings/basic" method="post" enctype="multipart/form-data">
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label" for="displayname">${_('Display Name')}
            <abbr title="Required">*</abbr>
        </label>
        <input type="text" id="displayname" name="name" value="${name}" autofocus required/>
      </li>
      <li class="form-row">
        <label class="styled-label" for="firstname">${_('First Name')}
        </label>
        <input type="text" id="firstname" name="firstname" value="${firstname}"/>
      </li>
      <li class="form-row">
        <label class="styled-label" for="lastname">${_('Last Name')}</label>
        <input type="text" id="lastname" name="lastname" value="${lastname}"/>
      </li>
      <li class="form-row">
        <label class="styled-label" for="jobTitle">${_('Job Title')}
            <abbr title="Required">*</abbr>
        </label>
        <input type="text" id="jobTitle" name="jobTitle" value="${jobTitle}" required/>
      </li>
      <li class="form-row">
        <label class="styled-label" for="timezone">${_('Country/Timezone')}</label>
        <select name="timezone" class="single-row">
          %for i, country_name in enumerate(location_tz_map):
            % if i == 7:
              <option value="" disabled="disabled">-----------------------------------------------</option>
            %endif
            %if location_tz_map[country_name] == myTimezone:
              <option value="${location_tz_map[country_name]}" selected="">${country_name}</option>
             %else:
              <option value="${location_tz_map[country_name]}">${country_name}</option>
            %endif
          %endfor
        </select>
      </li>
      <li class="form-row">
        <label class="styled-label" for="dp">${_('Photo')}</label>
        <input type="file" id="dp" name="dp" accept="image/jpeg,image/png,image/gif"/>
      </li>

      %if emailId and emailId[0]:
        <input type="hidden" value=${emailId[0]} name="emailId"/>
      %endif
      % if myKey:
        <input type="hidden" value=${myKey} name="id"/>
      %endif
    </ul>
    <div class="styledform-buttons">
      <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>


<%def name="changePasswd()">
  <form class="ajax" id="settings-form" action="/settings/passwd"
        method="post" enctype="multipart/form-data">
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label" for="curr_passwd">${_('Current Password')}</label>
        <input type="password" name="curr_passwd" id="curr_passwd" required autofocus />
      </li>
      <li class="form-row">
        <label class="styled-label" for="passwd1">${_('New Password')}</label>
        <input type="password" name="passwd1" id="passwd1" required />
      </li>
      <li class="form-row">
        <label class="styled-label" for="passwd2">${_('Confirm Password')}</label>
        <input type="password" name="passwd2" id="passwd2" required />
      </li>
    </ul>
    <input type="hidden" id = 'dt' name="dt" value="passwd"/>
    <div class="styledform-buttons">
      <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>


<%def name="editPersonal()">
  <form class="ajax" id="settings-form" action="/settings/personal" method="post"  enctype="multipart/form-data">
    <% personal = me.get('personal', {}) %>
    <div id="personal">
      <ul class="styledform">
        <li class="form-row">
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
          <label class="styled-label" for ="bday">${_('Date of Birth')}</label>
          ${self.selectDay("dob_day", "Day", dod)}
          ${self.selectMonth("dob_mon", "Month", dom)}
          ${self.selectYear("dob_year", "Year", doy)}
        </li>
        <li class="form-row">
          <label class="styled-label" for="email">${_('E-Mail')}</label>
          <input type="email" id="email" name="email" value="${personal.get('email', '')}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="phone">${_('Phone')}</label>
          <input type="text" id="phone" name="phone" value="${personal.get('phone', '')}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="mobile">${_('Mobile')}</label>
          <input type="text" id="mobile" name="mobile" value="${personal.get('mobile', '')}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="hometown">${_('Hometown')}</label>
          <input type="text" id="hometown" name="hometown" value="${personal.get('hometown', '')}"/>
        </li>
        <li class="form-row">
          <label class="styled-label" for="currentCity">${_('Current City')}</label>
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
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="${_('Save')}"/>
    </div>
  </form>
</%def>

##
## DUPLICATE CODE: Similar code exists in profile.mako
##
<%def name="companyItem(companyId, companyVal)">
  <%
    end, start, name = companyId.split(':', 2)
    title = companyVal
    companyId = utils.encodeKey(companyId)

    startYear = start[:4]
    startMonth = utils.monthName(int(start[4:]))
    endYear = end[:4]
    endMonth = utils.monthName(int(end[4:]))

    if endYear != '9999':
      duration = "%(startMonth)s, %(startYear)s &ndash; %(endMonth)s, %(endYear)s"
    else:
      duration = "%(startMonth)s, %(startYear)s &ndash; present"

    duration = duration % locals()
  %>
  <div class="company-item" id="${companyId}">
    <div class="company-avatar"/>
    <div class="company-details">
      <div class="company-name"><button data-ref="/settings/company?id=${companyId}" class="button-plain ajax" style="font-weight:bold;">${name}</button></div>
      %if title:
        <div class="company-title">${title}</div>
      %endif
      <div class="company-title">${duration}</div>
      <button class="company-remove ajaxpost" title="Delete ${name}"
              data-ref="/settings/company?id=${companyId}&action=d">&nbsp;</button>
    </div>
  </div>
</%def>


##
## DUPLICATE CODE: Similar code exists in profile.mako
##
<%def name="schoolItem(schoolId, schoolVal)">
  <%
    year, name = schoolId.split(':', 1)
    degree = schoolVal
    schoolId = utils.encodeKey(schoolId)
  %>
  <div class="company-item" id="${schoolId}">
    <div class="company-avatar school-default"/>
    <div class="company-details">
      <div class="company-name"><button data-ref="/settings/school?id=${schoolId}" class="button-plain ajax" style="font-weight:bold;">${name}</button></div>
      <div class="company-title">${degree}</div>
      <div class="company-title">${year}</div>
      <button class="company-remove ajaxpost" title="Delete ${name}"
           data-ref="/settings/school?id=${schoolId}&action=d">&nbsp;</button>
    </div>
  </div>
</%def>


<%def name="_expertise(expertise)">
  <%
    if not expertise:
        return
  %>
  %for item in expertise.keys():
    <span class="tag" id="expertise-${utils.encodeKey(item)}">
      ${item}
      <form class="ajax delete-tags" method="post" action="/settings/unexpertise">
        <input type="hidden" name="expertise" value="${utils.encodeKey(item)}"/>
        <button type="submit" class="button-link">x</button>
      </form>
    </span>
  %endfor
</%def>

<%def name="editWork()">
  <%
    contact = me.get('contact', {})
    emailId = me['basic']['emailId']
  %>
  <div id="contacts">
    <form class="ajax" id="settings-form" action="/settings/work" method="post" enctype="multipart/form-data">
      <div class="center-title">Work Contacts</div>
      <ul class="styledform">
          <li class="form-row">
              <label class="styled-label" for="email">${_('E-Mail')}</label>
              <input type="email" id="email" name="email" value="${emailId}" readonly='true' />
          </li>
          <li class="form-row">
              <label class="styled-label" for="phone">${_('Phone')}</label>
              <input type="text" id="phone" name="phone" value="${contact.get('phone', '')}"/>
          </li>
          <li class="form-row">
              <label class="styled-label" for="mobile">${_('Mobile')}</label>
              <input type="text" id="mobile" name="mobile" value="${contact.get('mobile', '')}"/>
          </li>
      </ul>
      <div class="styledform-buttons">
        <input type="submit" class="button default" value="${_('Save')}"/>
      </div>
    </form>
  </div>
  <div id="pro-summary" style="margin-bottom: 25px;">
    <div class="center-title">Professional Summary</div>
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label">Expertise</label>
        <div class="styledform-helpwrap">
          <div id="expertise-container" class="editing-tags" style="line-height: 1.3em;">
            <% _expertise(me.get('expertise', {})) %>
          </div>
          <form method="post" action="/settings/expertise" class="ajax" autocomplete="off">
            <div class="styledform-inputwrap" id="expertise-input">
              <input type="text" name="expertise" id="expertise-textbox" value="" required title="Add expertise" />
              <input type="submit" id="expertise-add" class="button" value="Add" style="margin:0px;"/>
            </div>
          </form>
          <span>Example: cpp, accounting, green-buildings, patent-law</span>
        </div>
      </li>
      <li class="form-row" style="margin-top: 35px;">
        <label class="styled-label">Past Employers</label>
        <div class="styledform-helpwrap">
          <div id="companies-wrapper">
            <%
              companies = me.get('companies', {})
              for companyId in companies.keys():
                companyItem(companyId, companies[companyId])
            %>
            %if not companies:
              <div id="company-empty-msg" class="company-empty-msg">
                Nothing found here!<br/>Please click the button below to add information.
              </div>
            %endif
          </div>
          <div id="addemp-wrap">
            <button class="button ajax" id="addemp-button" data-ref="/settings/company">Add Company</button>
          </div>
        </div>
      </li>
      <li class="form-row" style="margin-top: 35px;">
        <label class="styled-label">Education</label>
        <div class="styledform-helpwrap">
          <div class="tl-wrapper" id="schools-wrapper">
            <%
              schools = me.get('schools', {})
              for schoolId in schools.keys():
                schoolItem(schoolId, schools[schoolId])
            %>
            %if not schools:
              <div id="school-empty-msg" class="company-empty-msg">
                Nothing found here!<br/>Please click the button below to add information.
              </div>
            %endif
          </div>
          <div id="addedu-wrap">
            <button class="button ajax" id="addedu-button" data-ref="/settings/school">Add School</button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</%def>


<%def name="selectMonth(name, label=None, selected=None)">
  <%
    months = [_("January"), _("February"), _("March"), _("April"),
                _("May"), _("June"), _("July"), _("August"),
                _("September"), _("October"), _("November"), _("December")]
  %>
  <select name="${name}" class="inline-select">
    %if label:
      <option value="">${label}</option>
    %endif
    %for m in range(1, 13):
      <% value = "%02d" %m %>
      %if selected and int(selected) == m:
        <option selected value="${value}">${months[m-1]}</option>
      %else:
        <option value="${value}">${months[m-1]}</option>
      %endif
    %endfor
  </select>
</%def>

<%def name="selectDay(name, label=None, selected=None)">
  <select name="${name}" class="inline-select">
    %if label:
      <option value="">${label}</option>
    %endif
    %for d in range(1, 32):
      <% value = "%d" %d %>
      %if selected and int(selected) == d:
        <option selected value="${value}">${d}</option>
      %else:
        <option value="${value}">${d}</option>
      %endif
    %endfor
  </select>
</%def>

<%def name="selectYear(name, label=None, selected=None, years=None, id=None)">
  <select name="${name}" class="inline-select" id="${id}">
    %if label:
      <option value="">${label}</option>
    %endif
    <%
      if not years:
        years = reversed(range(1901, datetime.date.today().year + 1))
    %>
    %for d in years:
      <% value = "%d" % d %>
      %if selected and int(selected) == d:
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
          if x in settings._hiddenNotifys:
            continue
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


<%def name="schoolForm(schoolId=None, schoolVal=None)">
  <%
    year, name = schoolId.split(':', 1) if schoolId else ('', '')
    degree = schoolVal if schoolVal else ''
    dlgTitle = 'Add School' if not schoolId else 'Edit School'
  %>
  %if schoolId:
    <div id="${utils.encodeKey(schoolId)}">
  %else:
    <div>
  %endif
    <div class='ui-dlg-title addedu-title'>${dlgTitle}</div>
    <div class='addedu-center'>
      <form action="/settings/school" class="ajax">
      <ul class="dlgform">
          <li class="form-row">
              <label class="dlgform-label" for="school">${_('School')}</label>
              <input type="text" name="school" autofocus value="${name}" required/>
          </li>
          <li class="form-row">
              <label class="dlgform-label" for="degree">${_('Degree')}</label>
              <input type="text" name="degree" value="${degree}" required/>
          </li>
          <li class="form-row">
              <label class="dlgform-label" for="year">${_('Graduating Year')}</label>
              ${self.selectYear("year", selected=year)}
          </li>
          %if schoolId:
            <input type="hidden" name="id" value="${utils.encodeKey(schoolId)}"/>
          %endif
      </ul>
      <div class="addedu-buttons">
        %if not schoolId:
          <button type="button" class="button-plain" style="margin-right: 6px;"
                  onclick="$('#addedu-wrap').html('<button class=\'button ajax\' id=\'addedu-button\' data-ref=\'/settings/school\'>Add School</button>');">${_('Cancel')}</button>
          <input type="submit" class="button" value="${_('Add School')}"/>
        %else:
          <input type="submit" class="button" value="${_('Update School')}"/>
        %endif
      </div>
      </form>
    </div>
  </div>
</%def>


<%def name="companyForm(companyId=None, companyVal=None)">
  <%
    end, start, name = companyId.split(':', 2) if companyId else ('', '', '')
    jobTitle = companyVal if companyVal else ''
    dlgTitle = 'Add Company' if not companyId else 'Edit Company'
  %>
  %if companyId:
    <div id="${utils.encodeKey(companyId)}">
  %else:
    <div>
  %endif
    <div class='ui-dlg-title addemp-title'>${dlgTitle}</div>
    <div class='addemp-center'>
      <form action="/settings/company" class="ajax">
      <ul class="dlgform">
          <li class="form-row">
              <label class="dlgform-label" for="company">${_('Company')}</label>
              <input type="text" name="company" autofocus value="${name}" required/>
          </li>
          <li class="form-row">
              <label class="dlgform-label" for="title">${_('Job Title')}</label>
              <input type="text" name="title" value="${jobTitle}" required/>
          </li>
          <li class="form-row">
              <label class="dlgform-label">${_('Starting from')}</label>
              ${self.selectMonth("startmonth", selected=startMonth)}
              ${self.selectYear("startyear", selected=start)}
          </li>
          <li class="form-row">
              <label class="dlgform-label">${_('Till')}</label>
              ${self.selectMonth("endmonth", '-', selected=endMonth)}
              ${self.selectYear("endyear", '--', selected=end)}
          </li>
          %if companyId:
            <input type="hidden" name="id" value="${utils.encodeKey(companyId)}"/>
          %endif
      </ul>
      <div class="addemp-buttons">
        %if not companyId:
          <button type="button" class="button-plain" style="margin-right: 6px;"
                  onclick="$('#addemp-wrap').html('<button class=\'button ajax\' id=\'addemp-button\' data-ref=\'/settings/company\'>Add Company</button>');">${_('Cancel')}</button>
          <input type="submit" class="button" value="${_('Add Company')}"/>
        %else:
          <input type="submit" class="button" value="${_('Update Company')}"/>
        %endif
      </div>
      </form>
    </div>
  </div>
</%def>

