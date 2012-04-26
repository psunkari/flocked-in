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
                <li>by <a href="" style="display: inline">Dr. Mayank</a></li>
                <li>For CSE & IT students</li>
                <li>Apr 04, 2012 &ndash; Jun 25, 2012</li>
                <li>Badges to be won
                    <img src="/rsrcs/img/badge-yellow.png" style="position: relative; top: 4px"/>
                    <img src="/rsrcs/img/rosette.png" style="position: relative; top: 2px"/>
                </li>
            </ul>
        </div>
        <div class="sidebar-chunk">
          <div class="sidebar-title">Topics</div>
            <%
              tasks = [
              ("Networking Primer and intro to APIs", "Wk 1"),
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
          <div class="sidebar-title">Students</div>
            <ul class="v-links">
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Paul</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Lily</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Jack</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Abey</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">James</a></li>
              <li><a href="/group?id=-NrFyIeSEeG0owAe7FqcFw" class="ajax">Tina</a></li>
            </ul>
            <a href="" style="float: right;margin-top: 4px;margin-right: 4px;">Show All</a>
        </div>
        <div id ="feed-side-block-container"></div>
      </div>
      <div id="center">
        <div style="padding: 10px 10px 0px 10px; font-size: 12px;">
            <p>
                An application programming interface (API) is a source code-based specification intended to be used as an interface by software components to communicate with each other.
            </p>
            <p>
                This course will help you explore a sample API, understand the nuances of modeling an API and finally build a web service with a fully implemented API.
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
<div id="user-feed">
<div class="conv-item" data-convid="eGSLQo-IEeGC_QAe7FqcFw" id="conv-eGSLQo-IEeGC_QAe7FqcFw">
<div id="conv-avatar-eGSLQo-IEeGC_QAe7FqcFw" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="http://192.168.36.244:8000/avatar/m_mewstI-UEeGEqQAe7FqcFw.png">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-eGSLQo-IEeGC_QAe7FqcFw">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/delete', {id:'eGSLQo-IEeGC_QAe7FqcFw'});" class="menu-item noicon">Delete</a></li>
</ul>
<span class="conv-reason"><span class="user conv-user-cause"><a class="ajax" href="/profile?id=3YRzII7eEeG5dgAe7FqcFw">Dr. Mayank</a></span> awarded a badge <span class="item "><img style="position: relative; top: 4px" src="/rsrcs/img/badge-yellow.png"></span> to Abey, James and Tina</span>
<div class="conv-summary conv-quote">
<div class="comment-avatar" style="position: inherit; margin-right: 10px;">
<img src="http://192.168.36.244:8000/rsrcs/img/7.png" style="max-height: 32px; max-width: 32px;">
</div>
<div class="item-title ">
<div class="">

<span class="text-full">Abey's team scored 100% in the Twitter API quiz</span>
</div>
</div>
<div id="item-footer-eGSLQo-IEeGC_QAe7FqcFw" class="conv-footer busy-indicator">
<abbr class="timestamp" title="Thursday, April 26, 2012 at 3:43pm" data-ts="1335435209">30 minutes ago</abbr>  ·
<button class="button-link ajaxpost" data-ref="/item/like?id=eGSLQo-IEeGC_QAe7FqcFw">Like</button>·<button class="button-link" onclick="$$.convs.comment('eGSLQo-IEeGC_QAe7FqcFw');">Comment</button>·<button class="button-link" title="Add Tag" onclick="$$.convs.editTags('eGSLQo-IEeGC_QAe7FqcFw', true);">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-tags no-likes" id="conv-meta-wrapper-eGSLQo-IEeGC_QAe7FqcFw">
<div class="tags-wrapper" id="conv-tags-wrapper-eGSLQo-IEeGC_QAe7FqcFw">
<div class="conv-tags">
<button onclick="$$.convs.editTags('eGSLQo-IEeGC_QAe7FqcFw');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-eGSLQo-IEeGC_QAe7FqcFw">
</span>
<form id="addtag-form-eGSLQo-IEeGC_QAe7FqcFw" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="eGSLQo-IEeGC_QAe7FqcFw" name="id">
</form>
<button onclick="$$.convs.doneTags('eGSLQo-IEeGC_QAe7FqcFw');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-eGSLQo-IEeGC_QAe7FqcFw">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-eGSLQo-IEeGC_QAe7FqcFw">
<div id="comments-header-eGSLQo-IEeGC_QAe7FqcFw">
</div>
<div id="comments-eGSLQo-IEeGC_QAe7FqcFw">
<div id="comment-nkp6Bo-IEeGC_QAe7FqcFw" class="conv-comment">
<a name="nkp6Bo-IEeGC_QAe7FqcFw"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="http://192.168.36.244:8000/avatar/s_mewstI-UEeGEqQAe7FqcFw.png">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'nkp6Bo-IEeGC_QAe7FqcFw'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=3YRzII7eEeG5dgAe7FqcFw" class="ajax">Dr. Mayank</a></span></span>
<span class="text-full">Congratulations! Good luck for the rest of the course!</span>
</div>
<div id="item-footer-nkp6Bo-IEeGC_QAe7FqcFw" class="comment-meta">
<abbr data-ts="1335435273" title="Thursday, April 26, 2012 at 3:44pm" class="timestamp">28 minutes ago</abbr>
·
<button data-ref="/item/like?id=nkp6Bo-IEeGC_QAe7FqcFw" class="button-link ajaxpost">Like</button>
</div>
</div>
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-eGSLQo-IEeGC_QAe7FqcFw">
<form id="comment-form-eGSLQo-IEeGC_QAe7FqcFw" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="eGSLQo-IEeGC_QAe7FqcFw" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="eGSLQo-IEeGC_QAe7FqcFw" name="parent">
<input type="hidden" value="1" name="nc">
<div class="uploaded-filelist" id="comment-attach-eGSLQo-IEeGC_QAe7FqcFw-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-eGSLQo-IEeGC_QAe7FqcFw">
<div class="file-attach-outer busy-indicator" id="comment-attach-eGSLQo-IEeGC_QAe7FqcFw-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-eGSLQo-IEeGC_QAe7FqcFw-file-input" name="file">
<button class="file-attach-button" id="comment-attach-eGSLQo-IEeGC_QAe7FqcFw-fileshare">
<span class="background-icon attach-file-icon icon"></span>
<span>Attach File</span>
</button>
</div>
</form>
</div>
<div class="clear"></div>
</div>
</div>
</div>
</div>
</div>
</%def>

<%def name="topic_feed()">
  <div id="people-view" class="viewbar">
    <%townhall.viewOptions()%>
  </div>
  <div id="threads-wrapper" class="paged-container">
    <div id="user-discussion-feed"></div>
  </div>
</%def>
