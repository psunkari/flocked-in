<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
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
        <% q = term if term else '' %>
        <div style="float:left" >
          <div id="search-container">
            <form id="search" action="/search" method="GET" class="ajaxget">
              <input type="text" id="searchbox" name="q" value=${q} />
              <input type="submit" id="searchbutton" value="${_('Go!')}"/>
            </form>
          </div>
        </div>
        <div style="margin-top: 30px">
          <div class="center-contents">
            <div id="user-feed">
              %if not script:
                ${self.results()}
              %endif
            </div>
          </div>
        </div>
      </div>
        <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="_title()">
  <span class="middle title">${_("Search Results")}</span>
</%def>

<%def name="results()">
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
