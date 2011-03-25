
/*
 * Put all our stuff into a single namespace.
 * Accessible as "social", "$$" and "jQuery.social"
 */

(function(window, $) {
var social = {

/* 
 * parseUri:
 * Based on http://blog.stevenlevithan.com/archives/parseuri
 */
parseUri: function parseUri(str) {
    var matches = /^(?:([^:\/?#]+):)?(?:\/\/((?:(([^:@]*)(?::([^:@]*))?)?@)?([^:\/?#]*)(?::(\d*))?))?((((?:[^?#\/]*\/)*)([^?#]*))(?:\?([^#]*))?(?:#(.*))?)/.exec(str);
    var keys = ["source","protocol","authority","userInfo","user","password","host","port","relative","path","directory","file","query","anchor"];
    var uri = {}

    var i = 14
    while (i--) uri[keys[i]] = matches[i];

    return uri
},

/*
 * _initAjaxRequests:
 * Initialize ajax requests and history handling
 */
_fetchUriOldPath: null,
_initAjaxRequests: function _initAjaxRequests() {
    function _fetchUri(str) {
        uri = social.parseUri(str);
        if (social._fetchUriOldPath) {
            tail = '';
            if (social._fetchUriOldPath != uri.path)
                tail = uri.query? "&_fp=1": "?_fp=1";

            $.getScript('/ajax' + str + tail);
        }
        social._fetchUriOldPath = uri.path;
    };

    /* Async Get */
    $("a.ajax").live("click", function() {
        node = $(this)
        if (url = node.attr('_ref')) {
            $.getScript('/ajax' + url)
        } else if (url = node.attr('href')) {
            $.address.value(url);
            _fetchUri(url);
        }
        return false;
    });
    
    /* Async form submit */
    $('form.ajax').live("submit", function() {
        var node = $(this);
        $.post('/ajax' + node.attr('action'), node.serialize(), null, 'script');
        return false;
    });
    
    /* Global ajax error handler */
    $(document).ajaxError(function(event, request, settings) {
        alert("Error fetching: " + settings.url);
    });
    
    /* If the browser support HTML5 states, use them */
    if (window.history && history.pushState)
        $.address.state("/");
    
    /* An address or the hash changed externally, update the page */
    $.address.externalChange(function(event) {
        _fetchUri(event.value)
    });
},

/*
 * Update timestamps
 * XXX: Needs localization of strings and date formats
 */
_initTimestampUpdates: function _initTimestampUpdates() {
    window.setInterval(function() {
        $('.timestamp').each(function(idx, item) {
            timestamp = item.getAttribute("_ts")
            tooltip = item.getAttribute("title");
    
            current = new Date();
            current = current.getTime()/1000;
            delta = current - parseInt(timestamp);
    
            if ((delta < 60) || (delta > 3630 && delta < 7200) || (delta > 86430)) {
                // Do nothing.
            } else if (delta > 86400) {
                item.innerHTML = Math.floor(delta/86400) + " days ago";
            } else if (delta > 7200) {
                item.innerHTML = Math.floor(delta/3600) + " hours ago";
            } else if (delta > 3600) {
                item.innerHTML = "about an hour ago";
            } else if (delta > 60) {
                item.innerHTML = Math.floor(delta/60) + " minutes ago";
            }
        })
    }, 30000);
},

/* ChunkLoader: Load the page in Chunks.
 * Takes the already loaded resource ids as argument.
 */
_initChunkLoader: function(resources) {
    chunkLoader = {
        _delayed: [],   // Chunks on which scripts have not been called yet
        _requested: [], // resourceIDs of requested resources
        _loaded: [],    // resourceIDs of already loaded resources
        _resources: {}, // map of resourceID to resource
        _global: [],    // resourceIDs of global resources
    
        // Unload a stylesheet that is not needed anymore.
        _unloadResource: function() {
        },
    
        // Waiting for CSS to load before calling the callback is a pretty
        // ugly hack.  A small discussion about it is at:
        //                      http://stackoverflow.com/questions/4488567/
        // I choose to poll on rule getting applied to a DOM element.
        _loadResources: function(ids, callback, cleanup, depends) {
            resources = []
            for (var id in ids)
                if (id in chunkLoader._resources)
                    resources.push(chunkLoader._resources[id]);
    
            filesToLoad = ids.length;
            if (ids.length == 0)
                callback();
            function checkResourcesCount() {
                filesToLoad = filesToLoad - 1;
                if (filesToLoad == 0)
                    callback();
            }
    
            function cssCheckLoaded(id) {
                var maxWaitTime = 5000
                var currentWaitTime   = 0
                var w = 27;
                var nodeId = "_css_poll_" + id;
    
                var div = document.getElementById(nodeId)
                if (!document.getElementById(nodeId)) {
                    div = document.createElement("div");
                    div.id = nodeId;
                    document.body.appendChild(div);
                }
    
                var timer = null;
                function checker() {
                    if (div.offsetWidth == w || $(div).css('width') == w + 'px' ||
                        id in chunkLoader._loaded || currentWaitTime >= maxWaitTime) {
                        clearInterval(timer);
                        checkResourcesCount();
                    } else {
                        currentWaitTime += 20;
                    }
                }
                timer = setInterval(checker.bind(chunkLoader), 20)
            }
    
            function loadCSS(rsrc) {
                if (!rsrc.id in chunkLoader._requested)
                    $("document").ready(function(){
                        $("head").append('<link rel="stylesheet" type="text/css" href="' + rsrc.url + '"/>');
                        chunkLoader._requested.push(rsrc.id)
                    })
                cssCheckLoaded(rsrc.id);
            }
    
            for (var rsrc in resources) {
                if (rsrc.id in chunkLoader._loaded)
                    checkResourcesCount()
                else if (rsrc.type == 'css')
                    loadCSS(rsrc)
                else if (rsrc.type == "js")
                    $.getScript(rsrc.url, function() {checkResourcesCount()});
            }
        },
    
        _displayContent: function(rsrc) {
            if (rsrc.content && rsrc.node) {
                method = "method" in rsrc? rsrc.method: "set";
                switch(method) {
                    case "append":
                        $(rsrc.node).append(rsrc.content)
                        break;
                    case "prepend":
                        $(rsrc.node).prepend(rsrc.content)
                        break;
                    case "set":
                    default:
                        $(rsrc.node).html(rsrc.content);
                }
            }
        },
    
        // Load the chunk
        load: function(obj) {
            if (obj.hasOwnProperty("resources"))
                for (var rsrc in obj.resources)
                    chunkLoader._resources[rsrc.id] = rsrc;
    
            var cleanup = obj.method == "set"? true: false;
            chunkLoader._loadResources(obj.css || [],
                            chunkLoader._displayContent.bind(chunkLoader, obj),
                            cleanup, obj.parent || null);
    
            chunkLoader._delayed.push(obj);
            if (obj.last) {
                chunkLoader._loadResources(obj.js || [],
                              chunkLoader._runEventHandlers.bind(chunkLoader));
            }
        },
    
        _runEventHandlers: function() {
            $.each(chunkLoader._delayed, function(index, value) {
                    if (value.handlers) {
                        handlers = value.handlers;
                        if (handlers.onload)
                            eval(handlers.onload);
                    }
                }.bind(chunkLoader));
            chunkLoader._delayed = [];
        }
    };

    for (var rsrc in resources)
       chunkLoader._global.push(rsrc);

    social._chunkLoader = chunkLoader;
    social.load = chunkLoader.load;
}

}; // var social;

/* The .bind method from Prototype.js */
if (!Function.prototype.bind) {
  Function.prototype.bind = function(){
    var fn = this, args = Array.prototype.slice.call(arguments),
        object = args.shift();
    return function(){
      return fn.apply(object,
        args.concat(Array.prototype.slice.call(arguments)));
    };
  };
}

social._initChunkLoader();
social._initAjaxRequests();
social._initTimestampUpdates();

$.social = window.social = window.$$ = social;
})(window, jQuery);




/*
 * Popup manager: manager for menus and other types of popups
 */
(function($$, $) {
var popup = {
    _stack: [],

    // Change the state of the given popup to open.
    open: function(event, node) {
        evt = $.event.fix(event);
        node = $(node);
        node.parentsUntil(".popup-open").each(function(index, item) {
            if (item === document.body)
                popup.closeAll();
        })

        node.addClass("popup-open");
        popup._stack.push(node)

        evt.stopPropagation();
        evt.preventDefault();
    },

    // Hide the popup that is on the top of the stack
    close: function() {
        node = popup._stack.pop();
        if (node)
            node.removeClass("popup-open");
    },

    // Close all popups.
    closeAll: function() {
        while((node = popup._stack.pop()))
            node.removeClass("popup-open");
    }
}

// Close popups when user clicks outside the popup
$(document).click(function(event) {
    popup.closeAll();
});
$$.popups = popup;
})(social, jQuery);




/*
 * Handle access control related menus and dialog.
 */
(function($$, $) {
var acl = {
    updateGroupsList: function(target) {
        console.log("Updating groups list");
    },

    updateACL: function(event, parent) {
        evt = $.event.fix(event);
        target = $(evt.target);

        value = target.attr("type");
        if (value) {
            stub = parent.id;
            $("#" + stub + "-content").html(target.html());
            $("#" + stub + "-tooltip").html(target.attr("info"));
            $("#" + stub + "-input").attr("value", value);

            $$.popups.close();
        }

        evt.preventDefault();
        evt.stopPropagation();
    }
};
$$.acl = acl;
})(social, jQuery);
