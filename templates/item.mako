<%! from social import utils, _, __, plugins, constants, config, secureProxy %>
<%! from twisted.web.static import formatFileSize %>
<%! from base64 import b64encode, urlsafe_b64decode %>
<%! from urlparse import urlsplit %>

<!DOCTYPE HTML>

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
      <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="item_lazy_layout(convId)">
  <div id="conv-${convId}" data-convid="${convId}" class="conv-item init-conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}"></div>
    <div class="conv-data">
      <div id="conv-root-${convId}">
        <div class="conv-summary"></div>
        <div id="item-footer-${convId}" class="conv-footer busy-indicator"></div>
      </div>
      <div id="conv-meta-wrapper-${convId}" class="conv-meta-wrapper no-tags">
        <div id="conv-tags-wrapper-${convId}" class="tags-wrapper"></div>
        <div id="conv-likes-wrapper-${convId}" class="likes-wrapper"></div>
        <div id="conv-comments-wrapper-${convId}" class="comments-wrapper"></div>
        <div id="comment-form-wrapper-${convId}" class="comment-form-wrapper busy-indicator"></div>
      </div>
    </div>
  </div>
</%def>


<%def name="item_layout(convId, classes='')">
  <div id="conv-${convId}" data-convid="${convId}" class="conv-item ${classes} init-conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}">
      <%
        convMeta = items[convId]['meta']
        if reasonUserIds and reasonUserIds.get(convId, []):
            reasonUserId = reasonUserIds[convId][0]
        else:
            reasonUserId = convMeta["owner"]
      %>
      %if convMeta['type'] != 'feedback':
        ${self.conv_owner(reasonUserId)}
      %else:
        ${self.feedback_icon(convMeta['subType'])}
      %endif
    </div>
    <div class="conv-data">
      <%
        hasReason = reasonStr and reasonStr.has_key(convId)
        hasKnownComments = responses and len(responses.get(convId, []))
        hasTags = items[convId].get("tags", {})

        likesCount = int(items[convId]["meta"].get("likesCount", "0"))
        if likesCount:
            iLike = myLikes and convId in myLikes and len(myLikes[convId])
            knownLikes = likes.get(convId, []) if likes else []
            hasKnownLikes = (likes and len(knownLikes)) or iLike
        else:
            hasKnownLikes, iLike = None, None

        convType = convMeta["type"]
        convOwner = convMeta["owner"]
      %>
      <div id="conv-root-${convId}" class="conv-root">
        ${self._item_other_actions(convId, convOwner==myId, convType)}
        %if hasReason:
          <span class="conv-reason">${reasonStr[convId]}</span>
          <div class="conv-summary conv-quote">
        %else:
          <div class="conv-summary">
        %endif
          ${self.conv_root(convId, hasReason)}
          <div id="item-footer-${convId}" class="conv-footer busy-indicator">
            ${self.conv_footer(convId, hasKnownComments, hasKnownLikes, hasTags)}
          </div>
        </div>
      </div>
      <div id="conv-meta-wrapper-${convId}" class="conv-meta-wrapper${' no-comments' if not hasKnownComments else ''}${' no-tags' if not hasTags else ''}${' no-likes' if not hasKnownLikes else ''}">
        <div id="conv-tags-wrapper-${convId}" class="tags-wrapper">
          ${self.conv_tags(convId)}
        </div>
        <div id="conv-likes-wrapper-${convId}" class="likes-wrapper">
          <%
            if hasKnownLikes:
              self.conv_likes(convId, likesCount, iLike, knownLikes)
          %>
        </div>
        <div id="conv-comments-wrapper-${convId}" class="comments-wrapper">
          ${self.conv_comments(convId, isItemView)}
        </div>
        %if script:
        <div id="comment-form-wrapper-${convId}" class="comment-form-wrapper busy-indicator">
          ${self.conv_comment_form(convId, isItemView)}
        </div>
        %endif
      </div>
    </div>
  </div>
</%def>


