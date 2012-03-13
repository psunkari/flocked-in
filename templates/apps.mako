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
    apikeys = apps.get('apikeys', {})
    enabled = apps.get('apps', {})
    myapps = apps.get('my', {})
  %>
  <div id="apikeys-wrapper" class="applist-wrapper">
    <div class="center-title">API Keys</div>
    <div class="tl-wrapper">
      %for appId in apikeys.keys():
        %if appId in clients:
          <% client = clients[appId]['meta'] %>
          <div class="tl-item" id="app-${appId}">
            <div class="tl-avatar"></div>
            <div class="tl-details">
              <div class="tl-name"><a href="/apps?id=${appId}" class="ajax">${client['name']}</a></div>
              <div class="tl-title">${utils.simpleTimestamp(apikeys[appId], me.basic['timezone'])}</div>
              <div class="tl-toolbox"><button
                  class="button-link ajaxpost" title="Revoke access to ${client['name']}"
                  data-ref="/apps/revoke?id=${appId}">Revoke</button></div>
            </div>
          </div>
        %endif
      %endfor
      <div class="tl-item" id="app-gen-apikey" style="line-height: 48px;">
        <a href="/apps/register?type=apikey" class="ajax" style="display:block;text-align:center;">&laquo; Generate an API key &raquo;</a>
      </div>
    </div>
    <div class="clear" style="margin-bottom: 10px;"/>
  </div>
  <div id="enabled-wrapper" class="applist-wrapper">
    <div class="center-title">Allowed Applications</div>
    %if enabled:
      <div class="tl-wrapper">
        %for appId in enabled.keys():
          %if appId in clients:
            <% client = clients[appId]['meta'] %>
            <div class="tl-item" id="app-${appId}">
              <div class="tl-avatar"></div>
              <div class="tl-details">
                <div class="tl-name"><a href="/apps?id=${appId}" class="ajax">${client['name']}</a></div>
                <div class="tl-title" style="white-space:pre-wrap;">&ndash; ${client['desc']}</div>
              </div>
            </div>
          %endif
        %endfor
      </div>
    %else:
      <div class="tl-empty-msg">
        You did not authorize any third-party application to access your data.
      </div>
    %endif
    <div class="clear" style="margin-bottom: 10px;"/>
  </div>
  %if myapps:
    <div id="myapps-wrapper" class="applist-wrapper">
      <div class="center-title">My Applications</div>
      <div class="tl-wrapper">
        %for appId in myapps.keys():
          %if appId in clients:
            <% client = clients[appId]['meta'] %>
            <div class="tl-item" id="app-${appId}">
              <div class="tl-avatar"></div>
              <div class="tl-details">
                <div class="tl-name"><a href="/apps?id=${appId}" class="ajax">${client['name']}</a></div>
                <div class="tl-title" style="white-space:pre-wrap;">${client['desc']}</div>
              <div class="tl-toolbox"><button
                  class="button-link ajaxpost" title="Delete ${client['name']}"
                  data-ref="/apps/delete?id=${appId}">Delete</button></div>
              </div>
            </div>
          %endif
        %endfor
      </div>
      <div class="clear" style="margin-bottom: 10px;"/>
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
          %if apiKey:
            %for scope, description in scopes.items():
              <div class="multiselect">
                <label><input type="checkbox" name="scope" value=${scope}>${description}</label>
              </div>
            %endfor
          %else:
            %for scope in scopes.keys():
              <div class="multiselect">
                <label><input type="checkbox" name="scope" value=${scope}>${scope}</label>
              </div>
            %endfor
          %endif
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


<%def name="registrationResults()">
  <%
    meta = client
    clientScopes = meta['scope'].split(' ')
    apiKey = (meta['category'] == "apikey")
  %>
  <div style="text-align:center; margin: 30px; border-bottom: 1px solid #EEE;">
    %if not info:
      %if apiKey:
        <span style="font-size:18px;">API key created. Please note the Id and Secret.</span><br/>
      %else:
        <span style="font-size:18px;">Application registered. Please note the Id and Secret.</span><br/>
      %endif
    %else:
      <span style="font-size:18px;">${info}</span><br/>
    %endif
    <span style="color:#AAA;">The secret will not be displayed again. You may however generate a new client secret anytime later.</span>
  </div>
  <ul class="styledform">
    <li class="form-row">
      <label class="styled-label">Client Id</label>
      <span class="styledform-text" style="font-family: monospace;">${clientId}</span>
    </li>
    <li class="form-row">
      <label class="styled-label">Client Secret</label>
      <span class="styledform-text" style="font-family: monospace;">${meta['secret']}</span>
    </li>
    <li class="form-row">
      <span class="styled-label">Permissions</span>
      <span class="styledform-text" style="height: 9em;">
        <ul style="padding: 2px 0 2px 20px; line-height: 1.5em;">
        %for scope in clientScopes:
          <li>${scopes[scope]}</li>
        %endfor
        </ul>
      </span>
    </li>
    %if not apiKey:
      <li class="form-row">
        <span class="styled-label">Application Type</span>
        <span class="styledform-text">${meta['category']}</span>
      </li>
      <li class="form-row">
        <span class="styled-label">Redirection URI</span>
        <span class="styledform-text">${meta['redirect']}</span>
      </li>
    %endif
    <div class="styledform-buttons">
      <a href="/apps" class="ajax">&laquo; Back to Applications</a>&nbsp;&nbsp;&nbsp;&nbsp;
      %if apiKey:
        <button data-ref="/apps/revoke?id=${clientId}" class="button ajaxpost">Revoke Access</button>
      %else:
        <button data-ref="/apps/delete?id=${clientId}" class="button ajaxpost">Delete Client</button>
      %endif
    </div>
  </ul>
</%def>


<%def name="appDetails()">
  <%
    meta = client['meta']
    clientScopes = meta['scope'].split(' ')
    apiKey = (meta['category'] == "apikey")
    myApp = (meta['author'] == myId)
  %>
  <ul class="styledform">
    <li class="form-row">
      <label class="styled-label">Client Id</label>
      <span class="styledform-text" style="font-family: monospace;">${clientId}</span>
    </li>
    <li class="form-row">
      <span class="styled-label">Permissions</span>
      <span class="styledform-text" style="height: 9em;">
        <ul style="padding: 2px 0 2px 20px; line-height: 1.5em;">
        %for scope in clientScopes:
          <li>${scopes[scope]}</li>
        %endfor
        </ul>
      </span>
    </li>
    %if not apiKey:
      <li class="form-row">
        <span class="styled-label">Application Type</span>
        <span class="styledform-text">${meta['category']}</span>
      </li>
      <li class="form-row">
        <span class="styled-label">Redirection URI</span>
        <span class="styledform-text">${meta['redirect']}</span>
      </li>
    %endif
    <div class="styledform-buttons">
      <a href="/apps" class="ajax">&laquo; Back to Applications</a>&nbsp;&nbsp;&nbsp;&nbsp;
      %if subscribed or apiKey:
        <button data-ref="/apps/revoke?id=${clientId}" class="button ajaxpost">Revoke Access</button>
        &nbsp;&nbsp;
      %endif
      %if myApp:
        %if not apiKey:
          <button data-ref="/apps/revoke?id=${clientId}" class="button ajaxpost">Delete</button>
          &nbsp;&nbsp;
        %endif
        <button data-ref="/apps/secret?id=${clientId}" class="button ajaxpost">Generate new Secret</button>
      %endif
    </div>
  </ul>
</%def>

