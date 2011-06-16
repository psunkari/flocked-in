<%! from gettext import gettext as _ %>
<%! from pytz import common_timezones %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>${_('Synovel SocialNet')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/signin.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <script type = "text/javascript">
  %if view == 'userinfo':
    function validate() {
      var password = document.querySelector('input[name="password"]').value
      var pwdrepeat = document.querySelector('input[name="pwdrepeat"]').value
      if (password != pwdrepeat){
        document.getElementById('messages-wrapper').style.display = 'block';
        document.getElementById('messages-wrapper').innerHTML = 'Kindly confirm your Password.';
        setTimeout(function(){
          document.getElementById('messages-wrapper').style.display = 'none';
          document.getElementById('messages-wrapper').innerHTML = '';
        }, 3000)
      return false
      }
      else if (document.querySelector('input[name="name"]').value == ""){
        document.getElementById('messages-wrapper').style.display = 'block';
        document.getElementById('messages-wrapper').innerHTML = 'Your Name is a required field.';
        setTimeout(function(){
          document.getElementById('messages-wrapper').style.display = 'none';
          document.getElementById('messages-wrapper').innerHTML = '';
        }, 3000)
      return false
      }
      else{
        return true
      }
    }
  %endif
  </script>
</head>
<body>
  <div id="topbar">
    <div id="top" class="contents">
      <div id="sitelogo">
      </div>
    </div>
  </div>
  <div id="menubar">
    <div id="menu" class="contents">
    </div>
  </div>
  <div id="mainbar">
    ${self.layout()}
  </div>
</body>
</html>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
      </div>
    </div>
    <div id="center-right">
      <div id="right">
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            %if view == 'userinfo':
              <span class="middle title">${_('Create your Account')}</span>
            %elif view == 'invite':
              <span class="middle title">${_('Invite your friends')}</span>
            %endif
          </div>
        </div>
        <div class="center-contents">
            %if view == 'invite':
              ${self.invitePeople()}
            %elif view == 'userinfo':
              ${self.userInfo()}
            %endif
        </div>
      </div>
    </div>
    <div  id="footer">
      ${_('&copy;2011 Synovel Software')}
      &nbsp;|&nbsp;
      <a href="http://www.synovel.com/social">${_('Synovel SocialNet')}</a>
    </div>

  </div>
</%def>

<%def name="userInfo()">
 <form action="/signup/create" method="POST" onsubmit="return validate()" >
    <input id="email" type="hidden" name="email" value="${emailId}"/>
    <input id="token" type="hidden" name="token" value="${token}"/>
    <div class="edit-profile">
      <ul>
        <li>
          <label for="name">${_('Name')}</label>
          <input type="text" class="textfield" name="name" />
        </li>
        <li>
          <label for="jobTitle">${_('Job Title')}</label>
          <input name="jobTitle" id="jobTitle" type="text" />
        </li>
        <li>
          <label for="timezone">${_('Timezone')}</label>
          <select name="timezone" class="single-row">
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
          <label for="password">${_('Password')}</label>
          <input type="password" class="textfield" name="password" autocomplete="off"/>
        </li>
        <li>
          <label for="pwdrepeat">${_('Confirm Password')}</label>
          <input type="password" class="textfield" name="pwdrepeat" autocomplete="off"/>
        </li>
        <li style="display:none" id="messages-wrapper" class="messages-error"></li>
      </ul>
      <div class="profile-save-wrapper">
        <button type="submit" class="button" id="submit" value="Next"> ${_('Create')} </button>
      </div>
    </div>
  </form>
</%def>

<%def name="invitePeople()">
  <form action="/signup/invite" method="POST">
    <div class="edit-profile">
      <ul>
        <li>
          <label for="email">Email</label>
          <input type="text" name="email" />
        </li>
        <li>
          <label for="email">Email</label>
          <input type="text" name="email" />
        </li>
        <li>
          <label for="email">Email</label>
          <input type="text" name="email" />
        </li>
        <li>
          <label for="email">Email</label>
          <input type="text" name="email" />
        </li>
        <li>
          <label for="email">Email</label>
          <input type="text" name="email" />
        </li>
      </ul>
    </div>
    <div class="profile-save-wrapper" >
      <a href="/feed">Skip</a>
      <button type="submit" class="button" name="submit" value="Submit">Invite</button>
    </div>
  </form>
</%def>
