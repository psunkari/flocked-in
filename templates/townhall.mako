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
##        <div id="title">
##          <span class="middle title">Topic</span>
##          <a href="" class="title-button">${title}</a>
##        </div>
      </div>
      <div id="right">
        <div class="sidebar-chunk">
          <div class="sidebar-title">
            ${title}
             <div>by <a href="" >Dr. Prem</a></div>
          </div>
            <ul class="v-links">
              <li>234 Questions</li>
              <li>Started 36 minutes ago</li>
              <li>123 Participants</li>
            </ul>
        </div>
        <div class="sidebar-chunk">
          <div class="sidebar-title">Attachments</div>
            <ul class="v-links">
              <li><a href="">Questionaaire.xls</a></li>
              <li><a href="">Accessibility Access API Reference.pdf</a></li>
            </ul>
        </div>
        <div class="sidebar-chunk">
          <div class="sidebar-title">Links and References</div>
            <div class="link-item">
              <img class="link-image" style="max-height: 64px;max-width: 64px" src="https://d1swnjtqvd4898.cloudfront.net/url/aHR0cHM6Ly9zZWN1cmUuZ3JhdmF0YXIuY29tL2JsYXZhdGFyLzU2YTRjZmU2ZjEwMGUyN2M0N2FlYWU2NTU5YTFmOGY3P3M9MzAw">
              <div class="link-details">
                <a target="_blank" href="https://contagions.wordpress.com/"><div class="link-title">Contagions</div></a>
                <div class="link-summary" id="summary">thoughts on historic infectious disease</div>
                <div class="link-url" id="url">contagions.wordpress.com</div>
              </div>
            </div>
            <span style="float: right;margin-right: 5px;margin-top: 5px;">
              <span>1 <i>of</i> 3</span>
              <span class="nav-button"> &#9664;</span>
              <span class="nav-button"> &#9654;</span>
            </span>
        </div>
      </div>
      <div id="center">
        <div id="share-block"></div>
        <div class='center-contents' id="user-feed">
            %if not script:
              ${self.feed()}
            %endif
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="feed()">
  <div id="people-view" class="viewbar">
    <%viewOptions()%>
  </div>
  <div id="threads-wrapper" class="paged-container">
    <%filter_bar()%>
    <div class="conversation-layout-container">
      <%
        rows = [
          {"votes":253, "title":"The glimpse into the future of video game graphics...CryEngine3", "time-ago":"10 hours", "poster":"Ashok", "tags": ["abc", "def"], "likes": 4, "comments": 44},
          {"votes":113, "title":"The White House petition to double NASA's budget has reached it's 25,000 signature goal.", "time-ago":"23 Minutes", "poster":"Maggie", "tags": ["123", "456"], "likes": 6, "comments": 12},
          {"votes":53, "title":"Reed Hastings accuses Comcast of violating “net neutrality” principles by favoring its own Web video service over those from Netflix, HBO and Hulu when it comes to data usage.", "time-ago":"3 hours", "poster":"John", "tags": ["435rf", "gtyh"], "likes": 0, "comments": 4},
          {"votes":253, "title":"The glimpse into the future of video game graphics...CryEngine3", "time-ago":"10 hours", "poster":"Ashok", "tags": ["abc", "def"], "likes": 4, "comments": 44},
          {"votes":253, "title":"The glimpse into the future of video game graphics...CryEngine3", "time-ago":"10 hours", "poster":"Ashok", "tags": ["abc", "def"], "likes": 4, "comments": 44},
          {"votes":253, "title":"The glimpse into the future of video game graphics...CryEngine3", "time-ago":"10 hours", "poster":"Ashok", "tags": ["abc", "def"], "likes": 4, "comments": 44}
        ]
      %>
      % for row in rows:
        <%conversation_row(row)%>
      % endfor
    </div>
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
        <span class="conversation-row-question">${row["title"]}</span>
      </div>
      <div class="conversation-row-headers">
        <span class="item-subactions">submitted ${row["time-ago"]} ago by ${row["poster"]}</span>
      </div>
      <div class="conversation-row-headers conv-footer">
        <span class="conversation-row-people">
          %if row["likes"] > 0:
            <span>${row["likes"]} likes</span>
          %endif
          %if row["comments"] > 0:
            ·
            <span>${row["comments"]} comments</span>
          %endif
          ·
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

<%def name="filter_bar()">
  <div class="feed-filter-bar" id="feed-filter-bar">
    <span onclick="$$.convs.showFilterMenu(event);" class="feed-filter">Showing Trending Questions ▼</span>
      <ul style="display:none;">
        <li>
          <a data-ff="" class="ff-item">
            <span class="icon feed-icon"></span>
            Trending
          </a>
        </li>
        <li>
          <a data-ff="status" class="ff-item">
            <span class="icon status-icon"></span>
              Statuses
          </a>
        </li>
        <li>
          <a data-ff="question" class="ff-item">
            <span class="icon question-icon"></span>
            Questions
          </a>
        </li>
      </ul>
  </div>
</%def>

<%def name="viewOptions()">
  <ul class="h-links view-options">
    % for item, display in [('discussions', _('Discussion')), ('qna', _('Question and Answers')), ('archives', _('Archives'))]:
      % if filterType == item:
        <li class="selected">${_(display)}</li>
      % else:
        <li>
          <a href="/course/topic?type=${item}" class="ajax">${_(display)}</a>
        </li>
      % endif
    % endfor
  </ul>
</%def>
