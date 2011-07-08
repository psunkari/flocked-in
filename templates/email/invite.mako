## Do not delete this file.
## Edit this file and run it through
##  http://premailer.dialect.ca/
## Also, check all the options on the webpage before running it
## Copy the html output to invite.html
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta property="og:title" content="${subject}" />
    <title>${subject}</title>
    <style type="text/css">
      /* Client-specific Styles */
      #outlook a{padding:0;} /* Force Outlook to provide a "view in browser" button. */
      body{width:100% !important;} .ReadMsgBody{width:100%;} .ExternalClass{width:100%;} /* Force Hotmail to display emails at full width */
      body{-webkit-text-size-adjust:none;} /* Prevent Webkit platforms from changing default text sizes. */

      /* Reset Styles */
      body{margin:0; padding:0;}
      img{border:0; height:auto; line-height:100%; outline:none; text-decoration:none;}
      table td{border-collapse:collapse;}
      #backgroundTable{height:100% !important; margin:0; padding:0; width:100% !important;}

      /* Template Styles */

      body, #backgroundTable{
        background-color:#FAFAFA;
      }

      #templateContainer{
        border: 1px solid #DDDDDD;
      }

      h1, .h1{
        color:#202020;
        display:block;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:34px;
        font-weight:bold;
        line-height:100%;
        margin-top:0;
        margin-right:0;
        margin-bottom:10px;
        margin-left:0;
        text-align:left;
      }

      h2, .h2{
        color:#202020;
        display:block;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:30px;
        font-weight:bold;
        line-height:100%;
        margin-top:0;
        margin-right:0;
        margin-bottom:10px;
        margin-left:0;
        text-align:left;
      }

      h3, .h3{
        color:#202020;
        display:block;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:26px;
        font-weight:bold;
        line-height:100%;
        margin-top:0;
        margin-right:0;
        margin-bottom:10px;
        margin-left:0;
        text-align:left;
      }

      h4, .h4{
        color:#202020;
        display:block;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:22px;
        font-weight:bold;
        line-height:100%;
        margin-top:0;
        margin-right:0;
        margin-bottom:10px;
        margin-left:0;
        text-align:left;
      }

    pre {
        background: none repeat scroll 0 0 #222222;
        border-radius: 10px 10px 10px 10px;
        box-shadow: 0 2px 3px #555555;
        color: #555555;
        font-size: 11px;
        margin: 0 auto;
        padding: 20px;
        text-shadow: 0 2px 3px #171717;
        width: 500px;
    }

      #templatePreheader{
        background-color:#FAFAFA;
      }

     .preheaderContent div{
        color:#505050;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:10px;
        line-height:100%;
        text-align:left;
      }

      .preheaderContent div a:link, .preheaderContent div a:visited, /* Yahoo! Mail Override */ .preheaderContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      #templateHeader{
        background-color:#FFFFFF;
        border-bottom:0;
      }

      .headerContent{
        color:#202020;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:34px;
        font-weight:bold;
        line-height:100%;
        padding:5px;
        text-align:center;
        vertical-align:middle;
      }

      .headerContent a:link, .headerContent a:visited, /* Yahoo! Mail Override */ .headerContent a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      #headerImage{
        height:auto;
        max-width:600px;
      }

      .leftColumnContent{
        border-color: #FFFFFF #FFFFFF #DDDFE1 #DDDFE1;
        border-style: solid;
        border-width: 1px;
      }

      .leftColumnContent div{
        color:#505050;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:14px;
        line-height:150%;
        text-align:left;
      }

      .leftColumnContent div a:link, .leftColumnContent div a:visited, /* Yahoo! Mail Override */ .leftColumnContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      .leftColumnContent img{
        display:inline;
        height:auto;
      }

      .centerColumnContent{
        border-color: #FFFFFF #FFFFFF #DDDFE1 #DDDFE1;
        border-style: solid;
        border-width: 1px;
        /*background-color:#FFFFFF;*/
      }

      .centerColumnContent div{
        color:#505050;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:14px;
        line-height:150%;
        text-align:left;
      }

      .centerColumnContent div a:link, .centerColumnContent div a:visited, /* Yahoo! Mail Override */ .centerColumnContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      .centerColumnContent img{
        display:inline;
        height:auto;
      }

      .rightColumnContent{
        border-color: #FFFFFF #FFFFFF #DDDFE1 #DDDFE1;
        border-style: solid;
        border-width: 1px;
        /*background-color:#FFFFFF;*/
      }

      .rightColumnContent div{
        color:#505050;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:14px;
        line-height:150%;
        text-align:left;
      }

      .rightColumnContent div a:link, .rightColumnContent div a:visited, /* Yahoo! Mail Override */ .rightColumnContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      .rightColumnContent img{
        display:inline;
        height:auto;
      }

      #templateContainer, .bodyContent{
        background-color:#FFFFFF;
      }

      .bodyContent div{
        color:#505050;
        font-family:"lucida grande",tahoma,verdana,sans-serif;
        font-size:12px;
        line-height:150%;
        text-align:left;
      }

      .bodyContent div a:link, .bodyContent div a:visited, /* Yahoo! Mail Override */ .bodyContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      .bodyContent img{
        display:inline;
        height:auto;
      }


      #templateFooter{
        background-color:#FFFFFF;
        border-top:0;
      }

      .footerContent div{
        color:#707070;
        font-family:"lucida grande",tahoma,verdana,arial,sans-serif;
        font-size:12px;
        line-height:125%;
        text-align:left;
      }

      .footerContent div a:link, .footerContent div a:visited, /* Yahoo! Mail Override */ .footerContent div a .yshortcuts /* Yahoo! Mail Override */{
        color:#336699;
        font-weight:normal;
        text-decoration:underline;
      }

      .footerContent img{
        display:inline;
      }

      #social{
        background-color:#FAFAFA;
        border:0;
      }

      #social div{
        text-align:center;
      }

      #utility{
        background-color:#FFFFFF;
        border:0;
      }

      #utility div{
        text-align:center;
      }

      .contentBlock {
        background :none repeat scroll 0 0 #F0F4F8;
      }
    </style>
  </head>
  <body leftmargin="0" marginwidth="0" topmargin="0" marginheight="0" offset="0">
    <center>
      <table border="0" cellpadding="0" cellspacing="0" height="100%" width="100%" id="backgroundTable">
        <tr>
          <td align="center" valign="top">
            <table border="0" cellpadding="10" cellspacing="0" width="600" id="templatePreheader">
              <tr>
                <td valign="top" class="preheaderContent">
                  <table border="0" cellpadding="10" cellspacing="0" width="100%">
                    <tr>
                      <td valign="top">
                        <div>
                           ${invitee} has invited you to the ${myOrgName} network on ${brandName}. ${brandName} is a Private, Secure and Free way to stay connected with your co-workers!
                        </div>
                      </td>
                      <td valign="top" width="190">
                        <div>
                          <a href="http://flocked.in/about/product.html" target="_blank">View it in your browser</a>.
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <table border="0" cellpadding="0" cellspacing="0" width="600" id="templateContainer">
                <tr>
                <td align="center" valign="top">
                  <table border="0" cellpadding="0" cellspacing="0" width="600" id="templateHeader" style="background-color:#F4F4F4;border-bottom:15px solid #3D85C6;">
                  <tr>
                    <td class="headerContent">
                    <div>
                      <h1 style="color:#CC0000">
                        <img src="cid:${brandName}Logo" style="max-width:180px;" id="headerImage campaign-icon" alt="flocked.in"/>
                      </h1>
                    </div>
                    </td>
                    <td class="headerContent" width="100%" style="padding-left:10px; padding-right:20px;">
                    <div>
                      <h1></h1>
                    </div>
                    </td>
                  </tr>
                  </table>
                </td>
                </tr>
              <tr>
                <td colspan="3" valign="top" class="bodyContent">
                  <table border="0" cellpadding="20" cellspacing="0" width="100%">
                    <tr>
                      <td valign="top">
                        <div>
                          <strong>To accept ${invitee}'s invitation, <a href="${activationUrl}" target="_blank">click here</a> or copy and paste the following link in your browser</strong>
                          <br />
                          <div style="background-color:#FAFAFA;font-size:11px;font-family:Arial">
                              ${activationUrl}
                          </div>
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr class="contentBlock">
                <td align="center" valign="top">
                  <table border="0" cellpadding="0" cellspacing="0" width="600" id="templateBody">
                    <tr>
                      <td valign="top" width="180" class="leftColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Micro-blogging</h4>
                                  Share status information, links with people and ask questions.
                              </div>
                            </td>
                          </tr>
                        </table>

                      </td>
                      <td valign="top" width="180" class="centerColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Profiles</h4>
                                  Rich user profiles of people with their experience and expertise.
                              </div>
                            </td>
                          </tr>
                        </table>
                      </td>
                      <td valign="top" width="180" class="rightColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Networking</h4>
                                  Connect with people you are interested in. Get updates from them and share stuff.
                              </div>
                            </td>
                          </tr>
                        </table>

                      </td>
                    </tr>
                    <tr>
                      <td valign="top" width="180" class="leftColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Groups</h4>
                                  Form a closed groups for your team or department for private collaboration. From open interest groups to share knowledge openly.
                              </div>
                            </td>
                          </tr>
                        </table>
                      </td>
                      <td valign="top" width="180" class="centerColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Direct messages</h4>
                                  Send private message to people and have closed discussions.
                              </div>
                            </td>
                          </tr>
                        </table>
                      </td>
                      <td valign="top" width="180" class="rightColumnContent">

                        <table border="0" cellpadding="20" cellspacing="0" width="100%">
                          <tr>
                            <td valign="top">
                              <div>
                                <h4 class="h4">Topics</h4>
                                  Organize content in your network with Topics. Subscribe to interested Topics and be informed.
                              </div>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr class="contentBlock">
                <td align="center" valign="top">
                  <table border="0" cellpadding="10" cellspacing="0" width="600" id="templateFooter">
                    <tr>
                      <td valign="top" class="footerContent">

                        <table border="0" cellpadding="10" cellspacing="0" width="100%">
                          <tr>
                            <td colspan="2" valign="middle" id="social">
                              <div>
                                &nbsp;<a href="">follow on Twitter</a> | <a href="">friend on Facebook</a> | <a href="">forward to a friend</a>&nbsp;
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td valign="top" width="350">
                              <div>
                                <em>Copyright &copy; 2011 Synovel Software, All rights reserved.</em>
                                <br />

                                <br />
                                <strong>Our mailing address is:</strong>
                                <br />
                                info@synovel.com
                              </div>
                            </td>
                            <td valign="top" width="190">
                            </td>
                          </tr>
                          <tr>
                            <td colspan="2" valign="middle" id="utility">
                              <div>
                                &nbsp;<a href="">unsubscribe from this list</a> | <a href="">update subscription preferences</a>&nbsp;
                              </div>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <br />
          </td>
        </tr>
      </table>
    </center>
  </body>
</html>
