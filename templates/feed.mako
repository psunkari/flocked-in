<%! from social import utils, _, __, plugins %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
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
        <div id="invite-ppl">
            <form method="post" action="/register" class="ajax">
                <input type="text" name="emailId"/><br/>
                <input type="submit" id="submit" value="${_('Submit')}"/>
            </form>
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            %if heading:
              <div id="title"><span class="middle title">${_(heading)}</span></div>
            %else:
              <div id="title"><span class="middle title">${_("News Feed")}</span></div>
            %endif
          </div>
          <div id="share-block">
            %if not script:
              ${self.share_block()}
            %endif
          </div>
        </div>
        <div id="user-feed" class="center-contents">
          %if not script:
            ${self.feed()}
          %endif
          <div id="foot-loader"></div>
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="acl_button(id)">
  %if script:
    <%widgets:popupButton id="${id}" classes="acl-button" value="${_('Company')}"
                          tooltip="${_('Anyone working at my company')}">
      <input id="${id}-input" type="hidden" name="acl" value="company"/>
      <div class="popup" onclick="$$.acl.updateACL(event, this.parentNode);">
        <ul class="v-links">
          <li type="public" info="${'Everyone'}">${_("Everyone")}</li>
          <li type="company" info="${'Anyone working at my company'}">${_("Company")}</li>
          <li type="friends" info="${'All my friends'}">${_("Friends")}</li>
          <li id="${id}-groups" class="separator"></li>
          <li id="${id}-groups-end" class="separator"></li>
          <li type="custom">${_("Custom")}</li>
        </ul>
      </div>
    </%widgets:popupButton>
  %endif
</%def>

<%def name="share_block()">
  %if script:
    <div id="sharebar-tabs">
      <ul id="sharebar-links" class="h-links">
        <li>${_("Share:")}</li>
        <%
          supported = [(name.capitalize(), name) for name in plugins if plugins[name].position > 0]
          itemName, itemType = supported[0]
        %>
        <li><a _ref="/feed/share/${itemType}" id="sharebar-link-${itemType}" class="ajax selected">${_(itemName)}</a></li>
        %for itemName, itemType in supported[1:]:
          <li><a _ref="/feed/share/${itemType}" id="sharebar-link-${itemType}" class="ajax">${_(itemName)}</a></li>
        %endfor
      </ul>
    </div>
    <form id="share-form" class="ajax" autocomplete="off" method="post" action="/item/new">
      <div id="sharebar"></div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          <li>${acl_button("sharebar-acl")}</li>
          <li>${widgets.button("sharebar-submit", "submit", "default", None, "Share")}</li>
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

<%def name="feed()">
  %for convId in conversations:
    ${item.item_layout(convId, True, True)}
  %endfor
  %if nextPageStart:
    <div id="next-load-wrapper"><a id="next-page-load" class="ajax" _ref="/feed?start=${nextPageStart}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
  %endif
</%def>
