<%! from social import utils, _, __, plugins, constants %>
<%! from twisted.python import log %>
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
          %if script:
            ${self.item_lazy_layout(convId)}
          %else:
            ${self.item_layout(convId)}
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="item_lazy_layout(convId)">
  <div id="conv-${convId}" class="conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}"></div>
    <div class="conv-data">
      <div id="conv-root-${convId}">
        <div class="conv-summary"></div>
        <div id="item-footer-${convId}" class="conv-footer busy-indicator"></div>
      </div>
      <div id="conv-tags-wrapper-${convId}"></div>
      <div id="conv-likes-wrapper-${convId}"></div>
      <div id="conv-comments-wrapper-${convId}"></div>
      <div id="comment-form-wrapper-${convId}" class="comment-form-wrapper busy-indicator"></div>
    </div>
  </div>
</%def>


<%def name="item_layout(convId)">
  <div id="conv-${convId}" class="conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}">
      ${self.conv_owner(items[convId]['meta']['owner'])}
    </div>
    <div class="conv-data">
      <div id="conv-root-${convId}">
        <%
          hasReason = reasonStr and reasonStr.has_key(convId)
          hasComments = responses and len(responses.get(convId, {}))
          hasLikes = likes and len(likes.get(convId, {}))
          hasTags = items and items[convId].get("tags", {})
        %>
        %if hasReason:
          <span class="conv-reason">${reasonStr[convId]}</span>
          <div class="conv-summary conv-quote">
        %else:
          <div class="conv-summary">
        %endif
          ${self.conv_root(convId, hasReason)}
          <div id="item-footer-${convId}" class="conv-footer busy-indicator">
            ${self.conv_footer(convId, hasComments, hasLikes, hasTags)}
          </div>
        </div>
      </div>
      <div id="conv-meta-wrapper-${convId}" class="conv-meta-wrapper${' no-comments' if not hasComments else ''}${' no-tags' if not hasTags else ''}${' no-likes' if not hasLikes else ''}">
        <div id="conv-tags-wrapper-${convId}" class="tags-wrapper">
          ${self.conv_tags(convId)}
        </div>
        <div id="conv-likes-wrapper-${convId}" class="likes-wrapper">
          <%
            count = int(items[convId]["meta"].get("likesCount", "0"))
            if count:
              iLike = myLikes and convId in myLikes and len(myLikes[convId])
              self.conv_likes(convId, count, iLike, likes.get(convId, {}))
          %>
        </div>
        <div id="conv-comments-wrapper-${convId}" class="comments-wrapper">
          ${self.conv_comments(convId, True)}
        </div>
        %if script:
        <div id="comment-form-wrapper-${convId}" class="comment-form-wrapper busy-indicator">
          ${self.conv_comment_form(convId)}
        </div>
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


<%def name="conv_footer(convId, hasComments=True, hasLikes=True, hasTags=True)">
  <%
    meta = items[convId]['meta']
    timestamp = int(meta['timestamp'])
    likesCount = 0 if hasLikes else int(meta.get('likesCount', '0'))
    commentsCount = 0 if hasComments else int(meta.get('responseCount', '0'))
  %>
  ${utils.simpleTimestamp(timestamp)}\
  ## If none of my friends liked it, show the count of likes (onclick show the likes)
  %if (not hasLikes and likesCount) or (not hasComments and commentsCount):
    &#183;
  %endif
  %if not hasLikes and likesCount > 0:
    <button class="button-link" title="${likesCount} Likes"><div class="small-icon small-like"><div>${likesCount}</button>
  %endif
  ## Number of comments when none of my friends commented on it
  %if not hasComments and commentsCount > 0:
    <button class="button-link ajax" title="${commentsCount} Comments"><div class="small-icon small-comment"></div>${commentsCount}</button>
  %endif
  &#183;
  ## Like this conversation
  %if myLikes and myLikes.has_key(convId) and len(myLikes[convId]):
    <button class="button-link ajax" _ref="/item/unlike?id=${convId}">${_("Unlike")}</button>&#183;<button
  %else:
    <button class="button-link ajax" _ref="/item/like?id=${convId}">${_("Like")}</button>&#183;<button
  %endif
  ## Comment on this conversation
  class="button-link" onclick="$$.convs.comment('${convId}');" >${_("Comment")}</button>&#183;<button
  ## Add a tag
  class="button-link" title="${_('Add Tag')}" onclick="$$.convs.editTags('${convId}', true);">${_("Add Tag")}</button>
</%def>


<%def name="item_footer(itemId)">
  <%
    meta = items[itemId]['meta']
    timestamp = int(meta['timestamp'])
    likesCount = int(meta.get('likesCount', "0"))
  %>
  ${utils.simpleTimestamp(timestamp)}
  %if likesCount > 0:
    &#183;
    <button class="button-link" title="${likesCount} Likes"><div class="small-icon small-like"></div>${likesCount}</button>
  %endif
  &#183;
  %if myLikes and myLikes.has_key(convId) and len(myLikes[convId]):
    <button class="button-link ajax" _ref="/item/unlike?id=${itemId}">${_("Unlike")}</button>
  %else:
    <button class="button-link ajax" _ref="/item/like?id=${itemId}">${_("Like")}</button>
  %endif
