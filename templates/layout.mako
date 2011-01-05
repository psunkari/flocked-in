<%! from gettext import gettext as _ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html>

<head>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
</head>

<body>
  <div id="topbar">
    <div id="top" class="contents">
      <div id="avatar" class="left"></div>
      <div id="sitelogo" class="left"></div>
      <div id="searchform" class="right">
        <input type="text" id="searchbox" placeholder="Search people, messages and statuses..."/>
        <input type="button" id="searchbutton" value="${_('Go!')}"/>
      </div>
    </div>
  </div>
  <div id="menubar">
    <div id="menu" class="contents">
      <div id="name" class="b left"><a href="#">Prasad Sunkari, Hacker</a></div>
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
      </div>
      <div id="centerbar">${self.centerBar()}</div>
      <div id="rightbar">${self.rightBar()}</div>
    </div>
  </div>
</body>
<script type="application/javascript" src="/public/scripts/jquery.js"></script>
<script type="application/javascript" src="/public/scripts/jquery.address.js?state=/"></script>
<script type="application/javascript" src="/public/scripts/social.js"></script>
</html>
