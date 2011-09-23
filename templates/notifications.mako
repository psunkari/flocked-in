<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

##
## Profile is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
      </div>
      <div id="center">
        <div class="notifications" id="notifications">
          ${self.content()}
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="content()">
  %if notifications:
    %for notifyId in notifications:
      <div class="conv-item" >
        ${notifyStr[notifyId]}
      </div>
    %endfor
    %if nextPageStart:
      <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" data-ref="/notifications?start=${nextPageStart}">${_("Fetch older Notifications")}</a></div>
    %else:
      <div id="next-load-wrapper">${_("No more Notifications to show")}</div>
    %endif
  %else:
      <div id="next-load-wrapper">${_("No more Notifications to show")}</div>
  %endif
</%def>
