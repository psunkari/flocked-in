<!DOCTYPE HTML>

<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>
<%! import uuid %>

<%inherit file="base.mako"/>

<%def name="layout()">
  <div class="contents has-left">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div class="center-header">
        <div class="titlebar">
          <span class="middle title">${_('Files')}</span>
        </div>
        <div id="invite-people-wrapper">
        </div>
      </div>
      <div id="right"></div>
      <div id="center">
        <div class="center-contents">
          <div id="file-view" class="viewbar">
            %if not script:
              ${viewOptions(viewType)}
            %endif
          </div>
          <div id="files-content" class="paged-container">
            %if not script:
              ${listFiles()}
            %endif
          </div>
          <div id="files-paging" class="pagingbar">
            %if not script:
              ${pagingBar()}
            %endif
          </div>
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
 <%
    tabs = [('myFiles', _("My Files")),(_('myFeedFiles'), 'My Feed'), ( 'companyFiles', _('All Company'))]
 %>
  <ul class="h-links view-options">
    %for item, display in tabs:
      %if selected == item:
        <li class="selected">${_(display)}</li>
      %else:
        <li><a href="/files/list?type=${item}" class="ajax">${_(display)}</a></li>
      %endif
    %endfor
  </ul>
</%def>


<%def name="listFiles()">
  <%
    def getTimestamp(tuuid):
      timestamp = (uuid.UUID(bytes=tuuid).time - 0x01b21dd213814000)/1e7
      return utils.simpleTimestamp(timestamp, me['basic']['timezone'])

    files, hasPrevPage, nextPageStart, toFetchEntities = userfiles if userfiles else ('', '', '', '')
  %>
  <table cellspacing="0" cellpadding="0" class="files-table" style="width:100%;">
    <colgroup>
      <col style="width:auto;"></col>
      <col style="width:65%;"></col>
      <col style="width:20px;"></col>
    </colgroup>
    <tr>
      <th class="file-info toolbar">${_("File")}</th>
      <th class="file-context toolbar">${_("Context")}</th>
      <th class="file-actions toolbar"></th>
    </tr>
    <tbody>
    %for tuuid, (fId, name, itemId, ownerId, item) in files:
      <tr>
        <td class="file-info">
          <div class="file-wrapper">
            <div class="file-icon"></div>
            <div class="file-details">
              <div class="file-name"><a href='/files?id=${itemId}&fid=${fId}&ver=${utils.encodeKey(tuuid)}'>${name}</a></div>
              <div class="file-meta">${getTimestamp(tuuid)}</div>
            </div>
          </div>
        </td>
        <td class="file-context">
          <div class="file-name">${utils.userName(ownerId, entities[ownerId])}: ${utils.toSnippet(item['meta']['comment'], 200)}</div>
          <div class="file-meta"><a href='/item?id=${itemId}'>View full ${_(item['meta']['type'])}</a></div>
        </td>
        <td class="file-actions"></td>
      </tr>
    %endfor
    </tbody>
  </table>
</%def>

<%def name="pagingBar()">
  <%
    files, hasPrevPage, nextPageStart, toFetchEntities = userfiles if userfiles else ('', '', '', '')
    thisPageStart = files[0][0] if files else ''
  %>
  <ul class="h-links">
    %if hasPrevPage:
      <li class="button"><a class="ajax" href="/files/list?end=${utils.encodeKey(thisPageStart)}&type=${viewType}">${_("&#9666; Previous")}</a></li>
    %else:
      <li class="button disabled"><a>${_("&#9666; Previous")}</a></li>
    %endif
    %if nextPageStart:
      <li class="button"><a class="ajax" href="/files/list?start=${utils.encodeKey(nextPageStart)}&type=${viewType}">${_("Next &#9656;")}</a></li>
    %else:
      <li class="button disabled"><a>${_("Next &#9656;")}</a></li>
    %endif
  </ul>
</%def>

