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
          <span class="middle title">CSE91: Creating mashups using APIs</span>
          <button class="button title-button">${_('Join')}</a>
        </div>
      </div>
      <div id="right">
        <div class="course-logo">
          <img src="/rsrcs/img/subject.jpeg"/>
        </div>
        <p>
          The goal of the course is to assemble a toolkit for helping young children develop API integration skills using twitter API as an examplem.
        </p>
        <p>
          <b>Introduction.</b> This groundbreaking book provides you with the skills and resources necessary to build web applications for Twitter.
        </p>
        <p>
          <b>JSON Parsing & Tweet IDs.</b> The Streaming API is a family of powerful real-time APIs for Tweets and other social events.</b>
        </p>
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
        <div id="share-block">
          <%
            tasks = [
            ("Introduction", "Week 1"),
            ("Choose a query for your API call", "Week 2"),
            ("Learn about the Twitter API", "Week 3")]
          %>
          <table style="width: 100%; table-layout: fixed">
              % for x in range(len(tasks)):
                <tr>
                    <td style="width: 5%">${x+1}</td>
                    <td style="width: 75%"><a href="">${tasks[x][0]}</a></td>
                    <td style="width: 20%;text-align: right;">${tasks[x][1]}</td>
                </tr>
              % endfor
          </table>
          <a href="" style="float: right">Show all tasks</a>
          <div class="clear"></div>
        </div>
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
<div class="feed-filter-bar" id="feed-filter-bar">
<span onclick="$$.convs.showFilterMenu(event);" class="feed-filter">Showing All Items ▼</span>
<ul style="display:none;">
<li><a data-ff="" class="ff-item">
<span class="icon feed-icon"></span>
All Items
</a></li>
<li><a data-ff="status" class="ff-item">
<span class="icon status-icon"></span>
Statuses
</a></li>
<li><a data-ff="question" class="ff-item">
<span class="icon question-icon"></span>
Questions
</a></li>
<li><a data-ff="link" class="ff-item">
<span class="icon link-icon"></span>
Links
</a></li>
<li><a data-ff="event" class="ff-item">
<span class="icon event-icon"></span>
Events
</a></li>
<li><a data-ff="poll" class="ff-item">
<span class="icon poll-icon"></span>
Polls
</a></li>
</ul>
</div>
<div class="center-contents" id="user-feed">
<div class="conv-item" data-convid="Yq4bQIfEEeGttUBADSqDjg" id="conv-Yq4bQIfEEeGttUBADSqDjg">
<div id="conv-avatar-Yq4bQIfEEeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_ghbATKgMEeCVFkBAhdLyVQ.png">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-Yq4bQIfEEeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/delete', {id:'Yq4bQIfEEeGttUBADSqDjg'});" class="menu-item noicon">Delete</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=i-3wEp4wEeCDwEBAhdLyVQ" class="ajax">Abhishek</a> posted in <a href="">Learn about the Twitter API</a></span>
<div class="item-title has-icon">
<span class="icon item-icon link-icon"></span>
<div class="item-title-text">
<span class="text-full">Maths!!!</span>
<div class="link-item">
<div class="link-details">
<a target="_blank" href="http://www.ixl.com/"><div class="link-title">IXL</div></a>
<div class="link-summary" id="summary">IXL is the Web's most comprehensive math practice site. Popular among educators and families, IXL provides unlimited questions in more than 2,000 topics. An adaptive learning system, featuring games…</div>
<div class="link-url" id="url">www.ixl.com</div>
</div>
</div>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-Yq4bQIfEEeGttUBADSqDjg">
<abbr data-ts="1334581334" title="Monday, April 16, 2012 at 6:32pm" class="timestamp">36 minutes ago</abbr>  ·
<button data-ref="/item/like?id=Yq4bQIfEEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('Yq4bQIfEEeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('Yq4bQIfEEeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags no-likes" id="conv-meta-wrapper-Yq4bQIfEEeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-Yq4bQIfEEeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('Yq4bQIfEEeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-Yq4bQIfEEeGttUBADSqDjg">
</span>
<form id="addtag-form-Yq4bQIfEEeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="Yq4bQIfEEeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('Yq4bQIfEEeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-Yq4bQIfEEeGttUBADSqDjg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-Yq4bQIfEEeGttUBADSqDjg">
<div id="comments-header-Yq4bQIfEEeGttUBADSqDjg">
</div>
<div id="comments-Yq4bQIfEEeGttUBADSqDjg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-Yq4bQIfEEeGttUBADSqDjg">
<form id="comment-form-Yq4bQIfEEeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="Yq4bQIfEEeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 31px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 92px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="Yq4bQIfEEeGttUBADSqDjg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-Yq4bQIfEEeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-Yq4bQIfEEeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-Yq4bQIfEEeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-Yq4bQIfEEeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-Yq4bQIfEEeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="EEKbrofBEeGttUBADSqDjg" id="conv-EEKbrofBEeGttUBADSqDjg">
<div id="conv-avatar-EEKbrofBEeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_ghbATKgMEeCVFkBAhdLyVQ.png">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-EEKbrofBEeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/delete', {id:'EEKbrofBEeGttUBADSqDjg'});" class="menu-item noicon">Delete</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=i-3wEp4wEeCDwEBAhdLyVQ" class="ajax">Abhishek</a> posted in <a href="">Choose a query for your API call</a></span>
<div class="item-title ">
<div class="">
<span class="text-full">First draft screenshot of a townhall like application.</span>
</div>
</div>
<div class="attachment-list ">
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=EEKbrofBEeGttUBADSqDjg&amp;fid=EEL3NIfBEeGttUBADSqDjg">townhall.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;112K</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-EEKbrofBEeGttUBADSqDjg">
<abbr data-ts="1334579906" title="Monday, April 16, 2012 at 6:08pm" class="timestamp">about one hour ago</abbr>  ·
<button data-ref="/item/like?id=EEKbrofBEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('EEKbrofBEeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('EEKbrofBEeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-likes" id="conv-meta-wrapper-EEKbrofBEeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-EEKbrofBEeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('EEKbrofBEeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-EEKbrofBEeGttUBADSqDjg">
<span tag-id="0anlHnytEeGn8kBADSqDjg" class="tag">
<a href="/tags?id=0anlHnytEeGn8kBADSqDjg" class="ajax">goal</a>
<form action="/item/untag" method="post" class="ajax delete-tags">
<input type="hidden" value="EEKbrofBEeGttUBADSqDjg" name="id">
<input type="hidden" value="0anlHnytEeGn8kBADSqDjg" name="tag">
<button class="button-link" type="submit">x</button>
</form>
</span>
</span>
<form id="addtag-form-EEKbrofBEeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="EEKbrofBEeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('EEKbrofBEeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-EEKbrofBEeGttUBADSqDjg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-EEKbrofBEeGttUBADSqDjg">
<div id="comments-header-EEKbrofBEeGttUBADSqDjg">
</div>
<div id="comments-EEKbrofBEeGttUBADSqDjg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-EEKbrofBEeGttUBADSqDjg">
<form id="comment-form-EEKbrofBEeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="EEKbrofBEeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="EEKbrofBEeGttUBADSqDjg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-EEKbrofBEeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-EEKbrofBEeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-EEKbrofBEeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-EEKbrofBEeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-EEKbrofBEeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="Te8m0oebEeGttUBADSqDjg" id="conv-Te8m0oebEeGttUBADSqDjg">
<div id="conv-avatar-Te8m0oebEeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_WDaVtiWBEeGAEkBADSqDjg.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-Te8m0oebEeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'Te8m0oebEeGttUBADSqDjg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<span class="conv-reason"><span class="user conv-user-cause"><a href="/profile?id=tDM5JpfaEeCz1EBAhdLyVQ" class="ajax">Prasad Sunkari</a></span> commented on <span class="user conv-user-cause"><a href="/profile?id=tDM5JpfaEeCz1EBAhdLyVQ" class="ajax">Prasad Sunkari</a></span>'s <span class="item "><a href="/item?id=Te8m0oebEeGttUBADSqDjg" class="ajax">status</a></span></span>
<div class="conv-summary conv-quote">
<div class="item-title ">
<div class="">
<span class="user"><a href="/profile?id=tDM5JpfaEeCz1EBAhdLyVQ" class="ajax">Prasad Sunkari</a></span>
<span class="text-full">Some screenshots of Flocked-in.</span>
</div>
</div>
<div class="attachment-list ">
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfWJUIebEeGttUBADSqDjg">profile.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;255K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfCefIebEeGttUBADSqDjg">files.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;140K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfJscIebEeGttUBADSqDjg">feed+chat.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;244K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=Te-gioebEeGttUBADSqDjg">profile-goals.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;157K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfTT_IebEeGttUBADSqDjg">messages.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;192K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfNE9oebEeGttUBADSqDjg">events.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;113K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfZBJIebEeGttUBADSqDjg">groups+chat.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;113K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfQfeoebEeGttUBADSqDjg">notifications.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;214K</span>
</div>
<div class="attachment-item">
<span class="icon attach-file-icon"></span>
<span class="attachment-name"><a target="filedownload" href="/files?id=Te8m0oebEeGttUBADSqDjg&amp;fid=TfF5loebEeGttUBADSqDjg">group.png</a></span>
<span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;214K</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-Te8m0oebEeGttUBADSqDjg">
<abbr data-ts="1334563689" title="Monday, April 16, 2012 at 1:38pm" class="timestamp">5 hours ago</abbr>  ·
<button data-ref="/item/like?id=Te8m0oebEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('Te8m0oebEeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('Te8m0oebEeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-tags no-likes" id="conv-meta-wrapper-Te8m0oebEeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-Te8m0oebEeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('Te8m0oebEeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-Te8m0oebEeGttUBADSqDjg">
</span>
<form id="addtag-form-Te8m0oebEeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="Te8m0oebEeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('Te8m0oebEeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-Te8m0oebEeGttUBADSqDjg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-Te8m0oebEeGttUBADSqDjg">
<div id="comments-header-Te8m0oebEeGttUBADSqDjg">
</div>
<div id="comments-Te8m0oebEeGttUBADSqDjg">
<div id="comment-wtN_FoebEeGttUBADSqDjg" class="conv-comment">
<a name="wtN_FoebEeGttUBADSqDjg"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="https://depmigrvpjbd.cloudfront.net/avatar/s_WDaVtiWBEeGAEkBADSqDjg.jpeg">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'wtN_FoebEeGttUBADSqDjg'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=tDM5JpfaEeCz1EBAhdLyVQ" class="ajax">Prasad Sunkari</a></span></span>
<span class="text-full">We can create a more use-case centric screenshots soon</span>
</div>
<div id="item-footer-wtN_FoebEeGttUBADSqDjg" class="comment-meta">
<abbr data-ts="1334563885" title="Monday, April 16, 2012 at 1:41pm" class="timestamp">5 hours ago</abbr>
·
<button data-ref="/item/like?id=wtN_FoebEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>
</div>
</div>
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-Te8m0oebEeGttUBADSqDjg">
<form id="comment-form-Te8m0oebEeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="Te8m0oebEeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="Te8m0oebEeGttUBADSqDjg" name="parent">
<input type="hidden" value="1" name="nc">
<div class="uploaded-filelist" id="comment-attach-Te8m0oebEeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-Te8m0oebEeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-Te8m0oebEeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-Te8m0oebEeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-Te8m0oebEeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="0jWkioeBEeG2oUBA7DJiCg" id="conv-0jWkioeBEeG2oUBA7DJiCg">
<div id="conv-avatar-0jWkioeBEeG2oUBA7DJiCg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_iOoe2Kx6EeClGEBAhdLyVQ.png">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-0jWkioeBEeG2oUBA7DJiCg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'0jWkioeBEeG2oUBA7DJiCg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=296bPp4xEeCDwEBAhdLyVQ" class="ajax">sandeep</a></span>
<div class="item-title ">
<div class="">
<span class="text-full">Down with typhoid will be back to office from wednesday.</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-0jWkioeBEeG2oUBA7DJiCg">
<abbr data-ts="1334552744" title="Monday, April 16, 2012 at 10:35am" class="timestamp">8 hours ago</abbr>  ·
<button data-ref="/item/like?id=0jWkioeBEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('0jWkioeBEeG2oUBA7DJiCg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('0jWkioeBEeG2oUBA7DJiCg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags no-likes" id="conv-meta-wrapper-0jWkioeBEeG2oUBA7DJiCg">
<div class="tags-wrapper" id="conv-tags-wrapper-0jWkioeBEeG2oUBA7DJiCg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('0jWkioeBEeG2oUBA7DJiCg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-0jWkioeBEeG2oUBA7DJiCg">
</span>
<form id="addtag-form-0jWkioeBEeG2oUBA7DJiCg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="0jWkioeBEeG2oUBA7DJiCg" name="id">
</form>
<button onclick="$$.convs.doneTags('0jWkioeBEeG2oUBA7DJiCg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-0jWkioeBEeG2oUBA7DJiCg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-0jWkioeBEeG2oUBA7DJiCg">
<div id="comments-header-0jWkioeBEeG2oUBA7DJiCg">
</div>
<div id="comments-0jWkioeBEeG2oUBA7DJiCg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-0jWkioeBEeG2oUBA7DJiCg">
<form id="comment-form-0jWkioeBEeG2oUBA7DJiCg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="0jWkioeBEeG2oUBA7DJiCg" class="comment-input" style="resize: none; overflow: auto; height: 31px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 92px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="0jWkioeBEeG2oUBA7DJiCg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-0jWkioeBEeG2oUBA7DJiCg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-0jWkioeBEeG2oUBA7DJiCg">
<div class="file-attach-outer busy-indicator" id="comment-attach-0jWkioeBEeG2oUBA7DJiCg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-0jWkioeBEeG2oUBA7DJiCg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-0jWkioeBEeG2oUBA7DJiCg-fileshare">
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
<div class="conv-item" data-convid="Uo-oaoOfEeG2oUBA7DJiCg" id="conv-Uo-oaoOfEeG2oUBA7DJiCg">
<div id="conv-avatar-Uo-oaoOfEeG2oUBA7DJiCg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-Uo-oaoOfEeG2oUBA7DJiCg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'Uo-oaoOfEeG2oUBA7DJiCg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<span class="conv-reason"><span class="user conv-user-cause"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span> and <span class="user conv-user-cause"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span> commented on <span class="user conv-user-cause"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span>'s <span class="item "><a href="/item?id=Uo-oaoOfEeG2oUBA7DJiCg" class="ajax">status</a></span></span>
<div class="conv-summary conv-quote">
<div class="item-title ">
<div class="">
<span class="user"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span>
<span class="text-full">SCSDesktop linux build</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-Uo-oaoOfEeG2oUBA7DJiCg">
<abbr data-ts="1334125610" title="Wednesday, April 11, 2012 at 11:56am" class="timestamp">April 11 at 11:56am</abbr>  ·
<button data-ref="/item/like?id=Uo-oaoOfEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('Uo-oaoOfEeG2oUBA7DJiCg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('Uo-oaoOfEeG2oUBA7DJiCg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-likes" id="conv-meta-wrapper-Uo-oaoOfEeG2oUBA7DJiCg">
<div class="tags-wrapper" id="conv-tags-wrapper-Uo-oaoOfEeG2oUBA7DJiCg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('Uo-oaoOfEeG2oUBA7DJiCg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-Uo-oaoOfEeG2oUBA7DJiCg">
<span tag-id="0anlHnytEeGn8kBADSqDjg" class="tag">
<a href="/tags?id=0anlHnytEeGn8kBADSqDjg" class="ajax">goal</a>
<form action="/item/untag" method="post" class="ajax delete-tags">
<input type="hidden" value="Uo-oaoOfEeG2oUBA7DJiCg" name="id">
<input type="hidden" value="0anlHnytEeGn8kBADSqDjg" name="tag">
<button class="button-link" type="submit">x</button>
</form>
</span>
</span>
<form id="addtag-form-Uo-oaoOfEeG2oUBA7DJiCg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="Uo-oaoOfEeG2oUBA7DJiCg" name="id">
</form>
<button onclick="$$.convs.doneTags('Uo-oaoOfEeG2oUBA7DJiCg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-Uo-oaoOfEeG2oUBA7DJiCg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-Uo-oaoOfEeG2oUBA7DJiCg">
<div id="comments-header-Uo-oaoOfEeG2oUBA7DJiCg">
</div>
<div id="comments-Uo-oaoOfEeG2oUBA7DJiCg">
<div id="comment-mh9c8oOfEeG2oUBA7DJiCg" class="conv-comment">
<a name="mh9c8oOfEeG2oUBA7DJiCg"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="https://depmigrvpjbd.cloudfront.net/avatar/s_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'mh9c8oOfEeG2oUBA7DJiCg'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span></span>
<span class="text-preview">@Rahul, after installing yasm &gt; 1.0, start build <br>  Go to src directory<br>  "make -f client.mk build_all". <br><br>Once the build is complete, create installer. <br>  Go to release directory<br>  make -C…</span>
<span style="display:none;" class="text-full">@Rahul, after installing yasm &gt; 1.0, start build <br>  Go to src directory<br>  "make -f client.mk build_all". <br><br>Once the build is complete, create installer. <br>  Go to release directory<br>  make -C mail/installer<br><br>You will find the tar.bz2 in releasedir/mozilla/dist/install</span>
&nbsp;&nbsp;
<button onclick="$$.convs.expandText(event);" class="text-expander">Expand this comment »</button>
<button onclick="$$.convs.collapseText(event);" style="display:none;" class="text-collapser">Collapse this comment</button>
</div>
<div id="item-footer-mh9c8oOfEeG2oUBA7DJiCg" class="comment-meta">
<abbr data-ts="1334125730" title="Wednesday, April 11, 2012 at 11:58am" class="timestamp">April 11 at 11:58am</abbr>
·
<button data-ref="/item/like?id=mh9c8oOfEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>
</div>
</div>
<div id="comment-qiRYUIbsEeG2oUBA7DJiCg" class="conv-comment">
<a name="qiRYUIbsEeG2oUBA7DJiCg"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="https://depmigrvpjbd.cloudfront.net/avatar/s_qrmj0qe0EeCVFkBAhdLyVQ.jpeg">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'qiRYUIbsEeG2oUBA7DJiCg'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span></span>
<span class="text-full">Compilation successful and I am also able to run SCS Desktop. However, I do not see any of the bundled plugins :(.</span>
</div>
<div id="item-footer-qiRYUIbsEeG2oUBA7DJiCg" class="comment-meta">
<abbr data-ts="1334488682" title="Sunday, April 15, 2012 at 4:48pm" class="timestamp">April 15 at 4:48pm</abbr>
·
<button data-ref="/item/like?id=qiRYUIbsEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>
</div>
</div>
<div id="comment-SAgB7Id_EeG2oUBA7DJiCg" class="conv-comment">
<a name="SAgB7Id_EeG2oUBA7DJiCg"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="https://depmigrvpjbd.cloudfront.net/avatar/s_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'SAgB7Id_EeG2oUBA7DJiCg'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span></span>
<span class="text-full">We need to run a script which puts those plugins in the installer. I'll do that later today. Copy the installer to some place and post it here.</span>
</div>
<div id="item-footer-SAgB7Id_EeG2oUBA7DJiCg" class="comment-meta">
<abbr data-ts="1334551653" title="Monday, April 16, 2012 at 10:17am" class="timestamp">8 hours ago</abbr>
·
<button data-ref="/item/like?id=SAgB7Id_EeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>
</div>
</div>
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-Uo-oaoOfEeG2oUBA7DJiCg">
<form id="comment-form-Uo-oaoOfEeG2oUBA7DJiCg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="Uo-oaoOfEeG2oUBA7DJiCg" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="Uo-oaoOfEeG2oUBA7DJiCg" name="parent">
<input type="hidden" value="3" name="nc">
<div class="uploaded-filelist" id="comment-attach-Uo-oaoOfEeG2oUBA7DJiCg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-Uo-oaoOfEeG2oUBA7DJiCg">
<div class="file-attach-outer busy-indicator" id="comment-attach-Uo-oaoOfEeG2oUBA7DJiCg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-Uo-oaoOfEeG2oUBA7DJiCg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-Uo-oaoOfEeG2oUBA7DJiCg-fileshare">
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
<div class="conv-item" data-convid="aPUsNIdtEeG2oUBA7DJiCg" id="conv-aPUsNIdtEeG2oUBA7DJiCg">
<div id="conv-avatar-aPUsNIdtEeG2oUBA7DJiCg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-aPUsNIdtEeG2oUBA7DJiCg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'aPUsNIdtEeG2oUBA7DJiCg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span>
<div class="item-title ">
<div class="">
<span class="text-full">Need to send a presentation to Benison today. Will WFH until lunch at least.</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-aPUsNIdtEeG2oUBA7DJiCg">
<abbr data-ts="1334543978" title="Monday, April 16, 2012 at 8:09am" class="timestamp">10 hours ago</abbr>  ·
<button data-ref="/item/like?id=aPUsNIdtEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('aPUsNIdtEeG2oUBA7DJiCg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('aPUsNIdtEeG2oUBA7DJiCg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags no-likes" id="conv-meta-wrapper-aPUsNIdtEeG2oUBA7DJiCg">
<div class="tags-wrapper" id="conv-tags-wrapper-aPUsNIdtEeG2oUBA7DJiCg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('aPUsNIdtEeG2oUBA7DJiCg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-aPUsNIdtEeG2oUBA7DJiCg">
</span>
<form id="addtag-form-aPUsNIdtEeG2oUBA7DJiCg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="aPUsNIdtEeG2oUBA7DJiCg" name="id">
</form>
<button onclick="$$.convs.doneTags('aPUsNIdtEeG2oUBA7DJiCg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-aPUsNIdtEeG2oUBA7DJiCg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-aPUsNIdtEeG2oUBA7DJiCg">
<div id="comments-header-aPUsNIdtEeG2oUBA7DJiCg">
</div>
<div id="comments-aPUsNIdtEeG2oUBA7DJiCg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-aPUsNIdtEeG2oUBA7DJiCg">
<form id="comment-form-aPUsNIdtEeG2oUBA7DJiCg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="aPUsNIdtEeG2oUBA7DJiCg" class="comment-input" style="resize: none; overflow: auto; height: 31px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 92px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="aPUsNIdtEeG2oUBA7DJiCg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-aPUsNIdtEeG2oUBA7DJiCg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-aPUsNIdtEeG2oUBA7DJiCg">
<div class="file-attach-outer busy-indicator" id="comment-attach-aPUsNIdtEeG2oUBA7DJiCg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-aPUsNIdtEeG2oUBA7DJiCg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-aPUsNIdtEeG2oUBA7DJiCg-fileshare">
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
<div class="conv-item" data-convid="RfCqloWiEeGttUBADSqDjg" id="conv-RfCqloWiEeGttUBADSqDjg">
<div id="conv-avatar-RfCqloWiEeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-RfCqloWiEeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/delete', {id:'RfCqloWiEeGttUBADSqDjg'});" class="menu-item noicon">Delete</a></li>
</ul>
<span class="conv-reason"><span class="user conv-user-cause"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span> liked your <span class="item "><a href="/item?id=RfCqloWiEeGttUBADSqDjg" class="ajax">link</a></span></span>
<div class="conv-summary conv-quote">
<div class="item-title has-icon">
<span class="icon item-icon link-icon"></span>
<div class="item-title-text">
<span class="text-full">UI Components for faceted search.</span>
<div class="link-item">
<div class="link-details">
<a target="_blank" href="http://twigkit.com/"><div class="link-title">TwigKit: Search User Interfaces for the Enterprise</div></a>
<div class="link-summary" id="summary">TwigKit is an easy-to-use toolkit that enables any web designer to quickly build full-featured search applications that look and feel great.</div>
<div class="link-url" id="url">twigkit.com</div>
</div>
</div>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-RfCqloWiEeGttUBADSqDjg">
<abbr data-ts="1334346780" title="Saturday, April 14, 2012 at 1:23am" class="timestamp">April 14 at 1:23am</abbr>  ·
<button data-ref="/item/like?id=RfCqloWiEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('RfCqloWiEeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('RfCqloWiEeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags" id="conv-meta-wrapper-RfCqloWiEeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-RfCqloWiEeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('RfCqloWiEeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-RfCqloWiEeGttUBADSqDjg">
</span>
<form id="addtag-form-RfCqloWiEeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="RfCqloWiEeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('RfCqloWiEeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-RfCqloWiEeGttUBADSqDjg">
<div class="conv-likes">
<span class="user"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span> likes this
</div>
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-RfCqloWiEeGttUBADSqDjg">
<div id="comments-header-RfCqloWiEeGttUBADSqDjg">
</div>
<div id="comments-RfCqloWiEeGttUBADSqDjg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-RfCqloWiEeGttUBADSqDjg">
<form id="comment-form-RfCqloWiEeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="RfCqloWiEeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="RfCqloWiEeGttUBADSqDjg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-RfCqloWiEeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-RfCqloWiEeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-RfCqloWiEeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-RfCqloWiEeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-RfCqloWiEeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="QqN5soWtEeGttUBADSqDjg" id="conv-QqN5soWtEeGttUBADSqDjg">
<div id="conv-avatar-QqN5soWtEeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_ghbATKgMEeCVFkBAhdLyVQ.png">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-QqN5soWtEeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/delete', {id:'QqN5soWtEeGttUBADSqDjg'});" class="menu-item noicon">Delete</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=i-3wEp4wEeCDwEBAhdLyVQ" class="ajax">Abhishek</a></span>
<div class="item-title has-icon">
<span class="icon item-icon link-icon"></span>
<div class="item-title-text">
<span class="text-full">Like youtube but for your shell. The cool thing is you can copy, paste the text.</span>
<div class="link-item">
<div class="link-details">
<a target="_blank" href="http://shelr.tv/about"><div class="link-title">
Shelr
</div></a>
<div class="link-url" id="url">shelr.tv</div>
</div>
</div>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-QqN5soWtEeGttUBADSqDjg">
<abbr data-ts="1334351499" title="Saturday, April 14, 2012 at 2:41am" class="timestamp">April 14 at 2:41am</abbr>  ·
<button data-ref="/item/like?id=QqN5soWtEeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('QqN5soWtEeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('QqN5soWtEeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags no-likes" id="conv-meta-wrapper-QqN5soWtEeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-QqN5soWtEeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('QqN5soWtEeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-QqN5soWtEeGttUBADSqDjg">
</span>
<form id="addtag-form-QqN5soWtEeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="QqN5soWtEeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('QqN5soWtEeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-QqN5soWtEeGttUBADSqDjg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-QqN5soWtEeGttUBADSqDjg">
<div id="comments-header-QqN5soWtEeGttUBADSqDjg">
</div>
<div id="comments-QqN5soWtEeGttUBADSqDjg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-QqN5soWtEeGttUBADSqDjg">
<form id="comment-form-QqN5soWtEeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="QqN5soWtEeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 31px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 92px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="QqN5soWtEeGttUBADSqDjg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-QqN5soWtEeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-QqN5soWtEeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-QqN5soWtEeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-QqN5soWtEeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-QqN5soWtEeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="mGdjFoV4EeGttUBADSqDjg" id="conv-mGdjFoV4EeGttUBADSqDjg">
<div id="conv-avatar-mGdjFoV4EeGttUBADSqDjg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_qrmj0qe0EeCVFkBAhdLyVQ.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-mGdjFoV4EeGttUBADSqDjg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'mGdjFoV4EeGttUBADSqDjg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<span class="conv-reason"><span class="user conv-user-cause"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span> commented on <span class="user conv-user-cause"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span>'s <span class="item "><a href="/item?id=mGdjFoV4EeGttUBADSqDjg" class="ajax">status</a></span></span>
<div class="conv-summary conv-quote">
<div class="item-title ">
<div class="">
<span class="user"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span>
<span class="text-full">removed the script that I had added.</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-mGdjFoV4EeGttUBADSqDjg">
<abbr data-ts="1334328879" title="Friday, April 13, 2012 at 8:24pm" class="timestamp">April 13 at 8:24pm</abbr>  ·
<button data-ref="/item/like?id=mGdjFoV4EeGttUBADSqDjg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('mGdjFoV4EeGttUBADSqDjg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('mGdjFoV4EeGttUBADSqDjg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-tags no-likes" id="conv-meta-wrapper-mGdjFoV4EeGttUBADSqDjg">
<div class="tags-wrapper" id="conv-tags-wrapper-mGdjFoV4EeGttUBADSqDjg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('mGdjFoV4EeGttUBADSqDjg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-mGdjFoV4EeGttUBADSqDjg">
</span>
<form id="addtag-form-mGdjFoV4EeGttUBADSqDjg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="mGdjFoV4EeGttUBADSqDjg" name="id">
</form>
<button onclick="$$.convs.doneTags('mGdjFoV4EeGttUBADSqDjg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-mGdjFoV4EeGttUBADSqDjg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-mGdjFoV4EeGttUBADSqDjg">
<div id="comments-header-mGdjFoV4EeGttUBADSqDjg">
</div>
<div id="comments-mGdjFoV4EeGttUBADSqDjg">
<div id="comment-p2QHFoV4EeGttUBADSqDjg" class="conv-comment">
<a name="p2QHFoV4EeGttUBADSqDjg"> </a>
<div class="comment-avatar">
<img style="max-height: 32px; max-width: 32px;" src="https://depmigrvpjbd.cloudfront.net/avatar/s_qrmj0qe0EeCVFkBAhdLyVQ.jpeg">
</div>
<div class="comment-container">
<span onclick="$.post('/ajax/item/delete', {id:'p2QHFoV4EeGttUBADSqDjg'});" class="conv-other-actions">&nbsp;</span>
<span class="comment-user"><span class="user"><a href="/profile?id=KID0Jp5XEeCDwEBAhdLyVQ" class="ajax">Rahul</a></span></span>
<span class="text-full">for reliance netconnect in /etc/ppp/ip-up.d/ .</span>
</div>
<div id="item-footer-p2QHFoV4EeGttUBADSqDjg" class="comment-meta">
<abbr data-ts="1334328904" title="Friday, April 13, 2012 at 8:25pm" class="timestamp">April 13 at 8:25pm</abbr>
·
<button data-ref="/item/like?id=p2QHFoV4EeGttUBADSqDjg" class="button-link ajaxpost">Like</button>
</div>
</div>
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-mGdjFoV4EeGttUBADSqDjg">
<form id="comment-form-mGdjFoV4EeGttUBADSqDjg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="mGdjFoV4EeGttUBADSqDjg" class="comment-input" style="resize: none; overflow: auto; height: 23px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 455px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="mGdjFoV4EeGttUBADSqDjg" name="parent">
<input type="hidden" value="1" name="nc">
<div class="uploaded-filelist" id="comment-attach-mGdjFoV4EeGttUBADSqDjg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-mGdjFoV4EeGttUBADSqDjg">
<div class="file-attach-outer busy-indicator" id="comment-attach-mGdjFoV4EeGttUBADSqDjg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-mGdjFoV4EeGttUBADSqDjg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-mGdjFoV4EeGttUBADSqDjg-fileshare">
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
<div class="conv-item" data-convid="8v1hsIUrEeG2oUBA7DJiCg" id="conv-8v1hsIUrEeG2oUBA7DJiCg">
<div id="conv-avatar-8v1hsIUrEeG2oUBA7DJiCg" class="conv-avatar">
<img style="max-height: 48px; max-width: 48px;" src="https://depmigrvpjbd.cloudfront.net/avatar/m_W57otrzWEeCgW0BAhdLyVQ.jpeg">
</div>
<div class="conv-data">
<div class="conv-root" id="conv-root-8v1hsIUrEeG2oUBA7DJiCg">
<span onclick="$$.ui.showPopup(event, true);" class="conv-other-actions"></span>
<ul style="display:none;" class="acl-menu">
<li><a onclick="$.post('/ajax/item/remove', {id:'8v1hsIUrEeG2oUBA7DJiCg'});" class="menu-item noicon">Hide from my Feed</a></li>
</ul>
<div class="conv-summary">
<span class="user conv-user-cause"><a href="/profile?id=wG-abpfyEeCqH0BAhdLyVQ" class="ajax">Siva</a></span>
<div class="item-title ">
<div class="">
<span class="text-full">Got two meetings today. One with Zocampus now &amp; another with Pyramid at 3pm.<br>Post your updates guys :)</span>
</div>
</div>
<div class="conv-footer busy-indicator" id="item-footer-8v1hsIUrEeG2oUBA7DJiCg">
<abbr data-ts="1334295960" title="Friday, April 13, 2012 at 11:16am" class="timestamp">April 13 at 11:16am</abbr>  ·
<button data-ref="/item/like?id=8v1hsIUrEeG2oUBA7DJiCg" class="button-link ajaxpost">Like</button>·<button onclick="$$.convs.comment('8v1hsIUrEeG2oUBA7DJiCg');" class="button-link">Comment</button>·<button onclick="$$.convs.editTags('8v1hsIUrEeG2oUBA7DJiCg', true);" title="Add Tag" class="button-link">Add Tag</button>
</div>
</div>
</div>
<div class="conv-meta-wrapper no-comments no-tags no-likes" id="conv-meta-wrapper-8v1hsIUrEeG2oUBA7DJiCg">
<div class="tags-wrapper" id="conv-tags-wrapper-8v1hsIUrEeG2oUBA7DJiCg">
<div class="conv-tags">
<button onclick="$$.convs.editTags('8v1hsIUrEeG2oUBA7DJiCg');" title="Edit tags" class="button-link edit-tags-button"><span class="icon edit-tags-icon"></span>Edit Tags</button>
<span id="conv-tags-8v1hsIUrEeG2oUBA7DJiCg">
</span>
<form id="addtag-form-8v1hsIUrEeG2oUBA7DJiCg" autocomplete="off" class="ajax edit-tags-form" action="/item/tag" method="post">
<div class="input-wrap">
<input type="text" title="Tag" required="" placeholder="Add tag" value="" name="tag" class="conv-tags-input">
</div>
<input type="hidden" value="8v1hsIUrEeG2oUBA7DJiCg" name="id">
</form>
<button onclick="$$.convs.doneTags('8v1hsIUrEeG2oUBA7DJiCg');" title="Done editing tags" class="button-link done-tags-button"><span class="icon done-tags-icon"></span>Done</button>
<span class="clear"></span>
</div>
</div>
<div class="likes-wrapper" id="conv-likes-wrapper-8v1hsIUrEeG2oUBA7DJiCg">
</div>
<div class="comments-wrapper" id="conv-comments-wrapper-8v1hsIUrEeG2oUBA7DJiCg">
<div id="comments-header-8v1hsIUrEeG2oUBA7DJiCg">
</div>
<div id="comments-8v1hsIUrEeG2oUBA7DJiCg">
</div>
</div>
<div class="comment-form-wrapper busy-indicator" id="comment-form-wrapper-8v1hsIUrEeG2oUBA7DJiCg">
<form id="comment-form-8v1hsIUrEeG2oUBA7DJiCg" autocomplete="off" class="ajax" action="/item/comment" method="post">
<div class="input-wrap">
<textarea title="Comment" required="" placeholder="Leave a response..." name="comment" data-convid="8v1hsIUrEeG2oUBA7DJiCg" class="comment-input" style="resize: none; overflow: auto; height: 31px;"></textarea><div style="position: absolute; top: -10000px; left: -10000px; width: 92px; font-size: 12px; font-family: sans-serif; line-height: 15px; word-wrap: break-word;" class="autogrow-backplane"></div>
</div>
<input type="hidden" value="8v1hsIUrEeG2oUBA7DJiCg" name="parent">
<input type="hidden" value="0" name="nc">
<div class="uploaded-filelist" id="comment-attach-8v1hsIUrEeG2oUBA7DJiCg-uploaded"></div>
</form>
<div class="file-attach-wrapper">
<form class="ajax" enctype="multipart/form-data" method="post" action="" id="comment-attach-8v1hsIUrEeG2oUBA7DJiCg">
<div class="file-attach-outer busy-indicator" id="comment-attach-8v1hsIUrEeG2oUBA7DJiCg-wrapper">
<input type="file" class="file-attach-input" id="comment-attach-8v1hsIUrEeG2oUBA7DJiCg-file-input" name="file">
<button class="file-attach-button" id="comment-attach-8v1hsIUrEeG2oUBA7DJiCg-fileshare">
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
<div class="busy-indicator" id="next-load-wrapper"><a data-ref="/feed/i-3wEp4wEeCDwEBAhdLyVQ?start=xXqsa1aIUmEeGttUBADSqDjg&amp;more=1" href="/feed/i-3wEp4wEeCDwEBAhdLyVQ/?start=xXqsa1aIUmEeGttUBADSqDjg" class="ajax" id="next-page-load">Fetch older posts</a></div>
</div>
</%def>
