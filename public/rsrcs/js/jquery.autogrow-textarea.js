
/*
 * Based on:
 * http://onehackoranother.com/projects/jquery/jquery-grab-bag
 *
 * Changes (Prasad)
 *   1. The shadow div is inserted immediately after the textarea instead
 *      of to the body to make it more probable that the shadow is removed
 *      whenever the nodes around textarea are cleared.
 * 
 */

(function($) {
    $.fn.autogrow = function(options) {

        this.filter('textarea').each(function() {

            var $this       = $(this),
                verticalPad = parseInt($this.css('paddingTop')) + parseInt($this.css('paddingBottom')),
                minHeight   = $this.outerHeight(),
                lineHeight  = $this.css('lineHeight');

            if ($this.next().hasClass('autogrow-backplane'))
                return;

            var shadow = $('<div></div>').css({
                position:   'absolute',
                top:        -10000,
                left:       -10000,
                width:      $this.width() - parseInt($this.css('paddingLeft')) - parseInt($this.css('paddingRight')),
                fontSize:   $this.css('fontSize'),
                fontFamily: $this.css('fontFamily'),
                lineHeight: $this.css('lineHeight'),
                wordWrap:   'break-word'
            }).insertAfter(this).addClass('autogrow-backplane');

            var update = function(event) {
                if ($this.attr('placeholder') == $this.val())
                    return;

                if (event && event.type === "keydown" && event.which === 13 && !event.shiftKey) {
                    event.preventDefault();
                    $this.closest("form").submit();
                    return;
                }

                var times = function(string, number) {
                    for (var i = 0, r = ''; i < number; i ++) r += string;
                    return r;
                };

                var val = this.value.replace(/</g, '&lt;')
                                    .replace(/>/g, '&gt;')
                                    .replace(/&/g, '&amp;')
                                    .replace(/\n$/, '<br/>&nbsp;')
                                    .replace(/\n/g, '<br/>')
                                    .replace(/ {2,}/g, function(space) { return times('&nbsp;', space.length -1) + ' ' });

                shadow.html(val);

                // No clean way to know the property of box-sizing.
                // Currently assuming it as "border-box"
                $(this).css('height', Math.max(shadow.height() + 15 + verticalPad, minHeight));
            }

            $this.css({resize: 'none', overflow: 'auto'});
            $this.change(update).keyup(update).keydown(update);
            update.apply(this);
        });
        return this;
    }
})(jQuery);