<%def name="conv_owner(ownerId)">
  <% avatarURI = utils.userAvatar(ownerId, entities[ownerId]) %>
  %if avatarURI:
    <img src="${avatarURI}" style="max-height: 48px; max-width: 48px;"/>
  %endif
</%def>


<%def name="conv_attachments(convId, attachments, style_class='')">
  <%
    hits = {}
    if highlight and convId in highlight and 'attachment' in highlight[convId]:
      for x in highlight[convId]['attachment']:
        fileId, name = x.split(':', 1)
        hits[fileId] = name
  %>
  <div class="attachment-list ${style_class}">
    <%
        attachments_with_screenshot = []
        attachments_plain = []
        for fileId in attachments:
          name, size, ftype = attachments[fileId].split(':')
          name = hits[fileId] if fileId in hits else urlsafe_b64decode(name)
          size = formatFileSize(int(size))
          location = '/files?id=%s&fid=%s'%(convId, fileId)
          if ftype.startswith("image/"):
              attachments_with_screenshot.append((name, size, location, fileId))
          else:
              attachments_plain.append((name, size, location, fileId))
    %>
    %for attachment in attachments_plain:
      <div class="attachment-item">
        <span class="icon attach-file-icon"></span>
        <span class="attachment-name"><a href="${attachment[2]}" target="filedownload">${attachment[0]}</a></span>
        <span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;${attachment[1]}</span>
      </div>
    %endfor
    <div class="screenshots-holder">
      %for attachment in attachments_with_screenshot:
        <div class="attachment-item attachment-item-screenshot">
          <a class="attachment-item-link" href="${attachment[2]}" target="filedownload">
            <img class="attachment-item-img" id="${attachment[3]}" src="${attachment[2]}" style=""/>
          </a>
          <span class="attachment-item-name" style=""><a href="${attachment[2]}" target="filedownload">${attachment[0]}</a></span>
        </div>
      %endfor
    </div>
  </div>
</%def>


<%def name="conv_root(convId, isQuoted=False)">
  <% itemType = items[convId]["meta"]["type"] %>
  %if itemType in plugins:
    ${plugins[itemType].rootHTML(convId, isQuoted, context.kwargs)}
  %endif
  <%
    attachments = items[convId].get("attachments", {})
    if len(attachments.keys()) > 0:
      self.conv_attachments(convId, attachments)
  %>
</%def>


<%def name="conv_footer(convId, hasComments=True, hasLikes=True, hasTags=True)">
  <%
    meta = items[convId]['meta']
    convType = meta.get('type', 'status')
    timestamp = int(meta['timestamp'])
    likesCount = 0 if hasLikes else int(meta.get('likesCount', '0'))
    commentsCount = 0 if hasComments else int(meta.get('responseCount', '0'))
    myTimezone = me.basic.get("timezone", None)
  %>
  ${utils.simpleTimestamp(timestamp, myTimezone)}\
  ## If none of my subscriptions liked it, show the count of likes (onclick show the likes)
  %if (not hasLikes and likesCount) or (not hasComments and commentsCount):
    &#183;
  %endif
  %if not hasLikes and likesCount > 0:
    <button class="button-link" title="${likesCount} Likes" onclick="$$.convs.showItemLikes('${convId}')"><div class="small-icon small-like"></div>${likesCount}</button>
  %endif
  ## Number of comments when none of my subscriptions commented on it
  %if not hasComments and commentsCount > 0:
    <button class="button-link ajax" title="${commentsCount} Comments" href="/item?id=${convId}" data-ref="/item/responses?id=${convId}"><div class="small-icon small-comment"></div>${commentsCount}</button>
  %endif
  &#183;
  ## Like this conversation
  %if myLikes and myLikes.has_key(convId) and len(myLikes[convId]):
    <button class="button-link ajaxpost" data-ref="/item/unlike?id=${convId}">${_("Unlike")}</button>&#183;<button
  %else:
    <button class="button-link ajaxpost" data-ref="/item/like?id=${convId}">${_("Like")}</button>&#183;<button
  %endif
  ## Comment on this conversation
  <% commentString = "Answer" if convType == "question" else "Comment" %>
  class="button-link" onclick="$$.convs.comment('${convId}');" >${_(commentString)}</button>&#183;<button
  ## Add a tag
  class="button-link" title="${_('Add Tag')}" onclick="$$.convs.editTags('${convId}', true);">${_("Add Tag")}</button>
  %if convType != "activity":
    %if "reportId" in meta:
      &#183;<a class="button-link report-link ajax" title="${_('View Report')}" href="/item/report?id=${convId}">${_("View Report")}</a>
    %endif
  %endif
