<%! from social import utils, _, __, plugins %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

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
      <div id="right">
        <div id="home-notifications"></div>
        <div id="home-events"></div>
        <div id="home-todo"></div>
        <div id="invite-people-block">
          ${feed.invitePeopleBlock()}
        </div>
        <div id ="group-links" >
        </div>
      </div>
      <div id="center">
        <div class="center-header">
          <div class="titlebar">
            <div id="title">${self._title()}</div>
          </div>
        </div>
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
            <div id="search-paging" class="pagingbar">
              %if not script:
                ${self.paging()}
              %endif
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</%def>


<%def name="_title()">
  <span class="middle title">${_("Search Results")}</span>
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart == 0 or prevPageStart:
      <li class="button"><a class="ajax" href="/search?q=${term}&start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/search?q=${term}&start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="results()">
  % if not conversations:
    <div id="next-load-wrapper">${_("No Matching Results")}</div>
  % else:
    %for convId in conversations:
      ${item.item_layout(convId)}
    %endfor
  %endif
</%def>
