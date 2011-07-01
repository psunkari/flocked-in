
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
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
    %if userKey in relations.friends:
      <li><a href="/profile/unfriend?id=${userKey}" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}'); $.event.fix(event).preventDefault();">Remove as Friend</a></li>
    %else:
      %if relations.pending.get(userKey) == "0":
        <li><a href="/profile/unfriend?id=${userKey}" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}'); $.event.fix(event).preventDefault();">Cancel Friend Request</a></li>
      %endif
      %if userKey in relations.subscriptions:
        <li><a href="/profile/unfollow?id=${userKey}" onclick="$.post('/ajax/profile/unfollow', 'id=${userKey}'); $.event.fix(event).preventDefault();">Stop Following</a></li>
      %endif
    %endif
    <li><a href="/profile/block?id=${userKey}" onclick="$.post('/ajax/profile/block', 'id=${userKey}'); $.event.fix(event).preventDefault();">Block User</a></li>
    <li><a href="/profile/review?id=${userKey}" onclick="$.post('/ajax/profile/review', 'id=${userKey}'); $.event.fix(event).preventDefault();">Request Admin Review</a></li>
  %if renderWrapper:
  </ul>
  </div>
  %endif
  %endif
</%def>

<%def name="summary()">
  <div id="useravatar">
    <% avatarURI = utils.userAvatar(userKey, user, "large") %>
    %if avatarURI:
      <img src="${avatarURI}" width=128 height=128/>
    %endif
  </div>
  <div id="userprofile">
    <div class="titlebar">
      <div>
        <span class="middle title">${user['basic']['name']}</span>
        <ul id="user-actions-${userKey}" class="middle user-actions h-links">
          ${user_actions(userKey)}
        </ul>
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
      %if user.get('personal', {}).has_key('birthday'):
        <%
          stamp = user['personal']['birthday']  ## YYYYMMDD
          formatmap = {"year": stamp[0:4], "month": utils.monthName(int(stamp[4:6])), "day": stamp[6:]}
        %>
        ${'<span id="summary-born" class="summary-item">' + _('Born on %(month)s %(day)s, %(year)s') % formatmap + '</span>'}
      %endif
      %if user.get('contact',{}).has_key('mail'):
        ${'<span id="summary-workmail" class="summary-item">' + user['contact']['mail'] + '</span>'}
      %endif
      %if user.get('contact', {}).has_key('phone'):
        ${'<span id="summary-phone" class="summary-item">' + user['contact']['phone'] + '</span>'}
      %endif
      %if user.get('contact',{}).has_key('mobile'):
        ${'<span id="summary-mobile" class="summary-item">' + user['contact']['mobile'] + '</span>'}
      %endif

      %if myKey == userKey:
        ${'<span id="edit-profile" class="summary-item"><a href="/profile/edit" class="ajax">Edit Profile</a></span>'}
      %endif
    </div>
  </div>
  <div class="clear"></div>
</%def>

<%def name="tabs()">
  <ul id="profile-tablinks" class="tablinks h-links">
    <%
      path = "/profile?id=%s&" % userKey
    %>
    %for item, name in [('activity', 'Activity'), ('info', 'Info')]:
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
        <button class="button default" onclick="$.post('/ajax/profile/friend', 'id=${userKey}')"><span class="button-text">Add as Friend</span></button>
      %elif relations.pending.get(userKey) == "1":
        <button class="acl-button button" onclick="$$.ui.showPopUp(event)">Respond to Friend Request</button>
        <ul class="acl-menu" style="display:none;">
            <li><a class="acl-item" _acl="public" onclick="$.post('/ajax/profile/friend', 'id=${userKey}')"><div class="icon"></div>${_("Accept")}</a></li>
            <li><a class="acl-item" _acl="friends" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}')"><div class="icon"></div>${_("Reject")}</a></li>
        </ul>
      %else:
        <button class="button disabled"><span class="button-text">Friend request sent</span></button>
      %endif
      %if userKey not in relations.subscriptions and relations.pending.get(userKey) != "1":
        <button class="button" onclick="$.post('/ajax/profile/follow', 'id=${userKey}')"><span class="button-text">Follow User</span></button>
      %elif showRemove:
        <button class="button" onclick="$.post('/ajax/profile/unfollow', 'id=${userKey}')"><span class="button-text">Unfollow User</span></button>
      %endif
    %elif showRemove:
      <button class="button" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}')"><span class="button-text">Unfriend User</span></button>
    %endif
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
      rtype, itemId, convId, convType, convOwnerId, commentSnippet = key
      if not reasonStr.has_key(key):
        if len(block) > 0:
          self.activity_block(block)
          block = []
        item.item_layout(convId)
      elif convType in plugins:
        block.append(key)
    if block:
      self.activity_block(block)

  %>
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" _ref="/profile?id=${userKey}&start=${nextPageStart}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
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

