<%! from social import utils, _, __, plugins, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
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
        <div id="item-me">
          %if not script:
            ${self.item_me()}
          %endif
        </div>
        <div id="item-meta">
          %if not script:
            ${self.item_meta()}
          %endif
        </div>
        <div id="item-subactions">
          %if not script:
            ${self.item_subactions()}
          %endif
        </div>
      </div>
      <div id="center">
        <div class="center-contents">
          % if convId:
              ${self.item_layout(convId)}
          % endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="item_layout(convId, inline=False, isFeed=False)">
  <div id="conv-${convId}" class="conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}">
      %if inline or not script:
        ${self.conv_owner(items[convId]['meta']['owner'])}
      %endif
    </div>
    <div class="conv-data">
      <div id="conv-root-${convId}">
        %if inline:
          <% hasReason = reasonStr and reasonStr.has_key(convId) %>
          %if hasReason:
            <span class="conv-reason">${reasonStr[convId]}</span>
          %endif
          <div class="conv-summary${' conv-quote' if hasReason else ''}">
            ${self.conv_root(convId, hasReason)}
            <div id="item-footer-${convId}" class="conv-footer busy-indicator">
              ${self.item_footer(convId)}
            </div>
          </div>
        %else:
          <div class="conv-summary"></div>
          <div id="item-footer-${convId}" class="conv-footer busy-indicator"></div>
        %endif
      </div>
      <div id="conv-likes-wrapper-${convId}">
        %if likeStr and likeStr.has_key(convId):
          <div class="conv-likes">${likeStr[convId]}</div>
        %endif
      </div>
      <div id="conv-tags-wrapper-${convId}" class="busy-indicator">
        %if inline or not script:
          ${self.conv_tags(convId)}
        %endif
      </div>
      <div id="conv-comments-wrapper-${convId}">
        %if inline or not script:
          ${self.conv_comments(convId, isFeed)}
        %endif
      </div>
      <div id="comment-form-wrapper-${convId}" class="conv-comment-form busy-indicator">
        %if inline or not script:
          ${self.conv_comment_form(convId)}
        %endif
      </div>
    </div>
  </div>
</%def>

<%def name="conv_owner(ownerId)">
  <% avatarURI = utils.userAvatar(ownerId, entities[ownerId]) %>
  %if avatarURI:
    <img src="${avatarURI}" height="48" width="48"/>
  %endif
</%def>

<%def name="conv_root(convId, isQuoted=False)">
  <% itemType = items[convId]["meta"]["type"] %>
  %if itemType in plugins:
    ${plugins[itemType].rootHTML(convId, isQuoted, context.kwargs)}
  %endif
</%def>

<%def name="item_footer(itemId)">
  <%
    meta = items[itemId]['meta']
    hasParent = meta.has_key('parent')
    timestamp = int(meta['timestamp'])
    likesCount = int(meta.get('likesCount', "0"))
  %>
  ${utils.simpleTimestamp(timestamp)}
  &nbsp;&#183;&nbsp;
  %if hasParent and likesCount > 0:
    <span class="likes"><a class="ajax" _ref="/item/likes?id=${itemId}">${likesCount}</a></span>
    &nbsp;&#183;&nbsp;
  %endif
  %if myLikes and myLikes.has_key(itemId) and len(myLikes[itemId]):
    <span><a class="ajax" _ref="/item/unlike?id=${itemId}">${_("Unlike")}</a></span>
  %else:
    <span><a class="ajax" _ref="/item/like?id=${itemId}">${_("Like")}</a></span>
  %endif
</%def>

<%def name="conv_comments_head(convId, total, showing, isFeed)">
  %if total > showing:
    <div class="conv-comments-more" class="busy-indicator">
      %if isFeed:
        %if total > constants.MAX_COMMENTS_IN_FEED or not script:
          <a class="ajax" href="/item?id=${convId}">${_("View all %s comments &#187;") % (total)}</a>
        %else:
          <a class="ajax" href="/item?id=${convId}" _ref="/item/responses?id=${convId}">${_("View all %s comments &#187;") % (total)}</a>
        %endif
      %else:
        <span class="num-comments">${_("%s of %s") % (showing, total)}</span>
        %if oldest:
          <a class="ajax" href="/item?id=${convId}&start=${oldest}" _ref="/item/responses?id=${convId}&nc=${showing}&start=${oldest}">${_("View older comments &#187;")}</a>
        %else:
          <a class="ajax" href="/item?id=${convId}" _ref="/item/responses?id=${convId}&nc=${showing}">${_("View older comments &#187;")}</a>
        %endif
      %endif
    </div>
  %endif
