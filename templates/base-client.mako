<%! from social import utils, config, _, __ %>
<!DOCTYPE HTML>

<%def name="title()">
  ${config.get('Branding', 'Name')} &mdash; ${_('Private, Secure and Free Social Network for Enterprises')}
</%def>

<%def name="layout()">
</%def>

<%def name="nav_menu()">
  <%
    counts = latest or {}
    def navMenuItem(link, text, id):
      cls = "sidemenu-selected" if id == menuId else ''
      countStr = "<div class='new-count'>%s</div>" % counts[id] if (id in counts and counts[id] > 0) else ''
      return '<li><a href="%(link)s" id="%(id)s-sideitem" class="ajax busy-indicator %(cls)s"><span class="sidemenu-icon icon %(id)s-icon"></span><span class="sidemenu-text">%(text)s</span>%(countStr)s</a></li>' % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/feed", _("News Feed"), "feed")}
      ${navMenuItem("/notifications", _("Notifications"), "notifications")}
      ${navMenuItem("/messages", _("Messages"), "messages")}
      ##${navMenuItem("/event", _("Events"), "events")}
      ${navMenuItem("/people", _("People"), "people")}
      ${navMenuItem("/feed?id=%s" % orgKey, _("Company Feed"), "org")}
      ${navMenuItem("/groups", _("Groups"), "groups")}
      ${navMenuItem("/tags/list", _("Tags"), "tags")}
    </ul>
  </div>
%if script:
  <div id="feedbackmenu-container" class="sidemenu-container">
    <ul id="feedbackmenu" class="v-links sidemenu">
      <li><a title=${_('Feedback')} onclick="$$.feedback.showFeedback()"><span class="sidemenu-icon icon feedback-icon"></span><span class="sidemenu-text">${_('Feedback')}</span></a></li>
    </ul>
  </div>
%endif
</%def>

<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/screen-size.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/jquery.ui.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/messaging.css"/>
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
%if script:
  <noscript>
    <meta http-equiv="refresh" content="0; URL=${noscriptUrl}"/>
  </noscript>
%else:
%endif
</head>
%if script:
<body>
%else:
<body class="noscript">
%endif
  <div id="topbar">
    <div id="top" class="contents">
      <% avatarURI = None %>
      %if avatarURI:
        <div class="avatar" id="avatar" style="background-image:url('${avatarURI}')"></div>
      %endif
      <div id="sitelogo">
        %if org and org.has_key('basic'):
          <% logoURI = None %>
          %if logoURI:
            <img src="${logoURI}" alt="${org['basic']['name']}"/>
          %else:
            <span id="sitename">${org['basic']['name']}</span>
          %endif
        %endif
      </div>
      <div id="search-container">
        <form id="search" action="/search" method="GET" class="ajaxget">
          <input type="text" id="searchbox" name="q"
                 placeholder="${_('Search people, messages and statuses...')}" required title="${_('Search')}"/>
          <input type="submit" id="searchbutton" value="${_('Go!')}"/>
        </form>
      </div>
    </div>
  </div>
  <div id="menubar">
    <div id="menu" class="contents">
      <%
        name = "Third Party System"
        title = "Mr. World"
      %>
      <div id="name">${name}</div>
      <div id="menubar-links-wrapper">
        <a href="/feed" class="ajax">${_("Home")}</a>
        %if isOrgAdmin:
          <a href="/admin" class="ajax">${_("Admin")}</a>
        %endif
        <a href="/profile?id=" class="ajax">${_("My Profile")}</a>
        <a href="/signout">${_("Sign out")}</a>
      </div>
    </div>
  </div>
  <div id="mainbar">
    ${self.layout()}
  </div>
  <div id="alertbar"></div>
  <script type="text/javascript" src="/rsrcs/js/jquery-1.6.4.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.menu.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.autocomplete.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.address-1.4.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.autogrow-textarea.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.iframe-transport.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.html5form-1.3.js"></script>
  <script type="text/javascript" src="/rsrcs/js/social.js"></script>
  <script type="text/javascript" src="/rsrcs/js/client.js"></script>
  <script type="text/javascript">
    $().ready(function() {$$.ui.init()});
  </script>
</body>
</html>
