<%! from social import utils, _, __, constants %>
<%! import re %>
<%! import cgi %>
<%! from twisted.web.static import formatFileSize %>
<%! from base64 import urlsafe_b64decode %>

<!DOCTYPE HTML>

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
      <div class="titlebar center-header">
        <div id="title">${self.chat_title()}</div>
      </div>

      <div id="right">
        <div class="right-contents"></div>
      </div>
      <div id="center">
        <div class="center-contents"></div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="chat_title()">
  <% t = chatTitle if chatTitle else _('Chat Archives') %>
  <span class="middle title">${t}</span>
</%def>


<%!
  def formatPeopleInConversation(participants, myId, entities):
    others = [x for x in participants if x != myId]

    numOthers = len(others)
    def userName(userId):
      return entities[userId]["basic"]["name"]

    if numOthers > 2:
      return _("%s, %s and %d others") % (userName(others[0]), userName(others[1]), numOthers-1)
    elif numOthers == 2:
      return _("%s and %s") % (userName(others[0]), userName(others[1]))
    elif numOthers == 1:
      return _("%s") % (userName(others[0]))
    else:
      return _("%s") % (userName(myId))
%>

<%!
  def getSenderAvatar(senderId, entities, size="m"):
    #senderId = conv["meta"]["owner"]
    avatarURI = None
    avatarURI = utils.userAvatar(senderId, entities[senderId], size)
    avatarSize = "48" if size == "m" else "32"
    if avatarURI:
      return '<img src="%s" style="max-height:%spx; max-width:%spx; display:inline-block;"/>' \
        %(avatarURI, avatarSize, avatarSize)
    else:
      return ''
%>

<%!
  def getAvatarImg(avatarURI, size="m"):
    avatarSize = "48" if size == "m" else "32"
    return '<img src="%s" style="max-height=%spx; max-width=%spx; display:inline-block"/>' \
        %(avatarURI, avatarSize, avatarSize)
%>
<%def name="render_chat_row(chatId, chatLog, participants)">
  <%
    entityId, comment, timestamp = chatLog
    others = [x for x in participants if x != myId]
    if others and entityId == myId:
      entityId = others[-1]
    comment = utils.normalizeText(comment)
  %>
  <div id='thread-${chatId}' class="conversation-row">
    <div class="conversation-row-cell conversation-row-sender">
      ${getSenderAvatar(entityId, entities, 'm')}
    </div>
    <a class="conversation-row-cell conversation-row-info ajax" href='/chat/log?id=${chatId}'>
      <div class="conversation-row-headers">
        <span class="conversation-row-people">${formatPeopleInConversation(participants, myId, entities)}</span>
        <span class='conversation-row-time'>
          &ndash;&nbsp; ${utils.simpleTimestamp(timestamp, entities[myId]["basic"]["timezone"])}
        </span>
        <div class="conversation-row-subject-wrapper">
          <span class="conversation-row-snippet">${comment}</span>
        </div>
      </div>
    </a>
  </div>
</%def>

<%def name="render_chatLog()">
  %for (entityId, comment, timestamp) in chatLogs:
    <% comment = utils.normalizeText(comment)%>
    <div class="conv-item conversation-message-wrapper">
      <div class="comment-avatar">
        ${getSenderAvatar(entityId, entities, "s")}
      </div>
      <div class="comment-container conversation-message-container">
        <div class="conv-summary">
          <div class="conversation-message-headers">
            <div class="user conversation-message-headers-sender">
              <a href="/profile?id=${entityId}" class="ajax">
                ${entities[entityId]["basic"]["name"]}
              </a>
            </div>
            <nobr class="time-label conversation-message-headers-time">${utils.simpleTimestamp(float(timestamp), entities[myId]["basic"]["timezone"])}</nobr>
          </div>
          <div class="conversation-message-message">${comment}</div>
        </div>
      </div>
    </div>
  %endfor
  <div id="next-page-loader">
    %if nextPageStart:
      <div id="next-load-wrapper" class="busy-indicator">
        <a id="next-page-load" class="ajax" data-ref="/chat/log?start=${nextPageStart}&id=${chatId}">${_("Fetch newer chats")}</a>
      </div>
    %endif
  </div>
</%def>
<%def name='render_chat()'>
  <div class="conversation-messages-wrapper">
    ${render_chatLog()}
  </div>
  <div id="chat-reply-{chatId}">
    <input type='hidden' name='chatId' value='${chatId}' />
  </div>

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


<%def name="render_chatList()">
  <div id="threads-wrapper" class="paged-container">
    %for chatId in chatIds:
      ${render_chat_row(chatId, chats[chatId], chatParticipants[chatId])}
    %endfor
  </div>
</%def>

<%def name="center()">
  %if view == "list":
    ${render_chatList()}
  %elif view == "log":
  <div class="conversation-wrapper">
    ${render_chat()}
  </div>
  %endif
</%def>

<%def name="post_other()">
<form class='ajax' action='/chat' method='post'>
  <textarea name="comment"></textarea>
  <input type='hidden' name='to' value='KID0Jp5XEeCDwEBAhdLyVQ' />
  <input type='hidden' name='from' value='${to}' />
  <button type="submit" value="submit" >Submit</button>
</form>
</%def>

<%def name="post()">
<form class='ajax' action='/chat' method='post'>
  <textarea name="comment"></textarea>
  <input type='hidden' name='from' value='KID0Jp5XEeCDwEBAhdLyVQ' />
  <input type='hidden' name='to' value='${to}' />
  <button type="submit" value="submit" >Submit</button>
</form>
</%def>
