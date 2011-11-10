<%! from social import utils, _, __, constants %>
<%! from base64     import urlsafe_b64encode, urlsafe_b64decode %>

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
          <span class="middle title">${_('FlockedIn Third Party Applications')}</span>
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
    <strong>${client_name}</strong> is requesting permission to:</div><div id="scope_list">
    <ul>
      <li id="scope_summary_0" class="scope_summary" tabindex="0">Manage your ${client_scope}</li>
      <ul>
        <li class="scope_detail_line">View and manage your FlockedIn ${client_scope}</li>
      </ul>
      </div>
      </div>
      </li>
    </ul>
    </div>
  </div>

<div class="modal-dialog-buttons" id="button_div">
  <form style="display: inline;" class="ajax" method="POST" action="/o/a">
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
    <div class="styledform">
    <ul>
      <li>
        <label>Application Name</label>
        <input type="text" name="client_name"/>
      </li>
      <li>
        <label>Application Description</label>
        <input type="text" name="client_desc"/>
      </li>
      <li>
        <label>Application Category</label>
        <select name="client_category">
          <option value="code">Desktop/Web Application</option>
          <option value="client">Server Side Application</option>
        </select>
      </li>
      <li>
        <label>Application Scope</label>
         <input type="checkbox" name="client_scope" value="feed" id="scope_feed"/>
         <label for="scope_feed">Feed</label>
      </li>
      <li>
        <label>Application Redirect Urls</label>
        <input type="text" name="client_redirect_url"/>
        <input type="text" name="client_redirect_url"/>
      </li>
      <div class="styledform-buttons">
        <button class="default button" tabindex="1" type="submit" >Add Application</button>
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
        <div class="user-details-name"><a href="/apps?id=${appId}">${apps[appId]["meta"]["client_name"]} -- ${apps[appId]["meta"]["client_category"]}</a></div>
        <div class="user-details-title">${appId}</div>
        <div class="user-details-title">${apps[appId]["meta"]["client_scope"]}</div>
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

<h2>${client_name}</h2>
<div><label>Client Identifier</label><span> ${client_id}</span></div>
  %if client_category == "client":
    <label>Client Password: </label>
    <span>${client_password}</span>
  % endif
<div><label>Client Scope</label><span> ${client_scope.replace(":", ", ")}</span></div>
<div><label>Application Category </label>
  %if client_category == "client":
    <span>Server Side Application/ Service</span>
  %elif client_category == "code":
    <span>Desktop/Mobile/HTML5 Application</span>
  % endif
</div>
<div>
  %for url in client_redirects.split(":"):
    <pre>${urlsafe_b64decode(url)}</pre>
  %endfor
</div>

</%def>

<%def name="blank_layout()">

</%def>
