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
                 <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Activate your Account</div></a>
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
                 You or someone else requested a password reset for ${email} on <a href="${rootUrl}">${brandName}</a>.<br/></br>
                 Please ignore this mail if you did not request a password reset<br/><br/>
                 Click the following link to reset your password.<br/>
                 <a href="${resetPasswdUrl}">${resetPasswdUrl}</a> <br/>
                 This link is valid for 24hours only.<br/>
              </td>
            </tr>
            <tr><td style="border-top:1px solid #DDD; font-size: 14px;padding-top:10px;">
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

## Apply tag on an item that I shared
<%def name="notifyOwnerT()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
  </td>
  ${footer()}
</%def>

<%def name="notifyOwnerC()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> commented on your ${convType}.
    <br/>
    ${senderName} &mdash; ${comment}
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  ${footer()}
</%def>

<%def name="notifyOtherC()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> commented on ${convOwnerName}'s ${convType}.
    <br/>
    ${senderName} &mdash; ${comment}
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  ${footer()}
</%def>

<%def name="notifyOwnerL()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked on your ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  ${footer()}
</%def>

<%def name="notifyOwnerLC()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked your comment on your ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  ${footer()}
</%def>

<%def name="notifyOtherLC()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked your comment on ${convOwnerName}'s ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  ${footer()}
</%def>

##
## Yet to be implemented
##

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
    <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Add as Friend</div></a>
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
      <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Add as Friend</div></a>
      If you don't know ${senderName} you can ignore this request or block the user from sending similar requests in future.
    %elif senderId not in relations.subscriptions:
      <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Follow ${senderName}</div></a>
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
    <a href="${actionUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Add to Group</div></a>
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

