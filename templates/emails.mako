
<%def name="invite()">
  <html xmlns="http://www.w3.org/1999/xhtml">
  <body style="margin:5px;padding:0;color:#555;font-family:arial,sans-serif;">
    <div align="center" style="background-color:#f4f4f4;border-radius:4px;border:1px solid #dddddd;width:600px;">
      <table width="590" cellpadding="0" cellspacing="0" border="0">
        <tr><td align="left">
          <img src="${rootUrl}/rsrcs/img/flocked-in-small.png"
               alt="flocked.in" style="margin:10px 0;"/>
        </td></tr>
        <tr><td>
          <table cellspacing="20" cellpadding="0" width="590"
                 border="0" bgcolor="#ffffff"
                 style="border:1px solid #dddddd;border-radius:4px;">
            <tr>
              <td valign="top" align="right" style="width:48px;" rowspan="2">
                <img src="${senderAvatarUrl}" alt="">
              </td>
              <td style="font-size: 14px;">
                 %if sameOrg:
                   <b>${senderName}</b> invited you to join ${senderOrgName} network on ${brandName}.
                 %else:
                   <b>${senderName}</b> invited you to try ${brandName}.
                 %endif
                 <br/><br/>
                 <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3366cc;border:1px solid #204573;color:white;font-weight:bold;">Activate your Account</div></a>
                 <br/><br/>
                 You can also visit <a href="${activationUrl}">${activationUrl}</a> to activate your account.
              </td>
            </tr>
            <tr><td style="border-top:1px solid #DDD; font-size: 14px;padding-top:10px;">
              ${brandName} is an enterprise social platform built on top of
              micro-blogging and activity streams that helps you stay connected 
              with your co-workers.  It helps your company engage and keep
              everyone informed.
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="color:gray;font-size:11px;padding:5px 0;">
          You received this mail because ${senderName} invited you.<br/>
          <a href="${blockSenderUrl}">Click here</a> to block invitations
          from ${senderName}.  You may also block all invitations from ${brandName}
          <a href="${blockAllUrl}">by clicking here.</a>.
        </td></tr>
      </table>
    </div>
  </body>
  </html>
</%def>

