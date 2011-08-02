
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
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right"/>
      <div id="center">
        <div id="settings-title" class="center-header">
          %if not script:
            ${self.settingsTitle()}
          %endif
        </div>
        <div class="center-contents" id="settings-content"></div>
      </div>
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
      return '<li><a href="%(link)s" id="%(id)s-sideitem" class="ajax busy-indicator %(cls)s"><span class="sidemenu-icon %(id)s-icon"></span><span class="sidemenu-text">%(text)s</a></li>' % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
       ${navMenuItem("/feed", _("Back to Home"), "back")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/settings?dt=basic", _("Basic"), "basic")}
      ${navMenuItem("/settings?dt=contact", _("Contact"), "contact")}
      ${navMenuItem("/settings?dt=personal", _("Personal Info"), "personal")}
      ${navMenuItem("/settings?dt=work", _("Work & Education"), "work")}
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/settings?dt=passwd", _("Password"), "passwd")}
      ${navMenuItem("/settings?dt=notify", _("Notifications"), "notify")}
    </ul>
 </div>
</%def>

<%def name="settingsTitle()">
  <%
    detail_name_map = {'basic':_('Basic'), 'contact': _('Contact'),
                       'work':_('Work and Education'), 'personal':_('Personal'),
                       'passwd':_('Password'), 
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
  myTimezone = me.get("basic", {}).get("timezone", "")
  %>
  <form id="settings-form" action="/settings" method="post" class="ajax" enctype="multipart/form-data">
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
<form class="ajax" id="settings-form" action="/settings/passwd" method="post"  enctype="multipart/form-data">
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
<form class="ajax" id="settings-form" action="/settings" method="post"  enctype="multipart/form-data">
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
<form class="ajax" id="settings-form" action="/settings" method="post"  enctype="multipart/form-data">
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
        %if emailId and emailId[0]:
          <input type="hidden" value = ${emailId[0]} name="emailId" />
        %endif
        %if myKey:
          <input type="hidden" value = ${myKey} name="id" />
        %endif
    </div>
    <div class="styledform-buttons">
        <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
    </div>
  </form>
</%def>

<%def name="editContact()">
<form class="ajax" id="settings-form" action="/settings" method="post"  enctype="multipart/form-data">
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
      %for d in range(1, 31):
        <% value = "%d" %d %>
        %if dod and int(dod) == d:
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
        <% value = "%d" %d %>
        %if doy and int(doy)== d:
          <option selected value="${value}">${d}</option>
        %else:
          <option value="${value}">${d}</option>
        %endif
      %endfor
  </select>
</%def>

<%def name="emailPreferences()">
<%
  if 'email_preferences' in me['basic']:

    email_preferences = int(me['basic']['email_preferences'])
  else:
    email_preferences = 4095 #2**12-1 
  new_friend_request = email_preferences &1
  accepted_my_friend_request = email_preferences &2
  new_follower = email_preferences &4
  new_member_to_network = email_preferences &8

  new_group_invite = email_preferences &16
  pending_group_request = email_preferences &32
  accepted_my_group_membership = email_preferences &64
  new_post_to_group = email_preferences &128

  new_message = email_preferences &256
  #new_message_reply = email_preferences &512

  others_act_on_my_post = email_preferences &1024
  others_act_on_item_following = email_preferences &2048

  def foo(name, value):
    if value:
        return """<input type="checkbox" name="%s" value="1" checked="checked"/>""" %(name)
    else:
        return """<input type="checkbox" name="%s" value="0" /> """ %(name)
%>
<form class="ajax" id="settings-form" action="/settings/notify" method="post"  enctype="multipart/form-data">
  <div class="styledform">
    <legend> Email me when </legend>
    <ul>
      <li>
        <div id="new-requests">
          <ul>
            <li>
              ${foo("new_friend_request", new_friend_request)}
              ${_("Someone added me as a friend")}
            </li>      
            <li>
              ${foo("accepted_my_friend_request", accepted_my_friend_request)}
              ${_("Others accept my friend request")}
            </li>
             <li>
              ${foo("new_follower", new_follower)}
              ${_("Someone starts following me")}
            </li>
            <li>
              ${foo("new_member_to_network", new_member_to_network)}
              ${_("New member joins the network")}
            </li>
          </ul>
        </div>
      </li>
      <li>
        <div id="edit-setting-groups">
          <legend>Groups</legend>
          <ul>
            <li>
              ${foo("new_group_invite", new_group_invite)}
              ${_("Someone invites me to join a group")}
            </li>
            <li>
              ${foo("pending_group_request", pending_group_request)}
              ${_("Someone requests to join private group for which i am administrator")}
            </li>
            <li>
              ${foo("accepted_my_group_membership", accepted_my_group_membership)}
              ${_("My group membership is accepted")}
            </li>
            <li>
              ${foo("new_post_to_group", new_post_to_group)}
              ${_("Someone posts to a group im member of")}
            </li>
          </ul>
        </div>
      </li>
      <li>
        <div id="edit-setting-messages">
          <legend>Messages</legend>
          <ul>
            <li>
              ${foo("new_message", new_message)}
              ${_("I receive new message")}
            </li>
          </ul>
        </div>
      </li>
      <li>
        <div id="edit-setting-posts">
          <legend>Posts</legend>
          <ul>
            <li>
              ${foo("others_act_on_my_post", others_act_on_my_post)}
              ${_("Others liked/commented on my post")}
            </li>
            <li>
              ${foo("others_act_on_item_following", others_act_on_item_following)}
              ${_("Others liked/liked my comment/commented on posts i liked/commented ")}
            </li>
          </ul>
        </div>
      </li>
    </ul>
    <input type="hidden" id = 'dt' name="dt" value="email_preferences"/>
  </div>
  <div class="styledform-buttons">
    <input type="submit" class="button default" name="userInfo_submit" value="Save"/>
  </div>
</form>
</%def>

