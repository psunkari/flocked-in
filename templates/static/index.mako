<%inherit file="base.mako"/>

<%def name="layout()">
  <div id="contents" class="centered-wrapper">
    <div id="home-slideshow">
      <div class="home-slide">
        <img src="/rsrcs/img/screenshot.png"/>
      </div>
    </div>
    <div id="home-content">
      <h2 id="home-title" class="section-head">Join your company network.<br/>Private, Secure and Free</h2>
      <div id="home-signup">
        <form action="/signup/signup" id="signup-form" method="POST">
          <input id="signup-email" type="email" name="email" required/>
          <input id="signup-submit" type="submit" value="Sign Up"/>
        </form>
      </div>
      <div id="home-desc">
        Flocked-in is a social network exclusively for people within your company.
        Built to be highly secure &amp; scalable, it offers the features necessary
        to foster a productive community at work
        <ul id="home-links" class="header-links">
          <li><a href="/about/features.html">View Features</a>&#183;</li>
          <li><a href="/about/tour.html">Take a tour!</a>&#183;</li>
          <li><a href="/about/contact.html?s=hiring">We're Hiring!</a>&#183;</li>
          <li><a href="/about/contact.html">Contact Us</a></li>
        </ul>
      </div>
    </div>
    <div class="clear"></div>
  </div>
</%def>
