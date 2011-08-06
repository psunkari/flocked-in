
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

<%def name="forgotPasswd()">
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
              <td style="font-size: 14px;">
                 You are recieving this mail because you requested a password reset on ${brandName}.
                 <br/><br/>
                 Please go to the following page to reset your password. 
                 <a href="${resetPasswdUrl}">${resetPasswdUrl}</a> 
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
      </table>
    </div>
  </body>
  </html>
</%def>

## Generic notifications.

<%def name="header()">
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
</%def>

<%def name="footer()">
            </tr>
          </table>
        </td></tr>
        <tr><td style="color:gray;font-size:11px;padding:5px 0;">
          <a href="${rootUrl}/settings?dt=notify">Change your notification preferences</a> to choose what mails ${brandName} sends you.
        </td></tr>
      </table>
    </div>
  </body>
  </html>
</%def>

<%def name="friendRequest()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> requested to be your friend on ${brandName}.
    <br/><br/>
    If you don't know ${senderName} you can ignore this request or block the user from sending similar requests in future.
    <br/><br/>
    <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3366cc;border:1px solid #204573;color:white;font-weight:bold;">Add as Friend</div></a>
    <br/><br/>
    You can also visit <a href="${rootUrl}/people">${rootUrl}/people</a> to manage your relationships.
  </td>
  ${footer()}
</%def>

<%def name="friendAccept()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> accepted your friend request.
    You can also visit <a href="${rootUrl}/people">${rootUrl}/people</a> to manage your relationships.
  </td>
  ${footer()}
</%def>

<%def name="follower()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> started following you on ${brandName}
    %if senderId in relations.friends:
      <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#dddddd;border:1px solid #cccccc;color:#333333;font-weight:bold;">${senderName} is already your friend</div></a>
    %elif relations.pending.get(senderId, None) == "1":
      You also have a pending friend request from ${senderName}.
      <br/><br/>
      <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3366cc;border:1px solid #204573;color:white;font-weight:bold;">Add as Friend</div></a>
      If you don't know ${senderName} you can ignore this request or block the user from sending similar requests in future.
    %elif senderId not in relations.subscriptions:
      <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3366cc;border:1px solid #204573;color:white;font-weight:bold;">Follow ${senderName}</div></a>
    %endif
    You can also visit <a href="${rootUrl}/people">${rootUrl}/people</a> to manage your relationships.
  </td>
  ${footer()}
</%def>

<%def name="orgNewUser()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> just joined ${brandName}.
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow or add him/her as your friend.
  </td>
  ${footer()}
</%def>

<%def name="groupRequest()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> wants to join ${groupName}.
    <br/><br/>
    <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3366cc;border:1px solid #204573;color:white;font-weight:bold;">Add to Group</div></a>
    You can also visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to manage all your groups.
  </td>
  ${footer()}
</%def>

<%def name="groupAccept()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${groupAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    Your request to join <b>${groupName}</b> was accepted by the administrator.
    You can also visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to manage your group memberships.
  </td>
  ${footer()}
</%def>

<%def name="groupInvite()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> added you to ${groupName}.
    <br/><br/>
    You can visit <a href="${rootUrl}/groups?start=${groupId}">${rootUrl}/groups?start=${groupId}</a> to manage your subscription.
  </td>
  ${footer()}
</%def>

<%def name="groupNewMember()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> just joined ${groupName}.
    <br/><br/>
    You can visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to manage all your groups.
  </td>
  ${footer()}
</%def>

<%def name="myItemAction()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
  %if action == "C":
    <b>${senderName}</b> commented on your ${itemType}.
    <br/><br/>
    <blockquote>
      ${senderName}: ${comment}
    </blockquote>
  %elif action == "L":
    <b>${senderName}</b> liked your ${itemType}.
  %elif action == "CL":
    <b>${senderName}</b> liked your comment on ${convOwnerName}'s ${itemType}.
  %endif
  </td>
  ${footer()}
</%def>

<%def name="myActionAction()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
  %if action == "C":
    <b>${senderName}</b> commented on ${convOwnerName}'s ${itemType}.
    <br/><br/>
    <blockquote>
      ${senderName}: ${comment}
    </blockquote>
  %elif action == "L":
    <b>${senderName}</b> liked ${convOwnerName}'s ${itemType}.
  %endif
  </td>
  ${footer()}
</%def>

<%def name="messageConv()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> sent you a private message
    <br/><br/>
    <blockquote>
      ${senderName}: ${message}
    </blockquote>
  </td>
  ${footer()}
</%def>

<%def name="messageMessage()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> replied to a private conversation
    <br/><br/>
    <blockquote>
      ${senderName}: ${message}
    </blockquote>
  </td>
  ${footer()}
</%def>

<%def name="messageAccessChange()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> updated access permissions of a private conversation
  </td>
  ${footer()}
</%def>

