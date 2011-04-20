
## Render a button.
## Depending on the type and arguments given, we decide on rendering
## one of "input" and "button" tags.

<%def name="button(id=None, type='button', classes='', name=None, value=None, tooltip=None)">
%if name and value and type == "submit":
  <input class="button ${classes}" type="submit"
         ${'' if not id else ('id="%s" ' % id)}name="${name}" value="${value}"/>
%else:
  <button ${'' if not id else ('id="%s" ' % id)}type="${type}"
          class="button ${classes} ${'has-tooltip' if tooltip else ''}">
  %if value:
    <span ${'' if not id else ('id="%s-content" ' % id)}
          class="button-content">${value}</span>
    %if tooltip:
    <div class="tooltip">
      <span ${'' if not id else ('id="%s-content" ' % id)}
            class="tooltip-content">${tooltip}</span>
    </div>
    %endif
  %else:
    ${caller.body()}
  %endif
  </button>
%endif
</%def>
