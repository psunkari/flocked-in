/*
 * Error, warning and info alerts
 */
(function($$, $) { if (!$$.oclient) {
var access_endpoint = "http://localhost:8000/o/t"
var oclient = {
    getAccessToken: function(auth_token, auth_redirect, client_id) {
        console.log(auth_token)
        var d = $.post(access_endpoint, {
                                "grant_type":"authorization_code",
                                "code":auth_token,
                                "redirect_uri":auth_redirect,
                                "client_id":client_id
                                },
                        function(data){
                            console.log(data)
                        }, "json");
    },
    refreshAccessToken: function(refresh_token) {

    }
};

$$.oclient = oclient;
}})(social, jQuery);
