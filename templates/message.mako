<%! from social import utils, _, __, plugins, constants %>
<%! import re, pytz %>
<%! import email.utils %>
<%! import cgi %>
<%! import datetime; import dateutil.relativedelta%>
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
              <a class="ajax" href="/messages/write" _ref="/messages/write">${_('New Message')}</a>
            </span>
          </div>
          <div id="composer">
            %if view == "compose":
              %if not script:
                ${viewComposer()}
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
    return utils.normalizeText(cgi.escape(text))
%>

<%!
  def formatPeopleInConversation(conv, people_info):
    participants = conv["people"]
    sender = people_info[conv["meta"]["owner"]]["basic"]["name"]
    people_without_sender = set(participants) - set([sender,])
    last_sent_by = people_info[list(people_without_sender)[-1]]["basic"]["name"]

    if len(people_without_sender) > 1:
        return "%s...%s(%d)" %(sender, last_sent_by, len(participants)-1)
    else:
        return "%s and %s" %(sender, last_sent_by)
%>

<%!
    def formatBodyForReply(message, reply):
      body = cgi.escape(message["meta"].get('body', ''))
      sender = message["meta"]['owner']
      date = message["meta"]['Date']
      quoted_reply = "\n".join([">%s" %x for x in body.split('\n')]+['>'])
      prequotestring = "%s wrote" %(sender)
      new_reply = "\r\n\r\n\r\n%s\r\n\r\n%s\r\n%s" %(reply, prequotestring, quoted_reply)
      return new_reply
%>

<%!
    def formatBodyForForward(message):
      lines = []
      lines.append("")
      lines.append("")
      lines.append("-------- Original Message --------")
      lines.append("Subject: %s" %message["Subject"])
      lines.append("Date: %s" %message["Date"])
      lines.append("From: %s" %message["From"])
      lines.append("To: %s" %message["To"])
      lines.append("")
      lines.append(message["body"])
      new_reply = "\n".join(lines)
      return new_reply
%>

<%!
  def timeElapsedSince(then_string):
    then = float(then_string)
    then = datetime.datetime.fromtimestamp(then)
    now = datetime.datetime.now()
    weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday"]
    rc = dateutil.relativedelta.relativedelta(now, then)
    tz = pytz.timezone("Asia/Kolkata")
    dt = tz.localize(then)

    if rc.days < 1:
      if rc.days == 0:
        fmt = "%I:%M%p"
        date = dt.strftime(fmt)
        if then.day == now.day:
          return "Today at %s" %date
        else:
          return "Yesterday at %s" %date
      else:
        fmt = "%I:%M%p"
        date = dt.strftime(fmt)
        return "Yesterday at %s" %date
    elif rc.years < 1:
        fmt = "%b %d, at %I:%M%p"
        date = dt.strftime(fmt)
        return "%s" %date
    else:
      fmt = "%b %d, Y at %X"
      date = dt.strftime(fmt)
      return "%s" %date
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

<%def name="conversation_row_layout(script, convId, conv)">
  <div id="thread-${convId}" class="message-row ${'row-unread' if conv["read"] == "0" else 'row-read'}">
    <div class="message-row-cell message-row-select">
      <input type="checkbox" name="selected" value="${convId}"
        onchange="$('.thread-selector').attr('checked', false)"/>
    </div>
    <div class="message-row-cell message-row-sender">
        ${getSenderAvatar(conv, people)}
    </div>
    <div class="message-row-cell message-row-info" style="height:100%;width:100%;cursor:pointer">
        <div style="display:block;width:100%;height:100%">
            <div style="display:inline-block;padding:2px;width:635px" onclick="alert('clicked')">
                <span style="padding:4px 0 0 4px;width:150px">${formatPeopleInConversation(conv, people)}</span>
                <span style="width:450px;font-size:11px;color:#777;padding-left:4px">${conv['meta']["date_epoch"]|timeElapsedSince}</span>
            </div>
            <div style="display:inline-block;padding:2px">
                <span>
                    <div class="messaging-icon" style="display:inline-block;width:19px;height:19px;background-position:0px -175px;box-shadow:1px 0 2px #CCCCCC" title="Mark this conversation as unread">&nbsp</div>
                    <div class="messaging-icon" style="display:inline-block;width:19px;height:19px;background-position:0px -110px;box-shadow:1px 0 2px #CCCCCC" title="Archive this conversation">&nbsp</div>
                    <div class="messaging-icon" style="display:inline-block;width:19px;height:19px;background-position:0px -78px;box-shadow:1px 0 2px #CCCCCC" title="Delete this conversation">&nbsp</div>
                </span>
            </div>
            <a class="ajax message-link" href="/messages/thread?id=${convId}" style="display:block;padding:2px;position:relative">
                <div style="display:inline">${conv["meta"]["subject"]|h}</div>
                <div style="color:#777;overflow:hidden;display:inline-block;vertical-align:bottom;white-space:nowrap;min-width:640px"> - ${conv["meta"]["snippet"]}</div>
                <span style="position:absolute;right:1px;bottom:-4px;cursor:default;color:#000">
                    <span title="There are ${conv['count']} messages in this conversation">${conv['count']}</span>
                </span>
            </a>
        </div>
    </div>
  </div>
