<%! from social import utils, config, _, __ %>
<%! from pytz import common_timezones %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${config.get('Branding', 'Name')} &mdash; ${_('Private, Secure and Free Social Network for Enterprises')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/about.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
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
  <div id="header">
    <img src="/rsrcs/img/flocked-in.png" alt="Synovel">
  </div>

  <div id="wrapper">
    <div id="steps-banner" class="title-banner banner">
      <ul id="views-list">
        <%
          views = [('welcome', 'Welcome'), ('userinfo', 'About you'), ('invite', 'Invite co-workers')]
          foundSelected = False
        %>
        %for x in range(len(views)):
          <%
            (name, display) = views[x]
            selectedCls = ''
            if view == name:
              selectedCls = ' selected'
              foundSelected = True
            doneCls = ' done' if foundSelected else ''
            lastItemCls = ' last' if x == len(views)-1 else ''
          %>
          <li class="${selectedCls+lastItemCls+doneCls}"><span>${str(x+1)+'. '+_(display)}</span></li>
        %endfor
      </ul>
    </div>
    <div id="main">
      %if view == 'welcome':
        ${self.welcome()}
      %elif view == 'userinfo':
        ${self.userInfo()}
      %elif view == 'invite':
        ${self.invitePeople()}
      %endif
    </div>
  </div>
  <div id="footer">
    <div id="footer-contents" class="contents">
      ${_('&copy;2011 Synovel Software')}
      &nbsp;&#183;&nbsp;
      <a href="/about/contact">${_('Contact us')}</a>
    </div>
  </div>
</body>

<%def name="userInfo()">
  <form action="/signup/create" method="POST" onsubmit="return validate()" >
    <input id="email" type="hidden" name="email" value="${emailId}"/>
    <input id="token" type="hidden" name="token" value="${token}"/>
    <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
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
      <div class="styledform-buttons">
        <button type="submit" class="default button" id="submit" value="Next">${_('Create Account')}</button>
      </div>
    </div>
  </form>
</%def>

<%def name="invitePeople()">
  <form action="/signup/invite" method="POST">
    <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
      <ul>
        %for index in range(5):
          <li>
            <label for="email">Email</label>
            <input type="text" name="email" />
          </li>
        %endfor
      </ul>
      <div class="styledform-buttons" >
        <a href="/feed">Skip</a>&nbsp;&nbsp;&nbsp;
        <button type="submit" class="default button" name="submit" value="Submit">${_('Invite People')}</button>
      </div>
    </div>
  </form>
</%def>

