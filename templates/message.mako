<%! from social import utils, _, __, constants %>
<%! import re %>
<%! import cgi %>
<%! from twisted.web.static import formatFileSize %>
<%! from base64 import urlsafe_b64decode %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
        <div class="right-contents">
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <span class="middle title">${_('Messages')}</span>
            <span class="button title-button">
              <a class="ajax" href="/messages/write" data-ref="/messages/write">${_('New Message')}</a>
            </span>
          </div>
          <div id="composer">
            %if view == "compose":
              %if not script:
                ${render_composer()}
              %endif
            %endif
          </div>
        </div>
        <div class="center-contents">
          %if view != "compose":
            %if not script:
              ${center()}
            %endif
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%!
  def newlinescape(text):
    return utils.normalizeText(text)
%>

<%!
  def formatPeopleInConversation(conv, people):
    participants = conv["people"]
    owner = conv["meta"]["owner"]
    others = [x for x in participants if x != owner]

    numOthers = len(others)
    def userName(userId):
      return people[userId]["basic"]["name"]

    if numOthers > 2:
      return _("%s, %s and %d others") % (userName(owner), userName(others[0]), numOthers-1)
    elif numOthers == 2:
      return _("%s, %s and %s") % (userName(owner), userName(others[0]), userName(others[1]))
    elif numOthers == 1:
      return _("%s, %s") % (userName(owner), userName(others[0]))
    else:
      return _("%s") % (userName(owner))
%>

<%!
  def getSenderAvatar(conv, people, size="m"):
    senderId = conv["meta"]["owner"]
    avatarURI = None
    avatarURI = utils.userAvatar(senderId, people[senderId], size)
    avatarSize = "48" if size == "m" else "32"
    if avatarURI:
      return '<img src="%s" height="%s" width="%s" style="display:inline-block"/>' \
        %(avatarURI, avatarSize, avatarSize)
    else:
      return ''
%>

<%!
  def getAvatarImg(avatarURI, size="m"):
    avatarSize = "48" if size == "m" else "32"
    return '<img src="%s" height="%s" width="%s" style="display:inline-block"/>' \
        %(avatarURI, avatarSize, avatarSize)
%>

<%def name="render_conversation_row(script, convId, conv)">
  <div id="thread-${convId}" class="conversation-row ${'row-unread' if conv["read"] == "0" else ''}">
    <div class="conversation-row-cell conversation-row-select">
      <input type="checkbox" name="selected" value="${convId}" onchange="$('.thread-selector').attr('checked', false)"/>
    </div>
    <div class="conversation-row-cell conversation-row-sender">
        ${getSenderAvatar(conv, people)}
    </div>
    <a class="conversation-row-cell conversation-row-info ajax" href="/messages/thread?id=${convId}">
      <div class="conversation-row-headers">
        <span class="conversation-row-people">${formatPeopleInConversation(conv, people)}</span>
        <span class="conversation-row-time">
          &ndash;&nbsp; ${utils.simpleTimestamp(float(conv['meta']["date_epoch"]), people[myKey]["basic"]["timezone"])}
        </span>
      </div>
      <div class="conversation-row-subject-wrapper">
        <span class="conversation-row-subject">${conv["meta"]["subject"]}</span>
        <span class="conversation-row-snippet">${conv["meta"]["snippet"]}</span>
      </div>
    </a>
    <div class="conversation-row-cell conversation-row-actions">
      <span>
        %if filterType != "unread":
        <%
          readStatus = 'unread' if conv['read']=='0' else 'read'
          readAction = 'read' if conv['read']=='0' else 'unread'
        %>
        <div class="messaging-icon messaging-${readStatus}-icon"
             title="${_("Mark this conversation as ")}${readAction}"
             onclick="$.post('/ajax/messages/thread', 'action=${readAction}&selected=${convId}&filterType=${filterType}')">&nbsp;</div>
        %elif filterType == "unread":
        <div class="messaging-icon messaging-unread-icon"
             title="${_("Mark this conversation as read")}"
             onclick="$.post('/ajax/messages/thread', 'action=read&selected=${convId}&filterType=${filterType}')">&nbsp;</div>
        %endif
        %if filterType != "archive":
        <div class="messaging-icon messaging-archive-icon"
             title="${_("Archive this conversation")}"
             onclick="$.post('/ajax/messages/thread', 'action=archive&selected=${convId}&filterType=${filterType}')">&nbsp;</div>
        %endif
        %if filterType != "trash":
        <div class="messaging-icon messaging-delete-icon"
             title="${_("Delete this conversation")}"
             onclick="$.post('/ajax/messages/thread', 'action=trash&selected=${convId}&filterType=${filterType}')">&nbsp;</div>
        %endif
      </span>
    </div>
  </div>