</%def>

<%def name="viewConversation()">
    <form class="ajax" method="post" action="/messages/thread">
        ${toolbar_layout(view)}
        <input type="hidden" name="selected" value="${id}"/>
    </form>
    <div class="message-headline">
        <h2 class="message-headline-subject">${conv["meta"]["subject"]|h}</h2>
    </div>
    <div class="conversation-wrapper" style="padding:2px;border:1px solid #BCBCBC;border-radius:7px">
        <div class="conversation-messages-wrapper">
            ${render_conversation_messages()}
        </div>
        ${quick_reply_layout(script, messages[messageIds[-1]], id)}
    </div>
</%def>

<%def name="render_conversation_messages()">
    % for mid in messageIds:
        <div class="conversation-message-wrapper" style="padding-bottom:2px; margin-bottom:2px; border-bottom:1px solid #E2e2e2">
          <div class="comment-avatar">
            ${getSenderAvatar(messages[mid], people, "s")}
          </div>
          <div class="comment-container">
            <div class="conv-summary">
              <div class="message-headers">
                <span class="user conv-user-cause">
                  <a href="/profile?id=${messages[mid]['meta']['owner']}" class="ajax">
                    ${people[messages[mid]['meta']['owner']]["basic"]["name"]}
                  </a>
                </span>
                <span class="time-label message-headers-time">${messages[mid]["meta"]["date_epoch"]|timeElapsedSince}</span>
              </div>
              <div class="message-message">
                ${messages[mid]["meta"].get("body", '') | newlinescape}
              </div>
            </div>
          </div>
        </div>
    % endfor
</%def>

<%def name="quick_reply_layout(script, msg, convId)">
  <form method="post" class="ajax" action="/messages/write">
    <div class="message-composer">
      <div class="conv-avatar">
          ${getAvatarImg(utils.userAvatar(myKey, people[myKey]))}
      </div>
      <div class="input-wrap" style="margin-left:60px">
          <textarea class="conversation-reply" style="min-height:60px" name="body" placeholder="Quickly reply to this message"></textarea>
          <input type="hidden" value=${convId} name="parent"/>
      </div>
      <div style="text-align:right;padding:4px 0">
        <input type="submit" name="send" value="${_('Reply')}" class="button"/>
      </div>
    </div>
  </form>
</%def>

<%def name="viewComposer()">
  <div class="message-composer">
    <form method="post" action="/messages/write">
      <div class="input-wrap message-composer-field">
        <textarea class="message-composer-field-recipient" type="text" name="recipients" placeholder="${_('Enter name or email address') |h}"></textarea>
      </div>
      <div class="input-wrap message-composer-field">
        <input class="message-composer-field-subject" type="text" name="subject" placeholder="${_('Enter a subject of your message') |h}"/>
      </div>
      <div class="input-wrap message-composer-field">
        <textarea class="message-composer-field-body" placeholder="Write a message to your friends and colleagues" name="body"></textarea>
      </div>
      <div id="sharebar-actions">
        <ul class="middle user-actions h-links message-composer-field">
          <li class="button">
            <input type="submit" name="send" value="Send" class="button default">
          </li>
          <li class="button">
            %if script:
                <button type="button" class="button" onclick="$('#composer').empty()">
                    ${'Cancel'}
                </button>
            %else:
                <a class="ajax" _ref="/messages">${'Cancel'}</a>
            %endif
          </li>
        </ul>
      </div>
    </form>
  </div>
