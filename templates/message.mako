<%! from social import utils, _, __, plugins, constants %>
<%! import re, pytz %>
<%! import email.utils %>
<%! import datetime; import dateutil.relativedelta%>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%inherit file="base.mako"/>

<%def name="nav_menu()">
  <%
    specialFolders = ["sent", "inbox", "trash", "drafts", "archives"]
    def navMenuItem(link, text, icon):
        return '<li><a href="%(link)s" class="ajax busy-indicator"><span class="sidemenu-icon icon %(icon)s-icon"></span><span class="sidemenu-text">%(text)s</span></a></li>' % locals()

  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
        ${navMenuItem("/messages?fid=INBOX", _("Inbox"), "")}
        ${navMenuItem("/messages?fid=ARCHIVES", _("Archives"), "")}
        ${navMenuItem("/messages?fid=TRASH", _("Trash"), "")}
        ${navMenuItem("/messages?fid=SENT", _("Sent"), "")}
        <!--${navMenuItem("/messages?fid=DRAFTS", _("Drafts"), "")}-->
    </ul>
    <ul id="mymenu" class="v-links sidemenu">
        % for folderId in folders:
          % if folders[folderId]['label'].lower() not in specialFolders:
            ${navMenuItem("/messages?fid=%s"%(folderId), _(folders[folderId]['label']), "")}
          % endif
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
        <div class="center-contents" style="padding:10px 0 0">
          ${self.center()}
        </div>
      </div>
    </div>
  </div>
</%def>

<%!
  def newlinescape(text):
      return text.replace("\n", "<br>")
%>

<%!
  def nameinemail(text):
      return email.utils.parseaddr(text)[0]
%>

<%!
    def formatBodyForReply(message, reply):
      body = message['body']
      sender = message['From']
      date = message['Date']
      quoted_reply = "\n".join([">%s" %x for x in body.split('\n')]+['>'])
      prequotestring = "On %s, %s wrote" %(date, sender)
      new_reply = "\n%s\n\n%s\n%s" %(reply, prequotestring, quoted_reply)
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

<%def name="messages_layout(id, conversation, fid)">
  <div id="conv-${id}" class="conv-item">
    <div style="display:table-cell;vertical-align:top">
      <input type="checkbox" name="selected" value="${id}"/>
    </div>
    <div style="display:table-cell;vertical-align:top">
      <a>
        % if conversation["flags"]["star"] == "0":
          <img height="16" width="16" src="/public/images/star-empty.png">
        % else:
          <img height="16" width="16" src="/public/images/star.png">
        % endif
      </a>
    </div>
    <div style="display:table-cell;width:100%;padding-top:3px">
      <div style="display:table;width:100%">
      <div style="display:table-cell;width:80px">${conversation["From"]|nameinemail}</div>
      <div style="display:table-cell;width:130px">
        % if len(conversation["people"]) <= 2:
          ${", ".join(conversation["people"])}
        % else:
          ${", ".join(conversation["people"][:2])} and ${len(conversation["people"])-2} others
        % endif
      </div>
      <div style="display:table-cell;width:250px">
        % if conversation["flags"]["read"] == "0":
          <a style="font-weight:bold" href="/messages/thread?id=${conversation['message-id']}&fid=${fid}">${conversation["Subject"]|h}</a>
        % else:
          <a style="font-weight:normal" href="/messages/thread?id=${conversation['message-id']}&fid=${fid}">${conversation["Subject"]|h}</a>
        % endif
      </div>
      <abbr style="display:table-cell;width:130px">
        ${conversation["date_epoch"]|timeElapsedSince}
      </abbr>
      </div>
    </div>
  </div>
</%def>

