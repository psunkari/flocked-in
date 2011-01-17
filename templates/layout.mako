<%! from social import utils, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">


<%def name="title()">
  ${_('Synovel SocialNet')}
</%def>
<%def name="right()">
</%def>
<%def name="center_header()">
</%def>
<%def name="center_contents()">
</%def>

<%def name="left()">
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="sidemenu">
      <li><a href="/feed" class="ajax">News Feed</a></li>
      <li><a href="/messages" class="ajax">Messages</a></li>
      <li><a href="/events" class="ajax">Events</a></li>
      <li><a href="/friends" class="ajax">Friends</a></li>
    </ul>
  </div>
  <div id="grpmenu-container" class="sidemenu-container">
    <ul id="grpmenu" class="sidemenu">
      <li><a href="/groups" class="ajax">Groups</a></li>
    </ul>
  </div>
  <div id="orgmenu-container" class="sidemenu-container">
    <ul id="orgmenu" class="sidemenu">
      <li><a href="/org" class="ajax">Company Feed</a></li>
      <li><a href="/people" class="ajax">Contacts</a></li>
    </ul>
  </div>
</%def>

<html>
<head>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
%if script:
  <noscript>
    <meta http-equiv="refresh" content="0; URL=${noscriptUrl}"/>
  </noscript>
%else:
  <script>
    url = window.location.href.replace(/_ns=1&?/, "");
    window.location.href = url.replace(/(\?|&)$/, '');
  </script>
%endif
</head>
<body>
  <div id="topbar">
    <div id="top" class="contents">
      <!-- TODO: Avatar and Site Logo -->
      <div id="avatar" class="left">
        %if me.has_key('avatar'):
          <img src="${me['avatar']['small']}"/>
        %endif
      </div>
      <div id="sitelogo" class="left">
        %if org and org.has_key('basic'):
          <img src="${org['basic']['logo']}" alt="${org['basic']['name']}"/>
        %endif
      </div>
      <div id="search-container" class="right">
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
      <div id="name" class="b left"><a href="#">${name}</a></div>
      <div class="right">
        <ul id="menubar-links">
          <li><a href="/feed" class="ajax">${_("Home")}</a></li>
          <li><a href="/profile" class="ajax">${_("My Profile")}</a></li>
          <li><a href="/signout">${_("Sign out")}</a></li>
        </ul>
      </div>
    </div>
  </div>
  <div id="mainbar">
    <div id="main" class="contents">
      <div id="leftbar">
        %if not script:
          ${self.left()}
        %endif
      </div>
      <div id="centerbar">
        <div id="center-header">
          %if not script:
            ${self.center_header()}
          %endif
        </div>
        <div id="center-contents">
          %if not script:
            ${self.center_contents()}
          %endif
        </div>
      </div>
      <div id="rightbar">
        %if not script:
          ${self.right()}
        %endif
      </div>
    </div>
  </div>
%if script:
  <script type="application/javascript" src="/public/scripts/jquery.js"></script>
  <script type="application/javascript" src="/public/scripts/jquery.address.js?state=/"></script>
  <script type="application/javascript" src="/public/scripts/social.js"></script>
%else:
</body>
</html>
%endif