</%def>

<%def name="render_conversation()">
    ${toolbar_layout(view)}
    <div class="conversation-headline">
        <h2 class="conversation-headline-subject">${conv["meta"]["subject"]}</h2>
    </div>
    <div class="conversation-wrapper">
        <div class="conversation-messages-wrapper">
            ${render_conversation_messages()}
        </div>
        ${render_conversation_reply(script, messages[messageIds[-1]], id)}
    </div>
</%def>

<%def name="render_conversation_messages()">
  %for mid in messageIds:
    <div class="conv-item conversation-message-wrapper">
      <div class="comment-avatar">
        ${getSenderAvatar(messages[mid], people, "s")}
      </div>
      <div class="comment-container conversation-message-container">
        <div class="conv-summary">
          <!--<div class="message-headers" onclick="var _self=this;$(this).siblings().toggle(1, function(){$(_self).children('.message-headers-snippet').toggleClass('message-headers-snippet-show')});">-->
          <div class="conversation-message-headers">
            <div class="user conversation-message-headers-sender">
              <a href="/profile?id=${messages[mid]['meta']['owner']}" class="ajax">
                ${people[messages[mid]['meta']['owner']]["basic"]["name"]}
              </a>
            </div>
            <nobr class="time-label conversation-message-headers-time">
              ${utils.simpleTimestamp(float(messages[mid]["meta"]["date_epoch"]), people[myKey]["basic"]["timezone"])}
            </nobr>
          </div>
          <div class="conversation-message-message">
            ${messages[mid]["meta"].get("body", '')|newlinescape}
          </div>
        </div>
      </div>
    </div>
  %endfor
</%def>

<%def name="render_conversation_reply(script, msg, convId)">
  <form id="message-reply-form" method="post" class="ajax" action="/messages/write">
    <div class="conversation-composer">
      <div class="conv-avatar">
          ${getAvatarImg(utils.userAvatar(myKey, people[myKey]))}
      </div>
      <div class="input-wrap conversation-reply-wrapper">
          <textarea class="conversation-reply" name="body" placeholder="${_('Quickly reply to this message')}" required title="${_('Reply')}"></textarea>
          <input type="hidden" value=${convId} name="parent"/>
      </div>
      <div id="msgreply-attach-uploaded" class="uploaded-filelist"></div>
      <div class="conversation-reply-actions">
        <input type="submit" name="send" value="${_('Reply')}" class="button"/>
      </div>
    </form>
    </div>
    <div class="file-attach-wrapper conversation-reply-wrapper">
      ${widgets.fileUploadButton('msgreply-attach')}
    </div>
    <div class="clear"></div>
</%def>

