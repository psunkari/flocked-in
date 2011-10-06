
<%def name="header()">
  <%
    logoSrc = '/rsrcs/img/flocked-in-small.png'
    if not logoSrc.startswith('http'):
      logoSrc = rootUrl+logoSrc
  %>
  <html xmlns="http://www.w3.org/1999/xhtml">
  <body style="margin:5px;padding:0;color:#555;font-family:arial,sans-serif;">
    <div align="center" style="background-color:#f4f4f4;border-radius:4px;border:1px solid #dddddd;width:600px;">
      <table width="590" cellpadding="0" cellspacing="0" border="0">
        <tr><td align="left">
          <img src="${logoSrc}"
               alt="flocked.in" style="margin:10px 0;"/>
        </td></tr>
        <tr><td>
          <table cellspacing="20" cellpadding="0" width="590"
                 border="0" bgcolor="#ffffff"
                 style="border:1px solid #dddddd;border-radius:4px;">
            <tr>
</%def>

<%def name="footer(text=True)">
            </tr>
          </table>
        </td></tr>
        <tr><td style="color:gray;font-size:11px;padding:5px 0;">
          %if text:
            <a href="${rootUrl}/settings?dt=notify">Change your notification preferences</a> to choose what mails ${brandName} sends you.
          %endif
        </td></tr>
      </table>
    </div>
  </body>
  </html>
</%def>

## Invite someone to flocked.in
<%def name="invite()">
  ${header()}
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
                 %if sameOrg:
                    <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">${'Join %s network' % senderOrgName}</div></a>
                 %else:
                    <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">${'Join %s' % brandName}</div></a>
                 %endif
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


<%def name="signup()">
  ${header()}
              <td style="font-size: 14px;">
                Welcome to ${brandName}.<br/>
                Please click below to activate your account.
                 <br/><br/>
                 <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">${'Join %s' % brandName}</div></a>
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
        </td></tr>
      </table>
    </div>
  </body>
  </html>
</%def>


<%def name="accountExists()">
  ${header()}
  <td style="font-size: 14px;">
    You already have an account on ${brandName}.<br/><br/>
    <a href="${rootUrl}/signin" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Sign-in to ${brandName}</div></a>
  </td>
  ${footer(text=False)}
</%def>


## Forgot password email
<%def name="forgotPasswd()">
  ${header()}
  <td style="font-size: 14px;">
    A request was received to reset the password for ${email} on <a href="${rootUrl}">${brandName}</a>.
    To change the password please click the following link, or paste it into your browser:<br/><br/>
    <a href="${resetPasswdUrl}">${resetPasswdUrl}</a> <br/>
    This link is valid for 24 hours only.<br/>
    If you did not request this email there is no need for further action<br/>
  </td>
  ${footer(text=False)}
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

<%def name="notifyFA()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> accepted your friend request.<br/>
    You can visit <a href="${rootUrl}/people">${rootUrl}/people</a> to see the list of all your friends.
  </td>
  ${footer()}
</%def>

<%def name="notifyNF()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> started following you on ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow ${senderName}.<br/>
  </td>
  ${footer()}
</%def>

<%def name="notifyIA()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> accepted your invitation to join ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow or to add ${senderName} as your friend.
  </td>
  ${footer()}
</%def>

<%def name="notifyNU()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> just joined ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow or to add ${senderName} as your friend.
  </td>
  ${footer()}
</%def>

<%def name="notifyGA()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    Your request to join <b>${senderName}</b> was accepted by an administrator.<br/>
    Visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to see a list of all your groups.
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
    You can also visit <a href="${rootUrl}/people">${rootUrl}/people</a> to your relationships.
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

<%def name="notifyGI()">
  ${header()}
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    ${senderName} invited you to join <b>${groupName}</b> group.<br/>
    Visit <a href="${rootUrl}/groups?type=invitaions">${rootUrl}/groups?type=invitations</a> to accept the invitation.
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

