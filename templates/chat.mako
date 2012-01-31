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
      return _("Chat with %s, %s and %d others") % (userName(others[0]), userName(others[1]), numOthers-1)
    elif numOthers == 2:
      return _("Chat with %s and %s") % (userName(others[0]), userName(others[1]))
    elif numOthers == 1:
      return _("Chat with %s") % (userName(others[0]))
    else:
      return _("Chat with %s") % (userName(myId))
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

<%def name="chat_row(chatId, chatLog, participants)">
  <%
    entityId, comment, timestamp = chatLog
    others = [x for x in participants if x != myId]
    username = entities[entityId]['basic']['name']
    if others and entityId == myId:
      entityId = others[-1]
      username = "me"
    comment = comment.split("\n").pop()
    comment = comment
  %>
  <div id="thread-${chatId}" class="conversation-row ">
    <div class="conversation-row-cell conversation-row-sender">
        ${getSenderAvatar(entityId, entities)}
    </div>
    <a class="conversation-row-cell conversation-row-info ajax" href="/chats/chat?id=${chatId}">
      <div class="conversation-row-headers">
        <span class="conversation-row-people">${formatPeopleInConversation(participants, myId, entities)}</span>
        <span class="conversation-row-time">
          &ndash;&nbsp; ${utils.simpleTimestamp(timestamp, entities[myId]["basic"]["timezone"])}
        </span>
      </div>
      <div class="conversation-row-subject-wrapper" style="max-width:100% !important">
        <span class="conversation-row-subject">${username}</span>
        <span class="conversation-row-snippet">${comment}</span>
      </div>
    </a>
  </div>
</%def>

<%def name="chat()">
  <div class="conversation-messages-wrapper">
      <%
          previousBy = ""
          previousAt = None
      %>
      %for (entityId, comment, timestamp) in chatLogs:
        <%
          #comment = utils.normalizeText(comment)
        %>
          %if entityId == previousBy and (timestamp - previousAt < 300):
            <div class="conversation-message-wrapper">
              <div class="chat-message-header" style="margin-bottom:0;padding-top:0;padding-bottom:0">
                <div class="chat-summary">
                  <div class="user chat-sender" style="width:20px"></div>
                  <span class="conversation-message-message">${comment}</span>
                </div>
                <div class="time-label chat-time"></div>
              </div>
            </div>
          %else:
            <div class="chat-item conversation-message-wrapper">
              <div class="chat-message-header">
                <div class="chat-summary">
                  <div class="user chat-sender">
                    <a href="/profile?id=${entityId}" class="ajax">${entities[entityId]["basic"]["name"]}:</a>
                  </div>
                  <span class="conversation-message-message">${comment}</span>
                </div>
                <div class="time-label chat-time">${utils.simpleTimestamp(float(timestamp), entities[myId]["basic"]["timezone"])}</div>
              </div>
            </div>
            <%
              previousAt = timestamp
            %>
          %endif
          <%
            previousBy = entityId
          %>
      %endfor
  </div>
  <div id="next-page-loader">
    %if nextPageStart:
      <div id="next-load-wrapper" class="busy-indicator">
        <a id="next-page-load" class="ajax" data-ref="/chats/chat?start=${nextPageStart}&id=${chatId}">${_("Fetch newer chats")}</a>
      </div>
    %endif
  </div>
</%def>

<%def name="chatList()">
  <div id="threads-wrapper" class="paged-container">
    <div class="conversation-layout-container">
      %for chatId in chatIds:
        <% chat_row(chatId, chats[chatId], chatParticipants[chatId]) %>
      %endfor
    </div>
  </div>
  <div id="chat-paging" class="pagingbar">
    <ul class="h-links">
      %if prevPageStart:
        <li class="button">
          <a class="ajax" href="/chat?start=${prevPageStart}">${_("&#9666; Previous")}</a>
        </li>
      %else:
        <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
      %endif
      %if nextPageStart:
        <li class="button">
          <a class="ajax" href="/chat?&start=${nextPageStart}">${_("Next &#9656;")}</a>
        </li>
      %else:
        <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
      %endif
    </ul>
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
