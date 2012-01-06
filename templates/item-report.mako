<%! from social import utils, _, __, plugins, constants, config, secureProxy %>
<%! from twisted.web.static import formatFileSize %>
<%! from base64 import b64encode, urlsafe_b64decode %>
<%! from urlparse import urlsplit %>

<!DOCTYPE HTML>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%inherit file="base.mako"/>


<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right"></div>
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
  <div id="conv-${convId}" class="conv-item">
    <div class="conv-avatar" id="conv-avatar-${convId}"></div>
    <div class="conv-data">
      <div id="conv-root-${convId}">
        <div class="conv-summary"></div>
        <div id="item-footer-${convId}" class="conv-footer busy-indicator"></div>
      </div>
      <div id="report-contents" class="conv-meta-wrapper"></div>
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
        ${item.conv_owner(reasonUserId)}
      %else:
        ${item.feedback_icon(convMeta['subType'])}
      %endif
    </div>
    <div class="conv-data">
      <%
        hasReason = reasonStr and reasonStr.has_key(convId)
        hasKnownComments = responses and len(responses.get(convId, {}))
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
        %if hasReason:
          <span class="conv-reason">${reasonStr[convId]}</span>
          <div class="conv-summary conv-quote">
        %else:
          <div class="conv-summary">
        %endif
          ${item.conv_root(convId, hasReason)}
          <div id="item-footer-${convId}" class="conv-footer busy-indicator">
            <% self.conv_footer(convId) %>
          </div>
        </div>
      </div>
      <div id="conv-meta-wrapper-${convId}" class="conv-meta-wrapper${' no-comments' if not hasKnownComments else ''}${' no-tags' if not hasTags else ''}${' no-likes' if not hasKnownLikes else ''}">
        <% item_report() %>
      </div>
    </div>
  </div>
</%def>


<%def name="conv_footer(convId)">
  <%
    meta = items[convId]['meta']
    timestamp = int(meta['timestamp'])
    myTimezone = me['basic'].get("timezone", None)
  %>
  ${utils.simpleTimestamp(timestamp, myTimezone)}
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


<%def name="report_dialog()">
  <div class="ui-dlg-title">${title}</div>
  <div class="ui-dlg-center" style="padding:10px">
    <label id="feedback-type">${_('Reason for reporting this item')}</label>
    <textarea name="comment" id="conv-report-comment" placeholder="Enter a reason for reporting this item" required></textarea>
    <input type="hidden" name="id" value="${convId}" id="conv-report-id"></input>
    <input type="hidden" name="action" value="report" id="conv-report-action"></input>
  </div>
</%def>


<%def name="item_report()">
  <div id="conv-report" class="conv-item">
    ${report_status()}
    <%
      reportedBy = None
      if "reportId" in convMeta:
        if convMeta["reportStatus"] != "ok":
          reportedBy = convMeta["reportedBy"]
    %>
    <div>
      <div id="conv-meta-wrapper" class="conv-meta-wrapper no-tags">
        <div id="report-comments">
          %if not script:
            <% report_comments() %>
          %endif
        </div>
      </div>
    </div>
    %if myId != ownerId:
      ${self.report_comment_form(reportedBy)}
    %elif reportedBy is not None:
        ${self.report_comment_form(reportedBy)}
    %endif
  </div>
</%def>

<%def name="report_comment_form(reportedBy)">
  <div class="comment-form-wrapper busy-indicator" id="report-form-wrapper" >
    <form method="post" class="ajax" autocomplete="off" id="report-form">
      <div class="conversation-composer">
        <div class="comment-avatar">
          <% avatarURI = utils.userAvatar(ownerId, entities[ownerId], "small") %>
          %if avatarURI:
            <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
          %endif
        </div>
        <div class="comment-container">
          <div class="input-wrap">
            <input type="hidden" name="id" value="${convId}"></input>
            <textarea id="report-comment" title="Add comment" name="comment"
                      placeholder="${_('Add comment to this report')}" required
                      style="resize: none; overflow: auto; height: 60px;"></textarea>
          </div>
          <div class="conversation-reply-actions">
            %if "reportId" in convMeta:
              ${self.item_report_actions(reportedBy)}
            %endif
          </div>
        </div>
        <div class="clear"></div>
      </div>
    </form>
  </div>
</%def>


