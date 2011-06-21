<%! from social import utils, _, __, plugins %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

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