</%def>

<%def name="toolbar_layout(view, nextPageStart=None, prevPageStart=None)">
  %if view == "messages":
    <div id="msg-toolbar" class="toolbar">
      %if script:
        <input id="thread-selector" type="checkbox" name="select" value="all"
               onchange="$('.message-row input[name=selected]').attr('checked', this.checked)"/>
      %endif
      %if filterType != "trash":
        <input type="submit" name="trash" value="Trash" class="button"/>
      %endif
      %if filterType != "archive" and filterType != "trash":
        <input type="submit" name="archive" value="Archive" class="button"/>
      %endif
      %if filterType != "unread":
        <input type="submit" name="unread" value="Mark as Unread" class="button"/>
      %endif
      %if filterType != "all":
        <input type="submit" name="inbox" value="Move to Inbox" class="button"/>
      %endif
    </div>
  %elif view == "message":
    <div class="toolbar">
      <a class="${'ajax' if script else ''} action-link" href="/messages">Go Back</a>
      <input type="submit" name="trash" value="Trash" class="button "/>
      <input type="submit" name="archive" value="Archive" class="button "/>
      <input type="submit" name="unread" value="Mark as Unread" class="button "/>
      <span class="clear" style="display:block"></span>
    </div>
  %endif
</%def>

<%def name="viewListing()">
  <div id="people-view" class="viewbar">
    ${viewOptions()}
  </div>
  <div id="threads-wrapper" class="paged-container">
    <form action="/messages/thread" method="post" class="ajax">
        ${toolbar_layout(view, nextPageStart, prevPageStart)}
        <div class="conversation-layout-container">
            %for mid in mids:
              ${conversation_row_layout(script, mid, messages[mid])}
            %endfor
        </div>
    </form>
  </div>
  <div id="people-paging" class="pagingbar">
      ${paging()}
  </div>
</%def>

<%def name="center()">
  %if view == "messages":
    ${viewListing()}
  %elif view == "message":
    ${viewConversation()}
  %endif
</%def>

<%def name="right()">
    % if view == "message":
        <div class="sidebar-chunk">
          <div class="sidebar-title">People in this conversation</div>
          <ul class="v-links peoplemenu">
            %for person in conv["participants"]:
                <li>
                    <div style="display:table-cell">${getAvatarImg(utils.userAvatar(conv, people[person], "s"), "s")}</div>
                    <div style="display:table-cell;vertical-align:middle;padding-left:15px;width:160px"><a href="/profile?id=${person}">${people[person]["basic"]["name"]}</a></div>
                    <%
                        if (person == myKey) or (person == conv["meta"]["owner"]):
                            showDelete = False
                        else:
                            showDelete = True
                    %>
                    %if showDelete:
                        <div style="display:table-cell;vertical-align:middle;font-weight:bold;cursor:pointer;font-size:15px;vertical-align:middle" class="busy-indicator"
                             onclick="$.post('/ajax/messages/members', 'action=remove&parent=${id}&recipients=${person}', null, 'script')" title="Remove ${people[person]["basic"]["name"]} from this conversation"><span>X</span></div>
                    %else:
                        <div style="display:table-cell;vertical-align:middle;font-weight:bold">&nbsp</div>
                    %endif
                </li>
            %endfor
          </ul>
        </div>
        <div class="sidebar-chunk">
            <div class="sidebar-title">Add someone to this conversation</div>
            <div style="margin-top:4px">
                <form class="ajax" action="/messages/members" style="font-size:11px;width:185px">
                    <input type="hidden" name='parent' value=${id} />
                    <input type="hidden" name="action" value="add" />
                    <div class="input-wrap">
                        <input type="text" name="recipients" placeHolder="Your friend's name"/>
                    </div>
                </form>
            </div>
        </div>
    %else:
        <span>${view}</span>
    %endif
</%def>

<%def name="viewOptions()">
  <ul class="h-links view-options">
    %for item, display in [('all', 'Inbox'), ('unread', 'Unread'), ('archive', 'Archive'), ('trash', 'Trash')]:
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
      <li class="button"><a class="ajax" href="/messages?type=${filterType}&start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/messages?type=${filterType}&start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>
