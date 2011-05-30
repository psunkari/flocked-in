<%! from social import utils, _, __, constants %>
<%! import re %>
<%! import cgi %>
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
    return utils.normalizeText(cgi.escape(text))
%>

<%!
  def makeSnippet(body):
    lines = body.split("\n")
    snippet = ""
    for line in lines:
        if not line.startswith(">") or not "wrote:" in line:
            snippet = line[:120]
            break
        else:
            continue
    return snippet
%>

<%!
  def formatPeopleInConversation(conv, people_info):
    participants = conv["people"]
    sender = people_info[conv["meta"]["owner"]]["basic"]["name"]
    people_without_sender = set(participants) - set([sender,])
    last_sent_by = people_info[list(people_without_sender)[-1]]["basic"]["name"]

    if len(people_without_sender) > 2:
        return "%s...%s(%d)" %(sender, last_sent_by, len(participants))
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
            <div style="display:inline-block;padding:2px;width:635px"
                 onclick="var url='/messages/thread?id=${convId}';$.address.value(url); $$.fetchUri(url); ">
                <span style="padding:4px 0 0 4px;width:150px">${formatPeopleInConversation(conv, people)}</span>
                <span style="width:450px;font-size:11px;color:#777;padding-left:4px">${utils.simpleTimestamp(float(conv['meta']["date_epoch"]), people[myKey]["basic"]["timezone"])}</span>
            </div>
            <div style="display:inline-block;padding:2px">
                <span>
                    %if filterType != "unread":
                    <%
                      readStatus = 'unread' if conv['read']=='0' else 'read'
                      readAction = 'read' if conv['read']=='0' else 'unread'
                    %>
                    <div class="messaging-icon messaging-${readStatus}-icon"
                         title="Mark this conversation as ${readAction}"
                         onclick="$.post('/ajax/messages/thread', 'action=${readAction}&selected=${convId}&filterType=${filterType}', null, 'script')">&nbsp</div>
                    %elif filterType == "unread":
                    <div class="messaging-icon messaging-unread-icon"
                         title="Mark this conversation as read"
                         onclick="$.post('/ajax/messages/thread', 'action=read&selected=${convId}&filterType=${filterType}', null, 'script')">&nbsp</div>
                    %endif
                    %if filterType != "archive":
                    <div class="messaging-icon messaging-archive-icon"
                         title="Archive this conversation"
                         onclick="$.post('/ajax/messages/thread', 'action=archive&selected=${convId}&filterType=${filterType}', null, 'script')">&nbsp</div>
                    %endif
                    %if filterType != "trash":
                    <div class="messaging-icon messaging-delete-icon"
                         title="Delete this conversation"
                         onclick="$.post('/ajax/messages/thread', 'action=trash&selected=${convId}&filterType=${filterType}', null, 'script')">&nbsp</div>
                    %endif
                </span>
            </div>
            <a class="ajax message-link" href="/messages/thread?id=${convId}" style="display:block;padding:2px;position:relative">
                <div style="overflow: hidden;white-space: nowrap;width: 667px;color:#777;">
                    <span style="color:#000">${conv["meta"]["subject"]|h}</span> - ${conv["meta"]["snippet"]}
                </div>
                <span style="position:absolute;right:1px;bottom:-4px;cursor:default;color:#000">
                    <span title="There are ${conv['count']} messages in this conversation">${conv['count']}</span>
                </span>
            </a>
        </div>
    </div>
  </div>
</%def>

<%def name="render_conversation()">
    ${toolbar_layout(view)}
    <div class="conversation-headline">
        <h2 class="conversation-headline-subject">${conv["meta"]["subject"]|h}</h2>
    </div>
    <div class="conversation-wrapper">
        <div class="conversation-messages-wrapper">
            ${render_conversation_messages()}
        </div>
        ${render_conversation_reply(script, messages[messageIds[-1]], id)}
    </div>
</%def>

<%def name="render_conversation_messages()">
    % for mid in messageIds:
        <div class="conversation-message-wrapper" style="padding:2px; margin:2px; border:1px solid #E2e2e2">
          <div class="comment-avatar">
            ${getSenderAvatar(messages[mid], people, "s")}
          </div>
          <div class="comment-container" style="padding-top:0px;min-height:32px;padding-bottom:0px">
            <div class="conv-summary">
              <div class="message-headers" onclick="var _self=this;$(this).siblings().toggle(1, function(){$(_self).children('.message-headers-snippet').toggleClass('message-headers-snippet-show')});">
                <div class="user message-headers-sender">
                  <a href="/profile?id=${messages[mid]['meta']['owner']}" class="ajax">
                    ${people[messages[mid]['meta']['owner']]["basic"]["name"]}
                  </a>
                </div>
                <div class="message-headers-snippet">${messages[mid]["meta"].get("body", '') | makeSnippet}</div>
                <nobr class="time-label message-headers-time">${utils.simpleTimestamp(float(messages[mid]["meta"]["date_epoch"]), people[myKey]["basic"]["timezone"])}</nobr>
              </div>
              <div class="message-message">
                ${messages[mid]["meta"].get("body", '') | newlinescape}
              </div>
            </div>
          </div>
        </div>
    % endfor
