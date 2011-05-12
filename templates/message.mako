<%! from social import utils, _, __, plugins, constants %>
<%! import re, pytz %>
<%! import email.utils %>
<%! import cgi %>
<%! import datetime; import dateutil.relativedelta%>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%inherit file="base.mako"/>

<%def name="nav_menu()">
  <%
    SENT, INBOX, TRASH, DRAFTS, ARCHIVES = "", "", "", "", ""

    customFolders = {}
    for fId, fInfo in folders.iteritems():
        if ("special" in fInfo) and (fInfo["special"] == "INBOX"):
          INBOX = fId
        elif ("special" in fInfo) and (fInfo["special"] == "SENT"):
          SENT = fId
        elif ("special" in fInfo) and (fInfo["special"] == "TRASH"):
          TRASH = fId
        elif ("special" in fInfo) and (fInfo["special"] == "DRAFTS"):
          DRAFTS = fId
        elif ("special" in fInfo) and (fInfo["special"] == "ARCHIVES"):
          ARCHIVES = fId
        else:
          customFolders[fId] = fInfo

    def navMenuItem(id, link, text, icon, selected=False):
      if selected: style = "sidemenu-selected"
      else: style = ""
      return """
              <li id="%(id)s" class="%(style)s">
                <a href="%(link)s" class="ajax busy-indicator">
                  <span class="sidemenu-icon messaging-icon %(icon)s-icon"></span>
                  <span class="sidemenu-text">%(text)s</span>
                </a>
              </li>
              """ % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul class="v-links sidemenu">
      ${navMenuItem("home", "/feed", _("Back to Home"), "back")}
    </ul>
    <ul class="v-links sidemenu">
      ${navMenuItem("compose", "/messages/write", _("Compose"), "compose")}
    </ul>
    <ul id="sfmenu" class="v-links sidemenu">
        ${navMenuItem(INBOX, "/messages?fid=%s" %(INBOX), _("Inbox"), "inbox", fid==INBOX)}
        ${navMenuItem(ARCHIVES, "/messages?fid=%s" %(ARCHIVES), _("Archives"), "archive", fid==ARCHIVES)}
        ${navMenuItem(SENT, "/messages?fid=%s" %(SENT), _("Sent"), "sent", fid==SENT)}
        ${navMenuItem(TRASH, "/messages?fid=%s" %(TRASH), _("Trash"), "trash", fid==TRASH)}
    </ul>
    <ul id="ufmenu" class="v-links sidemenu">
        % for folderId in customFolders.keys():
            ${navMenuItem(folderId, "/messages?fid=%s"%(folderId),
              _(folders[folderId]['label']), "", folderId == fid)}
        % endfor
    </ul>
  </div>
</%def>


<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right"></div>
      <div id="center">
        <div class="center-contents" style="padding:0">
          ${self.center()}
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
  def formatPeopleInConversation(message, short=False):
    recipients = message["To"].split(",")
    senderEmailId = email.utils.parseaddr(message["From"])[1]
    rStrings = []
    for each in recipients:
        emailId = email.utils.parseaddr(each)[1]
        if not short:
            estring = "<a href='/profile?id=%s'>%s</a>" %(message["people"][emailId]["uid"],
                                                          message["people"][emailId]["basic"]["name"])
        else:
            if emailId != senderEmailId:
                estring = "<span>%s</span>" %(message["people"][emailId]["basic"]["name"])
            else:
                continue
        if emailId == message["people"]["self"]:
            estring = "<span>%s</span>" %("Me")

        rStrings.append(estring)

    if short:
        sString = "<span>%s</span>" %(message["people"][senderEmailId]["basic"]["name"])
    else:
        sString = "<a href='/profile?id=%s'>%s</a>" %(message["people"][senderEmailId]["uid"],
                                                      message["people"][senderEmailId]["basic"]["name"])

    if short:
        rString = ", ".join(set(rStrings))
        finalString = "%s, %s" %(sString, rString) if len(rStrings) > 0 else sString
    else:
        rString = ", ".join(set(rStrings))
        finalString = "%s Wrote to %s" %(sString, rString)

    return finalString
%>

