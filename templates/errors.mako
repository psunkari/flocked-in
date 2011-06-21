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
        %if script:
          <span class="button title-button default"><a href="javascript:history.go(-1);">Go Back</a></span>
        %else:
        %endif
      </div>
    </div>
  </div>
  <div id="content" class="center-contents error-page-contents">
    ${message}
  </div>
</%def>
