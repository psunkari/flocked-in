<%! from social import utils, config, _, __ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

<%def name="title()">
  ${config.get('Branding', 'Name')} &mdash; ${_('Private, Secure and Free Social Network for Enterprises')}
</%def>

<%def name="layout()">
</%def>

<%def name="nav_menu()">
  <%
    def navMenuItem(link, text, id):
      cls = "sidemenu-selected" if id == menuId else ''
      return '<li><a href="%(link)s" class="ajax busy-indicator %(id)s-sideitem %(cls)s"><span class="sidemenu-icon icon %(id)s-icon"></span><span class="sidemenu-text">%(text)s</span></a></li>' % locals()
  %>
  <div id="mymenu-container" class="sidemenu-container">
    <ul id="mymenu" class="v-links sidemenu">
      ${navMenuItem("/feed", _("News Feed"), "feed")}
      ${navMenuItem("/notifications", _("Notifications"), "notifications")}
      ${navMenuItem("/messages", _("Messages"), "messages")}
##      ${navMenuItem("/events", _("Events"), "events")}
      ${navMenuItem("/people", _("People"), "people")}
      ${navMenuItem("/feed?id=%s" % orgKey, _("Company Feed"), "org")}
      ${navMenuItem("/groups", _("Groups"), "groups")}
      ${navMenuItem("/tags", _("Tags"), "tags")}
    </ul>
  </div>
%if script:
  <div id="feedbackmenu-container" class="sidemenu-container">
    <ul id="feedbackmenu" class="v-links sidemenu">
      <li><a title="Feedback" onclick="$$.feedback.showFeedback()"><span class="sidemenu-icon icon feedback-icon"></span><span class="sidemenu-text">${_('Feedback')}</span></a></li>
    </ul>
  </div>
%endif
</%def>

<html>
<head>
  <title>${self.title()}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/social.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/widgets.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/jquery.ui.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/rsrcs/css/messaging.css"/>
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
          <% logoURI = utils.companyLogo(org) %>
          % if logoURI:
            <img src="${logoURI}" alt="${org['basic']['name']}"/>
          % endif
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
          %if isOrgAdmin:
            <li><a href="/admin" class="ajax">${_("Admin")}</a></li>
          %endif
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
  <script type="text/javascript" src="/rsrcs/js/jquery.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.menu.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.autocomplete.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.ui.datepicker.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.address.js"></script>
  <script type="text/javascript" src="/rsrcs/js/jquery.autogrow-textarea.js"></script>
  <script type="text/javascript" src="/rsrcs/js/social.js"></script>
  <script type="text/javascript">
    $().ready(function() {$$.ui.init()});
  </script>
%else:
</body>
</html>
%endif
