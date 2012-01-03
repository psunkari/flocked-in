<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins, constants %>
<%! from social.search import SearchResource as search %>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="itemTmpl" file="item.mako"/>
<%namespace name="feed" file="feed.mako"/>
<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="titlebar center-header">
        <div id="title">${self._title()}</div>
      </div>
      <div id="right">
        <div id="events-block"></div>
        <div id="todo-block"></div>
        <div id="people-block"></div>
        <div id="groups-block"></div>
      </div>
      <div id="center">
        <div id="search-results" class="center-contents">
            %if not script:
              ${self.results()}
            %endif
        </div>
      </div>
        <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="_title()">
  <span class="middle title">${_('Search Results for <a href="/search?q=%s"><em class="soccshl">%s</em></a>') % (term, term)}</span>
</%def>

<%def name="paging(start, count, total)">
  <%
    nextPageStart = start + count if 0 < start + count < total else -1
    prevPageStart = start - constants.SEARCH_RESULTS_PER_PAGE
    if prevPageStart < 0:
        prevPageStart = 0

    formatVars = {'start': start + 1, 'end': start + count, 'total': total}
  %>
  <ul class="h-links">
    <li class="search-pagemeta">${_('%(start)s&ndash;%(end)s of %(total)s') % formatVars}</li>
    %if start > 0:
      <li class="button"><a class="ajax" href="/search?q=${term}&it=${itemType}&start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart >= 0:
      <li class="button"><a class="ajax" href="/search?q=${term}&it=${itemType}&start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="peopleResults()">
  <%
    statsMap = {'total': matchedUserCount, 'shown': len(matchedUsers),
                'term': term, 'start': start, 'itemType': search.TYPE_PEOPLE}
  %>
  %if itemType != search.TYPE_PEOPLE:
    <div class="search-subtitle">
      %if len(matchedUsers) < matchedUserCount:
        ${_('People &mdash; Showing %(shown)s of %(total)s found. <a href="/search?q=%(term)s&start=%(start)s&it=%(itemType)s">View more people &raquo;</a>') % statsMap}
      %else:
        ${__('People &mdash; Only 1 found', 'People &mdash; Showing all %(total)s found.', len(matchedUsers)) % statsMap}
      %endif
    </div>
  %else:
    <div class="search-subtitle">People</div>
  %endif
  <div id="search-people">
    %for userId in matchedUsers.keys():
      <%
        user = matchedUsers[userId]
        matches = highlight[userId]

        name = matches['name'][0] if 'name' in matches else user.get('name', '')
        fname = matches['firstname'][0] if 'firstname' in matches else user.get('firstname', '')
        lname = matches['lastname'][0] if 'lastname' in matches else user.get('lastname', '')
        title = matches['jobTitle'][0] if 'jobTitle' in matches else user.get('jobTitle', '')
        avatarURI = user.get('avatar', '')
      %>
      <div id="user-${userId}" class="conv-item">
        <div class="conv-avatar">
          <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;" />
        </div>
        <div class="conv-data">
          <div class="item-title user"><a class="ajax" href="/profile?id=${userId}">${name}</a></div>
          <div>
            %if fname and lname:
              <span>${fname + " " + lname}</span>,
            %endif
            <span>${title}</span>
          </div>
          <%
            otherHits = [x for x in matches.keys() \
                         if x not in ['name','firstname','lastname','jobTitle']]
          %>
          %if otherHits:
            %for hit in otherHits:
              %if hit == "expertise":
                <% expertise = matches['expertise'][0].split(',') %>
                %for x in expertise:
                  <span class="tag">${x}</span>
                %endfor
              %else:
                <div>${matches[hit][0]}</div>
              %endif
            %endfor
          %endif
        </div>
      </div>
    %endfor
  </div>
  %if itemType == search.TYPE_PEOPLE:
    <div id="search-people-paging" class="pagingbar search-paging">
       <% paging(start, len(matchedUsers), matchedUserCount) %>
    </div>
  %endif
</%def>