</%def>


<%def name="item_footer(itemId)">
  <%
    meta = items[itemId]['meta']
    timestamp = int(meta['timestamp'])
    likesCount = int(meta.get('likesCount', "0"))
    myTimezone = me.basic.get("timezone", None)
  %>
  ${utils.simpleTimestamp(timestamp, myTimezone)}
  %if likesCount > 0:
    &#183;
    <button class="button-link" title="${likesCount} Likes" onclick="$$.convs.showItemLikes('${itemId}')"><div class="small-icon small-like"></div>${likesCount}</button>
  %endif
  &#183;
  %if myLikes and myLikes.has_key(itemId) and len(myLikes[itemId]):
    <button class="button-link ajaxpost" data-ref="/item/unlike?id=${itemId}">${_("Unlike")}</button>
  %else:
    <button class="button-link ajaxpost" data-ref="/item/like?id=${itemId}">${_("Like")}</button>
  %endif
</%def>


<%def name="conv_likes(convId, count=0, iLike=False, users=None)">
  <%
    if not count:
      return ''

    likeStr = None
    template = None
    other = count

    def linkifyLikes(txt):
      return '<a class="ajax" onclick="$$.convs.showItemLikes(\'%s\')">%s</a>' % (convId, txt)

    if iLike:
      try:
        users.remove(myId)
      except: pass
      other -= (1 + len(users[:2]))
      if other <= 0:
        template = ["You like this",
                    "You and %s like this",
                    "You, %s and %s like this"][len(users[:2])]
      else:
        template = ["You and %s like this",
                    "You, %s and %s like this",
                    "You, %s, %s and %s like this"][len(users[:2])]
    else:
      other -= len(users[:2])
      if other == 0 and len(users) > 0:
        template = ["",
                    "%s likes this",
                    "%s and %s like this"][len(users[:2])]
      if other >=1:
        template = ["%s likes this",
                    "%s and %s like this",
                    "%s, %s and %s like this"][len(users[:2])]

    if template:
      vals = [utils.userName(id, entities[id]) for id in users[:2]]
      if other == 1:
        if len(users) == 0 and not iLike:
          vals.append(linkifyLikes(_("1 person")))
        else:
          vals.append(linkifyLikes(_("1 other person")))
      elif other > 1:
        if len(users) == 0:
          vals.append(linkifyLikes(_("%s people")%other))
        else:
          vals.append(linkifyLikes(_("%s other people")%other))

      likeStr = _(template) % tuple(vals)

    if not likeStr:
      return ''
  %>
  <div class="conv-likes">
    ${likeStr}
  </div>
</%def>


<%def name="conv_comments_head(convId, total, showing, isItemView)">
  <% commentString = "answers" if items[convId]['meta']['type'] == "question" else "comments" %>
  %if total > showing:
    <div class="conv-comments-more" class="busy-indicator">
      %if not isItemView:
        <a class="ajax" href="/item?id=${convId}" data-ref="/item/responses?id=${convId}">${_("View all %s %s &#187;") % (total, commentString)}</a>
      %else:
        <span class="num-comments">${_("%s of %s") % (showing, total)}</span>
        %if oldest:
          <a class="ajax" href="/item?id=${convId}&start=${oldest}" data-ref="/item/responses?id=${convId}&nc=${showing}&start=${oldest}">${_("View older %s &#187;"%(commentString))}</a>
        %else:
          <a class="ajax" href="/item?id=${convId}" data-ref="/item/responses?id=${convId}&nc=${showing}">${_("View older %s &#187;"%(commentString))}</a>
        %endif
      %endif
    </div>
  %endif
</%def>


