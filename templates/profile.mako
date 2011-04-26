
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

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
          <div id="profile-tabs" class="busy-indicator">
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
      <li><a href="/profile/unfriend?id=${userKey}" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}', null, 'script'); $.event.fix(event).preventDefault();">Remove as Friend</a></li>
    %else:
      %if relations.pending.get(userKey) == "0":
        <li><a href="/profile/unfriend?id=${userKey}" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}', null, 'script'); $.event.fix(event).preventDefault();">Cancel Friend Request</a></li>
      %endif
      %if userKey in relations.subscriptions:
        <li><a href="/profile/unfollow?id=${userKey}" onclick="$.post('/ajax/profile/unfollow', 'id=${userKey}', null, 'script'); $.event.fix(event).preventDefault();">Stop Following</a></li>
      %endif
    %endif
    <li><a href="/profile/block?id=${userKey}" onclick="$.post('/ajax/profile/block', 'id=${userKey}', null, 'script'); $.event.fix(event).preventDefault();">Block User</a></li>
    <li><a href="/profile/review?id=${userKey}" onclick="$.post('/ajax/profile/review', 'id=${userKey}', null, 'script'); $.event.fix(event).preventDefault();">Request Admin Review</a></li>
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
      %if user.has_key('education'):
        <%
          keys = [x.split(':')[1] for x in user['education'].keys()]
          length = len(keys)
        %>
        ${'<span id="summary-education" class="summary-item">' + __('Studied at %s', 'Studied at %s and %s', length) % ((keys[0]) if length == 1 else (keys[1], keys[0])) + '</span>'}
      %endif
      %if user.get('personal', {}).has_key('currentCity'):
        ${'<span id="summary-lives" class="summary-item">' + _('Lives in %s') % user['personal']['currentCity'] + '</span>'}
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
        ${'<span id="edit-profile" class="summary-item"><a href="/profile/edit" class="ajax">edit</a></span>'}
      %endif
    </div>
  </div>
  <div class="clear"></div>
</%def>

<%def name="tabs()">
  <ul id="profile-tablinks" class="h-links">
    <%
      path = "/profile?id=%s&" % userKey
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

<%def name="user_actions(userKey, showRemove=False)">
  %if myKey != userKey:
    %if userKey not in relations.friends:
      %if not relations.pending or userKey not in relations.pending:
        <li class="button default" onclick="$.post('/ajax/profile/friend', 'id=${userKey}', null, 'script')"><span class="button-text">Add as Friend</span></li>
      %elif relations.pending.get(userKey) == "1":
        <li class="button default" onclick="$.post('/ajax/profile/friend', 'id=${userKey}', null, 'script')"><span class="button-text">Respond to Friend Request</span></li>
      %else:
        <li class="button disabled"><span class="button-text">Friend request sent</span></li>
      %endif
      %if userKey not in relations.subscriptions and relations.pending.get(userKey) != "1":
        <li class="button" onclick="$.post('/ajax/profile/follow', 'id=${userKey}', null, 'script')"><span class="button-text">Follow User</span></li>
      %elif showRemove:
        <li class="button" onclick="$.post('/ajax/profile/unfollow', 'id=${userKey}', null, 'script')"><span class="button-text">Unfollow User</span></li>
      %endif
    %elif showRemove:
      <li class="button" onclick="$.post('/ajax/profile/unfriend', 'id=${userKey}', null, 'script')"><span class="button-text">Unfriend User</span></li>
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

<%def name="content_notes()">
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
  %>
  %if nextPageStart:
    <% print nextPageStart %>
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" _ref="/profile?id=${userKey}&start=${nextPageStart}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
  %endif
</%def>

<%def name="content()">
  %if detail == 'info':
    ${content_info()}
  %endif
  % if detail == 'notes':
    ${content_notes()}
  %endif
</%def>

