<%! from social import utils, config, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${config.get('Branding', 'Name')} &mdash; ${_('Private, Secure and Free Social Network for Enterprises')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/about.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
  <script type="text/javascript">
    function validate() {
      var username = document.getElementById('username');
      var password = document.getElementById('password');
      var errorMessage = document.getElementById('error-message')

      if (username.value == '') {
        errorMessage.innerHTML = 'Enter your username';
        return false;
      }
      
      if (password.value == '') {
        errorMessage.innerHTML = 'Enter your password';
        return false;
      }

      return true;
    }
  </script>
</head>

<body>
  <div id="header">
    <img alt="Synovel" src="/rsrcs/img/flocked-in.png"/>
    <ul id="header-links">
      <li><a href="/">Home</a></li>
      <li><a href="/">Signup</a></li>
    </ul>
  </div>

  <div id="wrapper">
    <div id="title-banner" class="title-banner banner">
      <ul id="views-list">
        <li class="selected last"><span>${_('Signin')}</span></li>
      </ul>
    </div>
    <div id="main">
      %if reason:
      %endif
      <form action="/signin" method="POST" onsubmit="return validate()">
      <div id="main-contents" class="styledform contents" style="width: 600px; margin: 20px auto;">
        <ul>
          <li>
            <label for="username">${_('Username')}</label>
            <input id="username" type="text" class="textfield" name="u"></input>
          </li>
          <li>
            <label for="password">${_('Password')}</label></td>
            <input id="password" type="password" class="textfield" name="p"></input>
          </li>
          <div id="error-message" class="error" style="padding-left: 15em; margin-left: 12px;">${reason}</div>
          <li>
            <label for="remember">${_('Remember me')}</label>
            <input type="checkbox" id="remember" checked="true" name="remember"/>
          </li>
        </ul>
        <div class="styledform-buttons">
          %if redirect:
            <input type="hidden" id="_r" value="${redirect}" name="_r"/>
          %endif
          <a href="/password/forgotPassword">${_('forgot password?')}</a>&nbsp;&nbsp;&nbsp;
          <input type="submit" class="default button" id="submit" value="${_('Sign in')}"/>
        </div>
      </div>
      </form>
    </div>
  </div>
  <div id="footer">
    <ul id="footer-sharing">
      <li id="twitter-share">
        <a rel="nofollow" href="http://twitter.com/share" class="twitter-share-button" data-url="http://flocked.in/" data-count="none">Tweet</a><script type="text/javascript" src="http://platform.twitter.com/widgets.js"></script>
      </li>
      <li id="facebook-share">
        <iframe src="http://www.facebook.com/plugins/like.php?href=http%3A%2F%2Fflocked.in&amp;send=false&amp;layout=button_count&amp;width=100&amp;show_faces=false&amp;action=like&amp;colorscheme=light&amp;font=tahoma&amp;height=20" scrolling="no" frameborder="0" style="border:none; overflow:hidden; width:100px; height:20px;" allowTransparency="true"></iframe>
      </li>
    </ul>
    <div id="footer-contents" class="contents">
      ${_('&copy;2011 Synovel Software')}
      &nbsp;&#183;&nbsp;
      <a href="/about/contact">${_('Contact us')}</a>
    </div>
  </div>
</body>
</html>