<%def name="conv_root(convId)">
  <% itemType = items[convId]["meta"]["type"] %>
  %if itemType in plugins:
    ${plugins[itemType].rootHTML(convId, isQuoted, context.kwargs)}
  %endif
  <% attachments = items[convId].get("attachments", {}) %>
  %if len(attachments.keys()) > 0:
    <div class="attachment-list">
      %for attachmentId in attachments:
        <%
          tuuid, name, size, ftype = attachments[attachmentId].split(':')
          name = urlsafe_b64decode(name)
          size = formatFileSize(int(size))
          location = '/files?id=%s&fid=%s&ver=%s'%(convId, attachmentId, tuuid)
        %>
        <div class="attachment-item">
          <span class="icon attach-file-icon"></span>
          <span class="attachment-name"><a href="${location}" target="filedownload">${name|h}</a></span>
          <span class="attachment-meta">&nbsp;&nbsp;&ndash;&nbsp;&nbsp;${size}</span>
        </div>
      %endfor
    </div>
  %endif
</%def>


<%def name="item_layout(itemId, classes='')">
  <div id="conv-${itemId}" class="conv-item ${classes}">
    <div class="conv-avatar" id="conv-avatar-${itemId}">
      <%
        itemMeta = items[itemId]['meta']
        ownerId = itemMeta['owner']
        parentId = itemMeta.get('parent', None)
        itemType = itemMeta.get('type', 'status') if not parentId else 'comment'
      %>
      %if itemType != 'feedback':
        <% avatarURI = utils.userAvatar(ownerId, entities[ownerId], "small") %>
        <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
      %else:
        <div class="feedback-mood-icon ${type}-icon"></div>
      %endif
    </div>
    <div class="conv-data">
      <div id="conv-root-${itemId}" class="conv-root">
        <div class="conv-summary">
          %if itemType in plugins:
            ${plugins[itemType].rootHTML(itemId, isQuoted, context.kwargs)}
          %else:    ## responses
            <%
              if 'comment' in highlight[itemId]:
                  comment = highlight[itemId]['comment'][0]
              else:
                  comment = itemMeta.get('comment', '')

              snippet = itemMeta.get('snippet', '')
              richText = itemMeta.get('richText', 'False') == 'True'
              ownerName = utils.userName(ownerId, entities[ownerId], "conv-user-cause")
              if parentId:
                  parentMeta = items[parentId]['meta']
                  parentType = parentMeta.get('type', 'status')
                  parentOwnerId = parentMeta['owner']
                  parentOwnerName = entities[parentOwnerId]['basic']['name']
            %>
            %if parentId:
              ${_("%(ownerName)s, in reply to <a class='ajax' href='/item?id=%(parentId)s'>%(parentOwnerName)s's %(parentType)s</a>") % locals()}
            %else:
              ${ownerName}
            %endif
            <div class="item-title">
              ${itemTmpl._renderText(snippet, comment, richText=richText)}
            </div>
          %endif
          <%
            attachments = items[itemId].get("attachments", {})
            if len(attachments.keys()) > 0:
              itemTmpl.conv_attachments(itemId, attachments)
          %>
          <div id="item-footer-${itemId}" class="conv-footer busy-indicator">
            <%
              timestamp = int(itemMeta['timestamp'])
              likesCount = int(itemMeta.get('likesCount', '0'))
              commentsCount = int(itemMeta.get('responseCount', '0'))
              myTimezone = me['basic'].get("timezone", None)
            %>
            ${utils.simpleTimestamp(timestamp, myTimezone)}
            %if likesCount:
              &nbsp;&#183;
            %endif
            %if not parentId:
              <button class="ajax button-link" title="${_('View %s') % itemType}" href="/item?id=${itemId}">
                %if likesCount > 0:
                  <div class="small-icon small-like"></div>${likesCount}
                %endif
                %if commentsCount > 0:
                  &nbsp;&#183;&nbsp;
                  <div class="small-icon small-comment"></div>${commentsCount}
                %endif
                &nbsp;&#183;&nbsp;
                ${_('View %s' % itemType)}
              </button>
            %else:
              <button class="ajax button-link" title="${_('View %s') % parentType}" href="/item?id=${parentId}">
                %if likesCount > 0:
                  <div class="small-icon small-like"></div>${likesCount}
                %endif
              </button>
            %endif
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="results()">
  %if matchedUsers:
    <div id="search-people-wrapper">
      <% peopleResults() %>
    </div>
  %endif
  %if matchedItemIds:
    <%
      statsMap = {'total': matchedItemCount, 'shown': len(matchedItemIds),
                  'term': term, 'start': start, 'itemType': search.TYPE_ITEMS}
    %>
    <div id="search-convs-wrapper">
      %if itemType != search.TYPE_ITEMS:
        <div class="search-subtitle">
          %if len(matchedItemIds) < matchedItemCount:
            ${_('Posts &mdash; Showing %(shown)s of total %(total)s found. <a href="/search?q=%(term)s&start=%(start)s&it=%(itemType)s">View more posts &raquo;</a>') % statsMap}
          %else:
            ${__('Posts &mdash; Only 1 found', 'Showing all %(total)s found.', len(matchedItemIds)) % statsMap}
          %endif
        </div>
      %else:
        <div class="search-subtitle">Posts</div>
      %endif
      <div id="search-convs">
        %for itemId in matchedItemIds:
          ${self.item_layout(itemId)}
        %endfor
      </div>
      %if itemType == search.TYPE_ITEMS:
        <div id="search-convs-paging" class="pagingbar search-paging">
          <% paging(start, len(matchedItemIds), matchedItemCount) %>
        </div>
      %endif
    </div>
  %endif
