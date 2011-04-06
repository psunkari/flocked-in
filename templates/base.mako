<%! from social import utils, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">


<%def name="title()">
  ${_('Synovel SocialNet')}
</%def>
<%def name="layout()">
</%def>

<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, icon):
        return '<li><a href="%(link)s" class="ajax busy-indicator"><span class="sidemenu-icon icon %(icon)s-icon"></span><span class="sidemenu-text">%(text)s</span></a></li>' % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/feed", _("News Feed"), "feed")}
      ${navMenuItem("/notifications", _("Notifications"), "notifications")}
      ${navMenuItem("/messages", _("Messages"), "messages")}
      ${navMenuItem("/events", _("Events"), "events")}
      ${navMenuItem("/people/friends", _("Friends"), "people")}
    </ul>
  </div>
  <div id="grpmenu-container" class="sidemenu-container">
    <ul id="grpmenu" class="v-links sidemenu">
      ${navMenuItem("/groups", _("Groups"), "groups")}
    </ul>
  </div>
  <div id="orgmenu-container" class="sidemenu-container">
    <ul id="orgmenu" class="v-links sidemenu">
      ${navMenuItem("/feed?id=%s" % orgKey, _("Company Feed"), "org")}
      ${navMenuItem("/people", _("People"), "people")}
    </ul>
  </div>
</%def>

<html>
<head>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/widgets.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/jquery.ui.core.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/jquery.ui.menu.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/jquery.ui.autocomplete.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/jquery.ui.theme.css"/>
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
  <div id="topbar">
    <div id="top" class="contents">
      <div id="avatar">
        <% avatarURI = utils.userAvatar(myKey, me) %>
        %if avatarURI:
          <img src="${avatarURI}" width="48" height="48"/>
        %endif
      </div>
      <!-- TODO: Avatar and Site Logo -->
      <div id="sitelogo">
        %if org and org.has_key('basic'):
          <img src="${org['basic']['logo']}" alt="${org['basic']['name']}"/>
        %endif
      </div>
      <div id="search-container">
        <form id="search" action="/search" method="post">
          <input type="text" id="searchbox" name="searchbox"
                 placeholder="${_('Search people, messages and statuses...')}"/>
          <input type="submit" id="searchbutton" value="${_('Go!')}"/>
        </form>
      </div>
    </div>
  </div>
  <div id="menubar">
    <div id="menu" class="contents">
      <%
        name = me['basic']['name']
        if me['basic'].has_key('jobTitle'):
          title = me['basic']['jobTitle']
          name = _('%(name)s, %(title)s') % locals()
      %>
      <div id="name"><a href="#">${name}</a></div>
      <div id="menubar-links-wrapper">
        <ul class="h-links">
          <li><a href="/feed" class="ajax">${_("Home")}</a></li>
          <li><a href="/profile?id=${myKey}" class="ajax">${_("My Profile")}</a></li>
          <li><a href="/signout">${_("Sign out")}</a></li>
        </ul>
      </div>
    </div>
  </div>
  <div id="mainbar">
    ${self.layout()}
  </div>
%if script:
  <script type="text/javascript" src="/public/scripts/jquery.js"></script>
  <script type="text/javascript" src="/public/scripts/jquery.ui.js"></script>
  <script type="text/javascript" src="/public/scripts/jquery.ui.menu.js"></script>
  <script type="text/javascript" src="/public/scripts/jquery.ui.autocomplete.js"></script>
  <script type="text/javascript" src="/public/scripts/jquery.address.js"></script>
  <script type="text/javascript" src="/public/scripts/social.js"></script>
  <script type="text/javascript">
    $().ready(function() {$$.initUI()});
  </script>
%else:
</body>
</html>
%endif
