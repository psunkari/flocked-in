<%! from social import utils, _, __, plugins %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
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
        <div id="tag-me"></div>
        <div id="tag-followers"></div>
        <div id="tag-stats"></div>
      </div>
      <div id="center">
        <div class="center-header" id="tags-header">
          %if not script:
            ${self.header(tagId)}
          %endif
        </div>
        <div id="content" class="center-contents">
          %if not script:
            %if tagId:
              ${self.itemsLayout()}
            %else:
              ${self.tagsListLayout()}
            %endif
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="header(tagId=None)">
  <div class="titlebar">
    <div id="title">
      %if tagId:
        <span class="middle title">${tags[tagId]["title"]}</span>
        <ul id="tag-actions-${tagId}" class="middle user-actions h-links">
          ${tag_actions(tagId, tagFollowing)}
        </ul>
      %else:
        <span class="middle title">${"Tags"}</span>
      %endif
    </div>
  </div>
</%def>

<%def name="itemsLayout()">
  <div id="tag-items" class="center-contents">
    ${self.items()}
  </div>
</%def>

<%def name="items()">
  %for convId in conversations:
    ${item.item_layout(convId)}
  %endfor
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator"><a id="next-page-load" class="ajax" href="/tags?id=${tagId}&start=${nextPageStart}" _ref="/tags/more?id=${tagId}&start=${nextPageStart}">${_("Fetch older posts")}</a></div>
  %else:
    <div id="next-load-wrapper">No more posts to show</div>
  %endif
</%def>

<%def name="tag_actions(tagId, tagFollowing)">
  %if not tagFollowing:
    <button class="button default" onclick="$.post('/ajax/tags/follow', 'id=${tagId}', null, 'script')"><span class="button-text">Follow</span></button>
  %else:
    <button class="button" onclick="$.post('/ajax/tags/unfollow', 'id=${tagId}', null, 'script')"><span class="button-text">Unfollow</span></button>
  %endif
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/tags?start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/tags?start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="tagsListLayout()">
  <div id="tags-wrapper" class="paged-container">
    ${self.listTags()}
  </div>
  <div id="tags-paging" class="pagingbar">
    ${self.paging()}
  </div>
</%def>

<%def name="listTags()">
  <%
    counter = 0
    firstRow = True
  %>
  %for tagname in tags:
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">${_displayTag(tagname)}</div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif
</%def>

<%def name="_displayTag(tagname)" >
  <% tagId = tags[tagname] %>
  <div class = 'user-details'>
    <div class="user-details-name"><a class="ajax" href="/tags?id=${tagId}">${tagname}</a></div>
    <div class="user-details-actions">
      <ul id='tag-actions-${tagId}' class="middle h-links">
        ${tag_actions(tagId, tagId in tagsFollowing)}
      </ul>
    </div>
  </div>
</%def>
