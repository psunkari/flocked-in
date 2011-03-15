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
  <div class="poll-actions">Total votes: ${total}</div>
</%def>

<%def name="poll_choices(convId, voted=False)">
  <%
    conv = items[convId]
    question = conv["meta"]["question"]
    options = conv["options"]
  %>
  <div class="poll-title">
    <span>${question}</span>
  </div>
  <form action="/poll/post" method="POST" class="ajax">
    <div class="tabular-form">
      %for option in options:
        <ul>
          <li><input type="radio" name="option" value="${option}"/></li>
          <li>${options[option]}</li>
        </ul>
      %endfor
      </div>
      <input type="hidden" name="id" value="${convId}"/>
      <input type="submit" id="submit" value="${_('Submit Vote')}"/>
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
      self.poll_choices(convId, voted)
  %>
</%def>

<%def name="_poll_root(convId)">
  <%
    conv = items[convId]
    question = items[convId]["meta"]["question"]
    options = items[convId]["options"]
    counts = items[convId].get("counts", {})
  %>
  <div id="conv" class="conv-item">
    <div>
        %if convId in myVotes and myVotes[convId]:
        <p>You voted for: ${options.get(myVotes[convId], "")} </p>
        %endif
        <form action="/poll/post" method="POST" class="ajax">
        <p> ${question} </p>
        % for option in options:
            <input type="radio" name="option" value="${option}">${options[option]}</input> <br/>
        % endfor
            <input type="hidden" name="id" value="${convId}" />
            <input type="hidden" name="type" value="poll" />
            <input type="submit" id="submit" value="${_('Submit')}"/>
        </form>
        <span>${question}</span>
        % for option in options:
            <p> ${options[option]}: ${counts.get(option, '0')} </p>
        %endfor
    </div>
  </div>
</%def>

