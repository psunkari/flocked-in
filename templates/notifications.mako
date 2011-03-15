
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<%! from social import utils, _, __, plugins %>
<%! from social import relations as r %>

<%inherit file="base.mako"/>
<%namespace name="item" file="item.mako"/>

##
## Profile is displayed in a 3-column layout.
##
<%def name="layout()">
  <div class="contents has-left has-right">
    <div id="left">
      <div id="nav-menu">
        ${self.nav_menu()}
      </div>
    </div>
    <div id="center-right">
      <div id="right">
      </div>
      <div id="center">
        ${self.content()}
      </div>
    </div>
  </div>
</%def>

<%def name="content()">

  <div class="notifications">
    % if conversations:
      %for convId in conversations:
        <div class="conv-item" >
          %for reason in reasonStr[convId]:
            <div>
              ${reason}
            </div>
          %endfor
        </div>

      %endfor
    %endif
  </div>
</%def>
