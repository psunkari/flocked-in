<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins, constants %>
<%! from social.search import SearchResource as search %>

<%namespace name="itemTmpl" file="item.mako"/>
<%namespace name="admin" file="admin.mako"/>
<%inherit file="base.mako"/>

<%def name="nav_menu()">
  <% admin.nav_menu() %>
</%def>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="titlebar center-header">
        <div id="title">${self._title()}</div>
      </div>
      <div id="right"></div>
      <div id="center">
        <div id="match-content" class="center-contents">
          <div id="convs-wrapper" style="margin-top: 10px;">
            %if not script:
              ${self.feed()}
            %endif
          </div>
        </div>
      </div>
        <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="_title()">
  <span class="middle title">${_('Keyword matches for <em class="socschl">%s</em>') % keyword}</span>
</%def>


<%def name="conv_root(convId)">
  <% itemType = items[convId]["meta"]["type"] %>
  %if itemType in plugins:
    ${plugins[itemType].rootHTML(convId, isQuoted, context.kwargs)}
  %endif
  <% attachments = items[convId].get("attachments", {}) %>
  %if len(attachments.keys()) > 0:
    <div class="attachment-list">
      %for attachmentId in attachments:
        <%
          tuuid, name, size, ftype = attachments[attachmentId].split(':')
          name = urlsafe_b64decode(name)
          size = formatFileSize(int(size))
          location = '/files?id=%s&fid=%s&ver=%s'%(convId, attachmentId, tuuid)
        %>
        <div class="attachment-item">
          <span class="icon attach-file-icon"></span>
          <span class="attachment-name"><a href="${location}" target="filedownload">${name|h}</a></span>
          <span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;${size}</span>
        </div>
      %endfor
    </div>
  %endif
</%def>


<%def name="item_layout(itemId, classes='')">
  <div id="conv-${itemId}" class="conv-item ${classes}">
    <div class="conv-avatar" id="conv-avatar-${itemId}">
      <%
        itemMeta = items[itemId]['meta']
        ownerId = itemMeta['owner']
        parentId = itemMeta.get('parent', None)
        itemType = itemMeta.get('type', 'status') if not parentId else 'comment'
      %>
      %if itemType != 'feedback':
        <% avatarURI = utils.userAvatar(ownerId, entities[ownerId], "small") %>
        <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
      %else:
        <div class="feedback-mood-icon ${type}-icon"></div>
      %endif
    </div>
    <div class="conv-data">
      <div id="conv-root-${itemId}" class="conv-root">
        <div class="conv-summary">
          %if itemType in plugins:
            ${plugins[itemType].rootHTML(itemId, isQuoted, context.kwargs)}
          %else:    ## responses
            <%
              comment = itemMeta.get('comment', '')
              snippet = itemMeta.get('snippet', '')
              richText = itemMeta.get('richText', 'False') == 'True'
              ownerName = utils.userName(ownerId, entities[ownerId], "conv-user-cause")
              if parentId:
                  parentMeta = items[parentId]['meta']
                  parentType = parentMeta.get('type', 'status')
                  parentOwnerId = parentMeta['owner']
                  parentOwnerName = entities[parentOwnerId].basic['name']
            %>
            %if parentId:
              ${_("%(ownerName)s, in reply to <a class='ajax' href='/item?id=%(parentId)s'>%(parentOwnerName)s's %(parentType)s</a>") % locals()}
            %else:
              ${ownerName}
            %endif
            <div class="item-title">
              ${itemTmpl._renderText(snippet, comment, richText=richText)}
            </div>
          %endif
          <%
            attachments = items[itemId].get("attachments", {})
            if len(attachments.keys()) > 0:
              itemTmpl.conv_attachments(itemId, attachments)
          %>
          <div id="item-footer-${itemId}" class="conv-footer busy-indicator">
            <%
              timestamp = int(itemMeta['timestamp'])
              myTimezone = me.basic.get("timezone", None)
            %>
            ${utils.simpleTimestamp(timestamp, myTimezone)}
&#183;<button class="ajaxpost button-link" title="Ignore"
              data-ref="/admin/keywords/ignore?id=${itemId}&keyword=${keyword}">Ignore</button>\
&#183;<button class="ajaxpost button-link" title="Permanently hide"
              data-ref="/admin/keywords/hide?id=${itemId}&keyword=${keyword}">Permanently Hide</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="feed()">
  <%
    for itemId in matches:
      if "meta" in items[itemId]:
        self.item_layout(itemId)
  %>
  %if nextPageStart:
    <% typ_filter = '&type=%s' %(itemType) if itemType else '' %>
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/admin/keyword-matches?start=${nextPageStart}&keyword=${keyword}" data-ref="/admin/keyword-matches-more?start=${nextPageStart}&keyword=${keyword}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">${_("No more posts to show")}</div>
  %endif
</%def>


