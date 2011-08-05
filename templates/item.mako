<%! from social import utils, _, __, plugins, constants %>
<%! from twisted.python import log %>
<%! from twisted.web.static import formatFileSize %>
<%! from base64 import urlsafe_b64decode %>
<%! from urlparse import urlsplit %>
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
  <div id="conv-${convId}" class="conv-item ${classes}">
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
        hasComments = responses and len(responses.get(convId, {}))
        hasLikes = likes and len(likes.get(convId, {}))
        hasTags = items and items[convId].get("tags", {})
        convType = convMeta["type"]
        convOwner = convMeta["owner"]
      %>
      <div id="conv-root-${convId}" class="conv-root">
        ${self._item_other_actions(convId, convOwner==myKey, convType)}
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
              self.conv_likes(convId, count, iLike, likes.get(convId, []) if likes else [])
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
  <% attachments = items[convId].get("attachments", {}) %>
  %if len(attachments.keys()) > 0:
    <table>
    %for attachmentId in attachments:
      <%
          tuuid, name, size, ftype = attachments[attachmentId].split(':')
          name =urlsafe_b64decode(name)
          size = formatFileSize(int(size))
          location = '/file?id=%s&fid=%s&ver=%s'%(convId, attachmentId, tuuid)
      %>
      <tr>
        <td><a href="${location}" target="filedownload">${name|h}</a></td>
        %if size:
          <td>${size}</td>
        %endif
       <!--<td><a onclick="$$.ui.showFileVersions('${convId}' , '${attachmentId}')">versions</a></td>-->
      </tr>
      ##<form id="${convId}-file-form" method="post" action = "/file/new_version" enctype="multipart/form-data" >
      ##    <input type="file" name="file" />
      ##    <input type="hidden" name="id" value="${convId}" />
      ##    <input type="hidden" name="fid" value="${attachmentId}" />
      ##    <input type="submit" name="upload" value="upload" />
      ##</form>
    %endfor
    </table>
  %endif
</%def>


<%def name="conv_footer(convId, hasComments=True, hasLikes=True, hasTags=True)">
  <%
    meta = items[convId]['meta']
    convType = meta.get('type', 'status')
    timestamp = int(meta['timestamp'])
    likesCount = 0 if hasLikes else int(meta.get('likesCount', '0'))
    commentsCount = 0 if hasComments else int(meta.get('responseCount', '0'))
    myTimezone = me['basic'].get("timezone", None)
  %>
  ${utils.simpleTimestamp(timestamp, myTimezone)}\
  ## If none of my friends liked it, show the count of likes (onclick show the likes)
  %if (not hasLikes and likesCount) or (not hasComments and commentsCount):
    &#183;
  %endif
  %if not hasLikes and likesCount > 0:
    <button class="button-link" title="${likesCount} Likes" onclick="$$.convs.showItemLikes('${convId}')"><div class="small-icon small-like"></div>${likesCount}</button>
  %endif
  ## Number of comments when none of my friends commented on it
  %if not hasComments and commentsCount > 0:
    <button class="button-link ajax" title="${commentsCount} Comments" href="/item?id=${convId}" _ref="/item/responses?id=${convId}"><div class="small-icon small-comment"></div>${commentsCount}</button>
  %endif
  &#183;
  ## Like this conversation
  %if myKey == meta["owner"]:
    <button class="button-link disabled">${_("Like")}</button>&#183;<button 
  %elif myLikes and myLikes.has_key(convId) and len(myLikes[convId]):
    <button class="button-link ajaxpost" _ref="/item/unlike?id=${convId}">${_("Unlike")}</button>&#183;<button 
  %else:
    <button class="button-link ajaxpost" _ref="/item/like?id=${convId}">${_("Like")}</button>&#183;<button
  %endif
  ## Comment on this conversation
  <% commentString = "Answer" if convType == "question" else "Comment" %>
  class="button-link" onclick="$$.convs.comment('${convId}');" >${_(commentString)}</button>&#183;<button
  ## Add a tag
  class="button-link" title="${_('Add Tag')}" onclick="$$.convs.editTags('${convId}', true);">${_("Add Tag")}</button>
</%def>


