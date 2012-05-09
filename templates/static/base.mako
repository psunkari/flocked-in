<!DOCTYPE HTML>

<%def name="topbar(selected)">
  <div class="centered-wrapper"><div id="header">
    <a class="header-logo" href='/'><div><img id='sitelogo' src="/rsrcs/img/flocked-in.png" alt="Flocked-in"/></div><div>Connect, Collaborate and Innovate</div></a>
    <ul class="header-links">
      <li>
        <a title="Blog" class="menuitem" href="http://blog.flocked.in" id="nav-blog">Blog</a>
      </li>
      <li>
        <a title="Why Flocked-in?" class="menuitem" href="/about/why.html" id="nav-why">Why Flocked-in?</a>
      </li>
      <li>
        <a title="Contact Sales" class="menuitem" href="/contact?src=sales" id="nav-blog">Contact Sales</a>
      </li>
      <li>
        <a title="Signin" class="menuitem" href="/signin" id="nav-signin">Sign In</a>
      </li>
    </ul>
  </div></div>
</%def>

<html lang="en" dir="ltr" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml"
      xmlns:og="http://opengraphprotocol.org/schema/"
      xmlns:fb="http://www.facebook.com/2008/fbml">

<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

  <meta property="og:title" content="Flocked-in - Private, Secure and Free Social Network for Enterprises" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="http://flocked.in" />
  <meta property="og:image" content="/rsrcs/img/opengraph.png" />
  <meta property="og:site_name" content="Flocked-in" />
  <meta property="fb:admins" content="580083221,579977563" />

  <title>Flocked-in &mdash; Private, Secure and Free Social Network for Enterprises</title>

  <link href="/rsrcs/css/static.css" media="all" rel="stylesheet" type="text/css">
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />

  <script type="text/javascript">
    var _gaq = _gaq || [];
    _gaq.push(['_setAccount', 'UA-2921978-5']);
    _gaq.push(['_trackPageview']);

    (function() {
      var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
      ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
      var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
    })();
  </script>
</head>

<body>
  <%
    self.topbar('home')
    self.layout()
  %>
  <div id="footer" class="centered-wrapper">
    <div id="footer-contents" class="contents">
      <div class="sitemeta">
        <span class="copyright">&copy;2012 Synovel</span>
        &nbsp;|&nbsp;
        <a class="metalink" href="/about/tos.html">Terms of Service</a>
        &nbsp;|&nbsp;
        <a class="metalink" href="/about/privacy.html">Privacy Policy</a>
        &nbsp;|&nbsp;
        <a class="metalink" href="/about/contact.html">Contact Us</a>
      </div>
    </div>
  </div>
</body>

</html>