<%def name="editProfileTabs()">
  <ul id="profile-tablinks" class="h-links">
    <%
      path = "/profile/edit?id=%s&" % myKey
    %>
    %for item, name in [('basic', 'Basic'), ('detail', 'Info'), ('passwd', 'Change Password')]:
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
  %>
  <form action="/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="edit-profile">
      <ul>
        <li><label for="name"> Display Name: </label></li>
        <li><input type="text" id="name" name="name" value= "${name}" /></li>
      </ul>
      <ul>
        <li><label for="firstname"> First Name: </label></li>
        <li><input type="text" id="firstname" name="firstname" value= "${firstname}" /></li>
      </ul>
      <ul>
        <li><label for="lastname"> Last Name: </label></li>
        <li><input type="text" id="lastname" name="lastname" value= "${lastname}" /></li>
      </ul>
      <ul>
        <li><label for="jobTitle"> Job Title: </label></li>
        <li><input type="text" id="jobTitle" name="jobTitle" value="${jobTitle}" /></li>
      </ul>
      <ul>
        <li><label for="dp"> Photo </label> </li>
        <li><input type="file" id="dp" name="dp" accept="image/jpx, image/png, image/gif" />
      </ul>
      <ul>
        % if emailId and emailId[0]:
        <li><input type="hidden" value = ${emailId[0]} name="emailId" /></li>
        %endif
        % if myKey:
        <li><input type="hidden" value = ${myKey} name="id" /></li>
        %endif
      </ul>
      <ul>
        <li></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
      </ul>
    </div>
  </form>
</%def>

<%def name="changePasswd()">
<div id="error_block" style="color:red">
  % if errorMsg:
    ${errorMsg}
  %endif
</div>
<form action="/profile/changePasswd" method="post"  enctype="multipart/form-data">
  <div class="edit-profile">
    <ul>
      <li><label for="curr_passwd"> Current Password: </label></li>
      <li><input type="password" name="curr_passwd" id="curr_passwd"/></li>
    </ul>
    <ul>
      <li><label for="passwd1"> Password: </label></li>
      <li><input type="password" name="passwd1" id="passwd1"/></li>
    </ul>
    <ul>
      <li><label for="passwd2"> Confirm Password: </label></li>
      <li><input type="password" name="passwd2" id="passwd2"/></li>
    </ul>
    <ul>
        <li></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
    </ul>
    <input type="hidden" id = 'dt' name="dt" value="passwd"/>
  </div>

</form>
</%def>