<%def name="item_footer(itemId)">
  <%
    meta = items[itemId]['meta']
    timestamp = int(meta['timestamp'])
    likesCount = int(meta.get('likesCount', "0"))
    myTimezone = me['basic'].get("timezone", None)
  %>
  ${utils.simpleTimestamp(timestamp, myTimezone)}
  %if likesCount > 0:
    &#183;
    <button class="button-link" title="${likesCount} Likes" onclick="$$.convs.showItemLikes('${itemId}')"><div class="small-icon small-like"></div>${likesCount}</button>
  %endif
  &#183;
  %if myKey == meta["owner"]:
    <button class="button-link disabled">${_("Like")}</button>&#183;
  %elif myLikes and myLikes.has_key(itemId) and len(myLikes[itemId]):
    <button class="button-link ajaxpost" _ref="/item/unlike?id=${itemId}">${_("Unlike")}</button>
  %else:
    <button class="button-link ajaxpost" _ref="/item/like?id=${itemId}">${_("Like")}</button>
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
        users.remove(myKey)
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


<%def name="conv_comments_head(convId, total, showing, isFeed)">
  <% commentString = "answers" if items[convId]['meta']['type'] == "question" else "comments" %>
  %if total > showing:
    <div class="conv-comments-more" class="busy-indicator">
      %if isFeed:
        <a class="ajax" href="/item?id=${convId}" _ref="/item/responses?id=${convId}">${_("View all %s %s &#187;") % (total, commentString)}</a>
      %else:
        <span class="num-comments">${_("%s of %s") % (showing, total)}</span>
        %if oldest:
          <a class="ajax" href="/item?id=${convId}&start=${oldest}" _ref="/item/responses?id=${convId}&nc=${showing}&start=${oldest}">${_("View older %s &#187;"%(commentString))}</a>
        %else:
          <a class="ajax" href="/item?id=${convId}" _ref="/item/responses?id=${convId}&nc=${showing}">${_("View older %s &#187;"%(commentString))}</a>
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
    %if responsesToShow:
      ${self.conv_comments_head(convId, responseCount, len(responsesToShow), isFeed)}
    %endif
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
    if not items.get(commentId, {}).get("meta", {}):
        return ''

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
      <span class="conv-other-actions" onclick="$.post('/ajax/item/delete', {id:'${commentId}'});">&nbsp;</span>
      <span class="comment-user">${utils.userName(userId, entities[userId])}</span>
      <span class="comment-text">${comment|normalize}</span>
    </div>
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
    <button class="button-link edit-tags-button" title="${_('Edit tags')}" onclick="$$.convs.editTags('${convId}');"><div class="icon edit-tags-icon"></div>Edit Tags</button>
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
    convType = conv["meta"]["type"]
    userId = conv["meta"]["owner"]
    normalize = utils.normalizeText
    has_icon = "has-icon" if convType in ["question"] else ''
    itemTitleText = "item-title-text" if has_icon else ''
  %>
  %if not isQuoted:
    ${utils.userName(userId, entities[userId], "conv-user-cause")}
  %endif
  <div class="item-title ${has_icon}">
    %if has_icon:
      <span class="icon item-icon ${convType}-icon"></span>
    %endif

    <div class="${itemTitleText}">
      %if isQuoted and not has_icon:
        ${utils.userName(userId, entities[userId])}
      %endif
      %if conv["meta"].has_key("comment"):
        ${conv["meta"]["comment"]|normalize}
      %endif
    </div>
  </div>
</%def>

##<%def name="render_files(convId, isQuoted=False)">
##  <%
##    conv = items[convId]
##    convType = conv["meta"]["type"]
##    userId = conv["meta"]["owner"]
##    normalize = utils.normalizeText
##    attachments = conv.get("attachments", {})
##
##  %>
##  %if not isQuoted:
##    ${utils.userName(userId, entities[userId], "conv-user-cause")}
##  %endif
##  <div class="item-title">
##    <div class="">
##      %if isQuoted:
##        ${utils.userName(userId, entities[userId])}
##      %endif
##      %if conv["meta"].has_key("comment"):
##        ${conv["meta"]["comment"]|normalize}
##      %endif
##      % for attachmentId in attachments:
##         <%
##            timeuuid, fileId, name, size, filetype = attachments[attachmentId]
##            size = formatFileSize(int(size))
##         %>
##         <div>
##         <a href='/file?id=${convId}&fid=${attachmentId}&ver=${timeuuid}' >${name}</a>
##         % if size:
##            ##(${formatFileSize(size)})
##            (${size})
##         %endif
##         </div>
##      % endfor
##    </div>
##  </div>
##</%def>


<%def name="feedback_icon(type)">
  <div class="feedback-mood-icon ${type}-icon"></div>
