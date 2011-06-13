<%! from gettext import gettext as _ %>
<%! from pytz import common_timezones %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${_('Synovel SocialNet')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/signin.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/widgets.css"/>
  <script type = "text/javascript">
  %if view == 'userinfo':
    function validate() {
      return document.getElementById("password").value == document.getElementById("pwdrepeat").value
    }
  %endif
  </script>
</head>
<body>
  <div id="inner">
    <div id="header"><img alt="Synovel" src="/public/images/synovel.png"/></div>
    <div id="menu" class="signup-menu">
        <span class="hlinks view-options">
          <%
            currentView = view if view else 'userinfo'
            orderedViews = ['userinfo', 'invite']
            views = {'userinfo': 'Basic Info', 'invite': 'Invite Friends'}
          %>
          %for vtype in orderedViews:
            %if vtype == currentView:
              <span class="selected">${_(views[vtype])}</span>
            %else:
              <span>${_(views[vtype])}</span>
            %endif
          %endfor
        </span>
    </div>
    <div id="signup_form" >
      %if view == 'invite':
        ${self.invitePeople()}
      %elif view == 'userinfo':
        ${self.userInfo()}
      %endif
    </div>
    <div  id="footer" class="signup-save-wrapper">
      ${_('&copy;2011 Synovel Software')}
      &nbsp;|&nbsp;
      <a href="http://www.synovel.com/social">${_('Synovel SocialNet')}</a>
    </div>
  </div>
</body>
</html>

<%def name="userInfo()">
 <form action="/signup/create" method="POST" onsubmit="return validate()" >
    <div class="signup">
      <ul>
        <li><input id="emailId" type="hidden" class="textfield" name="emailId" value="${emailId}"></input></li>
        <li>
          <label for="name">${_('Name:')}</label>
          <input type="text" class="textfield" name="name" />
        </li>
        <li>
          <label for="jobTitle">${_('Job Title:')}</label>
          <input name="jobTitle" id="jobTitle" type="text" />
        </li>
        <li>
          <label for="timezone">${_('Timezone')}</label>
          <select name="timezone">
            ## for paid users, get the list of timezones from the org-preferences.
            ## either admin has to update the list of timezones when a branch is
            ## opened in a location of new timezone or the user will be given an
            ## option to choose from generic list.
            %for timezone in common_timezones:
              <option value="${timezone}">${timezone}</option>
            %endfor
          </select>
        </li>
        <li>
          <label for="password">${_('Password:')}</label>
          <input type="password" class="textfield" name="password"/>
        </li>
        <li>
          <label for="pwdrepeat">${_('Confirm Password:')}</label>
          <input type="password" class="textfield" name="pwdrepeat" />
        </li>
      </ul>
      <div class="signup-save-wrapper">
        <button type="submit" class="button" id="submit" value="Next"> ${_('Next')} </button>
      </div>
    </div>
  </form>
</%def>

<%def name="invitePeople()">
  <form action="/signup/invite" method="POST">
    <div class="signup" >
      <ul>
        <li>
          <h4>Invite Your Colleagues</h4>
        </li>
      </ul>
      <ul>
        <li><label for="email">email:</label>
          <input type="text" name="email" /></li>
        <li><label for="email">email:</label>
          <input type="text" name="email" /></li>
        <li><label for="email">email:</label>
          <input type="text" name="email" /></li>
        <li><label for="email">email:</label>
          <input type="text" name="email" /></li>
        <li><label for="email">email:</label>
          <input type="text" name="email" /></li>
      </ul>
    </div>
    <div class="signup" >
      <ul>
        <li><h4>Upload  Contacts</h4></li>
        <li></li>
        <li>
          <label for="file">Upload:</label>
          <input type="file" name="file" disabled="disabled" />
        </li>
      </ul>
    </div>
    <div class="signup-save-wrapper" >
      <a href="/feed">Skip</a>
      <button type="submit" class="button" name="submit" value="Submit">Submit</button>
    </div>
  </form>
</%def>
