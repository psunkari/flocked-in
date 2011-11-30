<%! from social import utils, config, apps, _, __ %>
<!DOCTYPE HTML>
<html lang="en" dir="ltr" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>${title}</title>
  <link href="/rsrcs/css/static.css" media="all" rel="stylesheet" type="text/css">
  <link rel="shortcut icon" href="/rsrcs/img/favicon.ico" type="image/x-icon" />
  <style type="text/css">
    .centered-wrapper {
      width: auto;
      max-width: 780px;
    }
  </style>
</head>

<body>
  <div id="header" class="centered-wrapper">
    <img id='sitelogo' src="/rsrcs/img/flocked-in.png" alt="flocked-in"/>
  </div>

  <div id="wrapper" class="centered-wrapper">
    <div id="main-contents" class="contents">
      %if errstr:
        ${self.error()}
      %else:
        ${self.authorizationForm()}
      %endif
    </div>
  </div>
</body>
</html>

<%def name="error()">
  <div id="caption">
    Authorization Error.<br/>
    ${errstr}
  </div>
  <div class="form-header">
  Please contact the application's developer for further help.
  </div>
</%def>

<%def name="authorizationForm()">
  <%
    clientMeta = client["meta"]
    clientLogoUri = clientMeta.get('avatar', '')
  %>
  <div id="scope-wrapper" style="float:left;margin-top:50px;">
    <strong>${clientMeta['name']}</strong> is requesting permission to:
    <ul style="font-size:90%;list-style-type:circle;">
      %for scope in request_scopes:
        <li>${apps.scopes[scope]}
      %endfor
    </ul>
  </div>
  %if clientLogoUri:
    <div id="client-logo" style="float:right;width:200px;height:200px;margin:30px 10px 0 0;">
      <img style="max-height:200px;max-width:200px;" src="${clientLogoUri}"/>
    </div>
  %endif
  <div id="auth-form-wrapper" style="float:left;clear:left;padding-top:20px;">
    <form class="ajax" method="POST" action="/oauth/authorize" style="display:inline;">
      <input type="hidden" value="${' '.join(request_scopes)}" name="scope"/>
      <input type="hidden" value="${client_id}" name="client_id"/>
      <input type="hidden" value="${redirect_uri}" name="redirect_uri"/>
      <input type="hidden" value="${state}" name="state"/>
      <input type="hidden" value="${signature}" name="signature"/>
      <input type="hidden" value="${token}" name="_tk"/>
      <button class="default button" tabindex="1" type="submit" name="allow" value="true"
              id="submit-approve-access" style="margin-right:10px;">Allow access</button>
      <button class="button" tabindex="1" type="submit" name="allow" value="false"
              id="submit-deny-access">No thanks</button>
    </form>
  </div>
</%def>