<%!
    def formatRecipientList(message):
        recipients = (message["From"]+", "+message["To"]).split(",")
        rStrings = []
        for each in recipients:
            emailId = email.utils.parseaddr(each)[1]
            if not emailId == message["people"]["self"]:
                rStrings.append("%s <%s>" %(message["people"][emailId]["basic"]["name"],
                                            emailId))

        return ", ".join(set(rStrings))
%>

<%!
    def formatBodyForReply(message, reply):
      body = message['body']
      sender = message['From']
      date = message['Date']
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
    def formatSubjectForReply(subject):
      reply_re = r"""(?i)^Re:\s+\w"""
      match = re.search(reply_re, subject)
      if match:
        return subject
      else:
        return "%s %s" %("Re:", subject.strip())
%>

<%!
    def formatSubjectForForward(subject):
      reply_re = r"""(?i)^Re|Fwd:\s+\w"""
      match = re.search(reply_re, subject)
      if match:
        return "%s %s" %("Fwd:", subject.strip("Re:"))
      else:
        return "%s %s" %("Fwd:", subject.strip())
%>

<%!
    def formatBodyForViewing(text):
        lines = text.split("\r\n")
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
    elif rc.years < 0:
        fmt = "%b %d, at %I:%M%p"
        date = dt.strftime(fmt)
        return "%s" %date
    else:
      fmt = "%x at %X"
      date = dt.strftime(fmt)
      return "%s" %date
%>

<%def name="messages_layout(script, mid, thread, fid)">
  <div id="thread-${mid}" class="message-row ${'row-unread' if thread["flags"]["read"] == "0" else 'row-read'}">
    <div class="message-row-cell message-row-select">
      <input type="checkbox" name="selected" value="${mid}"/>
    </div>
    <div class="message-row-cell message-row-star">
      <a>
        % if thread["flags"]["star"] == "0":
          <span onclick="$.post('/ajax/messages', 'fid=${fid}&action=star&selected=${mid}', null, 'script')" class="messaging-icon star-empty-icon"> </span>
        % else:
          <span onclick="$.post('/ajax/messages', 'fid=${fid}&action=unstar&selected=${mid}', null, 'script')" class="messaging-icon star-icon"> </span>
        % endif
      </a>
    </div>
    <div class="message-row-cell" style="width:210px">${formatPeopleInConversation(thread, True)}</div>
    <div class="message-row-cell" style="width:450px">
      <a class="${'ajax' if script else ''} message-link" href="/messages/thread?id=${thread['message-id']}&fid=${fid}">${thread["Subject"]|h}</a>
    </div>
    <abbr class="message-row-cell time-label" style="width:130px">
      ${thread["date_epoch"]|timeElapsedSince}
    </abbr>
  </div>
</%def>

<%def name="message_layout(mid, message, flags, fid)">
    <div class="message-headline">
      <h2 class="message-headline-subject">${message["Subject"]|h}</h2>
      % if flags["star"] == "0":
        <span class="message-headline-star ajax" onclick="$.post('/ajax/messages/thread', 'fid=${fid}&action=star&message=${mid}', null, 'script')" href="#">
          <span class="messaging-icon star-empty-icon"> </span>
        </span>
      %else:
        <span class="message-headline-star ajax"  onclick="$.post('/ajax/messages/thread', 'fid=${fid}&action=unstar&message=${mid}', null, 'script')" href="#">
          <span class="messaging-icon star-icon"> </span>
        </span>
      % endif
    </div>
    <div class="message-headers">
      <span class="message-headers-people">
        <%
            emailId = email.utils.parseaddr(message["From"])[1]
            avatarURI = utils.userAvatar(message["people"][emailId]["uid"], message["people"][emailId]["basic"])
        %>
        %if avatarURI:
          <img src="${avatarURI}" height="48" width="48" style="display:inline-block"/>
        %endif
        <span class="message-headers-people-list">${formatPeopleInConversation(message)}</span>
      </span>
      <span class="time-label message-headers-time">${message["date_epoch"]|timeElapsedSince}</span>
    </div>
    <div class="message-message">${message["body"] | newlinescape}</div>
    <input type="hidden" name="message" value="${message["message-id"]}"/>
    <input type="hidden" name="_body" value="${formatBodyForReply(message, "")}"/>
