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
    question = items[convId]["meta"]["question"] or "what is your fav game?"
    options = items[convId]["options"] or ["cricket", "football", "hockey"]
  %>
  <div id="conv" class="conv-item">
    <div>
        %if convId in  myVote and myVote[convId]:
        <p> you voted for: ${myVote[convId]} </p>
        %endif
        <form action="/poll/post" method="POST" class="ajax">
        <p> ${question} </p>
        % for option in options:
            <input type="radio" name="option" value= "${option}"> ${option} </input> <br/>
        % endfor
            <input type="hidden" name="id" value="${convId}" />
            <input type="hidden" name="type" value="poll" />
            <input type="submit" id="submit" value="${_('Submit')}"/>
        </form>
        <span>${question}</span>
        % for option in options:
            <p> ${option} : ${options[option]} </p>
        %endfor
    </div>
  </div>
</%def>

