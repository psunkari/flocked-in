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
          <span class="middle title">${title}</span>
          <a href="" class="title-button"></a>
        </div>
      </div>
      <div id="right">
        <div class="sidebar-chunk">
          <div class="sidebar-title">
            ${title}
             <div>by <a href="" >Dr. Mayank</a></div>
          </div>
            <ul class="v-links">
              <li>34 Questions</li>
              <li>Started 36 minutes ago</li>
              <li>23 Participants</li>
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
              <img class="link-image" style="max-height: 64px;max-width: 64px" src="/rsrcs/img/twitter.png">
              <div class="link-details">
                <a target="_blank" href="https://contagions.wordpress.com/"><div class="link-title">Twitter Dev Zone</div></a>
                <div class="link-summary" id="summary">Get started with the API, Explore all of Twitter's API documentation </div>
                <div class="link-url" id="url">https://dev.twitter.com/</div>
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
        <div style="padding: 10px;padding-bottom: 0px;font-size: 12px;">
            <p>
                This lecture will guide you through tasks that involve searching for and reading documentation online, executing an API call to a dynamic data source, processing the results in a language of your choice.
            </p>
        </div>
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
          {"votes":20, "snippet":"How do I send a cross-domain POST request via JavaScript? Notes - it shouldn't refresh the page, and I need to grab and parse the response afterward. Your help with some code examples will be much a … ", "title":"How do I send a cross-domain POST request via JavaScript?", "time-ago":"10 hours", "poster":"Arvind", "tags": ["python", "twitter"], "likes": 4, "comments": 18},
          {"votes":13, "snippet":"I have a table of schedule items, they may be scheduled for the same time. I'm wondering how to have them all execute at the correct time when: The problem I see is that executing one scheduled item … ", "title":"How Create a Scheduler (e.g. to schedule tweets, or an api request)", "time-ago":"23 Minutes", "poster":"Maggie", "tags": ["javascript", "JSON"], "likes": 6, "comments": 12},
          {"votes":9, "snippet":"Python and JavaScript both allow developers to use or to omit semicolons. However, I've often seen it suggested (in books and blogs) that I should not use semicolons in Python, while I should always u … ", "title":"What is the difference between semicolons in JavaScript and in Python?", "time-ago":"3 hours", "poster":"John", "tags": ["python", "syntax"], "likes": 0, "comments": 4},
          {"votes":4, "snippet":"I found this kind of syntax being used on Facebook for Ajax calls. I'm confused on the for (;;); part in the beginning of response. What is it used for? This is the call and response: GET http://0. … ", "title":"What does a Ajax call response like 'for (;;); { json data }' mean?", "time-ago":"10 hours", "poster":"Abhishek", "tags": ["ajax", "javascript"], "likes": 4, "comments": 5},
          {"votes":1, "snippet":"I am playing around with the Oauth 2.0 authorization in Facebook and was wondering if the access tokens Facebook passes out ever expire. If so, is there a way to request a long-life access token? … ", "title":"Do Facebook Oauth 2.0 Access Tokens Expire?", "time-ago":"10 hours", "poster":"Prasad", "tags": ["OAuth", "Auth API"], "likes": 4, "comments": 2},
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
    <div class="conversation-row-cell conversation-row-sender" style="vertical-align: top">
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
      <div style="font-size: 11px">
        ${row["snippet"]}
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
