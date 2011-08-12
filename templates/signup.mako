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
        document.getElementById('messages-wrapper').innerHTML = 'Passwords do not match.';
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
  %elif view == 'forgotPassword':
    function validate(){
      var email = document.querySelector('input[name="email"]').value
      if (email == null || email == ""){
        document.getElementById('messages-wrapper').style.display = 'block';
        document.getElementById('messages-wrapper').innerHTML = 'Enter your Email.';
        return false
      }
      return true
    }
   %elif view == 'resetPassword':
    function validate(){
      var password = document.querySelector('input[name="password"]')
      var pwdrepeat = document.querySelector('input[name="pwdrepeat"]')
      if (password.value != pwdrepeat.value){
        document.getElementById('messages-wrapper').style.display = 'block';
        document.getElementById('messages-wrapper').innerHTML = 'Passwords do not match.';
        password.value ='';
        pwdrepeat.value ='';
        return false
      }
      return true
    }
  %endif
  </script>
</head>

<body>
  <div id="header">
    <a href='/'><img id='sitelogo' src="/rsrcs/img/flocked-in.png" alt="Synovel"></a>
  </div>

  <div id="wrapper">
    <div id="steps-banner" class="title-banner banner">
      %if view in ['welcome', 'userinfo', 'invite']:
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
      %else:
        <ul id="views-list">
          % if view in ('forgotPassword'):
            <li class="selected"><span>${_("Forgot Password?")}</span></li>
          % elif view in ('resetPassword', 'forgotPassword-post'):
            <li class="selected"><span>${_("Reset Password")}</span></li>
          % else:
            <li class="last">${_('Unsubscribed')}</li>
          % endif
        </ul>
      %endif
    </div>
    <div id="main">
      %if view == 'welcome':
        ${self.welcome()}
      %elif view == 'userinfo':
        ${self.userInfo()}
      %elif view == 'invite':
        ${self.invitePeople()}
      %elif view == 'block':
        ${self.unsubscribed()}
      %elif view == 'forgotPassword':
        ${self.forgotPassword()}
      %elif view == 'resetPassword':
        ${self.resetPassword()}
      %elif view == 'forgotPassword-post':
        <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
          <ul>
            <li>
              <span> We have sent an email with instructions to reset your password </span><br>
              <span> <a href='/signin'>Back to Signin</a> </span>
            <li>
            <li>
            </li>
          </ul>
        </div>
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
          <input type="text" class="textfield" name="name" autofocus required />
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
          <input type="password" class="textfield" name="password" autocomplete="off" required />
        </li>
        <li>
          <label for="pwdrepeat">${_('Confirm Password')}</label>
          <input type="password" class="textfield" name="pwdrepeat" autocomplete="off" required/>
        </li>
        <div id="messages-wrapper" class="error-input"></div>
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
            %if index == 0:
              <input type="email" name="email" autofocus />
            %else:
              <input type="email" name="email" />
            %endif
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

<%def name="unsubscribed()">
  <div id="main-contents" class="contents" style="width: 600px; margin: 30px auto;">
    %if blockType == "all":
      <div><b>${_("No further invitations will be sent to %s from us.") % emailId}</b></div>
    %else:
      <div><b>${_("No further invitations will be sent to %s from this sender.") % emailId}</b></div>
    %endif
    <div style="margin:20px 0;">
      ${_("We are sorry to have bothered you")}<br/>
      ${_("In case you change your mind, you can still register by visiting <a href='http://flocked.in'>http://flocked.in</a>")}
    </div>
  </div>
</%def>


<%def name="forgotPassword()">
   <form action="/password/forgotPassword" method="POST" onsubmit="return validate()">
    <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
      <ul>
          <li>
            <label for="email">Email:</label>
            <input type="email" name="email" required autofocus/>
          </li>
          <div id="messages-wrapper" class="error-input"></div>
      </ul>
      <div class="styledform-buttons" >
        <input type="submit" class="default button" name="submit" value="Submit"></input>
      </div>
    </div>
  </form>
</%def>

<%def name="resetPassword()">
   <form action="/password/resetPassword" method="POST" onsubmit="return validate()">
    <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
      <ul>
          <li>
            <label for="password">Password:</label>
            <input type="password" name="password" required autofocus />
          </li>

          <li>
            <label for="pwdrepeat">Confirm Password:</label>
            <input type="password" name="pwdrepeat" required />
          </li>
          <div id="messages-wrapper" class="error-input"></div>
      </ul>
      <input type='hidden' name='email' value=${email} />
      <input type='hidden' name='token' value=${token} />
      <div class="styledform-buttons" >
        <input type="submit" class="default button" name="submit" value="Submit"></input>
      </div>
    </div>
  </form>
</%def>

