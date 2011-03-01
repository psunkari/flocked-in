<%! from gettext import gettext as _ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${_('Synovel SocialNet')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/signin.css"/>
</head>

<body>
  <div id="header">
    <img alt="Synovel" src="/public/images/synovel.png"/>
  </div>
  <div id="wrapper">
    <div id="inner">
      <form action="/signin${query}" method="POST">
      <div id="signin">
        <table id="signin-table" cellspacing="0" cellpadding="3" border="0" align="center">
          <tr>
            <td colspan="2" class="title">
              Signin to your account
            </td>
          </tr>
          <tr>
            <td id="userlabel"><label for="username">${_('Username')}:</label></td>
            <td id="userfield"><input id="username" type="text" class="textfield" name="u"></input></td>
          </tr>
          <tr>
            <td id="passlabel"><label for="password">${_('Password')}:</label></td>
            <td id="passfield"><input id="password" type="password" class="textfield" name="p"></input></td>
          </tr>
          <tr>
            <td id="rememberfield"><input type="checkbox" id="remember" checked="true" name="remember"/></td>
            <td id="rememberlabel"><label for="remember">${_('Keep me logged in')}</label></td>
          </tr>
          <tr>
            <td colspan="2" id="signin-submitbox"><input type="submit" id="submit" value="${_('Sign in')}"/>
            </td>
          </tr>
          <tr>
            <td colspan="2" id="signin-help">
              <a href="/public/support/signin">${_('Need help signing in?')}</a>
            </td>
          </tr>
        </table>
      </div>
      </form>
      <form action="/register" method="POST">
      <div id="signup">
        <table id="signup-table" cellspacing="0" cellpadding="3" border="0" align="center">
          <tr>
            <td colspan="2" class="title">
              Create a new account
            </td>
          </tr>
          <tr>
            <td id="emaillabel"><label for="email">${_('Email')}</label></td>
            <td id="emailfield"><input id="emailId" type="text" class="textfield" name="emailId"></input></td>
          </tr>
          <tr>
            <td colspan="2" id="signup-submitbox"><input type="submit" id="submit" value="${_('Sign Up')}"/>
          </tr>
          <tr>
            <td colspan="2" id="signup-info">
              Synovel provides a secure, private social network for your company.
              A valid company email address is required.
            </td>
          </tr>
          <tr>
            <td colspan="2" id="signup-help">
              <a href="/public/support/signup">${_('Know more')}</a>
            </td>
          </tr>
        </table>
      </div>
      </form>
      <div id="clear"></div>
    </div>
  </div>
  <div id="footer">
    ${_('&copy;2011 Synovel Software')}
    &nbsp;&#183;&nbsp;
    <a href="/public/support/contact">${_('Contact')}</a>
  </div>
</body>
</html>
