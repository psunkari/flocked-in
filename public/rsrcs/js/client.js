/*
 * Error, warning and info alerts
 */
(function($$, $) { if (!$$.oclient) {
var token_endpoint = "http://localhost:8000/o/t"
var api_endpoint = "http://localhost:8000/api"
var oclient = {
    getAccessToken41: function(auth_token, auth_redirect, client_id) {
        console.log("Auth Token is " + auth_token)
        var d = $.post(token_endpoint, {
                                "grant_type":"authorization_code",
                                "code":auth_token,
                                "redirect_uri":auth_redirect,
                                "client_id":client_id
                                },
                        function(data){
                            console.log("Access_key is " + data["access_token"])
                            oclient.getFeed(data["access_token"])
                        }, "json");
    },
    refreshAccessToken: function(refresh_token) {

    },
    getFeed: function(access_token){
        $.ajax(api_endpoint+"/feed", {
            type:'get',
            beforeSend:function(xhr){
                var header = "Bearer " + access_token;
                xhr.setRequestHeader ('Authorization', header);
            },
            dataType:"json"
            }).complete(function(data){
                oclient.processFeed(data)
        })
    },
    processFeed: function(feed){
        console.log("Feed has arrived" + feed)
    }
};

$$.oclient = oclient;
}})(social, jQuery);
