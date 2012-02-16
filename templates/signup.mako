<%! from social import utils, config, _, __, location_tz_map%>
<%! from pytz import common_timezones %>
<!DOCTYPE HTML>
<html lang="en" dir="ltr" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <title>Signup for Flocked-in</title>
  <link href="/rsrcs/css/static.css" media="all" rel="stylesheet" type="text/css">
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
  <script type = "text/javascript">
    %if view == 'userinfo':
      function validate() {
        var password = document.getElementById('signup-password').value;
        var pwdrepeat = document.getElementById('signup-pwdrepeat').value;
        message_wrapper = document.getElementById('messages-wrapper')

        if (document.getElementById('signup-name').value == "") {
          message_wrapper.style.display = 'block';
          message_wrapper.innerHTML = 'Name cannot be empty';
          return false;
        }
        else if (document.getElementById('signup-jobTitle').value == "") {
          message_wrapper.style.display = 'block';
          message_wrapper.innerHTML = 'Job Title cannot be empty';
          return false;
        }
        else if (password == '') {
          message_wrapper.style.display = 'block';
          message_wrapper.innerHTML = 'Password cannot be empty';
          return false;
        }
        else if (password != pwdrepeat) {
          message_wrapper.style.display = 'block';
          message_wrapper.innerHTML = 'Passwords do not match.';
          return false;
        }
        else {
          return true;
        }
      }
    %elif view == 'forgotPassword':
      function validate() {
        var email = document.getElementById('forgotpass-email').value;
        if (email == null || email == "") {
          document.getElementById('messages-wrapper').style.display = 'block';
          document.getElementById('messages-wrapper').innerHTML = 'Enter your Email.';
          return false;
        }
        return true;
      }
    %elif view == 'resetPassword':
      function validate() {
        var password = document.getElementById('resetpass-password');
        var pwdrepeat = document.getElementById('resetpass-pwdrepeat');
        if (password.value != pwdrepeat.value) {
          document.getElementById('messages-wrapper').style.display = 'block';
          document.getElementById('messages-wrapper').innerHTML = 'Passwords do not match.';
          password.value = '';
          pwdrepeat.value = '';
          return false;
        }
        return true;
      }
    %endif
  </script>
</head>

<body>
  <div id="header" class="centered-wrapper">
    <a href='/'><img id='sitelogo' src="/rsrcs/img/flocked-in.png" alt="flocked-in"/></a>
    %if view not in ['welcome', 'userinfo', 'invite']:
    <ul class="header-links">
      <li>
        <a title="What is flocked-in?" class="menuitem" href="/about/features.html" id="feature">What is flocked-in?</a>
      </li>
      <li>
        <a title="What can I use it for?" class="menuitem" href="/about/tour.html" id="feature">Tour</a>
      </li>
      <li>
        <a title="Pricing" class="menuitem" href="/about/pricing.html" id="pricing">Pricing</a>
      </li>
      <li>
        <a title="Signin" class="menuitem" href="/signin" id="signin">Sign In</a>
      </li>
    </ul>
    %endif
  </div>

  <div id="wrapper" class="centered-wrapper">
    <div id="main-contents" class="contents">
      %if view in ['welcome', 'userinfo', 'invite']:
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
      %else:
        <div id="signup-content">
          %if view in ('forgotPassword'):
            <div id="caption">${_("Forgot Password?")}</div>
          %elif view in ('resetPassword'):
            <div id="caption">${_("Reset Password")}</div>
          %elif view in ('block'):
            <div id="caption">${_("We are sorry to have bothered you")}</div>
          %endif
        </div>
      %endif
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
        <div class="styledform">
          <div id="caption">Please check your e-mail for instructions to reset your password</div>
          <a href='/signin' class="link-button">${_('Back to Signin')}</a>
        </div>
      %endif
    </div>
  </div>

  <div id="footer" class="centered-wrapper">
    <div id="footer-contents" class="contents">
      <span class="copyright">&copy;2011 Synovel</span>
      <div class="sitemeta">
        <a href="/about/tos.html">Terms of Service</a>
        &nbsp;|&nbsp;
        <a href="/about/privacy.html">Privacy Policy</a>
        &nbsp;|&nbsp;
        <a href="/about/contact.html">Contact Us</a>
      </div>
    </div>
  </div>

</body>
</html>

