<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

##
## Profile is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="titlebar center-header">
        <div id="title"><span class="middle title">${_('Notifications')}</span></div>
      </div>
      <div id="right">
      </div>
      <div id="center">
        <div class="notifications" id="notifications">
          ${self.content()}
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="content()">
  <%
    userAvatar = utils.userAvatar
    groupAvatar = utils.groupAvatar
    simpleTimestamp = utils.simpleTimestamp
    myTz = me.basic['timezone']
  %>
  %if notifications:
    %for notifyId in notifications:
      <%
        unreadClass = 'unread' if notifyId in latestNotifyIds else ''
      %>
      <div class="notification-item ${unreadClass}">
        <div class="notification-avatars-wrapper">
            %for entityId in reversed(notifyUsers[notifyId][:2]):
              <%
                 entity = entities[entityId]
                 entityType = entity.basic["type"]
                 if entityType == "user":
                    avatarURI = userAvatar(entityId, entity, "small")
                 elif entityType == "group":
                    avatarURI = groupAvatar(entityId, entity, "small")
              %>
              <div class="notification-avatar">
                <img src="${avatarURI}" style="max-height: 32px; max-width: 32px;"/>
              </div>
            %endfor
        </div>
        ${notifyStr[notifyId]}
        <div class="notification-footer">${simpleTimestamp(timestamps[notifyId], myTz)}</div>
      </div>
    %endfor
    %if nextPageStart:
      <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" data-ref="/notifications?start=${nextPageStart}">${_("Fetch older Notifications")}</a></div>
    %else:
      <div id="next-load-wrapper">${_("No more notifications to show")}</div>
    %endif
  %else:
      <div id="next-load-wrapper">${_("No more notifications to show")}</div>
  %endif
</%def>