<%def name="message_layout(mid, message, flags, fid)">
    <div style="padding:4px 10px">
      <h2 style="display:inline">${message["Subject"]|h}</h2>
      <a style="display:inline-block;float:right">
        % if flags["star"] == "0":
          <img width="16" height="16" src="/public/images/star-empty.png">
        %else:
          <img width="16" height="16" src="/public/images/star.png">
        % endif
      </a>
    </div>
    <div style="padding:4px 10px;background-color:#CCCCCC">
      % if len(message["people"]) <= 2:
        <span>${message["From"]|nameinemail} wrote to ${", ".join(message["people"][:2])}</span>
      % else:
        <span>${message["From"]|nameinemail} wrote to ${", ".join(message["people"][:2])} and ${len(message["people"])-2} others</span>
      % endif
      <span style="float:right">${message["date_epoch"]|timeElapsedSince}</span>
    </div>
    <div style="display:block;padding:4px 10px;background-color:#CCCCCC">
      <a style="padding:3px" href="/messages/write?parent=${message["message-id"]}">Reply</a>
      <a style="padding:3px" href="/messages/write?parent=${message["message-id"]}&action=forward">Forward</a>
    </div>
    <div style="margin:0;padding:10px">${message["body"] | newlinescape}</div>
    <input type="hidden" name="parent" value="${message["message-id"]}">
</%def>

<%def name="conversation_layout(conversation, inline=False, isFeed=False)">

</%def>

<%def name="composer_layout(view, msg)">
    <div style="background-color:#e0ecff">
        % if msg:
          <div style="display:table-row">
            <div style="display:table-cell;vertical-align:top;font-weight:bold">Recipients</div>
            <div style="display:table-cell;width:100%">
              <textarea style="width:99%;font-size:11px" name="recipients" placeholder="${_('Enter your colleagues name or email address') |h}">${msg['From']}</textarea>
            </div>
          </div>
          <div style="display:table-row">
            <div style="display:table-cell;vertical-align:top;font-weight:bold">Subject</div>
            <div style="display:table-cell;width:100%">
              % if view == "reply":
                <input style="width:99%;font-size:11px" type="text" name="subject" value="${formatSubjectForReply(msg['Subject'])}" placeholder="${_('Enter a subject of your message') |h}"/>
              % elif view == "forward":
                <input style="width:99%;font-size:11px" type="text" name="subject" value="${formatSubjectForForward(msg['Subject'])}" placeholder="${_('Enter a subject of your message') |h}"/>
              % endif
            </div>
          </div>
          % if view == "reply":
            <textarea style="width:99%;height:400px;font-size:11px" name="body">${formatBodyForReply(msg, "")}</textarea>
            <input type="hidden" value="${msg["message-id"]}" name="parent">
          % else:
            <textarea style="width:99%;height:400px;font-size:11px" name="body">${formatBodyForForward(msg)}</textarea>
          % endif
        % else:
          <div style="display:table-row">
            <div style="display:table-cell;vertical-align:top;font-weight:bold">Recipients</div>
            <div style="display:table-cell;width:100%">
              <textarea style="width:99%;font-size:11px" type="text" name="recipients" placeholder="${_('Enter name or email address') |h}"></textarea>
            </div>
          </div>
          <div style="display:table-row">
            <div style="display:table-cell;vertical-align:top;font-weight:bold">Subject</div>
            <div style="display:table-cell;width:100%">
              <input style="width:99%;font-size:11px" type="text" name="subject" placeholder="${_('Enter a subject of your message') |h}"/>
            </div>
          </div>
          <textarea style="width:99%;height:400px;font-size:11px" placeholder="Write a message to your friends and colleagues" name="body"></textarea>
        % endif
    </div>
    <div style="background-color:#e0ecff">
      <input type="submit" name="send" value="Send">
    </div>
</%def>

<%def name="quick_reply_layout(msg)">
    <div style="background-color:#e0ecff">
      <div style="background-color:#c3d9ff"><b>Quick Reply</b></div>
      <div>
          <textarea style="width:80ex;height:100px" name="body"></textarea>
          <input type="hidden" value="${msg["message-id"]}" name="parent"/>
          <input type="hidden" value="${formatSubjectForReply(msg['Subject'])}" name="subject"/>
          <input type="hidden" value="${msg["From"]}" name="recipients"/>
      </div>
    </div>
    <div style="background-color:#e0ecff">
      <input type="submit" name="send" value="Send">
    </div>
