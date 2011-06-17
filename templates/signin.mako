<%! from social import utils, config, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${config.get('Branding', 'Name')} &mdash; ${_('Private, Secure and Free Social Network for Enterprises')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/signin.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
</head>

<body>
  <div id="wrapper">
  <div id="header">
    <img alt="Synovel" src="/rsrcs/img/synovel.png"/>
    <ul id="header-links">
      <li><a href="/">Home</a></li>
      <li><a href="/">Signup</a></li>
    </ul>
  </div>
  <div id="main-wrapper">
    <div id="steps">
      <ul id="views-list">
        <li class="selected last"><span>${_('Signin to your account')}</span></li>
      </ul>
    </div>
    <div id="center">
      %if reason:
        <span class="error">${reason}</span>
      %endif
      <form action="/signin" method="POST">
      <div class="styledform">
        <ul>
          <li>
            <label for="username">${_('Username')}</label>
            <input id="username" type="text" class="textfield" name="u"></input>
          </li>
          <li>
            <label for="password">${_('Password')}</label></td>
            <input id="password" type="password" class="textfield" name="p"></input></td>
          </li>
          <li>
            <input type="checkbox" id="remember" checked="true" name="remember"/>
            <label for="remember">${_('Remember me')}</label>
          </li>
        </ul>
        <div class="styledform-buttons">
          %if redirect:
            <input type="hidden" id="_r" value="${redirect}" name="_r"/>
          %endif
          <a href="/about/support/signin">${_('Need help signing in?')}</a>&nbsp;&nbsp;&nbsp;
          <input type="submit" class="default button" id="submit" value="${_('Sign in')}"/>
        </div>
      </div>
      </form>
    </div>
  </div>
  <div id="footer-wrapper">
    ${_('&copy;2011 Synovel Software')}
    &nbsp;&#183;&nbsp;
    <a href="/about/contact">${_('Contact us')}</a>
  </div>
  </div>
</body>
</html>