</%def>

<%def name="render_conversation_reply(script, msg, convId)">
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

<%def name="render_composer()">
  <div class="message-composer">
    <form method="post" action="/messages/write" class="ajax" onsubmit="return false">
      <div class="input-wrap message-composer-field">
        <div class="message-composer-recipients"></div>
        <input class="message-composer-field-recipient" type="text" placeholder="${_('Enter name or email address') |h}"/>
      </div>
      <div class="input-wrap message-composer-field">
        <input class="message-composer-field-subject" type="text" name="subject" placeholder="${_('Enter a subject of your message') |h}"/>
      </div>
      <div class="input-wrap message-composer-field">
        <textarea class="message-composer-field-body" placeholder="Write a message to your friends and colleagues" name="body"></textarea>
      </div>
      <div style="text-align:right;padding:4px 0">
        %if script:
            <%
                onclickscript = """
                    var recipients = $('.message-composer-recipients').data('recipients');
                    var subject = $('.message-composer-field-subject').attr('value');
                    var body = $('.message-composer-field-body').attr('value');
                    var urlpostdata = 'recipients='+recipients+'&subject='+subject+'&body='+body;
                    $.post('/ajax/messages/write', urlpostdata, null, 'script')
                    $('#composer').empty()
            """%>
            <button type="button" class="button default" onclick="${onclickscript}">
                ${_('Send')}
            </button>
            <button type="button" class="button" onclick="$('#composer').empty()">
                ${'Cancel'}
            </button>
        %else:
            <a class="ajax" _ref="/messages">${'Cancel'}</a>
        %endif
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
            <input id="toolbarAction" name="action" value="" type="hidden"/>
          %endif
          %if filterType != "trash":
            <input type="submit" name="trash" value="Trash" class="button" onclick="$('#toolbarAction').attr('value', 'trash')"/>
          %endif
          %if filterType != "archive" and filterType != "trash":
            <input type="submit" name="archive" value="Archive" class="button" onclick="$('#toolbarAction').attr('value', 'archive')"/>
          %endif
          %if filterType != "unread":
            <input type="submit" name="unread" value="Mark as Unread" class="button" onclick="$('#toolbarAction').attr('value', 'unread')"/>
          %endif
          %if filterType != "all":
            <input type="submit" name="inbox" value="Move to Inbox" class="button" onclick="$('#toolbarAction').attr('value', 'inbox')"/>
          %endif
    </div>
  %elif view == "message":
    <div id="msg-toolbar" class="toolbar">
      <a class="${'ajax' if script else ''} back-link" href="/messages">Go Back</a>
        <form method="post" action="/messages/thread">
            <input type="hidden" name="selected" value="${id}"/>
            <input id="toolbarAction" name="action" value="" type="hidden"/>
            <input type="submit" name="trash" value="Trash" class="button" onclick="$('#toolbarAction').attr('value', 'trash')"/>
            <input type="submit" name="archive" value="Archive" class="button" onclick="$('#toolbarAction').attr('value', 'archive')"/>
            <input type="submit" name="unread" value="Mark as Unread" class="button" onclick="$('#toolbarAction').attr('value', 'unread')"/>
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
    <form action="/messages/thread" method="post">
        ${toolbar_layout(view, nextPageStart, prevPageStart)}
        <div class="conversation-layout-container">
            %for mid in mids:
              ${render_conversation_row(script, mid, messages[mid])}
            %endfor
        </div>
        <input type="hidden" name="filterType" value="${filterType}"/>
    </form>
  </div>
  <div id="people-paging" class="pagingbar" style="margin-top:0">
      ${paging()}
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
            <ul class="v-links peoplemenu middle user-subactions">
                <li>
                    <%
                       toggleMessagesScript = """
                          var isExpand = $(this).data('isExpand')
                          console.log(isExpand)
                          $('.message-message').not(':last').each(function(i, v){
                            if (isExpand == true){
                                $(v).show();
                                $(v).siblings().children('.message-headers-snippet').
                                   removeClass('message-headers-snippet-show');
                                $('#expandAll').html('Collapse All');
                            }
                            else{
                                $(v).hide();
                                $(v).siblings().children('.message-headers-snippet').
                                   addClass('message-headers-snippet-show');
                                $('#expandAll').html('Expand All');
                            }
                          });
                          $(this).data('isExpand', !isExpand)
                          """
                    %>
                    <a id="expandAll" href="#" onclick="${toggleMessagesScript}; $.event.fix(event).preventDefault();">Expand All</a>
                </li>
            </ul>
        </div>
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
                    <input type="hidden" name="recipients" id="conversation_recipients"/>
                    <div class="input-wrap">
                        <input type="text" placeHolder="Your friend's name" id="conversation_add_member"/>
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