</%def>

<%def name="thread_layout(thread, inline=False, isFeed=False)">

</%def>

<%def name="composer_layout(script, view, msg, fid)">
    <div class="message-composer">
        % if msg:
          <div class="message-composer-row">
            <div class="message-composer-label">Recipients</div>
            <div class="message-composer-field">
              <textarea class="message-composer-field-recipient" name="recipients" placeholder="${_('Enter your colleagues name or email address') |h}">${msg['From']}</textarea>
            </div>
          </div>
          <div class="message-composer-row">
            <div class="message-composer-label">Subject</div>
            <div class="message-composer-field">
              % if view == "reply":
                <input class="message-composer-field-subject" type="text" name="subject" value="${formatSubjectForReply(msg['Subject'])}" placeholder="${_('Enter a subject of your message') |h}"/>
              % elif view == "forward":
                <input class="message-composer-field-subject" type="text" name="subject" value="${formatSubjectForForward(msg['Subject'])}" placeholder="${_('Enter a subject of your message') |h}"/>
              % endif
            </div>
          </div>
          % if view == "reply":
            <textarea class="message-composer-field-body" name="body">${formatBodyForReply(msg, "")}</textarea>
            <input type="hidden" value="${msg["message-id"]}" name="parent">
          % else:
            <textarea class="message-composer-field-body" name="body">${formatBodyForForward(msg)}</textarea>
          % endif
        % else:
          <div class="message-composer-row">
            <div class="message-composer-label">Recipients</div>
            <div class="message-composer-field">
              <textarea class="message-composer-field-recipient" type="text" name="recipients" placeholder="${_('Enter name or email address') |h}"></textarea>
            </div>
          </div>
          <div class="message-composer-row">
            <div class="message-composer-label">Subject</div>
            <div class="message-composer-field">
              <input class="message-composer-field-subject" type="text" name="subject" placeholder="${_('Enter a subject of your message') |h}"/>
            </div>
          </div>
          <div class="message-composer-field-body-wrapper">
            <textarea class="message-composer-field-body" placeholder="Write a message to your friends and colleagues" name="body"></textarea>
          </div>
        % endif
      <div class="message-composer-row">
        <ul class="middle user-actions h-links message-composer-field">
          <li class="button">
            <input type="submit" name="send" value="Send" class="button default">
          </li>
          <li class="button">
            % if msg:
              <a class="ajax" href="/messages/thread?id=${msg['message-id']}&fid=${fid}">Cancel</a>
            % else:
              <a class="ajax" href="/messages?fid=${fid}">Cancel</a>
            % endif
          </li>
        </ul>
      </div>
    </div>
</%def>

<%def name="quick_reply_layout(script, msg)">
  <div class="message-composer">
    <div class="message-composer-quick-actions">
      <a href="#" onclick="$('textarea[class=message-composer-field-body-quick]').attr('value', $('input[name=_body]').attr('value'))">
        Quote Message
      </a>
    </div>
    <div class="message-composer-field-body-wrapper">
        <textarea class="message-composer-field-body-quick" name="body" placeholder="Quickly reply to this message"></textarea>
        <input type="hidden" value="${msg["message-id"]}" name="parent"/>
        <input type="hidden" value="${formatSubjectForReply(msg['Subject'])}" name="subject"/>
        <input type="hidden" value="${formatRecipientList(msg)}" name="recipients"/>
    </div>
    <div class="message-composer-field">
      <input type="submit" name="send" value="${_('Reply')}" class="button ">
    </div>
  </div>
</%def>

