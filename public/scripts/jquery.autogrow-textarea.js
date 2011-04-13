
/*
 * Based on:
 * http://onehackoranother.com/projects/jquery/jquery-grab-bag
 *
 * Changes (Prasad)
 *   1. The shadow div is inserted at the end of textarea's parent instead
 *      of to the body to make it more probable that the shadow is removed
 *      whenever the nodes around textarea are cleared.
 */

(function($) {
    $.fn.autogrow = function(options) {

        this.filter('textarea').each(function() {

            var $this       = $(this),
                minHeight   = $this.height(),
                lineHeight  = $this.css('lineHeight');

            var shadow = $('<div></div>').css({
                position:   'absolute',
                top:        -10000,
                left:       -10000,
                width:      $(this).width() - parseInt($this.css('paddingLeft')) - parseInt($this.css('paddingRight')),
                fontSize:   $this.css('fontSize'),
                fontFamily: $this.css('fontFamily'),
                lineHeight: $this.css('lineHeight'),
                resize:     'none'
            }).appendTo(this.parentNode);

            var update = function(event) {
                if (event.type === "keydown" && event.which === 13 && !event.shiftKey) {
                    event.preventDefault();
                    $this.parents("form").submit();
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
                $(this).css('height', Math.max(shadow.height() + 15, minHeight));
            }

            $this.css("resize", "none");
            $this.change(update).keyup(update).keydown(update);
            update.apply(this);
        });
        return this;
    }
})(jQuery);
