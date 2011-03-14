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

<%def name="poll_root(convId)">
  <%
    conv = items[convId]
    question = items[convId]["meta"]["question"]
    options = items[convId]["options"]
    counts = items[convId].get("counts", {})
  %>
  <div id="conv" class="conv-item">
    <div>
        %if convId in myVote and myVote[convId]:
        <p>You voted for: ${options.get(myVote[convId], "")} </p>
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

