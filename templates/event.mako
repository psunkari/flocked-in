<%! from social import utils, _, __, constants %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>

<%def name="share_event()">
  <div class="input-wrap">
    <input type="text" name="startTime" placeholder="${_('When?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="endTime" placeholder="${_('End Time?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="title" placeholder="${_('What?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="location" placeholder="${_('Where?')}"/>
  </div>
  <div class="input-wrap">
    <input type="text" name="desc" placeholder="${_('Description')}"/>
  </div>
  <input type="hidden" name="type" value="event"/>
</%def>

<%def name="event_root(convId)">
  <%
    conv = items[convId]
    title = items[convId]["meta"].get("title", '')
    location = items[convId]["meta"].get("location", '')
    desc = items[convId]["meta"].get("desc", "")
    start = items[convId]["meta"].get("startTime")
    end   = items[convId]["meta"].get("endTime", '')
    options = items[convId]["options"] or ["yes", "maybe", "no"]
  %>
  <div id="conv" class="conv-item">
    <div>
        %if convId in myResponse and myResponse[convId]:
        <p> are you attending the <a href="/item?id=${convId}&type=event">event</a>?: ${myResponse[convId]} </p>
        %endif
        <form action="/event/post" method="POST" class="ajax">
        <p> ${title} </p>
        % for option in options:
            <input type="radio" name="response" value= "${option}"> ${option} </input> <br/>
        % endfor
            <input type="hidden" name="id" value="${convId}" />
            <input type="hidden" name="type" value="event" />
            <input type="submit" id="submit" value="${_('Submit')}"/>
        </form>
        <span>${title}</span>
        <p>${desc}</p>
        <p>location: ${location}</p>
        <p>TIME: ${start} - ${end}</p>
        % for option in options:
            <p> ${option} : ${options[option]} </p>
        %endfor
    </div>

  </div>
</%def>
