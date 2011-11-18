<%! from social.apps import scopes %>
<%! from social import utils, _, __, constants %>
<%! from base64 import b64decode %>
<%! import pickle %>
<!DOCTYPE HTML>

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
          <span class="middle title">${_('Applications')}</span>
          <span class="button title-button">
            <a class="ajax" href="/apps/new" data-ref="/apps/new">${_('New Client')}</a>
          </span>
        </div>
        <div id="composer"></div>
      </div>
      <div id="center"></div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%!
  def newlinescape(text):
    return utils.normalizeText(text)
%>


<%def name="access_layout()">
<%
  client_scopes = supplied_scope.split(" ")
  print supplied_scope
%>

<div id="third_party_info">
  <table id="brand_icons">
    <tbody>
      <tr>
        <td id="google_icon">
          <h2>Flocked.In</h2>
        </td>
        <td id="arrow"><span class="vertical_bar"></span></td>
        <td id="third_party_name"><h3 class="brand_name">${client_name}</h3></td>
      </tr>
    </tbody>
  </table>
  <div id="grant_heading" class="clear">
    <strong>${client_name}</strong> is requesting permission to:
    <div id="scope_list">
      <ul>
        %for scope in client_scopes:
          <li class="scope_summary" >Manage your ${scope}</li>
            <ul>
              <li class="scope_detail">View and manage your FlockedIn ${scope}</li>
            </ul>
          </li>
        %endfor
      </ul>
    </div>
  </div>

<div class="modal-dialog-buttons" id="button_div">
  <form style="display: inline;" class="ajax" method="POST" action="/o/a">
    <input type="hidden" value="${supplied_scope}" name="scope"/>
    <input type="hidden" value="true" name="allow_access"/>
    <input type="hidden" value="${client_id}" name="client_id"/>
    <input type="hidden" value="${redirect_uri}" name="redirect_uri"/>
    <input type="hidden" value="${signature}" name="signature"/>
      <button class="default button" tabindex="1" type="submit" id="submit_approve_access">Allow access</button>
  </form>
  <form style="display: inline;" class="ajax" method="POST" action="/o/a">
    <input type="hidden" value="${client_id}" name="client_id"/>
    <input type="hidden" value="${redirect_uri}" name="redirect_uri"/>
    <input type="hidden" value="${signature}" name="signature"/>
    <input type="hidden" value="false" name="allow_access">
      <button class="button" tabindex="1" type="submit" id="submit_deny_access">No thanks</button>
  </form>
</div>
</%def>

<%def name="registration_layout()">
  <form style="display: inline;" class="ajax" method="POST" action="/apps">
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label">${_('Name')}</label>
        <input type="text" name="name"/>
      </li>
      <li class="form-row">
        <label class="styled-label">${_('Description')}</label>
        <textarea name="desc"/>
      </li>
      <li class="form-row">
        <label class="styled-label">${_('Type')}</label>
        <div class='styledform-inputwrap'>
          <div><label><input type="radio" name="category" value="webapp"/>Web Application</label></div>
          <div><label><input type="radio" name="category" value="native"/>Desktop/Mobile Application</label></div>
        </select>
      </li>
      <li class="form-row">
        <label class="styled-label">${_('Permissions')}</label>
        <div class='styledform-inputwrap' style='max-height:9em; overflow: auto;'>
          %for scope in scopes.keys():
            <div class="multiselect">
              <label><input type="checkbox" name="scope" value=${scope}>${scope}</label>
            </div>
          %endfor
        </div>
      </li>
      <li class="form-row">
        <label class="styled-label">${_('Redirect URL')}</label>
        <input type="text" name="redirect"/>
      </li>
      <div class="styledform-buttons">
        <button class="default button" tabindex="1" type="submit" >${_('Create Application')}</button>
        <button type="button" class="button" onclick="$('#composer').empty()">
          ${_('Cancel')}
        </button>
      </div>
    </ul>
    </div>
  </form>
</%def>

<%def name="application_listing_layout()">
  <%
    counter = 0
    firstRow = True
  %>
  %for appId in apps.keys():
    %if counter % 2 == 0:
      %if firstRow:
        <div class="users-row users-row-first">
        <% firstRow = False %>
      %else:
        <div class="users-row">
      %endif
    %endif
    <div class="users-user">
      <div class="users-details">
        <div class="user-details-name"><a href="/apps?id=${appId}">${apps[appId]["meta"]["name"]}</a></div>
        <div class="user-details-title">${appId}</div>
      </div>
    </div>
    %if counter % 2 == 1:
      </div>
    %endif
    <% counter += 1 %>
  %endfor
  %if counter % 2 == 1:
    </div>
  %endif

</%def>


<%def name="application_details_layout()">
<h2>${name}</h2>
<div><label>App Id</label><span>${id}</span></div>
    <label>Client Password: </label>
    <span>${password}</span>
<div>
  <label>Client Scope</label>
  <span>${scope}</span>
</div>
<div><label>Application Category </label>
  <span>${category}</span>
</div>
<div>
  <pre>${b64decode(redirect)}</pre>
</div>

</%def>

<%def name="blank_layout()">

</%def>
