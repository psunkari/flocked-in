<%! from social import utils, _, __ %>

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
        ${self.item_layout()}
      </div>
    </div>
  </div>
</%def>

<%def name="item_layout()">
  <div id="conv-${convId}" class="conv-item">
    <div id="conv-owner">
      %if not script:
        ${self.conv_owner()}
      %endif
    </div>
    <div id="conv-root-${convId}">
      %if not script:
        ${self.conv_root()}
      %endif
    </div>
    <div id="item-footer-${convId}" class="item-footer">
      %if not script:
        ${self.item_footer()}
      %endif
    </div>
    <div id="conv-comments-${convId}">
      %if not script:
        ${self.conv_comments()}
      %endif
    </div>
  </div>
</%def>

<%def name="conv_owner()">
  <div class="conv-avatar">
    <%
    def getImgURI(userId):
        data = owner.get('avatar', {}).get('small', '')
        if data:
            imgtyp, b64data = data.split(":")
            return "data:image/%s;base64,%s"%(imgtyp, b64data)
        return None
    avatar = getImgURI(ownerId)
    %>
    %if avatar:
      <img src="${avatar}" height="50" width="50"/>
    %endif
  </div>
  ${owner["basic"]["name"]}
  ${owner["basic"]["jobTitle"]}
</%def>

<%def name="conv_root()">
</%def>

<%def name="item_footer()">
  <span class="timestamp" ts="${conv['meta']['timestamp']}">${conv['meta']['timestamp']}</span>
  &nbsp;&#183;&nbsp;
  %if len(myLikes[convId]):
    <span><a class="ajax" _ref="/feed/unlike?itemKey=${convId}&parent=${convId}">${_("Unlike")}</a></span>
  %else:
    <span><a class="ajax" _ref="/feed/like?itemKey=${convId}&parent=${convId}">${_("Like")}</a></span>
  %endif
</%def>

<%def name="conv_comments()">
  <% responseCount = int(conv["meta"].get("responseCount", "0")) %>
  %if responseCount > len(responses):
    <div class="conv-comment">
      <span id="conv-comments-count" _num="${len(responses)}">${_("Showing %s of %s") % (len(responses), responseCount)}</span>
      View older responses
    </div>
  %endif
  %for responseId in responses:
    ${self.conv_comment(responseId)}
  %endfor
  <div class="conv-comment">
    <form method="post" action="/feed/share/status" class="ajax" id="form-${convId}">
      <input type="text" name="comment" value=""></input> 
      <input type="hidden" name="parent" value=${convId}></input>
      <input type="hidden" name="acl" value="${conv['meta']['acl']}"></input>
      ${widgets.button(None, type="submit", name="comment", value="comment")}<br/>
    </form>
  </div>
</%def>

<%def name="conv_comment(commentId)">
  <%
    item = items[commentId]
    userId  = item["meta"]["owner"]
    comment = item["meta"].get("comment", "")
    timestamp = item["meta"]["timestamp"]
    likesCount = item["meta"].get("likesCount", 0)
    fmtUser = lambda x: ("<span class='user comment-author'><a class='ajax' href='/profile?id=%s'>%s</a></span>" % (x, users[x]["basic"]["name"]))
    def getImgURI(userId):
        data = users[userId].get('avatar', {}).get('small', '')
        if data:
            imgtyp, b64data = data.split(":")
            return "data:image/%s;base64,%s"%(imgtyp, b64data)
        return None
  %>
  <div class="comment-avatar">
  %if getImgURI(userId) != None:
    <img src="${getImgURI(userId)}" height='25' width='25'/>
  %endif
  </div>

  <div class="comment-container">
    <span class="comment-user">${fmtUser(userId)}</span>
    <span class="comment-text">${comment}</span>
  </div>
  <div class="comment-meta">
    <span class="timestamp" _ts="${timestamp}">${timestamp}</span>
    <span class="likes">
      %if likesCount:
        &nbsp;&#183;&nbsp;
        <a class="ajax" href="/feed/likes?id=${commentId}">${likesCount}</a>
      %endif
    </span>
    &nbsp;&#183;&nbsp;
    %if commentId in myLikes:
      <span><a class="ajax" _ref="/feed/unlike?itemKey=${commentId}&parent=${convId}">${_("Unlike")}</a></span>
    %else:
      <span><a class="ajax" _ref="/feed/like?itemKey=${commentId}&parent=${convId}">${_("Like")}</a></span>
    %endif
  </div>
</%def>

<%def name="item_me()">
</%def>

<%def name="item_meta()">
</%def>

<%def name="item_subactions()">
</%def>
