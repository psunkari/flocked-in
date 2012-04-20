<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social.logging import log %>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%namespace name="feed_mako" file="feed.mako"/>
<%namespace name="townhall" file="townhall.mako"/>
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
          <span class="middle title">CSE91: Application programming interface</span>
          <button class="button title-button">${_('Join')}</a>
        </div>
      </div>
      <div id="right">
        <div class="sidebar-chunk">
          <div class="sidebar-title">About this course</div>
            <ul class="v-links">
                <li>Dr. Prem</li>
                <li>Difficulty -- Intermediate</li>
                <li>Duration -- 4 Weeks</li>
                <li>Badges --
                    <img src="/rsrcs/img/badge-yellow.png" style="position: relative; top: 4px"/>
                    <img src="/rsrcs/img/badge-maroon.png" style="position: relative; top: 4px"/>
                </li>
            </ul>
        </div>
        <div class="sidebar-chunk">
          <div class="sidebar-title">Topics</div>
            <%
              tasks = [
              ("Introduction", "Wk 1"),
              ("Choose a query for your API call", "Wk 2"),
              ("Learn about the Twitter API", "Wk 2"),
              ("Working with JSON-formatted data", "Wk 3"),
              ("Construct your query request", "Wk 3"),
              ("Time for code", "Wk 4")
              ]
            %>
            <ul class="v-links">
              % for x in range(len(tasks)):
                <li>
                    <a style="float: left" href="/course/topic" class="ajax">${tasks[x][0]}</a>
                    <span style="float: right;padding-right: 4px;">${tasks[x][1]}</span>
                    <div class="clear"></div>
                </li>
              % endfor
            </ul>
            <a href="" style="float: right;margin-top: 4px;margin-right: 4px;">Show All</a>
        </div>
        <div class="sidebar-chunk">
          <div class="sidebar-title">Participants</div>
            <ul class="v-links">
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Alex</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Barley</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Abhishek</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Prasad</a></li>
            </ul>
        </div>
      </div>
      <div id="center">
        <div style="padding: 10px">
            <p>
                An application programming interface (API) is a source code-based specification intended to be used as an interface by software components to communicate with each other. An API may include specifications for routines, data structures, object classes, and variables.
            </p>
            <p>
                This course will guide you through tasks that involve searching for and reading documentation online, executing an API call to a dynamic data source, processing the results in a language of your choice, and printing them out to a terminal.
            </p>
        </div>
        <div id="share-block"></div>
        <div id="user-feed-wrapper">
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
<div id="user-feed"></div>
</%def>

<%def name="topic_feed()">
  <div id="people-view" class="viewbar">
    <%townhall.viewOptions()%>
  </div>
  <div id="threads-wrapper" class="paged-container">
    <div id="user-discussion-feed"></div>
  </div>
</%def>