<%def name="conv_comments_only(convId)">
  <% responsesToShow = responses.get(convId, []) if responses else [] %>
  %for responseId in responsesToShow:
    ${self.conv_comment(convId, responseId)}
  %endfor
</%def>


<%def name="conv_comments(convId, isItemView=False)">
  <%
    responseCount = int(items[convId]["meta"].get("responseCount", "0"))
    responsesToShow = responses.get(convId, []) if responses else []
  %>
  <div id="comments-header-${convId}">
    %if responsesToShow:
      ${self.conv_comments_head(convId, responseCount, len(responsesToShow), isItemView)}
    %endif
  </div>
  <div id="comments-${convId}">
    %for responseId in responsesToShow:
      ${self.conv_comment(convId, responseId)}
    %endfor
  </div>
</%def>


<%def name="conv_comment_form(convId, isItemView)">
  <form method="post" action="/item/comment" class="ajax" autocomplete="off" id="comment-form-${convId}">
    <div class="input-wrap">
      <textarea class="comment-input" data-convId="${convId}" name="comment" placeholder="${_('Leave a response...')}" required title="${_('Comment')}"></textarea>
    </div>
    <input type="hidden" name="parent" value=${convId}></input>
    <% nc = len(responses.get(convId, [])) if responses else 0 %>
    <input type="hidden" name="nc" value=${nc}></input>
    %if isItemView and oldest:
      %if oldest:
        <input type="hidden" name="start" value=${oldest}></input>
      %endif
    %endif
    <div id="comment-attach-${convId}-uploaded" class="uploaded-filelist"></div>
  </form>
  <div class="file-attach-wrapper">
    ${widgets.fileUploadButton('comment-attach-%s'%(convId))}
  </div>
  <div class="clear"></div>
</%def>


<%def name="conv_comment(convId, commentId)">
  <%
    meta = items.get(commentId, {}).get("meta", {})
    if not meta:
        return ''

    userId = meta["owner"]
    comment = meta["comment"]
    snippet = meta.get('snippet', None)
    richText = meta.get('richText', 'False') == 'True'
    normalize = utils.normalizeText
  %>
  <div class="conv-comment" id="comment-${commentId}">
    <a name="${commentId}"> </a>
    <div class="comment-avatar">
      <% avatarURI = utils.userAvatar(userId, entities[userId], "small") %>
      %if avatarURI:
        <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
      %endif
    </div>
    <div class="comment-container">
      <span class="conv-other-actions" onclick="$.post('/ajax/item/delete', {id:'${commentId}'});">&nbsp;</span>
      <span class="comment-user">${utils.userName(userId, entities[userId])}</span>
      ${_renderText(snippet, comment, _('Expand this comment &#187;'), _('Collapse this comment'), richText)}
    </div>
    <%
      attachments = items.get(commentId, {}).get("attachments", {})
      if attachments:
        self.conv_attachments(commentId, attachments, 'comment-container')
    %>
    <div class="comment-meta" id = "item-footer-${commentId}">
      ${self.item_footer(commentId)}
    </div>
  </div>
</%def>


<%def name="conv_tag(convId, tagId, tagName)">
  <span class="tag" tag-id="${tagId}">
    <a class="ajax" href="/tags?id=${tagId}">${tagName}</a>
    <form class="ajax delete-tags" method="post" action="/item/untag">
      <input type="hidden" name="id" value="${convId}"/>
      <input type="hidden" name="tag" value="${tagId}"/>
      <button type="submit" class="button-link">x</button>
    </form>
  </span>
</%def>