<%def name="render_composer()">
  <div class="conversation-composer">
    <form method="post" action="/messages/write" class="ajax" id="message-form">
      <div class="input-wrap conversation-composer-field" onclick="$('.conversation-composer-field-recipient').focus()">
        <div class="conversation-composer-recipients"></div>
        <input name="recipients" id="recipientList" type="hidden"/>
        <div>
            <input class="conversation-composer-field-recipient" type="text"  size="15" 
                   placeholder="${_('Enter a name')}" title="${_('Recipient')}"/>
        </div>
      </div>
      <div class="input-wrap conversation-composer-field">
        <input class="conversation-composer-field-subject" type="text" name="subject" 
               placeholder="${_('Enter a subject of your message')}" title="${_('Subject')}"/>
      </div>
      <div class="input-wrap conversation-composer-field">
        <textarea class="conversation-composer-field-body"
                  placeholder="${_("Write a message to your friends and colleagues")}" name="body" title="${_('Message')}"></textarea>
      </div>
      <div id="msgcompose-attach-uploaded" class="uploaded-filelist"></div>
      <div class="conversation-composer-actions">
        %if script:
          <button type="submit" class="button default">
            ${_('Send')}
          </button>
          <button type="button" class="button" onclick="$('#composer').empty()">
            ${_('Cancel')}
          </button>
        %else:
          <a class="ajax" data-ref="/messages">${'Cancel'}</a>
        %endif
      </div>
    </form>
    <script>$('#message-form').html5form({messages: 'en'});</script>
    <div class="file-attach-wrapper">
      ${widgets.fileUploadButton('msgcompose-attach')}
    </div>
    <div class="clear"></div>
  </div>
</%def>

<%def name="toolbar_layout(view, nextPageStart=None, prevPageStart=None)">
  %if view == "messages":
    <div id="msg-toolbar" class="toolbar">
          %if script:
            <input id="thread-selector" type="checkbox" name="select" value="all"
                   onchange="$('.conversation-row input[name=selected]').attr('checked', this.checked)"/>
            <input id="toolbarAction" name="action" value="" type="hidden"/>
          %endif
          %if filterType == "unread":
            <input type="submit" name="read" value="${_("Mark as Read")}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'read')"/>
          %endif
          %if filterType != "trash":
            <input type="submit" name="trash" value="${_("Trash")}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'trash')"/>
          %endif
          %if filterType != "archive" and filterType != "trash":
            <input type="submit" name="archive" value="${_("Archive")}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'archive')"/>
          %endif
          %if filterType != "unread":
            <input type="submit" name="unread" value="${_("Mark as Unread")}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'unread')"/>
          %endif
          %if filterType != "all":
            <input type="submit" name="inbox" value="${_("Move to Inbox")}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'inbox')"/>
          %endif
    </div>
  %elif view == "message":
    <div id="msg-toolbar" class="toolbar">
      <%
        if "mAllConversations" in inFolders:
          tail = "?type=all"
        elif "mArchivedConversations" in inFolders:
          tail = "?type=archive"
        elif "mDeletedConversations" in inFolders:
          tail = "?type=trash"
      %>
      <a class="${'ajax' if script else ''} back-link" href="/messages${tail}">Go Back</a>
        <form method="post" action="/messages/thread" class="ajax">
            <input type="hidden" name="selected" value="${id}"/>
            <input id="toolbarAction" name="action" value="" type="hidden"/>
            %if "mAllConversations" in inFolders:
              <input type="submit" name="trash" value="${_('Move to Trash')}"
                     class="button" onclick="$('#toolbarAction').attr('value', 'trash')"/>
              <input type="submit" name="archive" value="${_('Archive')}"
                     class="button" onclick="$('#toolbarAction').attr('value', 'archive')"/>
              <input type="hidden" name="filterType" value="all"/>
            %elif "mArchivedConversations" in inFolders:
              <input type="submit" name="trash" value="${_('Move to Trash')}"
                     class="button" onclick="$('#toolbarAction').attr('value', 'trash')"/>
              <input type="submit" name="unread" value="${_('Move to Inbox')}"
                     class="button" onclick="$('#toolbarAction').attr('value', 'inbox')"/>
              <input type="hidden" name="filterType" value="archive"/>
            %elif "mDeletedConversations" in inFolders:
              <input type="submit" name="unread" value="${_('Move to Inbox')}"
                     class="button" onclick="$('#toolbarAction').attr('value', 'inbox')"/>
              <input type="hidden" name="filterType" value="trash"/>
            %endif
            <input type="submit" name="unread" value="${_('Mark as Unread')}"
                   class="button" onclick="$('#toolbarAction').attr('value', 'unread')"/>
            <input type="hidden" name="view" value="message"/>
        </form>
      <span class="clear" style="display:block"></span>
    </div>
  %endif
</%def>

