<%! from social import utils, _, __, plugins, constants %>
<%! import re, pytz %>
<%! import email.utils %>
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
          ${self.feed()}
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
      new_reply = "%s\n\n%s\n%s" %(reply, prequotestring, quoted_reply)
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
        return "Today at %s" %date
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

<%def name="messages_layout(id, conversation)">
  <div id="conv-${id}" class="conv-item">
    <div style="display:table-cell;vertical-align:top"><input type="checkbox" selected/></div>
    <div style="display:table-cell;width:100%">
      <div style="display:table;width:100%">
      <div style="display:table-cell;width:100px">${conversation["From"]|nameinemail}</div>
      % if len(conversation["people"]) <= 2:
        <div style="display:table-cell;width:130px">${", ".join(conversation["people"])}</div>
      % else:
        <div style="display:table-cell;width:130px">${", ".join(conversation["people"][:2])} and ${len(conversation["people"])-2} others</div>
      % endif
      <div style="display:table-cell;width:250px">
        <a href="/messages/thread?id=${conversation['message-id']}">${conversation["Subject"]|h}</a>
      </div>
      <abbr style="display:table-cell;width:130px" class="timestamp" _ts=${conversation["date_epoch"]}>
        ${conversation["date_epoch"]|timeElapsedSince}
      </abbr>
      </div>
    </div>
  </div>
</%def>

<%def name="message_layout(mid, message)">
    <div><h2>${message["Subject"]|h}</h2></div>
    % if len(message["people"]) <= 2:
      <div>${message["From"]|nameinemail} wrote to ${", ".join(message["people"][:2])}
    % else:
      <div>${message["From"]|nameinemail} wrote to ${", ".join(message["people"][:2])} and ${len(message["people"])-2} others</div>
    % endif
    <div style="display:inline-block;float:right">${message["date_epoch"]|timeElapsedSince}</div>

    <div class="conv-comment" style="margin:0">${message["body"] | newlinescape}</div>
</%def>

<%def name="conversation_layout(conversation, inline=False, isFeed=False)">
  <div id="conv-${conversation}" class="conv-item">
    <div class="conv-avatar" id="conv-avatar-${conversation}">
      %if inline or not script:
      %endif
    </div>
    <div class="conv-data">
      <div id="conv-root-${conversation}">
        %if inline or not script:
        %endif
      </div>
      <div id="item-footer-${conversation}" class="conv-footer">
        %if inline or not script:
        %endif
      </div>
      <div id="conv-comments-wrapper-${conversation}">
        %if inline or not script:
        %endif
      </div>
      <div id="comment-form-wrapper-${conversation}" class="conv-comment-form">
        %if inline or not script:
        %endif
      </div>
    </div>
  </div>
</%def>

<%def name="composer_layout(msg)">
  %if script:
    <form id="share-form" class="ajax" autocomplete="off" method="post" action="/messages/write">
      <div>
        <div>
          % if msg:
            <textarea style="width:99%" name="recipients" placeholder="${_('Enter your colleagues name or email address') |h}">${msg['From']}</textarea>
            <input style="width:99%" type="text" name="subject" value="${formatSubjectForReply(msg['Subject'])}" placeholder="${_('Enter a subject of your message') |h}"/>
            <textarea style="width:99%;height:400px" name="body">${formatBodyForReply(msg, "")}</textarea>
            <input type="hidden" value="${msg["message-id"]}" name="parent">
          % else:
            <textarea style="width:99%" type="text" name="recipients" placeholder="${_("Enter your colleague's name or email address") |h}"></textarea>
            <input style="width:99%" type="text" name="subject" placeholder="${_('Enter a subject of your message') |h}"/>
            <textarea style="width:99%;height:400px" name="body"></textarea>
          % endif
        </div>
      </div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          <li>${widgets.button("composer-submit", "submit", "default", None, "Compose")}</li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
  %endif
</%def>

<%def name="quick_reply_layout(msg)">
  %if script:
    <form id="share-form" class="ajax" autocomplete="off" method="post" action="/messages/write">
      <div id="sharebar">
        <div class="input-wrap" style="text-align:center">
            <textarea style="width:99%;height:100px" name="body"></textarea>
            <input type="hidden" value="${msg["message-id"]}" name="parent"/>
            <input type="hidden" value="${formatSubjectForReply(msg['Subject'])}" name="subject"/>
            <input type="hidden" value="${msg["From"]}" name="recipients"/>
        </div>
      </div>
      <div>
        <ul id="sharebar-actions" class="h-links">
          <li>${widgets.button("composer-submit", "submit", "default", None, "Quick Reply")}</li>
        </ul>
        <span class="clear" style="display:block"></span>
      </div>
    </form>
  %endif
</%def>

<%def name="feed()">
  % if view == "conversations":
    %for conversation in conversations:
      ${conversation_layout(conversation, msgs_map, True, True)}
    %endfor
  %elif view == "messages":
    <div style="padding-bottom:10px">
      <span>Viewing ${folder}</span>
        <ul id="sharebar-actions" class="h-links">
          <li><a href="/messages/write">Write</a></li>
          <li><a>Delete</a></li>
          <li><a>Archive</a></li>
          <li><a>Refresh</a></li>
        </ul>
        <span class="clear" style="display:block"></span>
    </div>
    %for mid in mids:
      ${messages_layout(mid, messages[mid])}
    %endfor
  %elif view == "message":
    <div>
        <ul id="sharebar-actions" class="h-links">
          % if script:
            <li><a href="javascript:history.go(-1)">Go Back</a></li>
          % else:
            <li><a href="/messages/">Go Back</a></li>
          % endif
          <li><a href="/messages/write?parent=${message["message-id"]}">Reply</a></li>
          <li><a>Delete</a></li>
          <li><a>Archive</a></li>
        </ul>
        <span class="clear" style="display:block"></span>
    </div>
    ${message_layout(id, message)}
    ${quick_reply_layout(message)}
  %elif view == "compose":
    <div>
        <ul id="sharebar-actions" class="h-links">
          % if script:
            <li><a href="javascript:history.go(-1)">Go Back</a></li>
          % else:
            <li><a href="/messages/">Go Back</a></li>
          % endif
        </ul>
        <span class="clear" style="display:block"></span>
    </div>
    ${composer_layout(None)}
  %elif view == "reply":
    <div>
        <ul id="sharebar-actions" class="h-links">
          % if script:
            <li><a href="javascript:history.go(-1)">Go Back</a></li>
          % else:
            <li><a href="/messages/">Go Back</a></li>
          % endif
        </ul>
        <span class="clear" style="display:block"></span>
    </div>
    ${composer_layout(parent_msg)}
  %endif
</%def>
