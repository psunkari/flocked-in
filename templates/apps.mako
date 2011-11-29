<%! from social.apps import scopes %>
<%! from social import utils, _, __, constants %>
<%! from base64 import b64decode %>
<%! import pickle %>
<!DOCTYPE HTML>

<%inherit file="base.mako"/>
<%namespace name="settings" file="settings.mako"/>

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
          <span id="apps-title" class="middle title">
            %if not script:
              ${title}
            %endif
          </span>
        </div>
      </div>
      <div id="center">
        <div id="apps-contents" class="center-contents"></div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>


<%def name="nav_menu()">
  ${settings.nav_menu()}
</%def>


<%def name="appListing()">
  <%
    apikeys = apps.get('apikeys', {}).keys()
    enabled = apps.get('apps', {}).keys()
    myapps = apps.get('my', {}).keys()
  %>
  <div id="apikeys-wrapper" class="applist-wrapper">
    <div class="center-title">API Keys</div>
    %if apikeys:
      %for key in apikeys:
      %endfor
    %else:
      You don't have any pre-authenticated API keys.
      <a class="ajax" href="/apps/register?type=apikey">Create a key?</a>
    %endif
  </div>
  <div id="enabled-wrapper" class="applist-wrapper">
    <div class="center-title">Allowed Applications</div>
    %if enabled:
      %for app in using:
      %endfor
    %else:
      You did not allow any external application to access your data.
    %endif
  </div>
  %if myapps:
    <div id="myapps-wrapper" class="applist-wrapper">
      <div class="center-title">My Applications</div>
        %for app in myapps:
          ${app}
        %endfor
    </div>
  %endif
</%def>


<%def name="registrationForm(apiKey=False)">
  <form style="display: inline;" class="ajax" method="POST" action="/apps/register">
    <ul class="styledform">
      <li class="form-row">
        <label class="styled-label">${_('Name')}</label>
        <input type="text" name="name"/>
      </li>
      %if not apiKey:
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
      %else:
        <input type="hidden" name="category" value="apikey"/>
      %endif
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
      %if not apiKey:
        <li class="form-row">
          <label class="styled-label">${_('Redirect URL')}</label>
          <input type="text" name="redirect"/>
        </li>
      %endif
      <div class="styledform-buttons">
        <a href="/apps" class="ajax">&laquo; Back to Applications</a>&nbsp;&nbsp;&nbsp;&nbsp;
        %if apiKey:
          <button class="default button" tabindex="1" type="submit" >${_('Generate Key')}</button>
        %else:
          <button class="default button" tabindex="1" type="submit" >${_('Create Application')}</button>
        %endif
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


<%def name="appDetails()">
<h2>${name}</h2>
<div><label>App Id</label><span>${id}</span></div>
    <label>Client Password: </label>
    <span>${secret}</span>
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