</%def>


<%def name="conv_likes(convId, count=0, me=False, users=None)">
  <%
    if not count:
      return ''

    likeStr = None
    template = None
    other = count

    if me:
      users.remove(myKey)
      other -= (1 + len(users))
      if other <= 0:
        template = ["You like this",
                    "You and %s like this",
                    "You, %s and %s like this"][len(users)]
      elif other == 1:
        template = ["You and 1 other person like this",
            "You, %s and 1 other person like this",
            "You, %s, %s and 1 other person like this"][len(users)]
      else:
        template = ["You and %s other people like this",
            "You, %s and %s other people like this",
            "You, %s, %s and %s other people like this"][len(users)]
    else:
      other -= len(users)
      if other == 0 and len(users) > 0:
        template = ["%s likes this",
                    "%s and %s like this"][len(users)-1]
      if other == 1:
        template = ["1 person likes this",
            "%s and 1 other person like this",
            "%s, %s and 1 other people like this"][len(users)]
      elif other > 1:
        template = ["%s people like this",
            "%s and %s other people like this",
            "%s, %s and %s other people like this"][len(users)]

    if template:
        vals = [utils.userName(id, entities[id]) for id in users]
        if other > 1:
            vals.append(str(other))

        likeStr = _(template) % tuple(vals)

    if not likeStr:
      return ''
  %>
  <div class="conv-likes">
    ${likeStr}
  </div>
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
    <div class="input-wrap">
      <textarea class="comment-input" name="comment" placeholder="${_('Leave a response...')}" value=""></textarea>
    </div>
    <input type="hidden" name="parent" value=${convId}></input>
    %if not isFeed:
      <% nc = len(responses.get(convId, {})) if responses else 0 %>
      <input type="hidden" name="nc" value=${nc}></input>
      %if oldest:
        <input type="hidden" name="start" value=${oldest}></input>
      %endif
    %endif
  </form>
</%def>


<%def name="conv_comment(convId, commentId)">
  <%
    item = items[commentId]
    userId = item["meta"]["owner"]
    comment = item["meta"]["comment"]
    normalize = utils.normalizeText
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
      <span class="comment-text">${comment|normalize}</span>
    </div>
    <div class="comment-meta">
      ${self.item_footer(commentId)}
    </div>
  </div>
</%def>


<%def name="conv_tag(convId, tagId, tagName)">
  <span class="tag" id="tag-${tagId}">
    <a class="ajax" href="/tags?id=${tagId}">${tagName}</a>
    <form class="ajax delete-tags" action="/item/untag">
      <input type="hidden" name="id" value="${convId}"/>
      <input type="hidden" name="tag" value="${tagId}"/>
      <button type="submit" class="button-link">x</button>
    </form>
  </span>
</%def>


<%def name="conv_tags(convId)">
  <% itemTags = items[convId].get("tags", {}) %>
  <div class="conv-tags">
    <button class="button-link edit-tags-button" title="${_('Edit tags')}" onclick="$$.convs.editTags('${convId}');"><div class="icon edit-tags-icon"></div>Edit Tags</button>
    <span id="conv-tags-${convId}">
    %for tagId in itemTags.keys():
      <span class="tag" id="tag-${tagId}">
        <a class="ajax" href="/tags?id=${tagId}">${tags[tagId]["title"]}</a>
        <form class="ajax delete-tags" action="/item/untag">
          <input type="hidden" name="id" value="${convId}"/>
          <input type="hidden" name="tag" value="${tagId}"/>
          <button type="submit" class="button-link">x</button>
        </form>
      </span>
    %endfor
    </span>
    <form method="post" action="/item/tag" class="ajax edit-tags-form" autocomplete="off" id="addtag-form-${convId}">
      <div class="input-wrap">
        <input type="text" class="conv-tags-input" name="tag" value="" placeholder="${_('Add tag')}"></input>
      </div>
      <input type="hidden" name="id" value=${convId}></input>
    </form>
    <button class="button-link done-tags-button" title="${_('Done editing tags')}" onclick="$$.convs.doneTags('${convId}');"><div class="icon done-tags-icon"></div>Done</button>
  </div>
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
    normalize = utils.normalizeText
  %>
  %if not isQuoted:
    ${utils.userName(userId, entities[userId], "conv-user-cause")}
  %endif
  <div class="item-title">
    %if isQuoted:
      ${utils.userName(userId, entities[userId])}
    %endif
    %if conv["meta"].has_key("comment"):
      ${conv["meta"]["comment"]|normalize}
    %endif
  </div>
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
    elif subtype == "groupJoin":
      activity = _("%s joined the group: %s.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
    elif subtype == "groupLeave":
      activity = _("%s left the group: %s.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
  %>
  ${activity}
</%def>
