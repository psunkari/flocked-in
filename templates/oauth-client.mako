<%! from social import utils, _, __, constants %>
<!DOCTYPE HTML>

<%inherit file="base-client.mako"/>

<%def name="layout()">
  <% client_id = "6f3b0d99a48deea7ec940c148a8099ebc82027c7" %>
  <div class="contents">
    <div id="center-right">
      <div class="center-header">
        <div class="titlebar">
          <span class="middle title">${_('Third Party Access')}</span>
          <span class="button title-button">
            <a class="ajax" href="/client?view=pop&id=${client_id}"  data-ref="/client?view=pop&id=${client_id}">${_('Login in using Flocked.in')}</a>
          </span>
          </span>
        </div>
      </div>
      <div id="center">
        <div id="app-dialog"></div>
      </div>
      <div class="clear"></div>
    </div>
  </div>
</%def>

<%!
  def newlinescape(text):
    return utils.normalizeText(text)
%>


<%def name="access_granted_layout()">
<% client_id = "6f3b0d99a48deea7ec940c148a8099ebc82027c7" %>
<h2> We are now ready to access your feed.
<button onclick="window.opener.$('#app-dialog').text('Please wait while we fetch your feed');window.opener.$$.oclient.getAccessToken41('${code}', '${redirect_url}', '${client_id}');window.close();" class="default button" tabindex="1" type="button" id="submit_approve_access">Continue to foo bar'ed feeds</button>
</%def>

<%def name="access_denied_layout()">
<% client_id = "6f3b0d99a48deea7ec940c148a8099ebc82027c7" %>
<h2> You denied a request to access your feed. Start over again if you wish .

</%def>