<%def name="toolbar_layout(script, view, fid, message=None)">
  % if view == "messages":
    <div class="toolbar">
      <input type="submit" name="delete" value="Delete" class="button "/>
      <input type="submit" name="archive" value="Archive" class="button "/>
    </div>
  % elif view == "message":
    <div class="toolbar">
        <a class="${'ajax' if script else ''} action-link" href="/messages?fid=${fid}">Go Back</a>
        <input type="submit" name="delete" value="Delete" class="button "/>
        <input type="submit" name="archive" value="Archive" class="button "/>
        % if script:
            <input type="submit" name="unread" value="Mark as Unread" class="button "/>
        % else:
            <select name="action" class="button ">
              <option value="">More Actions</option>
              <option value="star">Add Star</option>
              <option value="unstar">Remove Star</option>
              <option value="unread">Mark as Unread</option>
            </select>
            <input type="submit" value="Go" name="other" class="button ">
        % endif
        <span class="clear" style="display:block"></span>
    </div>
  %elif view == "compose":
    <div class="toolbar">
      <a class="${'ajax' if script else ''} action-link" href="/messages?fid=${fid}">Go Back</a>
    </div>
  % elif view == "reply":
    <div class="toolbar">
      <a class="${'ajax' if script else ''} action-link" href="/messages/thread?id=${message['message-id']}&fid=${fid}">Go Back</a>
    </div>
  % elif view == "forward":
    <div class="toolbar">
      <a class="${'ajax' if script else ''} action-link" href="/messages/thread?id=${message['message-id']}&fid=${fid}">Go Back</a>
    </div>
  % endif
</%def>

<%def name="navigation_layout(script, view, start, end, fid)">
  % if view == "messages":
    <div style="display:table-row;float:right">
      <ul class="h-links">
        % if start !=0:
          %if fid:
            <li style="padding: 0pt 4px;"><a class="${'ajax' if script else ''}" href="/messages?start=${start}&fid=${fid}&back=True">Back</a></li>
          %else:
            <li style="padding: 0pt 4px;"><a class="${'ajax' if script else ''}" href="/messages?start=${start}&back=True">Back</a></li>
          %endif
        % endif
        % if end != 0:
          % if fid:
            <li style="padding: 0pt 4px;"><a class="${'ajax' if script else ''}" href="/messages?start=${end}&fid=${fid}">Next</a></li>
          %else:
            <li style="padding: 0pt 4px;"><a class="${'ajax' if script else ''}" href="/messages?start=${end}">Next</a></li>
          %endif
        % endif
      </ul>
    </div>
    <span class="clear" style="display:block"></span>
  % endif
</%def>

<%def name="center()">
  % if view == "threads":
    %for thread in threads:
      ${thread_layout(thread, msgs_map, True, True)}
    %endfor
  %elif view == "messages":
    <form method="post" action="/messages">
    ${toolbar_layout(script, view, fid)}
    ${navigation_layout(script, view, start, end, fid)}
    %for mid in mids:
      ${messages_layout(script, mid, messages[mid], fid)}
    %endfor
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
  %elif view == "message":
    <form method="post" action="/messages/thread">
    ${toolbar_layout(script, view, fid, message=message)}
    ${message_layout(id, message, flags, fid)}
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
    <form method="post" action="/messages/write">
    ${quick_reply_layout(script, message)}
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
  %elif view == "compose":
    <form method="post" action="/messages/write">
    ${toolbar_layout(script, view, fid)}
    ${composer_layout(script, view, None, fid)}
    </form>
  %elif view == "reply":
    <form method="post" action="/messages/write">
    ${toolbar_layout(script, view, fid, message=parent_msg)}
    ${composer_layout(script, view, parent_msg, fid)}
    </form>
  %elif view == "forward":
    <form method="post" action="/messages/write">
    ${toolbar_layout(script, "reply", fid, message=parent_msg)}
    ${composer_layout(script, view, parent_msg, fid)}
    </form>
  %endif
</%def>

<%def name="render_message_headline_star(action, mid, fid)">
  %if action == "star":
    <span class="message-headline-star ajax"  onclick="$.post('/ajax/messages/thread', 'fid=${fid}&action=unstar&message=${mid}', null, 'script')" href="#">
      <span class="messaging-icon star-icon"> </span>
    </span>
  %else:
    <span class="message-headline-star ajax" onclick="$.post('/ajax/messages/thread', 'fid=${fid}&action=star&message=${mid}', null, 'script')" href="#">
      <span class="messaging-icon star-empty-icon"> </span>
    </span>
  %endif
</%def>
