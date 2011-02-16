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
    <form action="/register" method="POST" class="loginfields">
      <div id="inner">
        <table id="logintable" cellspacing="0" cellpadding="3" border="0" align="center">
          <tr>
            <td id="logintitle" colspan="2">
              <img alt="Synovel" src="/public/images/synovel.png"/>
            </td>
          </tr>
          <tr>
            <td id="emaillabel"><label for="email">${_('Email')}</label></td>
            <td id="emailfield"><input id="emailId" type="text" class="textfield" name="emailId"></input></td>
          </tr>
          <tr>
            <td colspan="2" id="submitbox"><input type="submit" id="submit" value="${_('Register')}"/>
            <td/>
          </tr>
                
        </table>
      </div>
    </form>
  </div>
  </td></tr></table>
</body>
</html>
