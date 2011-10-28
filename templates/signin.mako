<%! from social import utils, config, _, __ %>

<!DOCTYPE HTML>
<html lang="en" dir="ltr" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Sign In</title>
  <link href="/rsrcs/css/static.css" media="all" rel="stylesheet" type="text/css">
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
  <script type="text/javascript">
    function validate() {
      var email = document.getElementById('signin-email');
      var password = document.getElementById('signin-password');
      var errorMessage = document.getElementById('error-message')

      if (email.value == '') {
        errorMessage.innerHTML = 'Enter your company email';
        errorMessage.className = 'form-header error-input';
        return false;
      }

      if (password.value == '') {
        errorMessage.innerHTML = 'Enter your password';
        errorMessage.className = 'form-header error-input';
        return false;
      }

      return true;
    }
  </script>
</head>

<body>
  <div id="header" class="centered-wrapper">
    <a href='/'><img id='sitelogo' src="/rsrcs/img/flocked-in.png" alt="flocked-in"/></a>
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
    </ul>
  </div>

  <div id="wrapper" class="centered-wrapper">
    <div id="main-contents" class="contents">
      <div id="caption">Sign In</div>
      <form action="/signin" class="styledform"
            method="POST" onsubmit="return validate()">
        <%
          reasonStr = reason if reason else _('Sign-in to Flocked-in')
          msgClass = 'error-input' if reason else ''
        %>
        <p id="error-message" class="form-header ${msgClass}">${reasonStr}</p>
        <ul>
          <li>
            <label for="signin-email" class="styled-label required">
              ${_('Email')}
              <abbr title="Required">*</abbr>
            </label>
            <input id="signin-email" type="email" class="textfield" name="u" required autofocus></input>
          </li>
          <li>
            <label for="signin-password" class="styled-label required">
              ${_('Password')}
              <abbr title="Required">*</abbr>
            </label>
            <input id="signin-password" type="password" class="textfield" name="p" required></input>
          </li>
          <li>
            <label for="signin-remember" class="styled-label required">
              ${_('Remember me')}
              <abbr title="Required" style="visibility:hidden;">*</abbr>
            </label>
            <input type="checkbox" id="signin-remember" name="r" value="r"/>
          </li>
        </ul>
        <div class="buttons-wrapper">
          %if redirect:
            <input type="hidden" id="_r" value="${redirect}" name="_r"/>
          %endif
          <a href="/password/forgotPassword">${_('forgot password?')}</a>&nbsp;&nbsp;&nbsp;
          <button type="submit" class="default button">${_('Sign in')}</button>
        </div>
      </form>

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