<%def name="conv_tags(convId)">
  <% itemTags = items[convId].get("tags", {}) %>
  <div class="conv-tags">
    <button class="button-link edit-tags-button" title="${_('Edit tags')}" onclick="$$.convs.editTags('${convId}');"><span class="icon edit-tags-icon"></span>${_("Edit Tags")}</button>
    <span id="conv-tags-${convId}">
    %for tagId in itemTags.keys():
      <span class="tag" tag-id="${tagId}">
        <a class="ajax" href="/tags?id=${tagId}">${tags[tagId]["title"]}</a>
        <form class="ajax delete-tags" method="post" action="/item/untag">
          <input type="hidden" name="id" value="${convId}"/>
          <input type="hidden" name="tag" value="${tagId}"/>
          <button type="submit" class="button-link">x</button>
        </form>
      </span>
    %endfor
    </span>
    <form method="post" action="/item/tag" class="ajax edit-tags-form" autocomplete="off" id="addtag-form-${convId}">
      <div class="input-wrap">
        <input type="text" class="conv-tags-input" name="tag" value="" placeholder="${_('Add tag')}" required title="Tag"></input>
      </div>
      <input type="hidden" name="id" value=${convId}></input>
    </form>
    <button class="button-link done-tags-button" title="${_('Done editing tags')}" onclick="$$.convs.doneTags('${convId}');"><span class="icon done-tags-icon"></span>${_("Done")}</button>
    <span class="clear"></span>
  </div>
</%def>


<%def name="item_me()">
</%def>


<%def name="item_meta()">
</%def>


<%def name="item_subactions()">
</%def>

<%def name="_renderText(snippet, text, expandStr=None, collapseStr=None, richText=False)">
  <%
    normalize = utils.normalizeText
    snippet = normalize(snippet, richText)
    text = normalize(text, richText)
  %>
  %if snippet:
    <span class="text-preview">${snippet}</span>
    <span class="text-full" style="display:none;">${text}</span>
    &nbsp;&nbsp;
    <button class="text-expander" onclick="$$.convs.expandText(event);">${expandStr or _('Expand this post &#187;')}</button>
    <button class="text-collapser" style="display:none;" onclick="$$.convs.collapseText(event);">${collapseStr or _('Collapse this post')}</button>
  %else:
    <span class="text-full">${text}</span>
  %endif
</%def>

<%def name="render_status(convId, isQuoted=False)">
  <%
    conv = items[convId]
    meta = conv["meta"]
    convType = meta["type"]
    userId = meta["owner"]
    has_icon = "has-icon" if convType in ["question"] else ''
    itemTitleText = "item-title-text" if has_icon else ''
    target = meta.get('target', '')
    target = target.split(',') if target else ''
    richText = meta.get('richText', 'False') == 'True'
    if target:
      target = [x for x in target if x in relations.groups]
  %>
  %if not isQuoted:
    %if not target:
      ${utils.userName(userId, entities[userId], "conv-user-cause")}
    %else:
      ${utils.userName(userId, entities[userId], "conv-user-cause")}<span class="conv-target">&#9656;</span>${utils.groupName(target[0], entities[target[0]])}
    %endif
  %endif
  <div class="item-title ${has_icon}">
    %if has_icon:
      <span class="icon item-icon ${convType}-icon"></span>
    %endif

    <div class="${itemTitleText}">
      %if isQuoted and not has_icon:
        ${utils.userName(userId, entities[userId])}
      %endif
      <%
        matches = highlight.get(convId, None) if highlight else None
        comment = matches['comment'][0] if matches and 'comment' in matches else meta.get('comment', '')
        snippet = matches['snippet'][0] if matches and 'snippet' in matches else meta.get('snippet', '')
      %>
      ${_renderText(snippet, comment, richText=richText)}
    </div>
  </div>
</%def>


<%def name="feedback_icon(type)">
  <div class="feedback-mood-icon ${type}-icon"></div>
</%def>


<%def name="render_feedback(convId, isQuoted=False)">
  <%
    conv = items[convId]
    meta = conv["meta"]
    mood = meta["subType"]
    user = entities[meta['userId']]
    userOrg = entities[meta['userOrgId']]
  %>
  %if not isQuoted:
    <span class="conv-user-cause" style="color:#3366CC">
      ${", ".join([user.basic["name"], user.basic.get('jobTitle', None)])}
    </span>
    (${userOrg.basic["name"]})
  %endif
  <div class="item-title">
    <div>
      %if isQuoted:
        <span class="conv-user-cause" style="color:#3366CC">
          ${", ".join([user.basic["name"], user.basic.get('jobTitle', None)])}
        </span>
        (${userOrg.basic["name"]})<br/>
      %endif
      <%
        comment = meta.get('comment', '')
        snippet = meta.get('snippet', '')
      %>
      ${_renderText(snippet, comment)}
    </div>
  </div>