</%def>


<%def name="render_feedback(convId, isQuoted=False)">
  <%
    conv = items[convId]
    normalize = utils.normalizeText
    meta = conv["meta"]
    mood = meta["subType"]
    user = entities[meta['userId']]
    userOrg = entities[meta['userOrgId']]
  %>
  %if not isQuoted:
    <span class="conv-user-cause" style="color:#3366CC">
      ${", ".join([user["basic"]["name"], user["basic"].get('jobTitle', None)])}
    </span>
    (${userOrg["basic"]["name"]})
  %endif
  <div class="item-title">
    <div>
      %if isQuoted:
        <span class="conv-user-cause" style="color:#3366CC">
          ${", ".join([user["basic"]["name"], user["basic"].get('jobTitle', None)])}
        </span>
        (${userOrg["basic"]["name"]})<br/>
      %endif
      %if conv["meta"].has_key("comment"):
        ${conv["meta"]["comment"]|normalize}
      %endif
    </div>
  </div>
</%def>


<%def name="render_link(convId, isQuoted=False)">
  <%
    conv = items[convId]
    convType = conv["meta"]["type"]
    userId = conv["meta"]["owner"]
    normalize = utils.normalizeText

    meta = conv["meta"]
    url = meta.get("url", "")
    title = meta.get("title", '')
    imgsrc = meta.get("imgSrc", '')
    summary = meta.get("summary", '')

    hasEmbed = False
    embedType = meta.get("embedType", '')
    embedSrc = meta.get("embedSrc", '')
    embedWidth = meta.get("embedWidth", 0)
    embedHeight = meta.get("embedHeight", 0)
    if embedType and embedSrc and embedWidth and embedHeight:
        hasEmbed = True

    title = title if title else url
  %>
  %if not isQuoted:
    ${utils.userName(userId, entities[userId], "conv-user-cause")}
  %endif
  <div class="item-title has-icon">
    <span class="icon item-icon link-icon"></span>
    <div class="item-title-text">
      %if conv["meta"].has_key("comment"):
        ${conv["meta"]["comment"]|normalize}
      %endif
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
        <a href=${url} target="_blank"><div class="link-title">${_(title)}</div></a>
        <div id="summary" class="link-summary">${_(summary)}</div>
        %if title != url:
          <% domain = urlsplit(url)[1] %>
          <div id="url" class="link-url">${domain}</div>
        %endif
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
    if subtype == "connection":
      activity = _("%s and %s are now friends.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
    elif subtype == "following":
      activity = _("%s started following %s.") % (fmtUser(userId, entities[userId]), fmtUser(target, entities[target]))
    elif subtype == "groupJoin":
      activity = _("%s joined %s.") % (fmtUser(userId, entities[userId]), fmtGroup(target, entities[target]))
    elif subtype == "groupLeave":
      activity = _("%s left %s.") % (fmtUser(userId, entities[userId]), fmtGroup(target, entities[target]))
  %>
  ${activity}
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
        jobTitle = userMeta["basic"].get("jobTitle", "")
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
            Made me Happy
          </div>
          <div id="feedback-sad" class="feedback-mood" onclick="$$.feedback.mood('sad');">
            <div class="feedback-mood-icon sad-icon"></div>
            Made me Sad
          </div>
          <div id="feedback-idea" class="feedback-mood" onclick="$$.feedback.mood('idea');">
            <div class="feedback-mood-icon idea-icon"></div>
            I have an Idea
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

<%def name="set_attachment(itemId, attachmentId, timeuuid, name, size)">
     <% size = formatFileSize(int(size)) %>
      <a href='/file?id=${itemId}&fid=${attachmentId}&ver=${timeuuid}' >${name}</a>
      %if size:
        ${size}
      %endif
</%def>

<%def name="_item_other_actions(convId, iamOwner, convType)">
  %if convType not in ["activity"]:
    <span class="conv-other-actions" onclick="$$.ui.showPopup(event, true);"></span>
    <ul class="acl-menu" style="display:none;">
        %if iamOwner:
          <li><a class="menu-item noicon" onclick="$.post('/ajax/item/delete', {id:'${convId}'});">${_("Delete")}</a></li>
        %else:
          <li><a class="menu-item noicon" onclick="$.post('/ajax/item/remove', {id:'${convId}'});">${_("Remove")}</a></li>
          <li><a class="menu-item noicon" onclick="">${_("Report")}</a></li>
        %endif
    </ul>
  %endif
</%def>
