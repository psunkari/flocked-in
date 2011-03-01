<%! from social import utils, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">


<%def name="title()">
  ${_('Synovel SocialNet')}
</%def>
<%def name="layout()">
</%def>

<%def name="nav_menu()">
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
      <li><a href="/feed" class="ajax">News Feed</a></li>
      <li><a href="/messages" class="ajax">Messages</a></li>
      <li><a href="/events" class="ajax">Events</a></li>
      <li><a href="/friends" class="ajax">Friends</a></li>
    </ul>
  </div>
  <div id="grpmenu-container" class="sidemenu-container">
    <ul id="grpmenu" class="v-links sidemenu">
      <li><a href="/groups" class="ajax">Groups</a></li>
    </ul>
  </div>
  <div id="orgmenu-container" class="sidemenu-container">
    <ul id="orgmenu" class="v-links sidemenu">
      <li><a href="/org" class="ajax">Company Feed</a></li>
      <li><a href="/people" class="ajax">People</a></li>
    </ul>
  </div>
</%def>

<html>
<head>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/widgets.css"/>
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
          <img src="${avatarURI}" width=50 height=50/>
        %endif
      </div>
      <!-- TODO: Avatar and Site Logo -->
      <div id="sitelogo">
        %if org and org.has_key('basic'):
          <img src="${org['basic']['logo']}" alt="${org['basic']['name']}"/>
        %endif
      </div>
      <div id="search-container">
        <form id="search">
          <input type="text" id="searchbox"
                 placeholder="${_('Search people, messages and statuses...')}"/>
          <input type="button" id="searchbutton" value="${_('Go!')}"/>
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
  <script type="text/javascript" src="/public/scripts/jquery.address.js?state=/"></script>
  <script type="text/javascript" src="/public/scripts/social.js"></script>
%else:
</body>
</html>
%endif
