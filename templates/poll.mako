<%! from social import utils, _, __, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>

<%def name="share_poll()">
  <div class="input-wrap">
    <input type="text" name="question" placeholder="${_('Question')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="options" placeholder="${_('Option')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="options" placeholder="${_('Option')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="options" placeholder="${_('Option')}"/>
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
  <div class="poll-title">
    <span>${question}</span>
  </div>
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
          <div class="poll-share">${"%d%%"%percent}</div>
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
  <div class="poll-title">
    <span>${question}</span>
  </div>
  <form action="/poll/vote" method="POST" class="ajax">
    <div class="tabular-form poll-options">
      %for option in options:
        <ul>
          <li><input type="radio" name="option" value="${option}"/></li>
          <li>${options[option]}</li>
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

<%def name="poll_root(convId)">
  <%
    conv = items[convId]
    question = items[convId]["meta"]["question"]
    options = items[convId]["options"]
    counts = items[convId].get("counts", {})
    voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                            else False
    if voted:
      self.poll_results(convId, voted)
    else:
      self.poll_options(convId, voted)
  %>
</%def>

