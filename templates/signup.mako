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
  function validate()
  {

    return document.getElementById("password1").value == document.getElementById("password2").value
  }
  </script>
</head>

<body>
  <div id="inner">
    <div id="header"><img alt="Synovel" src="/public/images/synovel.png"/></div>
    <div id="menu" class="register-menu">
        <span class="hlinks view-options">
          <%
            uview = view if view else 'userinfo'
            orderedViews = ['userinfo', 'invite']
            views = {'userinfo': 'Basic Info', 'invite': ' Invite Friends' }
          %>
          % for vtype in orderedViews:
            % if vtype == uview:
              <span class="selected"> ${_(views[vtype])} </span>
            % else:
              <span> ${_(views[vtype])} </span>
            % endif
          % endfor
        </span>
    </div>
    <div id="signup_form" >
      % if view == 'people':
        ${self.userInfo()}
      % elif view == 'invite':
        ${self.invitePeople()}
      % else:
        ${self.userInfo()}
      % endif
    </div>
    <div  id="footer" class="register-save-wrapper">
        ${_('&copy;2011 Synovel Software')}
        &nbsp;|&nbsp;
        <a href="http://www.synovel.com/social">${_('Synovel SocialNet')}</a>
    </div>
  </div>
</body>
</html>


<%def name="userInfo()">
 <form action="/register/create" method="POST" onsubmit="return validate()" >
    <div class="register">
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
                % for timezone in common_timezones:
                ## for paid users, get the list of timezones from the org-preferences.
                ## either admin has to update the list of timezones when a branch is opened in a location of new timezone or.
                ## user will be given an option to choose from generic list.
                  <option value="${timezone}"> ${timezone} </option>
                % endfor
            </select>
        </li>
        <li>
          <label for="password">${_('Password:')}</label>
          <input type="password" class="textfield" name="password"/>
        </li>
        <li>
          <label for="password1">${_('Confirm Password:')}</label>
          <input type="password" class="textfield" name="password1" />
        </li>
      </ul>
      <div class="register-save-wrapper">
        <button type="submit" class="button" id="submit" value="Next"> ${_('Next')} </button>
      </div>
    </div>
  </form>
</%def>

<%def name="invitePeople()">
    <form action="/register/invite" method="POST">
      <input type="hidden" name="sender" value="${emailId}" />
      <div class="register" >
        <ul>
          <li>
            <h4> Invite Your Colleagues </h4>
          </li>
          ##<li><input type="hidden" name="sender" value="${emailId}" /></li>
        </ul>
        <ul>
          <li><label for="email" >email:</label>
            <input type="text" name="emailId" /></li>
          <li><label for="email" >email:</label>
            <input type="text" name="emailId" /></li>
          <li><label for="email" >email:</label>
            <input type="text" name="emailId" /></li>
          <li><label for="email" >email:</label>
            <input type="text" name="emailId" /></li>
          <li><label for="email" >email:</label>
            <input type="text" name="emailId" /></li>
        </ul>
      </div>
      <div class="register" >
        <ul>
          <li><h4> Upload  Contacts </h4></li>
          <li></li>
          <li><label for="file"> Upload:</label>
              <input type="file" name="file" disabled="disabled" />
          </li>
        </ul>
            ##<h4> Or Import Contacts From</h4>
            ##<span class="icons">
            ##  <img src="/public/images/22/google-talk.png" alt="Google" height="36px" width="36px"/>
            ##  <img src="/public/images/48/yahoo.png" alt="Yahoo!" height="36px" width="36px" />
            ##  <img src="/public/images/48/msn.png" alt="MSN" height="36px" width="36px"/>
            ##</span>
      </div>
      <div class="register-save-wrapper" >
        <button type="submit" class="button " name="skip" value="Skip">Skip </button>
        <button type="submit" class="button" name="submit" value="Submit">Submit</button>
      </div>
    </form>
</%def>
