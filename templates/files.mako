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
        </div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%def name="viewOptions(selected)">
 <%
    tabs = [('myFiles', _("My Files")),(_('myFeedFiles'), 'Files in Feed'), ( 'companyFiles', _('Company Files'))]
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
      return (uuid.UUID(bytes=tuuid).time - 0x01b21dd213814000)/1e7
    _files, nextPageStart, toFetchEntities= userfiles if userfiles else ('', '', '')
    user = {'basic': {'name': 'name'}}
    tr_class = 'even'
  %>
  %if not fromFetchMore:
    <table class="files">
      <tr>
        <th>${_("File")}</th>
        <th>${_("Conv-type")}</th>
        <th>${_("Uploaded By")}</th>
        <th>${_('Uploaded On ')}</th>
      </tr>
  %endif
  %for tuuid, (fid, name, itemId, ownerId, convType) in _files:
    <tr class="row-${tr_class}">
      <td> <a href='/files?id=${itemId}&fid=${fid}&ver=${tuuid}'>${name}</a> </td>
      <td > <a href='/item?id=${itemId}'>${_(convType)}</a></td>
      %if ownerId != fid:
        <td > ${utils.userName(ownerId, entities[ownerId])}</td>
      %else:
        <td > ${utils.userName(ownerId, user)}</td>
      %endif
      <td > ${utils.simpleTimestamp(getTimestamp(utils.decodeKey(tuuid)))} </td>
    </tr>
    <% tr_class = "odd" if tr_class == 'even' else 'even' %>
  %endfor

  %if nextPageStart:
      <tr></tr>
      <tr id="next-load-wrapper" class="busy-indicator">
        <td class="button">
        %if fromProfile:
          <a id="next-page-load" class="ajax" data-ref="/profile?id=${userKey}&start=${nextPageStart}&dt=${detail}">${_("Fetch older files")}</a>
        %else:
          <a id="next-page-load" class="ajax" data-ref="/files/list?start=${nextPageStart}&type=${viewType}">${_("Fetch older files")}</a>
        %endif
        </td>
        <td></td>
        <td></td>
        <td></td>
      </tr>
  %else:
      <tr id="next-load-wrapper">
        <td class="button disabled">${_("No more files to show")}</td>
      </tr>
  %endif

  %if not fromFetchMore:
    </table>
  %endif

</%def>