<%def name="editDetail()">
<form action="/profile/edit" method="post"  enctype="multipart/form-data">
    <div class="edit-profile">
      <div id="personal">
        <h3> Personal </h3>
        <ul>
          <li> <label for ="bday"> DOB: </label></li>
          <li> ${self.selectDay("dob_day")} </li>
          <li> ${self.selectMonth("dob_mon")} </li>
          <li> ${self.selectYear("dob_year")} </li>
        </ul>
        <ul>
          <li><label for="p_email"> Email: </label> </li>
          <li><input type ="text" id= "p_email" name = "p_email"/> </li>
        </ul>
        <ul>
          <li><label for="p_phone"> Phone: </label> </li>
          <li><input type ="text" id= "p_phone" name = "p_phone"/> </li>
        </ul>
        <ul>
          <li><label for="p_mobile"> Mobile: </label> </li>
          <li><input type ="text" id= "p_mobile" name = "p_mobile"/> </li>
        </ul>
        <ul>
          <li><label for="hometown"> Hometown: </label> </li>
          <li><input type ="text" id= "hometown" name = "hometown"/> </li>
        </ul>
        <ul>
          <li><label for="currentCity"> Current City: </label> </li>
          <li><input type ="text" id= "currentCity" name = "currentCity"/> </li>
        </ul>
      </div>
      <div id="contacts">
        <h3> Contacts </h3>
        <ul>
            <li> <label for="email"> Email: </label> </li>
            <li> <input type ="text" id= "c_email" name = "c_email"/> </li>
        </ul>
        <ul>
            <li> <label for="im"> IM: </label> </li>
            <li> <input type ="text" id= "c_im" name = "c_im"/> </li>
        </ul>
        <ul>
            <li> <label for="phone">Work Phone: </label> </li>
            <li> <input type ="text" id= "c_phone" name = "c_phone"/> </li>
        </ul>
        <ul>
            <li> <label for="c_mobile">Mobile: </label> </li>
            <li> <input type ="text" id= "c_mobile" name = "c_mobile"/> </li>
        </ul>
      </div>
      <div id="workNedu">
        <h3> Work & Education </h3>
        <div id="work">
          <div>
            <ul>
              <li> <label for="employer"> Employer: </label> </li>
              <li> <input type ="text" id= "employer" name = "employer"/> </li>
            </ul>
            <ul>
              <li> <label for="emp_title"> Title: </label> </li>
              <li> <input type ="text" id= "emp_title" name = "emp_title"/> </li>
            </ul>
            <ul>
              <li> <label for="emp_desc"> Description: </label> </li>
              <li> <input type ="text" id= "emp_desc" name = "emp_desc"/> </li>
            </ul>
            <ul>
              <li> <label for="emp_start"> Years: </label> </li>
              <li> ${self.selectYear("emp_start", "Start year")}</li>
              <li> ${self.selectYear("emp_end", "End year")}</li>
            </ul>
          </div>
        </div>
        <div>
          <ul><li></li></ul>
        </div>
        <div id="education">
          <div>
            <ul>
              <li> <label for="college"> College: </label> </li>
              <li> <input type ="text" id= "college" name = "college"/> </li>
            </ul>
            <ul>
              <li> <label for="degree"> Degree: </label> </li>
              <li> <input type ="text" id= "degree" name = "degree"/> </li>
            </ul>
            <ul>
              <li> <label for="edu_end"> Year of Completion: </label> </li>
              <li> ${self.selectYear("edu_end","year")}</li>

            </ul>
          </div>
        </div>
      </div>
      <ul>
        % if emailId and emailId[0]:
        <li><input type="hidden" value = ${emailId[0]} name="emailId" /></li>
        %endif
        % if myKey:
        <li><input type="hidden" value = ${myKey} name="id" /></li>
        %endif
      </ul>
      <ul>
        <li></li>
        <li><input type="submit" name="userInfo_submit" value="Save"/> </li>
      </ul>

    </div>
  </form>

</%def>

<%def name="selectMonth(name)">

  <select name="${name}" >
        <option value="">Month</option>
        <option value="01">January</option>
        <option value="02">February</option>
        <option value="04">April</option>
        <option value="05">May</option>
        <option value="06">June</option>
        <option value="07">July</option>
        <option value="08">August</option>
        <option value="09">September</option>
        <option value="10">October</option>
        <option value="11">November</option>
        <option value="12">December</option>
    </select>
</%def>
<%def name="selectDay(name)">

  <select name="${name}">
    <option value="">day</option>
    <option value="1">1</option>
    <option value="2">2</option>
    <option value="3">3</option>
    <option value="4">4</option>
    <option value="5">5</option>
    <option value="6">6</option>
    <option value="7">7</option>
    <option value="8">8</option>
    <option value="9">9</option>
    <option value="10">10</option>
    <option value="11">11</option>
    <option value="12">12</option>
    <option value="13">13</option>
    <option value="14">14</option>
    <option value="15">15</option>
    <option value="16">16</option>
    <option value="17">17</option>
    <option value="18">18</option>
    <option value="19">19</option>
    <option value="20">20</option>
    <option value="21">21</option>
    <option value="22">22</option>
    <option value="23">23</option>
    <option value="24">24</option>
    <option value="25">25</option>
    <option value="26">26</option>
    <option value="27">27</option>
    <option value="28">28</option>
    <option value="29">29</option>
    <option value="30">30</option>
    <option value="31">31</option>
  </select>
