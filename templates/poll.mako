<%! from social import utils, _, __, constants %>
<!DOCTYPE HTML>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>

<%def name="share_poll()">
  <div class="input-wrap">
    <textarea name="comment" placeholder="${_('What would you like to know?')}" required title="${_('Question')}"/>
  </div>
  <div id="share-poll-options">
    <div class="input-wrap">
      <span class="icon poll-option">&nbsp;</span>
      <input type="text" name="options" placeholder="${_('Add an option')}" required title="${_('Option')}"/>
    </div>
    <div class="input-wrap">
      <span class="icon poll-option">&nbsp;</span>
      <input type="text" name="options" placeholder="${_('Add an option')}" required title="${_('Option')}"/>
    </div>
    <div class="input-wrap">
      <span class="icon poll-option">&nbsp;</span>
      <input type="text" name="options" placeholder="${_('Add an option')}"/>
    </div>
  </div>
  <input type="hidden" name="type" value="poll"/>
</%def>

<%def name="poll_results(convId, voted=False)">
  <%
    if not voted:
      return

    conv = items[convId]
    options = conv["options"]
    counts = conv.get("counts", {})
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
        percent = (count * 100)/total if total > 0 else 0
        checked = 'checked="true"' if (voted and voted == option) else ''
        optionId = 'option-%s-%s' % (option, convId)

        if highlight and convId in highlight and "poll_option_%s"%option in highlight[convId]:
          optionText = highlight[convId]["poll_option_%s"%option][0]
        else:
          optionText = options[option]
      %>
      <li>
        %if checked:
          <span class=" icon tick-icon">&nbsp;</span>
        %else:
          <span class=" icon empty-icon">&nbsp;</span>
        %endif
        <div class="poll-wrapper">
          <div class="poll-bar-wrapper">
            <span class="poll-option-text" title="${options[option]}">${optionText}</span>
            <div class="poll-bar option-${int(option)%10}" style="width:${percent}%;">&nbsp;</div>
          </div>
          %if percent > 0:
            <div class="poll-percent">
              <span onclick="$$.dialog.create({id:'poll-users-${option}-${convId}'});
                             $.getScript('/ajax/poll/voters?id=${convId}&option=${option}');">
                ${"%d%%"%percent}
              </span>
            </div>
          %else:
            <div class="poll-percent"><span>${"%d%%"%percent}</span></div>
          %endif
        </div>
      </li>
    %endfor
  </ul>
  <div class="item-subactions">
    ${_("%d total votes")%total}
    &nbsp;&#183;&nbsp;
    <a class="ajax" data-ref="/poll/change?id=${convId}">${_("Change vote")}</a>
  </div>
</%def>

<%def name="poll_options(convId, voted=False)">
  <%
    conv = items[convId]
    options = conv["options"]
    counts = conv.get("counts", {})
  %>
  <form action="/poll/vote" method="POST" class="ajax">
      <ul class="poll-results">
        <%
          total = 0
          for votes in counts.values():
            total += int(votes)
        %>
        %for option in options:
          <%
            count = int(counts.get(option, '0'))
            percent = (count * 100)/total if total > 0 else 0
            checked = 'checked="true"' if (voted and voted == option) else ''
            optionId = 'option-%s-%s' % (option, convId)

            if highlight and convId in highlight and "poll_option_%s"%option in highlight[convId]:
              optionText = highlight[convId]["poll_option_%s"%option][0]
            else:
              optionText = options[option]
          %>
          <li>
            <input type="radio" name="option" value="${option}" id="${optionId}" ${checked} class="poll-options-option"/>
            <div class="poll-wrapper" onclick="$('#${optionId}').attr('checked', true)">
              <div class="poll-bar-wrapper">
                <span class="poll-option-text" title="${options[option]}">${optionText}</span>
                <div class="poll-bar option-${int(option)%10}" style="width:${percent}%;">&nbsp;</div>
              </div>
              %if percent > 0:
                <div class="poll-percent">
                  <span onclick="$$.dialog.create({id:'poll-users-${option}-${convId}'});
                                                         $.getScript('/ajax/poll/voters?id=${convId}&option=${option}');">
                    ${"%d%%"%percent}
                  </span>
                </div>
              %else:
                <div class="poll-percent"><span>${"%d%%"%percent}</span></div>
              %endif
            </div>
          </li>
        %endfor
      </ul>
      <div class="item-subactions">
        <input type="hidden" name="id" value="${convId}"/>
        %if voted:
          <input type="submit" class="button" id="submit" value="${_('Update')}"/>&nbsp;
          <a class="ajax" data-ref="/poll/results?id=${convId}">${_('Go back to results')}</a>
        %else:
          <input type="submit" id="submit" class="button" value="${_('Vote')}"/>
        %endif
      </div>
    </form>
  </form>
</%def>

<%def name="poll_root(convId, isQuoted=False)">
  <%
    conv = items[convId]
    meta = conv['meta']
    userId = meta["owner"]
    voted = myVotes[convId] if (myVotes and myVotes.get(convId, False)) else False
    richText = meta.get('richText', 'False') == 'True'

    target = meta.get('target', '')
    target = target.split(',') if target else ''
    if target:
      target = [x for x in target if x in relations.groups]
  %>
  %if not isQuoted:
    <span class="conv-reason">
      %if not target:
        ${utils.userName(userId, entities[userId], "conv-user-cause")}
      %else:
        ${utils.userName(userId, entities[userId], "conv-user-cause")}  ${_("on")} ${utils.groupName(target[0], entities[target[0]])}
      %endif
    </span>
  %endif
  <div class="item-title has-icon">
    <span class="icon item-icon poll-icon"></span>
    <div class="item-title-text">
      <%
        matches = highlight.get(convId, None) if highlight else None
        comment = matches['comment'][0] if matches and 'comment' in matches else meta.get('comment', '')
        snippet = matches['snippet'][0] if matches and 'snippet' in matches else meta.get('snippet', '')
      %>
      ${item._renderText(snippet, comment, richText=richText)}
    </div>
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
