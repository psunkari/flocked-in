<%! from social import utils, _, __, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>

<%def name="share_poll()">
  <div class="input-wrap">
    <textarea name="question" placeholder="${_('What would you like to know?')}"/>
  </div>
  <div id="share-poll-options">
    <div class="input-wrap">
      <img class="icon poll-option"/>
      <input type="text" name="options" placeholder="${_('Add an option')}"/>
    </div>
    <div class="input-wrap">
      <img class="icon poll-option"/>
      <input type="text" name="options" placeholder="${_('Add an option')}"/>
    </div>
    <div class="input-wrap">
      <img class="icon poll-option"/>
      <input type="text" name="options" placeholder="${_('Add an option')}"/>
    </div>
  </div>
  <input type="hidden" name="type" value="poll"/>
</%def>

<%def name="poll_results(convId, voted=False)">
  <%
    conv = items[convId]
    question = conv["meta"]["question"]
    options = conv["options"]
    counts = conv.get("counts", {})
    if not voted:
      return
  %>
  <ul class="poll-results">
    <%
      total = 0
      for votes in counts.values():
        total += int(votes)
    %>
    %for option in options:
      <%
        count = int(counts.get(option, '0'))
        percent = (count * 100)/total
      %>
      <li>
        <div>${options[option]}</div>
        <div>
          <div class="poll-bar-wrapper">
            <div class="poll-bar option-${int(option)%10}" style="width:${percent}%;">&nbsp;</div>
          </div>
          %if percent > 0:
            <div class="poll-percent"><button class="button-link" onclick="$$.dialog.create({id:'poll-users-${option}-${convId}'});$.getScript('/ajax/poll/voters?id=${convId}&option=${option}');">${"%d%%"%percent}</button></div>
          %else:
            <div class="poll-percent"><button class="button-link">${"%d%%"%percent}</button></div>
          %endif
        </div>
      </li>
    %endfor
  </ul>
  <div class="poll-actions">
    ${_("%d total votes")%total}
    &nbsp;&#183;&nbsp;
    <a class="ajax" _ref="/poll/change?id=${convId}">${_("Change vote")}</a>
  </div>
</%def>

<%def name="poll_options(convId, voted=False)">
  <%
    conv = items[convId]
    question = conv["meta"]["question"]
    options = conv["options"]
  %>
  <form action="/poll/vote" method="POST" class="ajax">
    <div class="tabular-form poll-options">
      %for option in options:
        <%
          checked = 'checked="true"' if (voted and voted == option) else ''
          optionId = 'option-%s-%s' % (option, convId)
        %>
        <ul>
          <li><input type="radio" name="option" value="${option}" id="${optionId}" ${checked}/></li>
          <li><label for="${optionId}">${options[option]}</label></li>
        </ul>
      %endfor
      </div>
      <input type="hidden" name="id" value="${convId}"/>
      %if voted:
        <input type="submit" id="submit" value="${_('Update')}"/>&nbsp;
        <a class="ajax" _ref="/poll/results?id=${convId}">${_('Go back to results')}</a>
      %else:
        <input type="submit" id="submit" value="${_('Vote')}"/>
      %endif
    </form>
  </form>
</%def>

<%def name="poll_root(convId, isQuoted=False)">
  <%
    conv = items[convId]
    question = conv["meta"]["question"]
    options = conv["options"]
    userId = conv["meta"]["owner"]
    counts = conv.get("counts", {})
    voted = myVotes[convId] if (myVotes and myVotes.get(convId, False))\
                            else False
  %>
  %if not isQuoted:
    <span class="conv-reason">
      ${utils.userName(userId, entities[userId], "conv-user-cause")}
    </span>
  %endif
  <div class="item-title has-icon">
    <span class="icon item-icon poll-icon"></span>
    <span class="item-title-text">${question}</span>
  </div>
  <div id="poll-contents-${convId}" class="item-contents has-icon">
  <%
    if voted:
      self.poll_results(convId, voted)
    else:
      self.poll_options(convId, voted)
  %>
  </div>
</%def>