</%def>
<%def name="selectYear(name, t='year')">
  <select name="${name}">
    <option value="">${t}</option>
    <option value="2011">2011</option>
    <option value="2010">2010</option>
    <option value="2009">2009</option>
    <option value="2008">2008</option>
    <option value="2007">2007</option>
    <option value="2006">2006</option>
    <option value="2005">2005</option>
    <option value="2004">2004</option>
    <option value="2003">2003</option>
    <option value="2002">2002</option>
    <option value="2001">2001</option>
    <option value="2000">2000</option>
    <option value="1999">1999</option>
    <option value="1998">1998</option>
    <option value="1997">1997</option>
    <option value="1996">1996</option>
    <option value="1995">1995</option>
    <option value="1994">1994</option>
    <option value="1993">1993</option>
    <option value="1992">1992</option>
    <option value="1991">1991</option>
    <option value="1990">1990</option>
    <option value="1989">1989</option>
    <option value="1988">1988</option>
    <option value="1987">1987</option>
    <option value="1986">1986</option>
    <option value="1985">1985</option>
    <option value="1984">1984</option>
    <option value="1983">1983</option>
    <option value="1982">1982</option>
    <option value="1981">1981</option>
    <option value="1980">1980</option>
    <option value="1979">1979</option>
    <option value="1978">1978</option>
    <option value="1977">1977</option>
    <option value="1976">1976</option>
    <option value="1975">1975</option>
    <option value="1974">1974</option>
    <option value="1973">1973</option>
    <option value="1972">1972</option>
    <option value="1971">1971</option>
    <option value="1970">1970</option>
    <option value="1969">1969</option>
    <option value="1968">1968</option>
    <option value="1967">1967</option>
    <option value="1966">1966</option>
    <option value="1965">1965</option>
    <option value="1964">1964</option>
    <option value="1963">1963</option>
    <option value="1962">1962</option>
    <option value="1961">1961</option>
    <option value="1960">1960</option>
    <option value="1959">1959</option>
    <option value="1958">1958</option>
    <option value="1957">1957</option>
    <option value="1956">1956</option>
    <option value="1955">1955</option>
    <option value="1954">1954</option>
    <option value="1953">1953</option>
    <option value="1952">1952</option>
    <option value="1951">1951</option>
    <option value="1950">1950</option>
    <option value="1949">1949</option>
    <option value="1948">1948</option>
    <option value="1947">1947</option>
    <option value="1946">1946</option>
    <option value="1945">1945</option>
    <option value="1944">1944</option>
    <option value="1943">1943</option>
    <option value="1942">1942</option>
    <option value="1941">1941</option>
    <option value="1940">1940</option>
    <option value="1939">1939</option>
    <option value="1938">1938</option>
    <option value="1937">1937</option>
    <option value="1936">1936</option>
    <option value="1935">1935</option>
    <option value="1934">1934</option>
    <option value="1933">1933</option>
    <option value="1932">1932</option>
    <option value="1931">1931</option>
    <option value="1930">1930</option>
    <option value="1929">1929</option>
    <option value="1928">1928</option>
    <option value="1927">1927</option>
    <option value="1926">1926</option>
    <option value="1925">1925</option>
    <option value="1924">1924</option>
    <option value="1923">1923</option>
    <option value="1922">1922</option>
    <option value="1921">1921</option>
    <option value="1920">1920</option>
    <option value="1919">1919</option>
    <option value="1918">1918</option>
    <option value="1917">1917</option>
    <option value="1916">1916</option>
    <option value="1915">1915</option>
    <option value="1914">1914</option>
    <option value="1913">1913</option>
    <option value="1912">1912</option>
    <option value="1911">1911</option>
    <option value="1910">1910</option>
    <option value="1909">1909</option>
    <option value="1908">1908</option>
  </select>
</%def>
