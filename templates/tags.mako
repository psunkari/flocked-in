<%! from social import utils, _, __, plugins %>
<%! from social.logging import log %>

<!DOCTYPE HTML>

<%namespace name="widgets" file="widgets.mako"/>
<%namespace name="item" file="item.mako"/>
<%inherit file="base.mako"/>

<%def name="layout()">
  %if tagId:
  <div class="contents has-left has-right">
  %else:
  <div class="contents has-left">
  %endif
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="center-header" id="tags-header">
        %if not script:
          ${self.header(tagId)}
        %endif
      </div>
      <div id="right">
        <div id="tag-me"></div>
        <div id="tag-followers"></div>
        <div id="tag-stats"></div>
      </div>
      <div id="center">
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
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="header(tagId=None)">
  <div class="titlebar">
    <div id="title">
      %if tagId:
        <span class="middle title">${tags[tagId]["title"]}</span>
        <ul id='tag-actions-${tagId}' class="middle h-links">
          ${tag_actions(tagId, tagFollowing, False)}
        </ul>
      %else:
        <span class="middle title">${"Tags"}</span>
      %endif
    </div>
  </div>
</%def>

<%def name="itemsLayout()">
  <div id="tag-items">
    ${self.items()}
  </div>
</%def>

<%def name="items()">
  <%
    for convId in conversations:
      try:
        item.item_layout(convId)
      except Exception, e:
        log.err("Exception when displaying %s in tags" % convId)
        log.err(e)
  %>
  %if nextPageStart:
    <div id="next-load-wrapper" class="busy-indicator">
      <a id="next-page-load" class="ajax" href="/tags?id=${tagId}&start=${nextPageStart}"
         data-ref="/tags/more?id=${tagId}&start=${nextPageStart}">
        ${_("Fetch older posts")}
      </a>
    </div>
  %else:
    <div id="next-load-wrapper">${_("No more posts to show")}</div>
  %endif
</%def>

<%def name="tag_actions(tagId, tagFollowing, fromListTags=True)">
  <%
    if fromListTags:
      button_class  = 'button-link'
    elif tagFollowing:
      button_class = 'button'
    else:
      button_class= 'button default'
  %>
  %if not tagFollowing:
    <button class='${button_class} ajaxpost' title='follow the tag' data-ref="/tags/follow?id=${tagId}">${_("Follow")}</button>
  %else:
    <button class="${button_class} ajaxpost"  data-ref='/tags/unfollow?id=${tagId}' title='unfollow the tag'>${_("Unfollow")}</button>
  %endif
</%def>

<%def name="paging()">
  <ul class="h-links">
    %if prevPageStart:
      <li class="button"><a class="ajax" href="/tags/list?start=${prevPageStart}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/tags/list?start=${nextPageStart}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

<%def name="tagsListLayout()">
  <div id="tags-wrapper" class="paged-container tl-wrapper">
    ${listTags()}
  </div>
  <div class='clear'></div>
  <div id="tags-paging" class="pagingbar">
    ${self.paging()}
  </div>
</%def>

<%def name="listTags()">
  %for tagId in tagIds:
    ${_displayTag(tagId)}
  %endfor
</%def>

<%def name="_displayTag(tagId, showActions=True, showDelete=False)">
  <%
    tagName = tags[tagId]['title']
    followersCount = tags[tagId].get('followersCount', 0)
    itemsCount = tags[tagId].get("itemsCount", "0")
    tagicon = 'large-icon' if not tagsFollowing or tagId not in tagsFollowing else 'large-icon large-tag-following'
  %>
  <div id ='tag-${tagId}'>
    <div class="tl-item" id="tag-${tagId}">
      <div class='tl-avatar ${tagicon}'></div>
      <div class='tl-details'>
        <div class='tl-name'><a href='/tags?id=${tagId}'>${tagName}</a></div>
        <div class='tl-title'>${_('%s posts, %s followers' %(itemsCount, followersCount))}</div>
        % if showDelete:
            <button class='company-remove ajaxpost' title='' data-ref='/admin/tags/delete?id=${tagId}'></button>
        %endif
        %if showActions:
          <div class="tl-toolbox" id='tag-actions-${tagId}'>${tag_actions(tagId, tagId in tagsFollowing)}</div>
        %endif
      </div>
    </div>
  </div>
</%def>
