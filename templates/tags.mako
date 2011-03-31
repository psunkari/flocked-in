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
            ${self.header()}
          %endif
        </div>
        <div id="tag-items" class="center-contents">
          %if not script:
            ${self.items()}
          %endif
        </div>
      </div>
    </div>
  </div>
</%def>

<%def name="header(tagId)">
  <div class="titlebar">
    <div id="title">
      <span class="middle title">${tags[tagId]["title"]}</span>
      <ul id="tag-actions-${tagId}" class="middle user-actions h-links">
        ${tag_actions(tagId)}
      </ul>
    </div>
  </div>
</%def>

<%def name="items()">
  %for convId in conversations:
    ${item.item_layout(convId, True, True)}
  %endfor
</%def>

<%def name="tag_actions(tagId, showRemove=True)">
  %if not tagFollowing:
    <li class="button default" onclick="$.post('/ajax/tags/follow', 'id=${tagId}', null, 'script')"><span class="button-text">Follow</span></li>
  %elif showRemove:
    <li class="button" onclick="$.post('/ajax/tags/unfollow', 'id=${tagId}', null, 'script')"><span class="button-text">Unfollow</span></li>
  %endif
</%def>
