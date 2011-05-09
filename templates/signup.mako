<%! from gettext import gettext as _ %>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">

<head>
  <title>${_('Synovel SocialNet')}</title>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/signin.css"/>
  <link rel="stylesheet" type="text/css" media="screen" href="/public/style/social.css"/>
  <script type = "text/javascript">
  function validate()
  {

    return document.getElementById("password1").value == document.getElementById("password2").value
  }
  </script>
</head>

<body>
  <div id="signup_form">
    ${self.userInfo()}
  </div>
</body>
</html>


<%def name="userInfo()">
 <form action="/register/create" method="POST" onsubmit="return validate()" >
    <div class="edit-profile">
      <ul>
        <li id="logintitle">
        <img alt="Synovel" src="/public/images/synovel.png"/>
        </li>
      </ul>
      <ul><li></li></ul>
      <ul><li></li></ul>
      <ul>
        <li><label for="emailId">${_('Email:')}</label></li>
        <li><label for="emailId">${emailId}</label></li>
        <li><input id="emailId" type="hidden" class="textfield" name="emailId" value="${emailId}"></input></li>
      </ul>

      <ul>
        <li><label for="name">${_('Display Name:')}</label></li>
        <li><input type="text" class="textfield" name="name" /></li>
      </ul>

      <ul>
        <li><label for="fname">${_('First Name:')}</label></li>
        <li><input type="text" class="textfield" name="fname" /></li>
      </ul>

      <ul>
        <li><label for="lname">${_('Last Name:')}</label></li>
        <li><input type="text" class="textfield" name="lname" /></li>
      </ul>

      <ul>
        <li><label for="jobTitle">${_('Job Title:')}</label></li>
        <li> <input name="jobTitle" id="jobTitle" type="text" /></li>
      </ul>

      <ul>
        <li><label for="password">${_('Password:')}</label></li>
        <li><input type="password" class="textfield" name="password"/></li>
      </ul>

      <ul>
        <li><label for="password1">${_('Confirm Password:')}</label></li>
        <li><input type="password" class="textfield" name="password1" /></li>
      </ul>

      <ul>
        <li></li>
        <li><input type="submit" id="submit" value="${_('Save')}"/></li>
      </ul>
      <ul>
        <li  id="footer">
          ${_('&copy;2011 Synovel Software')}
          &nbsp;|&nbsp;
          <a href="http://www.synovel.com/social">${_('Synovel SocialNet')}</a>
        </li>
      </ul>
    </div>
  </form>
</%def>

<%def name="invitePeople()">
    <h3> Invite </h3>
    <form action="/register/invite" method="POST">
      <div class="edit-profile">
        <ul>
          <li><label for="user1" >email:</label></li>
          <li><input type="text" name="user1" /></li>
        </ul>
        <ul>
          <li><label for="user2" >email:</label></li>
          <li><input type="text" name="user2" /></li></ul>
        <ul>
          <li><label for="user3" >email:</label></li>
          <li><input type="text" name="user3" /></li></ul>
        <ul>
          <li><label for="user4" >email:</label></li>
          <li><input type="text" name="user4" /></li></ul>
        <ul>
          <li><label for="user5" >email:</label></li>
          <li><input type="text" name="user5" /></li></ul>
        <ul><li><input type="submit" name="submit" value="Submit"/> </li></ul>
        <ul><li><input type="submit" name="skip" value="Skip" /> </li></ul>
        <ul><li><input type="hidden" name="sender" value=${emailId}/></li></ul>
      </div>
    </form>
</%def>
