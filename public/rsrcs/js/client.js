/*
 * Error, warning and info alerts
 */
(function($$, $) { if (!$$.oclient) {
var oclient = {
    getAccessToken: function(auth_token) {
        console.log(auth_token)
        //Now do  
    },
    refreshAccessToken: function(refresh_token) {

    }
};

$$.oclient = oclient;
}})(social, jQuery);
