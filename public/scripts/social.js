
$("a.ajax").click(function() {
    $.address.value($(this).attr('href'))
    return false;
})

$.address.change(function(event) {
    $('#centerbar').load('/ajax' + event.value)
})
