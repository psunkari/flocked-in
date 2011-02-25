<%! from social import _, __ %>

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
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
        <div id="invite-ppl">
            <form method="post" action="/register" class="ajax">
                <input type="text" name="emailId"/><br/>
                <input type="submit" id="submit" value="${_('Submit')}"/>
            </form>
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <div id="title"><span class="middle title">${_("News Feed")}</span></div>
          </div>
          <div id="share-block">
            %if not script:
              ${self.share_block()}
            %endif
          </div>
        </div>
        <div id="user-feed" class="center-contents">
          %if not script:
            ${self.feed()}
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="acl_button(id)">
  %if script:
    <%widgets:popupButton id="${id}" classes="acl-button" value="${_('Company')}"
                          tooltip="${_('Anyone working at my company')}">
      <input id="${id}-input" type="hidden" name="acl" value="company"/>
      <div class="popup" onclick="acl.updateACL(event, this.parentNode);">
        <ul class="v-links">
          <li type="public" info="${'Everyone'}">${_("Everyone")}</li>
          <li type="company" info="${'Anyone working at my company'}">${_("Company")}</li>
          <li type="friends" info="${'All my friends'}">${_("Friends")}</li>
          <li id="${id}-groups" class="separator"></li>
          <li id="${id}-groups-end" class="separator"></li>
          <li type="custom">${_("Custom")}</li>
        </ul>
      </div>
    </%widgets:popupButton>
  %endif
</%def>

<%def name="share_block()">
  %if script:
    <div id="sharebar-tabs">
      <ul id="sharebar-links" class="h-links">
        <li>${_("Share:")}</li>
        %for name, target in [("Status", "status"), ("Link", "link"), ("Document", "document")]:
          %if target == 'status':
            <li><a _ref="/feed/share/${target}" id="sharebar-link-${target}" class="ajax selected">${_(name)}</a></li>
          %else:
            <li><a _ref="/feed/share/${target}" id="sharebar-link-${target}" class="ajax">${_(name)}</a></li>
          %endif
        %endfor
      </ul>
    </div>
    <form id="share-form" class="ajax" autocomplete="off" method="post">
      <div id="sharebar"></div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          <li>${acl_button("sharebar-acl")}</li>
          <li>${widgets.button("sharebar-submit", "submit", "default", None, "Share")}</li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
  %endif
</%def>

<%def name="share_status()">
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('What are you currently working on?')}"/>
  </div>
  <input type="hidden" name="type" value="status"/>
</%def>

<%def name="share_link()">
  <div class="input-wrap">
    <input type="text" name="url" placeholder="${_('http://')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('Say something about this link')}"/>
  </div>
</%def>

<%def name="share_document()">
  <div class="input-wrap">
    <input type="file" name="file" placeholder="${_('Select the document to share')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="comment" placeholder="${_('Say something about this file')}"/>
  </div>
</%def>

