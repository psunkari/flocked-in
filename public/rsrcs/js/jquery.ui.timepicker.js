/*
 * Time Picker Widget
 *
 */
(function( $, undefined ) {
$.widget( "ui.timepicker", {
    options: {
            currentTime: null,
            appendTo: null
    },

    parseTimeString: function(string) {
        var matcher = new RegExp(/^([01]?\d|2[0-3]):([0-5]\d) (AM|PM)$/i);
        var parts = string.match( matcher ),
            hours = 0;

        if (parts) {
            hour = parts[1];
            minute = parts[2];
            ampm = parts[3];

            if (hour > 12) {
                hours = parseInt(hour, 10)
            }
            else if (ampm.toUpperCase() == "PM") {
                hours = parseInt(hour, 10) + 12
            }else {
                hours = parseInt(hour, 10)
            }
            var secondsElapsed = (hours * 60 * 60) + (parseInt(minute, 10) * 60);
            return secondsElapsed
        }else {
            return 0
        }
    },

    _showTimePicker: function() {
        if ( this.input.autocomplete( "widget" ).is( ":visible" ) ) {
                //this.input.autocomplete( "close" );
                return;
        }

        $( this ).blur();

        this.input.autocomplete( "search", "" );
    },

    _create: function() {
            var self = this,
                    select = this.element.hide(),
                    selected = select.children( ":selected" ),
                    value = selected.val() ? selected.text() : "";
            var input = this.input = $( "<input>" )
                    .insertAfter( select )
                    .val( value )
                    .click(function() {
                        self._showTimePicker();
                    })
                    .focus(function() {
                        self._showTimePicker();
                    })
                    .attr('id', select.attr('id')+'-picker')
                    .attr('required', true)
                    .autocomplete({
                            delay: 0,
                            minLength: 0,
                            appendTo: this.options.appendTo || "body",
                            source: function( request, response ) {
                                var matcher = new RegExp( $.ui.autocomplete.escapeRegex(request.term), "i" );
                                response( select.children( "option" ).map(function() {
                                    var text = $( this ).text();
                                    if ( this.value && ( !request.term || matcher.test(text) ) )
                                        return {
                                            label: text.replace(
                                                    new RegExp(
                                                            "(?![^&;]+;)(?!<[^<>]*)(" +
                                                            $.ui.autocomplete.escapeRegex(request.term) +
                                                            ")(?![^<>]*>)(?![^&;]+;)", "gi"
                                                    ), "<strong>$1</strong>" ),
                                            value: text,
                                            timestamp: parseInt($(this).val(), 10),
                                            option: this
                                        };
                                }) );
                            },
                            select: function( event, ui ) {
                                self._trigger( "selected", event, {
                                        item: {'timestamp': ui.item.timestamp}
                                });
                            },
                            change: function( event, ui ) {
                                if ( !ui.item ) {
                                    var matcher = new RegExp(/^([01]?\d|2[0-3]):([0-5]\d) (AM|PM)$/i),
                                        valid = false;
                                    if ( $( this ).val().trim().match( matcher ) ) {
                                        console.info("Matched")
                                        valid = true;
                                        var timestamp = self.parseTimeString($( this ).val().trim())
                                        self._trigger( "selected", event, {
                                                item: {'timestamp': timestamp}
                                        });
                                        var parts = $(this).val().trim().match(matcher);
                                        hours = parts[1];
                                        minutes = parts[2];
                                        ampm = parts[3];
                                        if (hours > 12) {
                                            hours = parseInt(hours, 10) - 12
                                            ampm = "PM"
                                        }
                                        $( this ).val(hours+":"+minutes+" " + ampm.toUpperCase());
                                        return false;
                                    }
                                    if ( !valid ) {
                                        //$( this ).val( "" );
                                        select.val( "" );
                                        input.data( "autocomplete" ).term = "";
                                        return false;
                                    }
                                }
                            },
                            open: function(event, ui) {
                                var timeNow = new Date(self.options.currentTime),
                                    hoursNow = timeNow.getHours(),
                                    minutesNow = timeNow.getMinutes();
                                var height = (hoursNow - 1.5)*2*25;
                                $(this).data('autocomplete').menu.element.scrollTop(height);
                            }
                    })
                    .addClass( "ui-widget ui-widget-content ui-corner-left" );

            input.data( "autocomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" )
                            .data( "item.autocomplete", item )
                            .append( "<a>" + item.label + "</a>" )
                            .appendTo( ul );
            };
    },

    destroy: function() {
            this.input.remove();
            $.Widget.prototype.destroy.call( this );
    }
});

}(jQuery));
