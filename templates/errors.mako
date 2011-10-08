<%! from social import utils, _, __, plugins, config %>

<!DOCTYPE HTML>
<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents">
    <div id="center-right">
      <div id="center">
        ${self.showError(msg)}
      </div>
    </div>
  </div>
</%def>

<%def name="showError(message)">
  <div class="center-header">
    <div class="titlebar">
      <div id="title">
        <span class="middle title">${('Oops... there was a problem!')}</span>
      </div>
    </div>
  </div>
  <div id="content" class="center-contents error-page-contents">
    <div>
      ${message}
    </div>
    <div>
      <ul class="h-links error-buttons">
        <li><form action="/" method="GET"><button type="submit" class="button default">${_('Go Home')}</button></form></li>
        %if not isDeepLink:
        <li><form action="${referer}" method="GET"><button type="submit" class="button default" onclick="history.go(-1); return false;">${_('Go Back')}</button></form></li>
        %endif
      </ul>
    </div>
  </div>
</%def>

<%def name="fallback()">
  <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                      "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
  <html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>${_('Error')} &mdash; ${config.get('Branding', 'Name')}</title>
    <link rel="stylesheet" type="text/css" media="all" href="/rsrcs/css/static.css"/>
    <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
  </head>

  <body>
    <div id="header" class="centered-wrapper">
      <a href='/'><img id="sitelogo" alt="Synovel" src="/rsrcs/img/flocked-in.png" alt="flocked-in"/></a>
    </div>

    <div id="wrapper" class="centered-wrapper">
      <div id="caption" class="contents">${_('Error')}</div>
      <div id="main" class="contents">
        <div id="main-contents" style="font-size: 14px; text-align: center; padding: 30px 40px; font-weight: bold;">
          ${msg}
          <form action="/" method="GET"><button type="submit" class="button default">${_('Go Home')}</button></form>
        </div>
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
</%def>
