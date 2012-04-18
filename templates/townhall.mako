<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social.logging import log %>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%namespace name="feed_mako" file="feed.mako"/>
<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="titlebar center-header">
        <div id="title">
          <span class="middle title">Forums</span>
          <a href="" class="title-button">${_('#Chemistry2011IT')}</a>
        </div>
      </div>
      <div id="right">
        <div class="sidebar-chunk">
          <div class="sidebar-title">Gas looming through the fog in divers places in the streets</div>
            <ul class="v-links">
              <li>234 Questions</li>
              <li>1024 Comments</li>
              <li>123 Participants</li>
            </ul>
        </div>
      </div>
      <div id="center">
        <div id="share-block"></div>
      </div>
      <div class="clear"></div>
        <div class='center-contents' id="user-feed" style="position: relative; top: -140px;">
            %if not script:
              ${self.feed()}
            %endif
        </div>

    </div>
  </div>
</%def>

<%def name="feed()">
  <div id="people-view" class="viewbar">
    <%viewOptions()%>
  </div>
  <div id="threads-wrapper" class="paged-container">
    <div class="conversation-layout-container">
      <%
        rows = [
          {"votes":253, "title":"The glimpse into the future of video game graphics...CryEngine3", "time-ago":"10 hours", "poster":"Ashok", "tags": ["abc", "def"], "likes": 4, "comments": 44},
          {"votes":113, "title":"The White House petition to double NASA's budget has reached it's 25,000 signature goal.", "time-ago":"23 Minutes", "poster":"Maggie", "tags": ["123", "456"], "likes": 6, "comments": 12},
          {"votes":53, "title":"Reed Hastings accuses Comcast of violating “net neutrality” principles by favoring its own Web video service over those from Netflix, HBO and Hulu when it comes to data usage.", "time-ago":"3 hours", "poster":"John", "tags": ["435rf", "gtyh"], "likes": 0, "comments": 4}
        ]
      %>
      % for row in rows:
        <%conversation_row(row)%>
      % endfor
    </div>
  </div>
  <div id="people-paging" class="pagingbar">
    <ul class="h-links">
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
      <li class="button">
        <a class="ajax" href="">${_("Next &#9656;")}</a>
      </li>
    </ul>
  </div>
</%def>

<%def name="conversation_row(row)">
  <div class="conversation-row">
    <div class="conversation-row-cell conversation-row-sender">
      <span class="townhall-item-icon">
        <div>
          <div class="townhall-item-vote-link">Vote</div>
          <div class="townhall-item-votes">${row["votes"]}</div>
        </div>
      </span>
    </div>
    <a class="conversation-row-cell conversation-row-info">
      <div>
        <span class="conversation-row-subject">${row["title"]}</span>
      </div>
      <div class="conversation-row-headers">
        <span class="item-subactions">submitted ${row["time-ago"]} ago by ${row["poster"]}</span>
      </div>
      <div class="conversation-row-headers conv-footer">
        <span class="conversation-row-people">
          %if row["likes"] > 0:
            ·
            <span>${row["likes"]} likes</span>
          %endif
          %if row["comments"] > 0:
            ·
            <span>${row["comments"]} comments</span>
          %endif
          <button class="button-link ajaxpost">Like</button>
          ·
          <button class="button-link">Comment</button>
          %for tag in row["tags"]:
            ·
            <span class="townhall-tag">${tag}</span>
          %endfor
        </span>
      </div>
    </a>
  </div>
</%def>

<%def name="viewOptions()">
  <ul class="h-links view-options">
    % for item, display in [('new', _('New')), ('trending', _('Trending')), ('popular', _('Popular'))]:
      % if filterType == item:
        <li class="selected">${_(display)}</li>
      % else:
        <li>
          % if item == "new":
            <a href="/forums?type=${item}" class="ajax">${_(display)}</a>
            <span class="view-options-count" id="pending-group-requests-count">6</span>
          % else:
            <a href="/forums?type=${item}" class="ajax">${_(display)}</a>
          % endif
        </li>
      % endif
    % endfor
  </ul>
</%def>
