
<%! from social import utils, _, __, brandName, rootUrl %>

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
  <% header() %>
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
              ${brandName} is a social network exclusively for people within your company
              to help you collaborate better. It revolutionizes communication at
              workplace with a richer, easier and more effective form of communication
              &ndash; <a href="${rootUrl}/about/features.html">View all features &#187;</a>
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
  <% header() %>
              <td style="font-size: 14px;">
                Thanks for signing up for ${brandName}.<br/>
                Just one more step left to complete the registration. Click below:
                <br/><br/>
                <a href="${activationUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">${'Complete Registration'}</div></a>
                <br/><br/>
                Or visit <a href="${activationUrl}">${activationUrl}</a>.
                <br/><br/>
                Thank you,<br/>
                Flocked-in team
              </td>
            </tr>
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
  <% header() %>
  <td style="font-size: 14px;">
    You already have an account on ${brandName}.<br/><br/>
    <a href="${rootUrl}/signin" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Sign-in to ${brandName}</div></a>
  </td>
  <% footer(text=False) %>
</%def>


## Forgot password email
<%def name="forgotPasswd()">
  <% header() %>
  <td style="font-size: 14px;">
    A request was received to reset the password for ${email} on <a href="${rootUrl}">${brandName}</a>.
    To change your password please click the button below:<br/><br/>
    <a href="${resetPasswdUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Reset Your Account</div></a>
    <br/><br/>
    You may also paste this link in your browser:
    <a href="${resetPasswdUrl}">${resetPasswdUrl}</a>
    <br/><br/>
    This link is valid for 24 hours only.<br/>
    If you did not request this email there is no need for further action<br/>
  </td>
  <% footer(text=False) %>
</%def>

## Apply tag on an item that I shared
<%def name="notifyOwnerT()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
  </td>
  <% footer() %>
</%def>

<%def name="notifyOwnerC()">
  <% header() %>
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
  <% footer() %>
</%def>

<%def name="notifyOtherC()">
  <% header() %>
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
  <% footer() %>
</%def>

<%def name="notifyOwnerL()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked on your ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOwnerLC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked your comment on your ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOtherLC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> liked your comment on ${convOwnerName}'s ${convType}.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View conversation</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOwnerFC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> flagged your ${convType} for review.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View report</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOwnerRFC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> commented on your ${convType} that was flagged for review.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View report</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOtherRFC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> commented on the ${convType} that you flagged for review.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View report</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyOwnerUFC()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    Your ${convType} that was earlier flagged for review by <b>${senderName}</b> has been restored.
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View report</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="notifyNF()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> started following you on ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow ${senderName}.<br/>
  </td>
  <% footer() %>
</%def>

<%def name="notifyIA()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> accepted your invitation to join ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow ${senderName}.
  </td>
  <% footer() %>
</%def>

<%def name="notifyNU()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> just joined ${brandName}.<br/>
    Visit <a href="${rootUrl}/profile?id=${senderId}">${senderName}'s profile</a> to follow ${senderName}.
  </td>
  <% footer() %>
</%def>

<%def name="notifyGA()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    Your request to join <b>${senderName}</b> was accepted by an administrator.<br/>
    Visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to see a list of all your groups.
  </td>
  <% footer() %>
</%def>

## Group Request
<%def name="notifyGR()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> wants to join ${groupName}.
    <br/><br/>
    <a href="${rootUrl}/groups?type=pendingRequests" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View all pending requests</div></a>
    <br/>
    You can also visit <a href="${rootUrl}/groups">${rootUrl}/groups</a> to manage all your groups.
  </td>
  <% footer() %>
</%def>

## Group Invite
<%def name="notifyGI()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    ${senderName} invited you to join <b>${groupName}</b> group.<br/>
    Visit <a href="${rootUrl}/groups?type=invitations">${rootUrl}/groups?type=invitations</a> to accept the invitation.
  </td>
  <% footer() %>
</%def>

## New private conversation
<%def name="notifyNM()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b>: ${message}
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View Full Conversation</div></a>
  </td>
  <% footer() %>
</%def>

## Conversation Reply
<%def name="notifyMR()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b>: ${message}
    <br/><br/>
    <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View Full Conversation</div></a>
  </td>
  <% footer() %>
</%def>

## Message access change
<%def name="notifyMA()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    %if addedMembers:
        <b>${senderName}</b> added ${" ".join([utils.userName(member, entities[member]) for member in addedMembers])} to the private conversation
    %elif removedMembers:
        <b>${senderName}</b> removed ${" ".join([utils.userName(member, entities[member]) for member in removedMembers])} from the private conversation
    %else:
        <b>${senderName}</b> updated access premissions of the private conversation
    %endif
    <br/><br/>
      <a href="${convUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View Full Conversation</div></a>
  </td>
  <% footer() %>
</%def>

## Keyword match
<%def name="notifyKW()">
  <% header() %>
  <td valign="top" align="right" style="width:48px;" rowspan="2">
    <img src="${senderAvatarUrl}" alt="">
  </td>
  <td style="font-size: 14px;">
    <b>${senderName}</b> posted content that matched a keyword - ${keyword}
    <br/><br/>
      <a href="${keywordUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">View Matching Conversations</div></a>
  </td>
  <% footer() %>
</%def>

<%def name="html_stats()">
  <table>
  <tr><td> No.of new domains </td><td > ${stats[frm_to]["newDomainCount"]} </td></tr>
  <tr> <td> New domains      </td><td  > ${stats[frm_to]["newDomains"]} </td> </tr>
  <tr><td> New signups      </td><td  > ${stats[frm_to]["signups"]} </td></tr>
  </table>
  <br/> <br/>
  <table>
    <tr> <th> Domain-Name </th> <th> new users </th> <th> total users </th> <th> new items </th> <th> total items</tr>
  % for domain in stats['domain']:
    <tr>
      <td> ${domain} </td>
      <td> ${stats['domain'][domain]["newUsers"]} </td>
      <td> ${stats['domain'][domain]["totalUsers"]} </td>
      <td> ${stats['domain'][domain]["newItems"]} </td>
      <td> ${stats['domain'][domain]["items"]} </td>
    </tr>
  %endfor
  </table>
</%def>

<%def name="reportUser()">
  <% header() %>
  <td style="font-size: 14px;">
    ${reportedBy} has flagged your account for verification.
    Please click the button to verify your account:
    <br/><br/>
    <a href="${reactivateUrl}" style="text-decoration:none!important;"><div style="display:inline-block;padding:6px 12px;border-radius:4px;background:#3D85C6;text-shadow:1px 1px 2px rgba(0,0,0,0.4);color:white;font-weight:bold;">Verify Your Account</div></a>
    <br/><br/>
    You may also paste this link in your browser:
    <a href="${reactivateUrl}">${reactivateUrl}</a>
    <br/><br/>
  </td>
  <% footer(text=False) %>
</%def>
