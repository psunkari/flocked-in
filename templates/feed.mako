<%! from social import _, __ %>

<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <div id="title"><span class="middle title">${_("News Feed")}</span></div>
          </div>
          <div id="share-block">
            %if not script:
              ${self.share_block()}
            %endif
        </div>
        <div class="center-contents">
          %if not script:
            ${self.feed()}
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="acl_button(id)">
  %if script:
    <li class="acl-button button has-popup has-tooltip" id=${id} onclick="acl.updateGroupsList(this);popup.open(event, this)">
      <input type="hidden" name="acl" value="company"/>
      <span class="button-text">Company</span>
      <div class="tooltip top right">
        <span class="tooltip-contents">${_("Anyone working at my company")}</span>
      </div>
      <div class="popup" onclick="acl.update(event, this);">
        <ul class="v-links">
          <li value="public" info="${'Everyone'}">${_("Everyone")}</li>
          <li value="company" info="${'Anyone working at my company'}">${_("Company")}</li>
          <li value="friends" info="${'All my friends'}">${_("Friends")}</li>
          <li id="${id}-groups" class="separator"></li>
          <li id="${id}-groups-end" class="separator"></li>
          <li value="custom">${_("Custom setting")}</li>
        </ul>
      </div>
    </li>
  %endif
</%def>

<%def name="share_block()">
  %if script:
    <div id="sharebar-tabs">
      <ul id="sharebar-links" class="h-links">
        <li>${_("Share:")}</li>
        %for name, target in [("Status", "status"), ("Link", "link"), ("Document", "document")]:
          %if target == 'status':
            <li><a _ref="/feed/share/${target}" id="sharebar-link-${target}" class="ajax selected">${_(name)}</a></li>
          %else:
            <li><a _ref="/feed/share/${target}" id="sharebar-link-${target}" class="ajax">${_(name)}</a></li>
          %endif
        %endfor
      </ul>
    </div>
    <form id="share-form" method="post" autocomplete="off">
      <div id="sharebar"></div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          ${acl_button("sharebar-acl")}
          <li id="sharebar-submit" class="default button"><span class="button-text">${_('Share')}</span></li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
  %endif
</%def>

<%def name="share_status()">
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('What are you currently working on?')}"/>
  </div>
  <input type="hidden" name="type" value="status"/>
</%def>

<%def name="share_link()">
  <div class="input-wrap">
    <input type="text" name="link" placeholder="${_('http://')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('Say something about this link')}"/>
  </div>
</%def>

<%def name="share_document()">
  <div class="input-wrap">
    <input type="file" name="file" placeholder="${_('Select the document to share')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('Say something about this file')}"/>
  </div>
</%def>

<%def name="feed()">
</%def>