<%def name="render_conversations()">
  <div id="people-view" class="viewbar">
    ${viewOptions()}
  </div>
  <div id="threads-wrapper" class="paged-container">
    <form action="/messages/thread" method="post" class="ajax">
      
      %if not mids:
        <div id="empty-message" >${_("No messages")}</div>
      %else:
        ${toolbar_layout(view, nextPageStart, prevPageStart)}
        <div class="conversation-layout-container">
          %for mid in mids:
            ${render_conversation_row(script, mid, messages[mid])}
          %endfor
        </div>
      %endif
      <input type="hidden" name="filterType" value="${filterType}"/>
      <input type="hidden" name="view" value="messages"/>
    </form>
  </div>
  <div id="people-paging" class="pagingbar">
    %if mids:
      ${paging()}
    %endif
  </div>
</%def>

<%def name="center()">
  %if view == "messages":
    ${render_conversations()}
  %elif view == "message":
    ${render_conversation()}
  %endif
</%def>

<%def name="right()">
    % if view == "message":
        <div class="sidebar-chunk">
          <div class="sidebar-title">${_("People in this conversation")}</div>
          <ul class="v-links peoplemenu">
            %for person in conv["participants"]:
                <li>
                    <div class="conversation-people-avatar">
                      ${getAvatarImg(utils.userAvatar(conv, people[person], "s"), "s")}
                    </div>
                    <div class="conversation-people-profile">
                      <a href="/profile?id=${person}">${people[person]["basic"]["name"]}</a>
                    </div>
                    <%
                        if (person == myKey) or (person == conv["meta"]["owner"]):
                            showDelete = False
                        else:
                            showDelete = True
                    %>
                    %if showDelete:
                        <div class="conversation-people-remove" class="busy-indicator"
                             title="${_('Remove %s from this conversation') % people[person]["basic"]["name"]}">
                          <div class="messaging-icon messaging-delete-icon"
                               onclick="$.post('/ajax/messages/members', 'action=remove&parent=${id}&recipients=${person}')">&nbsp;</div>
                        </div>
                    %else:
                        <div class="conversation-people-no-remove">&nbsp;</div>
                    %endif
                </li>
            %endfor
          </ul>
        </div>
        <div class="sidebar-chunk">
            <div class="sidebar-title">${_("Add your colleague")}</div>
            <div class="conversation-people-add-wrapper">
                <form class="ajax" action="/messages/members">
                    <input type="hidden" name='parent' value=${id} />
                    <input type="hidden" name="action" value="add" />
                    <input type="hidden" name="recipients" id="conversation_recipients"/>
                    <div class="input-wrap">
                        <input type="text" placeHolder="Your friend's name" id="conversation_add_member" required title="${_('Friend name')}"/>
                    </div>
                </form>
            </div>
        </div>
        <div class="sidebar-chunk">
            <div class="sidebar-title">${_("Attached Files")}</div>
            <div class="conversation-attachments-wrapper">
              <% attachments = conv.get("attachments", {}) %>
              <ul class="v-links peoplemenu">
                %for file, file_meta in attachments.iteritems():
                  <%
                     tuuid, name, size, ftype = file_meta.split(':')
                     size = formatFileSize(int(size))
                     name = urlsafe_b64decode(name)
                  %>
                  <li>
                      <a href='/messages/file?id=${id}&fid=${file}&ver=${tuuid}'>${name|h}</a>
                  </li>
                %endfor
              </ul>
            </div>
        </div>
    %else:
        <span>${view}</span>
    %endif
</%def>

<%def name="viewOptions()">
  <ul class="h-links view-options">
    %for item, display in [('all', _('Inbox')), ('unread', _('Unread')), ('archive', _('Archive')), ('trash', _('Trash'))]:
      %if filterType == item:
        <li class="selected">${_(display)}</li>
      %else:
        <li><a href="/messages?type=${item}" class="ajax">${_(display)}</a></li>
      %endif
    %endfor
  </ul>
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button">
        <a class="ajax" href="/messages?type=${filterType}&start=${prevPageStart}">${_("&#9666; Previous")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button">
        <a class="ajax" href="/messages?type=${filterType}&start=${nextPageStart}">${_("Next &#9656;")}</a>
      </li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>