<%def name="feed()">
  %for convId in conversations:
    <%
      comments = feedItems[convId]["comments"]
      rootItem = feedItems[convId]["root"]
      likes = feedItems[convId]["likes"]
      fmtUser = lambda x,y=None: ("<span class='user %s'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (y if y else "", x, users[x]["basic"]["name"]))

      ## Let the user know why this item is in the feed.
      (recentType, recentUserId, recentItemId) = feedItems[convId]["recent"]
      userIds = None
      template = None
      if recentType == "C":
          userIds = set([x[0] for x in comments])
          template = ["%s commented on %s's %s",
                      "%s and %s commented on %s's %s",
                      "%s, %s and %s commented on %s's %s"][len(userIds)-1]
      elif recentType == "L" and itemId == convId:
          userIds = set([x[0] for x in likes])
          template = ["%s liked %s's %s",
                      "%s and %s liked %s's %s",
                      "%s, %s and %s liked %s's %s"][len(userIds)-1]
      elif recentType == "L":
          userIds = set([userId])
          template == ["%s liked a comment on %s's %s"]

      reason = None
      if template:
          args = [fmtUser(id, "conv-user-cause") for id in userIds]
          args.append(fmtUser(rootItem[0]))
          itemType = items[convId]["meta"]["type"]
          args.append("<span class='item'><a class='ajax' href='/%s?id=%s'>%s</a></span>" % (itemType, convId, _(itemType)))
          reason = _(template) % tuple(args)
    %>
    <div id=${"conv-%s" % convId} class="conv-item">
      <div class="conv-avatar"></div>
      <div class="conv-data">
        <div class="conv-root-render">
          %if reason:
            <span class="conv-reason">${reason}</span>
          %endif
          ${self.renderRootItem(convId, reason)}
        </div>
        <div class="conv-meta"></div>
        <div class="conv-comments">
          <%
            if len(comments) < 2 and len(feedItems[convId]["extras"]):
              extras = feedItems[convId]["extras"]
              if len(comments) == 0:
                comments.extend(extras)
              else:
                comments.extend(extras)
                comments.sort(key=lambda x: items[x[1]]["meta"]["timestamp"])
          %>
          %for userId, commentId in comments:
            <div class="conv-comment" id="comment-${commentId}">
              ${self.renderComment(commentId)}
            </div>
          %endfor
          <div class="conv-comment" id="form-${convId}">
            <form method="post" action="/feed/share/status" class="ajax">
              <input type="text" name="comment" value=""></input> 
              <input type="hidden" name="parent" value=${convId}></input>
              <input type="hidden" name="parentUserId" value="${rootItem[0]}"></input>
              <input type="hidden" name="acl" value="${items[convId]['meta']['acl']}"></input>
              ${widgets.button(None, type="submit", name="comment", value="comment")}<br/>
            </form>
          </div>
        </div>
      </div>
      <div class="conv-item-bottom"></div>
    </div>
  %endfor
</%def>

<%def name="renderComment(commentId)">
  <%
    item = items[commentId]
    userId = item["meta"]["owner"]
    comment = item["meta"]["comment"]
    timestamp = item["meta"]["timestamp"]
    fmtUser = lambda x: ("<span class='user comment-author'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (x, users[x]["basic"]["name"]))
  %>
  <div class="comment-avatar"></div>
  <div class="comment-container">
    <span class="comment-user">${fmtUser(userId)}</span>
    <span class="comment-text">${comment}</span>
  </div>
  <div class="comment-meta">
    <span class="timestamp" _ts="${timestamp}">${timestamp}</span>
  </div>
</%def>

<%def name="renderRootItem(convId, reason)">
  <%
    conv = items[convId]
    type = conv["meta"]["type"]
    userId = conv["meta"]["owner"]
    fmtUser = lambda x,y=None: ("<span class='user %s'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (y if y else '', x, users[x]["basic"]["name"]))
  %>
  %if type == "activity":
    <%
      subtype = conv["meta"]["subType"]
      target = conv["data"]["target"]
      if subtype == "connection":
        activity = _("%s and %s are now friends.") % (fmtUser(userId), fmtUser(target))
      elif subtype == "following":
        activity = _("%s started following %s.") % (fmtUser(userId), fmtUser(target))
    %>
    <div class="conv-summary">${activity}</div>
  %elif type in ["status", "link", "document"]:
    %if not reason:
      <span class="conv-reason">
        ${fmtUser(userId, "conv-user-cause")}
      </span>
    %endif
    <div class="conv-summary">
      %if conv["meta"].has_key("comment"):
        ${conv["meta"]["comment"]}
      %endif
    </div>
  %endif
  <span class="timestamp" ts="${conv['meta']['timestamp']}">${conv['meta']['timestamp']}</span>
</%def>

<%def name="feed_()">
% for items in comments:
    <% parentUserKey= items[0][5] %> 
    <% parentItemId = items[0][3] %>
    <% acl = items[0][4] %>
    <div id=${parentItemId}>
        <span>${items[0][2]}</span> 
        % if items[0][6]:
            <span>${items[0][6]}</span> 
        % endif
        % if not items[0][7]:
            <a href="feed/like?itemKey=${parentItemId}&parent=${parentItemId}" class="ajax" >like</a>
        % else:
            <a href="feed/unlike?itemKey=${parentItemId}&parent=${parentItemId}" class="ajax" >unlike</a>
        % endif
        <br/>
        <span>${items[0][0]}</span>
        % if items[0][1]:
            <a href=http://${items[0][1]}>link</a>
        % endif
        <div id=${parentItemId}_comment>
        % for comment, url, user, itemKey, acl, likedBy, unlike in items[1:]:
            <span>${user}</span>
                % if likedBy:
                    <span>${likedBy}</span>
                % endif
                % if not unlike:
                    <a href="feed/like?itemKey=${itemKey}&parent=${parentItemId}" class="ajax" >like</a>
                % else: 
                    <a href="feed/unlike?itemKey=${itemKey}&parent=${parentItemId}" class="ajax">unlike</a>
                % endif
                <br>
                <span>${comment}</span><br>
                % if url:
                    <a href=http://${url}>link</a>
                % endif
        % endfor
        </div>
        <div id=${parentItemId}_form >
        <form method="post" action="/feed/share/status" class="ajax" >
            <input type="text" name="comment" value=""/> 
            <input type="hidden" name="parent" value=${parentItemId}></input>
            <input type="hidden" name="parentUserId" value="${parentUserKey}"></input>
            <input type="hidden" name="acl" value=${acl}></input>
            ${widgets.button(None, type="submit", name="comment", value="comment")}<br/>
        </form>
        </div>
    </div>
% endfor
</%def>

<%def name="updateComments()">
<span>${item[2]}</span>
<a href="feed/like?itemKey=${item[4]}&parent=${item[5]}" class="ajax" >like</a>
<br>
<span>${item[0]}</span><br>
    % if item[1]:
<a href=http://${item[1]}>link</a>
    % endif
</%def>

