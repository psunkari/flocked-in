<%! from gettext import gettext as _ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${_('Synovel SocialNet')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/signin.css"/>
</head>

<body>
  <table id="aligntable"><tr><td align="center" valign="middle">
  <div id="outer">
    <form action="/register/create" method="POST" class="loginfields">
      <div id="inner">
        <table id="logintable" cellspacing="0" cellpadding="3" border="0" align="center">
          <tr>
            <td id="logintitle" colspan="2">
              <img alt="Synovel" src="/public/images/synovel.png"/>
            </td>
          </tr>
          <tr>
            <td id="userlabel"><label for="username">${_('Username')}</label></td>
            <td id="userfield"><label for="username">${emailId[0]}:</label></td>
            <td id="userfield"><input id="username" type="hidden" class="textfield" name="emailId" value="${emailId[0]}"></input></td>
          </tr>
          <tr>
            <td id="passlabel"><label for="password">${_('Password')}</label></td>
            <td id="passfield"><input id="password" type="password" class="textfield" name="password"></input></td>
          </tr>
          <tr>
            <td id="passlabel"><label for="password">${_('Confirm Password')}</label></td>
            <td id="passfield"><input id="password" type="password" class="textfield" name="password"></input></td>
          </tr>
          <tr>
            <td colspan="2" id="submitbox"><input type="submit" id="submit" value="${_('Sign in')}"/>
            </td>
          </tr>
          <tr>
            <td colspan="2" id="footer">
              ${_('&copy;2011 Synovel Software')}
              &nbsp;|&nbsp;
              <a href="http://www.synovel.com/social">${_('Synovel SocialNet')}</a>
            </td>
          </tr>
        </table>
      </div>
    </form>
  </div>
  </td></tr></table>
</body>
</html>