<%def name="item_report_actions(reportedBy)">
  <ul class="middle user-actions h-links" id="report-actions">
    %if myId != ownerId :
      %if reportedBy:
        %if convMeta["reportStatus"] == "repost":
          <input type="submit" onclick="$('#report-form').attr('action', '/item/report/reject')"
                 class="button default" value="Post Comment"/>
        %elif convMeta["reportStatus"] == "pending":
          <input type="submit" onclick="$('#report-form').attr('action', '/item/report/report')"
                 class="button default" value="Post Comment"/>
        %endif
        %if convMeta["reportStatus"] != "accept":
          <input type="submit" onclick="$('#report-form').attr('action', '/item/report/repost')"
                 class="button" value="Unflag and Publish"/>
        %endif
      %else:
        <input type="submit" onclick="$('#report-form').attr('action', '/item/report/report')"
               class="button default" value="Flag for Review"/>
      %endif
    %else:
      %if reportedBy and convMeta["reportStatus"] in ["pending", "repost"]:
        <input type="submit" onclick="$('#report-form').attr('action', '/item/report/repost')"
                class="button default" type="submit" value="Request to Publish"/>
      %endif
      <input type="submit" onclick="$('#report-form').attr('action', '/item/report/accept')"
             class="button" value="Hide Permanently"/>
    %endif
  </ul>
</%def>

<%def name="report_comments()">
  %for responseKey in responseKeys:
    <%
      userId = reportItems[responseKey]['meta']['owner']
      comment = reportItems[responseKey]['meta']['comment']
      snippet = None
      timestamp = int(reportItems[responseKey]['meta']['timestamp'])
      myTimezone = me['basic'].get("timezone", None)
    %>
    <div class="conv-comment">
      <div class="comment-avatar">
        <% avatarURI = utils.userAvatar(userId, entities[userId], "small") %>
        %if avatarURI:
          <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
        %endif
      </div>
      <div class="comment-container">
        <span class="comment-user">${utils.userName(userId, entities[userId])}</span>
        ${_renderText(snippet, comment, _('Expand this comment &#187;'), _('Collapse this comment'), richText)}
      </div>
      <div class="comment-meta">
        ${report_meta_status(userId, reportResponseActions[responseKey])}
        &#183;
        ${utils.simpleTimestamp(timestamp, myTimezone)}
      </div>
    </div>
  %endfor
</%def>

<%def name="report_meta_status(userId, action)">
  <%
    if userId == convMeta["reportedBy"]:
      if action == "report":
        status = "Item reported"
      elif action == "reject":
        status = "Request to publish rejected"
      elif action == "repost":
        status = "Item published"
    else:
      if action == "repost":
        status = "Request to publish submitted"
      elif action == "accept":
        status = "Item permanently hidden"
  %>
  <span>${status}</span>
</%def>

<%def name="report_status()">
  <div id="report-status">
    ## reportStatus can be ["pending", "accept", "repost"]
    ##   pending is pending action from owner
    ##   accept is permanently hidden by owner
    ##   repost is when owner replies back with a reason to repost the item
    <%
      if myId == ownerId:
        if "reportId" not in convMeta:
          status = "Your item is currently not flagged for review."
        else:
          item_status = convMeta["reportStatus"]
          reported_by = utils.userName(convMeta["reportedBy"],
                                       entities[convMeta["reportedBy"]])
          if item_status == "pending":
            status = "This item was flagged for review by %s. \
                      Please perform a suitable action below" \
                      %reported_by
          elif item_status == "repost":
            status = "Your request to repost this item was sent to %s.\
                      The item will be reposted when %s accepts your reason" \
                      %(reported_by, reported_by)
          elif item_status == "accept":
            status = "This item is hidden because it was flagged for\
                      review and you chose to hide it permanently."
      else:
        if "reportId" not in convMeta:
          status = "This item is currently not flagged for review.\
                    You can report the content using the form below."
        else:
          item_status = convMeta["reportStatus"]
          owned_by = utils.userName(ownerId, entities[ownerId])
          if item_status == "pending":
            status = "This item was flagged for review\
                      and is pending action from %s." %owned_by
          elif item_status == "repost":
            status = "%s requested that you reconsider your report. \
                      You may choose to unflag the item or keep it hidden" %owned_by
          elif item_status == "accept":
            status = "This post was permanently hidden by %s." %owned_by
    %>
    <span>${status}</span>
  </div>
</%def>