</%def>

<%def name="toolbar_layout(view, fid=None, message=None)">
  % if view == "messages":
    <div style="background-color:#C3D9FF;padding-bottom:10px">
      % if fid:
        <b style="float:right;padding:4px">Viewing ${_(folders[fid]['label'])}</b>
      % endif
      <a style="padding:3px;color:white" href="/messages/write">New Message</a>
      <input type="submit" name="delete" value="Delete">
      <input type="submit" name="archive" value="Archive">
    </div>
  % elif view == "message":
    <div style="background-color:#C3D9FF">
        <a style="padding:3px" href="/messages?fid=${fid}">Go Back</a>
        <input type="submit" name="delete" value="Delete">
        <input type="submit" name="archive" value="Archive">
        <select name="more">
          <option value="">More Actions</option>
          <option value="star">Add Star</option>
          <option value="unstar">Remove Star</option>
          <option value="read">Mark as Read</option>
          <option value="unread">Mark as Unread</option>
        </select>
        <input type="submit" value="Go" name="other">
        <span class="clear" style="display:block"></span>
    </div>
  %elif view == "compose":
    <div style="background-color:#C3D9FF;padding:3px 0">
      <a style="padding:3px;font-weight:bold" href="/messages?fid=${fid}">Go Back</a>
    </div>
  % elif view == "reply":
    <div style="background-color:#C3D9FF;padding:3px 0">
      <a style="padding:3px;font-weight:bold" href="/messages?fid=${fid}">Go Back</a>
    </div>
  % endif
</%def>

<%def name="navigation_layout(view, start, end, fid)">
  % if view == "messages":
    <div style="display:table-row;float:right">
      <ul class="h-links">
        % if start !=0:
          %if fid:
            <li style="padding: 0pt 4px;"><a href="/messages?start=${start}&fid=${fid}&back=True">Back</a></li>
          %else:
            <li style="padding: 0pt 4px;"><a href="/messages?start=${start}&back=True">Back</a></li>
          %endif
        % endif
        % if end != 0:
          % if fid:
            <li style="padding: 0pt 4px;"><a href="/messages?start=${end}&fid=${fid}">Next</a></li>
          %else:
            <li style="padding: 0pt 4px;"><a href="/messages?start=${end}">Next</a></li>
          %endif
        % endif
      </ul>
    </div>
    <span class="clear" style="display:block"></span>
  % endif
</%def>

<%def name="center()">
  % if view == "conversations":
    %for conversation in conversations:
      ${conversation_layout(conversation, msgs_map, True, True)}
    %endfor
  %elif view == "messages":
    <form method="post" action="/messages">
    ${toolbar_layout(view, fid)}
    ${navigation_layout(view, start, end, fid)}
    %for mid in mids:
      ${messages_layout(mid, messages[mid], fid)}
    %endfor
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
  %elif view == "message":
    <form method="post" action="/messages/thread">
    ${toolbar_layout(view, message=message, fid=fid)}
    ${message_layout(id, message, flags, fid)}
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
    <form method="post" action="/messages/write">
    ${quick_reply_layout(message)}
    <input type="hidden" name="fid" value="${fid}"/>
    </form>
  %elif view == "compose":
    <form method="post" action="/messages/write">
    ${toolbar_layout(view, fid=fid)}
    ${composer_layout(view, None)}
    </form>
  %elif view == "reply":
    <form method="post" action="/messages/write">
    ${toolbar_layout(view, fid=fid, message=parent_msg)}
    ${composer_layout(view, parent_msg)}
    </form>
  %elif view == "forward":
    <form method="post" action="/messages/write">
    ${toolbar_layout("reply", fid=fid, message=parent_msg)}
    ${composer_layout(view, parent_msg)}
    </form>
  %endif
</%def>
