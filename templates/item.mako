<%! from social import utils, _, __ %>
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
          ${self.item_layout(convId)}
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
        %if inline or not script:
          %if reasonStr and reasonStr.has_key(convId):
            <span class="conv-reason">${reasonStr[convId]}</span>
          %endif
          ${self.conv_root(convId)}
        %endif
      </div>
      <div id="item-footer-${convId}" class="item-footer">
        %if inline or not script:
          ${self.item_footer(convId)}
        %endif
      </div>
      <div id="conv-likes-wrapper-${convId}">
        %if likeStr and likeStr.has_key(convId):
          <div class="conv-likes">${likeStr[convId]}</div>
        %endif
      </div>
      <div id="conv-comments-${convId}" class="conv-comments">
        %if inline or not script:
          ${self.conv_comments(convId, isFeed)}
        %endif
      </div>
      <div class="conv-comment-form">
        <form method="post" action="/feed/share/status" class="ajax" id="form-${convId}">
          <input type="text" name="comment" value=""></input>
          <input type="hidden" name="parent" value=${convId}></input>
          ${widgets.button(None, type="submit", name="comment", value="Comment")}<br/>
        </form>
      </div>
    </div>
  </div>
</%def>

<%def name="conv_owner(ownerId)">
  <% avatarURI = utils.userAvatar(ownerId, users[ownerId]) %>
  %if avatarURI:
    <img src="${avatarURI}" height="50" width="50"/>
  %endif
</%def>

<%def name="conv_root(convId)">
  <%
  itemType = items[convId]["meta"]["type"]
  %>
  % if itemType in ("status", "link", "document", "activity"):
      ${self.renderStatus(convId)}
  % elif itemType == "poll":
      ${self.poll_root(convId)}
  % elif itemType == "event":
      ${self.event_root(convId)}
  %endif

</%def>

<%def name="item_footer(itemId)">
  <%
    meta = items[itemId]['meta']
    hasParent = meta.has_key('parent')
    timestamp = meta['timestamp']
    likesCount = int(meta.get('likesCount', "0"))
  %>
  <span class="timestamp" ts="${timestamp}">${timestamp}</span>
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

<%def name="conv_comments(convId, isFeed=False)">
  <%
    responseCount = int(items[convId]["meta"].get("responseCount", "0"))
    responsesToShow = responses.get(convId, {}) if responses else {}
  %>
  %if responseCount > len(responsesToShow):
    <div class="conv-comments-more">
      %if isFeed:
        ${_("View all %s comments &#187;") % (responseCount)}
      %else:
        <span _num="${len(responsesToShow)}">${_("Showing %s of %s") % (len(responsesToShow), responseCount)}</span>
        ${_("View older comments &#187;")}
      %endif
    </div>
  %endif
  %for responseId in responsesToShow:
    ${self.conv_comment(convId, responseId)}
  %endfor
</%def>

<%def name="conv_comment(convId, commentId)">
  <%
    item = items[commentId]
    userId  = item["meta"]["owner"]
    comment = item["meta"].get("comment", "")
    fmtUser = lambda x: ("<span class='user comment-author'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (x, users[x]["basic"]["name"]))
  %>
  <div class="conv-comment" id="comment-${commentId}">
    <div class="comment-avatar">
      <% avatarURI = utils.userAvatar(userId, users[userId], "small") %>
      %if avatarURI:
        <img src="${avatarURI}" height='25' width='25'/>
      %endif
    </div>
    <div class="comment-container">
      <span class="comment-user">${fmtUser(userId)}</span>
      <span class="comment-text">${comment}</span>
    </div>
    <div class="comment-meta">
      ${self.item_footer(commentId)}
    </div>
  </div>
</%def>

<%def name="item_me()">
</%def>

<%def name="item_meta()">
</%def>

<%def name="item_subactions()">
</%def>


<%def name="poll_root(convId)">
  <%
    conv = items[convId]
    question = items[convId]["meta"]["question"] or "what is your fav game?"
    options = items[convId]["options"] or ["cricket", "football", "hockey"]
  %>
  <div id="conv" class="conv-item">
    <div>
        %if myVote:
        <p> you voted for: ${myVote} </p>
        %endif
        <form action="/item/act" method="POST" class="ajax">
        <p> ${question} </p>
        % for option in options:
            <input type="radio" name="option" value= "${option}"> ${option} </input> <br/>
        % endfor
            <input type="hidden" name="id" value="${convId}" />
            <input type="hidden" name="type" value="poll" />
            <input type="submit" id="submit" value="${_('Submit')}"/>
        </form>
        <span>${question}</span>
        % for option in options:
            <p> ${option} : ${options[option]} </p>
        %endfor
    </div>

  </div>
</%def>

<%def name="renderStatus(convId, isQuoted=False)">
  <%
    conv = items[convId]
    type = conv["meta"]["type"]
    userId = conv["meta"]["owner"]
    fmtUser = lambda x,y=None: ("<span class='user %s'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (y if y else '', x, users[x]["basic"]["name"]))
  %>
  %if type == "activity":
    <%
      subtype = conv["meta"]["subType"]
      target = conv["meta"]["target"]
      if subtype == "connection":
        activity = _("%s and %s are now friends.") % (fmtUser(userId), fmtUser(target))
      elif subtype == "following":
        activity = _("%s started following %s.") % (fmtUser(userId), fmtUser(target))
    %>
    <div class="conv-summary${' conv-quote' if isQuoted else ''}">
      ${activity}
  %elif type in ["status", "link", "document"]:
    %if not isQuoted:
      <span class="conv-reason">
        ${fmtUser(userId, "conv-user-cause")}
      </span>
    %endif
    <div class="conv-summary${' conv-quote' if isQuoted else ''}">
      %if conv["meta"].has_key("comment"):
        ${conv["meta"]["comment"]}
      %endif
  %endif
</div>
</%def>

<%def name="event_root(convId)">
  <%

    conv = items[convId]
    title = items[convId]["meta"].get("title", '')
    location = items[convId]["meta"].get("location", '')
    desc = items[convId]["meta"].get("desc", "")
    start = items[convId]["meta"].get("startTime")
    end   = items[convId]["meta"].get("endTime", '')
    options = items[convId]["options"] or ["yes", "maybe", "no"]
  %>
  <div id="conv" class="conv-item">
    <div>
        %if myResponse:
        <p> are you attending the <a href="/item?id=${convId}&type=event">event</a>?: ${myResponse} </p>
        %endif
        <form action="/item/act" method="POST" class="ajax">
        <p> ${title} </p>
        % for option in options:
            <input type="radio" name="response" value= "${option}"> ${option} </input> <br/>
        % endfor
            <input type="hidden" name="id" value="${convId}" />
            <input type="hidden" name="type" value="event" />
            <input type="submit" id="submit" value="${_('Submit')}"/>
        </form>
        <span>${title}</span>
        <p>${desc}</p>
        <p>location: ${location}</p>
        <p>TIME: ${start} - ${end}</p>
        % for option in options:
            <p> ${option} : ${options[option]} </p>
        %endfor
    </div>

  </div>
</%def>
