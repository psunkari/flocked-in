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
      ${navMenuItem("/feed/", _("News Feed"), "feed")}
      ${navMenuItem("/notifications", _("Notifications"), "notifications")}
      ${navMenuItem("/messages", _("Messages"), "messages")}
      ${navMenuItem("/event", _("Events"), "events")}
      ${navMenuItem("/people", _("People"), "people")}
      ${navMenuItem("/feed/%s" % orgId, _("Company Feed"), "org")}
      ${navMenuItem("/groups", _("Groups"), "groups")}
      ${navMenuItem("/course", _("Courses"), "courses")}
      ${navMenuItem("/files/list", _("Files"), "files")}
      ${navMenuItem("/tags/list", _("Tags"), "tags")}
      ${navMenuItem("/chats", _("Chats"), "chats")}
    </ul>
  </div>

  %if script:
  <div id="roster-container">
    <div class="sidebar-title">Chat</div>
    <div id="roster-loading" class="busy-indicator busy" style="display:none;line-height:2.5em;color:gray;">Loading...</div>
    <div id="roster">
      <div id="online-status-bar">
        <button id="online-status-button" class="acl-button acl-text-button" onclick="$$.chatUI.showStatusList(event, 'online-status');">
          <img id="user-online-status-icon" src="/rsrcs/img/offline.png" style="float:left"/>
          <span id="user-online-status-text">${_("Offline")}</span>
          <span>▼</span>
        </button>
        <ul class="acl-menu" style="display:none;width:170px;">
            <li><a class="acl-item" onclick='$$.chatUI.setStatus("available")'>${_("Available")}</a></li>
            <li><a class="acl-item" onclick='$$.chatUI.setStatus("away")'>${_("Away")}</a></li>
            <li><a class="acl-item" onclick='$$.chatUI.setStatus("busy")'>${_("Busy")}</a></li>
            <li><a class="acl-item" onclick='$$.chat.signout()'>${_("Offline")}</a></li>
        </ul>
      </div>
      <div id="roster-list-container" >
        <div class="roster-list">
        </div>
      </div>
    </div>
  </div>
  %endif
</%def>

<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/jquery.ui.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/jquery.tagedit.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/screen-size.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/messaging.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/jquery.ui.datepicker.css"/>
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />

%if script:
  <noscript>
    <meta http-equiv="refresh" content="0; URL=${noscriptUrl}"/>
  </noscript>
%else:
  <script>
    var date = new Date(); date.setDate(date.getDate() - 2);
    document.cookie = "_ns=0;path=/;expires=" + date.toUTCString();
    url = window.location.href.replace(/_ns=1&?/, "");
    window.location.href = url.replace(/(\?|&)$/, '');
  </script>

%endif
</head>
%if script:
<body>
%else:
<body class="noscript">
%endif
  <noscript>
    <div id='missing-javascript'>
      <span class='unsupported-text'>
        Read only mode &mdash; Enable Javascript for complete functionality
      </span>
    </div>
  </noscript>
  <div id='unsupported-browser'>
    <span class='unsupported-text'>
      Unsupported Browser &ndash; Please upgrade to a newer version
    </span>
  </div>
  <div id='compatibility-mode'>
    <span class='unsupported-text'>
      Compatibility mode &ndash; Please switch your browser to normal mode
    </span>
  </div>
  <div id="topbar">
    <div id="top" class="contents">
      <% avatarURI = utils.userAvatar(myId, me) %>
      %if avatarURI:
        <div class="avatar" id="avatar" style="background-image:url('${avatarURI}')"></div>
      %endif
      <div id="sitelogo">
        <a id="sitelogo-link" href="/" title="${org.basic['name']}">
          %if org and org.basic:
            <% logoURI = utils.companyLogo(org) %>
            %if logoURI:
              <img id="sitelogo-img" src="${logoURI}" alt="${org.basic['name']}"/>
            %else:
              <span id="sitename">${org.basic['name']}</span>
            %endif
          %endif
        </a>
      </div>
      <div id="search-container">
        <form id="search" action="/search" method="GET" class="ajaxget">
          <input type="text" id="searchbox" name="q"
                 placeholder="${_('Search people and posts...')}" required title="${_('Search')}"/>
          <input type="submit" id="searchbutton" value="${_('Go!')}"/>
        </form>
      </div>
    </div>
  </div>
  <div id="menubar">
    <div id="menu" class="contents">
      <%
        name = me.basic['name']
        if me.basic.has_key('jobTitle'):
          title = me.basic['jobTitle']
          name = _('%(name)s, %(title)s') % locals()
      %>
      <div id="name">${name}</div>
      <div id="menubar-links-wrapper">
        <a href="/feed/" class="ajax">${_("Home")}</a>
        %if isOrgAdmin:
          <a href="/admin" class="ajax">${_("Admin")}</a>
        %endif
        <a href="/profile?id=${myId}" class="ajax">${_("My Profile")}</a>
        <a href="/signout">${_("Sign out")}</a>
      </div>
    </div>
  </div>
  <div id="mainbar">
    ${self.layout()}
  </div>
%if script:
  <div id="feedback-linkwrap">
    <a href="javascript:" title=${_('Feedback')} onclick="$$.feedback.showFeedback()"><span class="icon feedback-icon"></span><span>${_('Feedback')}</span></a></li>
  </div>
%endif
  <div id="alertbar"></div>
%if script:
  <script type="text/javascript">
      var social_config = {
          cometdURL: "${config.get('Cometd', 'Url')}",
          orgId: "${orgId}",
          myId : "${myId}"
      }
  </script>
  <script type="text/javascript" src="/rsrcs/js/jquery-1.6.4.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.autocomplete.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.address-1.4.js?tracker=null"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.autogrow-textarea.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.cookie.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.iframe-transport.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.html5form-1.3.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.autoGrowInput.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.tagedit.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.datepicker.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.timepicker.js"></script>
  <script type="text/javascript" src="/rsrcs/js/Cometd.js"></script>
  <script type="text/javascript" src="/rsrcs/js/ReloadExtension.js"></script>
  <script type="text/javascript" src="/rsrcs/js/json2.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.cometd.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.cometd-reload.js"></script>
  <script type="text/javascript" src="/rsrcs/js/social.js"></script>
  <script type="text/javascript">
    $().ready(function() {$$.ui.init()});
  </script>
  <script type="text/javascript">
    var _gaq = _gaq || [];
    _gaq.push(['_setAccount', 'UA-2921978-5']);
    /*_gaq.push(['_trackPageview']);*/

    (function() {
      var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
      ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
      var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
    })();
  </script>
%else:
</body>
</html>
%endif