</%def>


<%def name="render_link(convId, isQuoted=False)">
  <%
    conv = items[convId]
    convType = conv["meta"]["type"]
    userId = conv["meta"]["owner"]

    meta = conv["meta"]
    if highlight and convId in highlight:
      match = highlight[convId]
      url = match["link_url"][0] if 'link_url' in match else meta.get("link_url", '')
      title = match["link_title"][0] if 'link_title' in match else meta.get("link_title", '')
      summary = match["link_summary"][0] if 'link_summary' in match else meta.get("link_summary", '')
    else:
      url = meta.get("link_url", '')
      title = meta.get("link_title", '')
      summary = meta.get("link_summary", '')

    imgsrc = meta.get("link_imgSrc", '')
    richText = meta.get('richText', 'False') == 'True'

    hasEmbed = False
    embedType = meta.get("link_embedType", '')
    embedSrc = meta.get("link_embedSrc", '')
    embedWidth = meta.get("link_embedWidth", '')
    embedHeight = meta.get("link_embedHeight", '')
    if embedType and embedSrc and embedWidth and embedHeight:
        hasEmbed = True

    title = title if title else url
    if imgsrc and secureProxy:
        imgsrc = secureProxy % b64encode(imgsrc)
    target = items[convId]["meta"].get('target', '')
    target = target.split(',') if target else ''
    if target:
      target = [x for x in target if x in relations.groups]
  %>
  %if not isQuoted:
    %if not target:
      ${utils.userName(userId, entities[userId], "conv-user-cause")}
    %else:
      ${utils.userName(userId, entities[userId], "conv-user-cause")}<span class="conv-target">&#9656;</span>${utils.groupName(target[0], entities[target[0]])}
    %endif
  %endif
  <div class="item-title has-icon">
    <span class="icon item-icon link-icon"></span>
    <div class="item-title-text">
      <%
        matches = highlight.get(convId, None) if highlight else None
        comment = matches['comment'][0] if matches and 'comment' in matches else meta.get('comment', '')
        snippet = matches['snippet'][0] if matches and 'snippet' in matches else meta.get('snippet', '')
      %>
      ${_renderText(snippet, comment, richText=richText)}
      <div class="link-item">
        %if imgsrc and hasEmbed:
          <div onclick="$$.convs.embed('${convId}');" class="embed-wrapper">
            <div class="embed-overlay embed-${embedType}"></div>
            <img src='${imgsrc}' class="link-image has-embed embed-${embedType}"/>
          </div>
          <div class="embed-frame-wrapper" id="embed-frame-${convId}"
               style="width:${embedWidth}px;height:${embedHeight}px;display:none;"/>
        %elif imgsrc:
          <img src='${imgsrc}' class="link-image"/>
        %endif
        <div class="link-details">
          <a href=${url} target="_blank"><div class="link-title">${title}</div></a>
          %if summary:
            <div id="summary" class="link-summary">${summary}</div>
          %endif
          %if title != url:
            <% domain = urlsplit(url)[1] %>
            <div id="url" class="link-url">${domain}</div>
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="render_activity(convId, isQuoted=False)">
  <%
    conv = items[convId]
    userId = conv["meta"]["owner"]
    subtype = conv["meta"]["subType"]
    target = conv["meta"]["target"]
    fmtUser = utils.userName
    fmtGroup = utils.groupName
    activity = None
    if subtype == "following":
      activity = _("%s started following %s.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
    elif subtype == "groupJoin":
      activity = _("%s joined %s.") % (fmtUser(userId, entities[userId]), fmtGroup(target, entities[target]))
    elif subtype == "groupLeave":
      activity = _("%s left %s.") % (fmtUser(userId, entities[userId]), fmtGroup(target, entities[target]))
    elif subtype == "groupAdmin":
      activity = _("%s is now an administrator for %s group.") % (fmtUser(userId, entities[userId]), fmtGroup(target, entities[target]))
  %>
  %if activity:
    ${activity}
  %endif
</%def>


<%def name="userListDialog()">
  <%
    userName = utils.userName
    userAvatar = utils.userAvatar
  %>
  <div class="ui-dlg-title">${title}</div>
  <div class="ui-list ui-dlg-center">
    %for uid in users:
      <%
        userMeta = entities[uid]
        jobTitle = userMeta.basic.get("jobTitle", "")
      %>
      <div class="ui-listitem">
        <div class="ui-list-icon"><img src="${userAvatar(uid, userMeta, 'small')}"/></div>
        <div class="ui-list-title">${userName(uid, userMeta)}</div>
        <div class="ui-list-meta">${jobTitle}</div>
      </div>
    %endfor
  </div>
</%def>


<%def name="feedbackDialog()">
  <div id="ui-feedback-dlg">
    <div class='ui-dlg-title' id='feedback-dlg-title'>${_("flocked.in made me happy!")}</div>
    <div class='ui-dlg-center' id='feedback-center'>
      <div id="feedback-mood-wrapper">
        <div id="feedback-mood-inner">
          <div id="feedback-happy" class="feedback-mood feedback-mood-selected" onclick="$$.feedback.mood('happy');">
            <div class="feedback-mood-icon happy-icon"></div>
            ${_("Made me Happy")}
          </div>
          <div id="feedback-sad" class="feedback-mood" onclick="$$.feedback.mood('sad');">
            <div class="feedback-mood-icon sad-icon"></div>
            ${_("Made me Sad")}
          </div>
          <div id="feedback-idea" class="feedback-mood" onclick="$$.feedback.mood('idea');">
            <div class="feedback-mood-icon idea-icon"></div>
            ${_("I have an Idea")}
          </div>
          <div style="clear:both;"></div>
        </div>
      </div>
      <div id="feedback-desc-page">
        <div>
          <label id="feedback-type">${_('Please describe what you liked')}</label>
          <textarea rows="2" id="feedback-desc"></textarea>
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="_item_other_actions(convId, iamOwner, convType)">
  %if convType not in ["activity"]:
    <span class="conv-other-actions" onclick="$$.ui.showPopup(event, true);"></span>
    <ul class="acl-menu" style="display:none;">
        %if iamOwner:
          <li><a class="menu-item noicon" onclick="$.post('/ajax/item/delete', {id:'${convId}'});">${_("Delete")}</a></li>
        %else:
          <li><a class="menu-item noicon" onclick="$.post('/ajax/item/remove', {id:'${convId}'});">${_("Hide from my Feed")}</a></li>
##          <li><a class="menu-item noicon" onclick="$$.convs.showItemReportDialog('${convId}')">${_("Report this %s" %convType)}</a></li>
        %endif
    </ul>
  %endif
</%def>


<%def name="requireReviewDlg()">
  <div class="ui-dlg-title">Confirm Administrator Notification</div>
  <div class="ui-dlg-center" style="padding:20px;font-size: 14px;">
    %if convId:
      %if len(keywords) == 1:
        <p>Your comment will be shared with the administrator as it includes a
        flagged word (<span class="socschl">${keywords[0]}</span>)<br/><br/>
        You may edit your comment or continue to post it.</p>
      %else:
        <p>Your comment will be shared with the administrator as it includes
        flagged words (${', '.join(['<span class="socschl">%s</span>'%x for x in keywords])})<br/><br/>
        You may edit your comment or continue to post it.</p>
      %endif
    %else:
      %if len(keywords) == 1:
        <p>Your post will be shared with the administrator as it includes a
        flagged word (<span class="socschl">${keywords[0]}</span>)<br/><br/>
        You may edit your post or continue to share it.</p>
      %else:
        <p>Your post will be shared with the administrator as it includes
        flagged words (${', '.join(['<span class="socschl">%s</span>'%x for x in keywords])})<br/><br/>
        You may edit your post or continue to share it.</p>
      %endif
    %endif
  </div>
</%def>