</%def>


<%def name="_results()">
  <%
    rTypeClasses = {"status": "comment", "question": "answer", "L": "like"}
    simpleTimestamp = utils.simpleTimestamp
    rTypeClass = "comment"
    tzone = me['basic']['timezone']
  %>
  %if people and fromSidebar :
    ${listUsers()}
  %endif
  %if conversations:
    %for itemId in conversations:
      <%
        convId = items[itemId]['meta'].get('parent', itemId)
        convType = items[convId]['meta']['type']
        rTypeClass = convType if convId == itemId else rTypeClasses.get(convType, 'comment')
        icon_class = '%s-icon'%(convType) if convId == itemId else ''
        convOwner = items[convId]['meta']['owner']
        itemOwner = items[itemId]['meta']['owner']
        convOwnerStr = _("%s's "%(utils.userName(convOwner, entities[convOwner])))
        itemOwnerStr = _("%s's "%(utils.userName(itemOwner, entities[itemOwner])))
      %>

      <div class="activity-item ${rTypeClass}">
        <div class="activity-icon icon ${rTypeClass}-icon"></div>
        <div class="activity-content">
          %if itemId == convId:
            <span>${items[itemId]['meta']['comment']} - ${convOwnerStr}<a href="/item?id=${convId}">${convType}</a></span>
          %else:
            <span>${items[itemId]['meta']['comment']} ${itemOwnerStr} ${rTypeClass} ${_('on')} ${convOwnerStr}<a href="/item?id=${convId}">${convType}</a></span>
          %endif
          <div class="activity-footer">${simpleTimestamp(int(items[itemId]['meta']['timestamp'])*1.0, tzone)}</div>
        </div>
      </div>
    %endfor
  %endif

  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/search?start=${nextPageStart}&q=${term}" data-ref="/search?start=${nextPageStart}&q=${term}">${_("Fetch more results")}</a></div>
  %else:
    %if fromFetchMore:
      <div id="next-load-wrapper">${_("No more posts to show")}</div>
    %else:
      <div id="next-load-wrapper">${_("No matching posts")}</div>
    %endif

  %endif
</%def>

<%def name="listUsers()">
  <%
    counter = 0
    firstRow = True
  %>
  %for userId in people:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayUser(userId)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>


<%def name="_displayUser(userId, smallAvatar=False)">

  <%
    max_height = '32px' if smallAvatar else '48px'
    max_width =  '32px' if smallAvatar else '48px'
  %>

  <div class="users-avatar">
    <% avatarURI = utils.userAvatar(userId, entities[userId], "medium") %>
    %if avatarURI:
      <img src="${avatarURI}" style="max-height:${max_height}; max-width:${max_width}"></img>
    %endif
  </div>
  <div class="users-details">
    <div class="user-details-name">${utils.userName(userId, entities[userId])}</div>
    <div class="user-details-title">${entities[userId]["basic"].get("jobTitle", '')}</div>
  </div>
</%def>

<%def name="_displayUsersMini()" >
  <div class='sidebar-chunk'>
    <div class="sidebar-title">${_("People")}</div>
    %for userId in people[:2]:
      <div class="suggestions-user" > ${_displayUser(userId, True)}</div>
    %endfor
    %if len(people) > 2:
      <div style="float:right"><a href='/search?q=${term}&filter=people'>more</a></div>
    %endif
  </div>
</%def>
