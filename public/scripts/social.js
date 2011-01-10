
$("a.ajax").click(function() {
    $.address.value($(this).attr('href'))
    return false;
})

$(document).ajaxError(function(event, request, settings) {
    alert("Error fetching: " + settings.url)
})

$.address.change(function(event) {
    $('#centerbar').load('/ajax' + event.value)
})

function BlockLoader() {
    objects = [];

    function load(obj) {
        // First load the stylesheets
        if (obj.css)
            $(head).append("<link rel='stylesheet' type='text/css' href='" + obj.css + "'/>")

        // Add markup to the document.
        if (obj.markup && obj.parent) {
            method = "method" in obj? obj.method: "set";
            switch(method) {
                case "append":
                    $(obj.parent).append(obj.markup)
                    break;
                case "prepend":
                    $(obj.parent).prepend(obj.markup)
                    break;
                case "set":
                default:
                    $(obj.parent).html(obj.markup);
            }
        }

        if (obj.isLast) {
            this.loadAndRunScripts();
        }
    }

    function loadAndRunScripts() {
        $.each(objects, function(index, value) {
                if (value.script)
                    $.getScript(value.script, function() {
                            if (value.onload)
                                setTimeout(value.onload, 250)
                        })
            })
    }
}
loader = new BlockLoader();