<%def name="editProfileTabs()">
  <ul class="tablinks h-links">
    <%
      path = "/profile/edit?id=%s&" % myKey
    %>
    %for item, name in [('basic', _('Basic')), ('contact', _('Contact')), ('work', _('Work Experience')), ('personal', _('Personal')), ('passwd', _('Change Password'))]:
      %if detail == item:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax selected">${_(name)}</a></li>
      %else:
        <li><a href="${path}dt=${item}" id="profile-tab-${item}" class="ajax">${_(name)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="editBasicInfo()">
  <%
  name = me.get("basic", {}).get("name", '')
  firstname = me.get("basic", {}).get("firstname", '')
  lastname = me.get("basic", {}).get("lastname", '')
  jobTitle = me.get("basic", {}).get("jobTitle", '')
  myTimezone = me.get("basic", {}).get("timezone", "")
  %>
  <form id="profile_form" action="/ajax/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="styledform">
      <ul>
        <li>
            <label for="name"> Display Name</label>
            <input type="text" id="displayname" name="name" value= "${name}" />
        </li>
        <li>
            <label for="firstname"> First Name</label>
            <input type="text" id="firstname" name="firstname" value= "${firstname}" />
        </li>
        <li>
            <label for="lastname"> Last Name</label>
            <input type="text" id="lastname" name="lastname" value= "${lastname}" />
        </li>
        <li>
            <label for="jobTitle"> Job Title</label>
            <input type="text" id="jobTitle" name="jobTitle" value="${jobTitle}" />
        </li>
        <li>
          <label for="timezone">Timezone </label>
          <select name="timezone" class="single-row">
            % for timezone in common_timezones:
              % if timezone == myTimezone:
                <option value = "${timezone}" selected="">${timezone}</option>
              % else:
                <option value = "${timezone}" >${timezone}</option>
              % endif
            % endfor
          </select>
        </li>
        <li>
            <label for="dp"> Photo </label>
            <input type="file" id="dp" name="dp" accept="image/jpx, image/png, image/gif" />
        </li>

        % if emailId and emailId[0]:
        <input type="hidden" value = ${emailId[0]} name="emailId" />
        %endif
        % if myKey:
        <input type="hidden" value = ${myKey} name="id" />
        %endif
      </ul>
    </div>
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
    </div>
  </form>
</%def>

<%def name="changePasswd()">
<div id="error_block" style="color:red">
  % if errorMsg:
    ${errorMsg}
  %endif
</div>
<form class="ajax" id="profile_form" action="/profile/changePasswd" method="post"  enctype="multipart/form-data">
  <div class="styledform">
    <ul>
      <li>
        <label for="curr_passwd"> Current Password</label>
        <input type="password" name="curr_passwd" id="curr_passwd"/>
      </li>
      <li>
        <label for="passwd1"> New Password</label>
        <input type="password" name="passwd1" id="passwd1"/>
      </li>
      <li>
        <label for="passwd2"> Confirm Password</label>
        <input type="password" name="passwd2" id="passwd2"/>
      </li>
    </ul>
    <input type="hidden" id = 'dt' name="dt" value="passwd"/>
  </div>
  <div class="styledform-buttons">
    <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
  </div>
</form>
</%def>

<%def name="editWork()">
<form class="ajax" id="profile_form" action="/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="styledform">
        <div id="work">
          <div>
            <legend>Current Work</legend>
            <ul>
              <li>
                <label for="employer"> Employer</label>
                <input type ="text" />
              </li>
              <li>
                <label for="emp_title"> Title</label>
                <input type ="text" name="jobTitle"/>
              </li>
              <li>
                <label for="emp_start">Working Since</label>
                ${self.selectYear("c_emp_start", "Start year")}
              </li>
            </ul>
            <legend>Previous Work</legend>
            <ul>
              <li>
                <label for="employer"> Employer</label>
                <input type ="text" id= "employer" name = "employer"/>
              </li>
              <li>
                <label for="emp_title"> Title</label>
                <input type ="text" id= "emp_title" name = "emp_title"/>
              </li>
              <li>
                <label for="emp_start"> Years</label>
                ${self.selectYear("emp_start", "Start year")}
                ${self.selectYear("emp_end", "End year")}
              </li>
            </ul>
          </div>
        </div>
        <div id="education">
          <div>
            <legend>Education</legend>
            <ul>
              <li>
                <label for="college"> College</label>
                <input type ="text" id= "college" name = "college"/>
              </li>
            </ul>
            <ul>
              <li>
                <label for="degree"> Degree</label>
                <input type ="text" id= "degree" name = "degree"/>
              </li>
            </ul>
            <ul>
              <li>
                <label for="edu_end"> Year of Completion</label>
                ${self.selectYear("edu_end","year")}
              </li>
            </ul>
          </div>
      </div>
    </div>
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
    </div>
    % if emailId and emailId[0]:
    <input type="hidden" value = ${emailId[0]} name="emailId" />
    %endif
    % if myKey:
    <input type="hidden" value = ${myKey} name="id" />
    %endif
</form>
</%def>

<%def name="editPersonal()">
<form class="ajax" id="profile_form" action="/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="styledform">
      <div id="personal">
        <ul>
          <li>
            <%
                rawstr = r"""(?P<doy>\d{4})(?P<dom>\d{2})(?P<dod>\d{1,2})"""
                matchstr = personalInfo.get('birthday', '')
                compile_obj = re.compile(rawstr)
                match_obj = compile_obj.search(matchstr)
                if match_obj:
                    doy = match_obj.group('doy')
                    dom = match_obj.group('dom')
                    dod = match_obj.group('dod')
                else:
                    doy = dom = dod = None
            %>
            <label for ="bday"> Date Of Birth</label>
            ${self.selectDay("dob_day", "Day", dod)}
            ${self.selectMonth("dob_mon", "Month", dom)}
            ${self.selectYear("dob_year", "Year", doy)}
          </li>
          <li>
            <label for="p_email"> Email</label>
            <input type ="text" id= "p_email" name = "p_email" value="${personalInfo.get('mail', '')}"/>
          </li>
          <li>
            <label for="p_phone"> Phone</label>
            <input type ="text" id= "p_phone" name = "p_phone" value="${personalInfo.get('phone', '')}"/>
          </li>
          <li>
            <label for="p_mobile"> Mobile</label>
            <input type ="text" id= "p_mobile" name = "p_mobile" value="${personalInfo.get('mobile', '')}"/>
          </li>
          <li>
            <label for="hometown"> Hometown</label>
            <input type ="text" id= "hometown" name = "hometown" value="${personalInfo.get('hometown', '')}"/>
          </li>
          <li>
            <label for="currentCity"> Current City</label>
            <input type ="text" id= "currentCity" name = "currentCity" value="${personalInfo.get('currentCity', '')}"/>
          </li>
        </ul>
      </div>
        % if emailId and emailId[0]:
        <input type="hidden" value = ${emailId[0]} name="emailId" />
        %endif
        % if myKey:
        <input type="hidden" value = ${myKey} name="id" />
        %endif
    </div>
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
    </div>
  </form>
</%def>

<%def name="editContact()">
<form class="ajax" id="profile_form" action="/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="styledform">
      <div id="contacts">
        <ul>
            <li>
                <label for="email"> Email</label>
                <input type ="text" id= "c_email" name = "c_email" value="${contactInfo.get('mail', '')}"/>
            </li>
            <li>
                <label for="im"> IM</label>
                <input type ="text" id= "c_im" name = "c_im" value="${contactInfo.get('im', '')}"/>
            </li>
            <li>
                <label for="phone">Work Phone</label>
                <input type ="text" id= "c_phone" name = "c_phone" value="${contactInfo.get('phone', '')}"/>
            </li>
            <li>
                <label for="c_mobile">Work Mobile</label>
                <input type ="text" id= "c_mobile" name = "c_mobile" value="${contactInfo.get('mobile', '')}"/>
            </li>
        </ul>
      </div>
      <div class="styledform-buttons">
          <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
      </div>
    </div>
    % if emailId and emailId[0]:
    <input type="hidden" value = ${emailId[0]} name="emailId" />
    %endif
    % if myKey:
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
        %for m in range(1, 12):
            <%
                value = "%02d" %m
            %>
            %if dom and int(dom)== m:
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
        %for d in range(1, 31):
            <%
                value = "%d" %d
            %>
            %if dod and int(dod)== d:
                <option selected value="${value}">${d}</option>
            %else:
                <option value="${value}">${d}</option>
            %endif
        %endfor
  </select>
</%def>

<%def name="selectYear(name, label, doy=None)">
  <select name="${name}" class="inline-select">
    <option value="">${label}</option>
        %for d in reversed(range(1901, datetime.date.today().year)):
            <%
                value = "%d" %d
            %>
            %if doy and int(doy)== d:
                <option selected value="${value}">${d}</option>
            %else:
                <option value="${value}">${d}</option>
            %endif
        %endfor
  </select>
</%def>