</%def>

<%def name="conv_comments_only(convId)">
  <% responsesToShow = responses.get(convId, {}) if responses else [] %>
  %for responseId in responsesToShow:
    ${self.conv_comment(convId, responseId)}
  %endfor
</%def>

<%def name="conv_comments(convId, isFeed=False)">
  <%
    responseCount = int(items[convId]["meta"].get("responseCount", "0"))
    responsesToShow = responses.get(convId, {}) if responses else []
  %>
  <div id="comments-header-${convId}">
    ${self.conv_comments_head(convId, responseCount, len(responsesToShow), isFeed)}
  </div>
  <div id="comments-${convId}">
    %for responseId in responsesToShow:
      ${self.conv_comment(convId, responseId)}
    %endfor
  </div>
</%def>

<%def name="conv_comment_form(convId)">
  <form method="post" action="/item/comment" class="ajax" autocomplete="off" id="comment-form-${convId}">
    <input type="text" name="comment" value=""></input>
    <input type="hidden" name="parent" value=${convId}></input>
    %if not isFeed:
      <% nc = len(responses.get(convId, {})) if responses else 0 %>
      <input type="hidden" name="nc" value=${nc}></input>
      %if oldest:
        <input type="hidden" name="start" value=${oldest}></input>
      %endif
    %endif
    ${widgets.button(None, type="submit", name="comment", value="Comment")}<br/>
  </form>
</%def>

<%def name="conv_comment(convId, commentId)">
  <%
    item = items[commentId]
    userId  = item["meta"]["owner"]
    comment = item["meta"].get("comment", "")
  %>
  <div class="conv-comment" id="comment-${commentId}">
    <div class="comment-avatar">
      <% avatarURI = utils.userAvatar(userId, entities[userId], "small") %>
      %if avatarURI:
        <img src="${avatarURI}" height='32' width='32'/>
      %endif
    </div>
    <div class="comment-container">
      <span class="comment-user">${utils.userName(userId, entities[userId])}</span>
      <span class="comment-text">${comment}</span>
    </div>
    <div class="comment-meta">
      ${self.item_footer(commentId)}
    </div>
  </div>
</%def>


<%def name="conv_tag(convId, tagId, tagName)">
  <span><a class="ajax" href="/tags?id=${tagId}">${tagName}</a><span class="delete-tag"><a class="ajax" _ref="/item/untag?id=${convId}&tag=${tagId}">X</a></span></span>
</%def>


<%def name="conv_tags(convId)">
  <% itemTags = items[convId].get("tags", {}) %>
  <div id="conv-tags-${convId}" class="conv-tags">
    %for tagId in itemTags.keys():
      <span><a class="ajax" href="/tags?id=${tagId}">${tags[tagId]["title"]}</a><span class="delete-tag"><a class="ajax" _ref="/item/untag?id=${convId}&tag=${tagId}">X</a></span></span>
    %endfor
  </div>
  <form method="post" action="/item/tag" class="ajax" autocomplete="off" id="addtag-form-${convId}">
    <input type="text" name="tag" value=""></input>
    <input type="hidden" name="id" value=${convId}></input>
    ${widgets.button(None, type="submit", name="add", value="Add")}<br/>
  </form>
</%def>

<%def name="item_me()">
</%def>

<%def name="item_meta()">
</%def>

<%def name="item_subactions()">
</%def>

<%def name="render_status(convId, isQuoted=False)">
  <%
    conv = items[convId]
    userId = conv["meta"]["owner"]
  %>
  %if not isQuoted:
    ${utils.userName(userId, entities[userId], "conv-user-cause")}
  %else:
    ${utils.userName(userId, entities[userId])}
  %endif
  %if conv["meta"].has_key("comment"):
    ${conv["meta"]["comment"]}
  %endif
</%def>

<%def name="render_activity(convId, isQuoted=False)">
  <%
    conv = items[convId]
    userId = conv["meta"]["owner"]
    subtype = conv["meta"]["subType"]
    target = conv["meta"]["target"]
    fmtUser = utils.userName

    if subtype == "connection":
      activity = _("%s and %s are now friends.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
    elif subtype == "following":
      activity = _("%s started following %s.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
  %>
  ${activity}
</%def>