<%def name="userInfo()">
  <div class="styledform">
    <form action="/signup/create" method="POST" class="styledform" onsubmit="return validate()" accept-charset='UTF-8'>
      <input id="email" type="hidden" name="email" value="${emailId}"/>
      <input id="token" type="hidden" name="token" value="${token}"/>
      <ul>
        <li>
          <label for="name" class="styled-label">${_('Name')}</label>
          <input type="text" class="textfield" id="signup-name" name="name" autofocus required />
        </li>
        <li>
          <label for="jobTitle" class="styled-label">${_('Job Title')}</label>
          <input name="jobTitle" class="textfield" id="signup-jobTitle" type="text" required />
        </li>
        <li>
          <label for="timezone" class="styled-label">${_('Country/Timezone')}</label>
          <select name="timezone" class="single-row">
            ## for paid users, get the list of timezones from the org-preferences.
            ## either admin has to update the list of timezones when a branch is
            ## opened in a location of new timezone or the user will be given an
            ## option to choose from generic list.
            %for i, country_name in enumerate(location_tz_map):
              %if i == 7:
                <option value="" disabled="disabled">-----------------------------------------------</option>
              %endif
              <option value="${location_tz_map[country_name]}">${country_name}</option>
            %endfor
          </select>
        </li>
        <li>
          <label for="password" class="styled-label">${_('Password')}</label>
          <input type="password" class="textfield" id="signup-password" name="password" autocomplete="off" required />
        </li>
        <li>
          <label for="pwdrepeat" class="styled-label">${_('Confirm Password')}</label>
          <input type="password" class="textfield" id="signup-pwdrepeat" name="pwdrepeat" autocomplete="off" required/>
        </li>
        <li>
        </li>
        <div id="messages-wrapper" class="error-input"></div>
      </ul>
      <div class="buttons-wrapper">
        <span id="accept-tos">By clicking on "Create Account" below you agree with the Flocked-in <a href="/about/tos.html" target="new">Terms of Service</a> and the <a href="/about/privacy.html" target="new">Privacy Policy</a></span>
        <button type="submit" class="default button" id="submit">${_('Create Account')}</button>
      </div>
    </form>
  </div>
</%def>

<%def name="invitePeople()">
  <div>
    <form action="/signup/invite" class="styledform" method="POST">
      <ul>
        %for index in range(5):
          <li>
            <label for="email" class="styled-label">Email</label>
            %if index == 0:
              <input type="email" name="email" autofocus />
            %else:
              <input type="email" name="email" />
            %endif
          </li>
        %endfor
      </ul>
      <div class="buttons-wrapper" >
        <a href="/feed/">Skip</a>&nbsp;&nbsp;&nbsp;
        <button type="submit" class="default button" name="submit" value="Submit">${_('Invite People')}</button>
      </div>
    </form>
  </div>
</%def>

<%def name="unsubscribed()">
  <div>
    %if blockType == "all":
      <div>${_("No further invitations will be sent to %s from us.") % emailId}</div>
    %else:
      <div>${_("No further invitations will be sent to %s from this sender.") % emailId}</div>
    %endif
    <div>
      ${_("In case you change your mind, you can still register by visiting <a href='https://flocked.in'>https://flocked.in</a>")}
    </div>
  </div>
</%def>


<%def name="forgotPassword()">
  <div>
    <form action="/password/forgotPassword" class="styledform" method="POST" onsubmit="return validate()">
      <ul>
          <li>
            <label for="email" class="styled-label">Email:</label>
            <input type="email" id="forgotpass-email" name="email" required autofocus/>
          </li>
          <div id="messages-wrapper" class="error-input"></div>
      </ul>
      <div class="buttons-wrapper" >
        <button type="submit" class="default button">${_('Submit')}</button>
      </div>
    </form>
  </div>
</%def>


<%def name="resetPassword()">
  <div>
    <form action="/password/resetPassword" class="styledform" method="POST" onsubmit="return validate()">
      <ul>
          <li>
            <label for="password" class="styled-label">Password:</label>
            <input type="password" id="resetpass-password" name="password" required autofocus />
          </li>

          <li>
            <label for="pwdrepeat" class="styled-label">Confirm Password:</label>
            <input type="password" id="resetpass-pwdrepeat" name="pwdrepeat" required />
          </li>
          <div id="messages-wrapper" class="error-input"></div>
      </ul>
      <input type='hidden' name='email' value=${email} />
      <input type='hidden' name='token' value=${token} />
      <div class="buttons-wrapper">
        <button type="submit" class="default button">${_('Reset Password')}</button>
      </div>
    </form>
  </div>
</%def>

