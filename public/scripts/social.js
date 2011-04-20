
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
_historyHasStates: false,
fetchUri: function _fetchUri(str) {
    uri = social.parseUri(str);
    deferred = null;
    if (social._fetchUriOldPath) {
        tail = '';
        if (social._fetchUriOldPath != uri.path)
            tail = uri.query? "&_fp=1": "?_fp=1";

        deferred = $.getScript('/ajax' + str + tail);
    }
    social._fetchUriOldPath = uri.path;
    return deferred;
},
setBusy: function _setBusy(deferred, node) {
    busyIndicator = null;
    if (!deferred)
        return;

    if (node.hasClass('busy-indicator'))
        busyIndicator = node;
    else if (bi = node.attr("_bi"))
        busyIndicator = $('#' + bi);
    else
        busyIndicator = node.closest('.busy-indicator');

    busyIndicator.addClass("busy");
    deferred.done(function(){busyIndicator.removeClass("busy");});
},
_initAjaxRequests: function _initAjaxRequests() {
    var self = this;

    /* Async Get */
    $("a.ajax").live("click", function() {
        node = $(this);
        deferred = null;

        if (url = node.attr('_ref')) {
            deferred = $.getScript('/ajax' + url);
        } else if (url = node.attr('href')) {
            $.address.value(url);
            deferred = self.fetchUri(url);
        }

        self.setBusy(deferred, node);
        return false;
    });

    /* Async Post */
    $("a.ajaxpost").live("click", function() {
        node = $(this);
        url = node.attr('_ref');
        parsed = social.parseUri(url);

        deferred = $.post('/ajax' + parsed.path, parsed.query, null, 'script');

        self.setBusy(deferred, node);
        return false;
    });

    /* Async form submit */
    $('form.ajax').live("submit", function() {
        if (this.hasAttribute("disabled"))
            return false;

        var $this = $(this);
        var deferred = $.post('/ajax' + $this.attr('action'),
                          $this.serialize(), null, 'script');

        self.setBusy(deferred, $this)

        // Prevent accidental resubmission by disabling the
        // form till we get a response from the server.
        $this.attr("disabled", true);
        $inputs = $this.find(":input").attr("disabled", true);
        var enabler = function() {
            $inputs.removeAttr("disabled");
            $this.removeAttr("disabled");
        };
        deferred.then(enabler, enabler);

        return false;
    });

    /* Global ajax error handler */
    $(document).ajaxError(function(event, request, settings) {
        alert("Error fetching: " + settings.url);
    });

    /* If the browser support HTML5 states, use them */
    if (window.history && history.pushState) {
        social._historyHasStates = true;
        $.address.state("/");
    } else {
        var hash = window.location.hash;
        if (hash != "" && hash != "/")
            window.location.href = hash.substr(1);
    }

    /* An address or the hash changed externally, update the page */
    $.address.externalChange(function(event) {
        self.fetchUri(event.value)
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
_initChunkLoader: function _initChunkLoader(resources) {
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
                    case "replace":
                        $(rsrc.node).replaceWith(rsrc.content)
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
                        if (handlers.onload) {
                            try {
                                (new Function(handlers.onload)).apply(value);
                            } catch(ex) {}
                        }
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
 * Custom loading for the share block (publisher)
 * TODO: Handle extra options for showing buttons etc;
 */
(function($$, $) {
var publisher = {
    load: function(obj) {
        // Tab selection
        $('.selected-publisher').removeClass('selected-publisher');
        $('#publisher-'+obj.publisherName).addClass('selected-publisher');

        // Placeholders
        $$.ui.placeholders('#sharebar input:text, #sharebar textarea');

        // Auto expand textareas
        $('#sharebar textarea').autogrow();
    }
};

$$.publisher = publisher;
})(social, jQuery);




/*
 * Callback to be called when one or more items are loaded
 * into the view. Initializes the item's display - the comment form etc;
 */
(function($$, $) {
var items = {
    load: function(obj) {
        // Placeholders in comment input boxes
        $$.ui.placeholders('.comment-input');

        // Auto expand comment boxes
        $('.comment-input').autogrow();
    }
};

$$.items = items;
})(social, jQuery);




/*
 * Elements of the UI
 */
(function($$, $){
var ui = {
    init: function() {
        /* Add a scroll to bottom handler */
        $(window).scroll(function(){
            if ($(window).scrollTop() > $(document).height() - (50 + $(window).height())){
                $('#next-page-load').click();
            }
        });

        $.extend($.ui.autocomplete.prototype, {
            _renderItem: function(ul, item) {
                return $("<li></li>")
                            .data("item.autocomplete", item)
                            .append($( "<a></a>" ).html( item.label ))
                            .appendTo(ul);
            }
        });

        /* Searchbar must support autocomplete */
        $("#searchbox").autocomplete({
            source: '/auto/searchbox',
            minLength: 3,
            select: function(event, obj){
                url = obj.item.href;
                if (url !== undefined) {
                    $.address.value(url);
                    deferred = $$.fetchUri(url);
                    event.target.value = "";
                    return false;
                }
                return true;
            }
        });
        ui.placeholders("#searchbox");

        /* Install handlers for placeholder text */
        if (!ui._placeholders) {
            $(".ui-ph-label").live("click", function() {
                var input = this.nextSibling;
                input.focus();
            });

            $(".ui-ph-active").live("focus", function() {
                var label = this.previousSibling;
                $(label).css('display', 'none');
                $(this).removeClass('ui-ph-active');
            })

            $(".ui-ph").live("blur", function() {
                if (this.value != "")
                    return;

                var label = this.previousSibling;
                $(label).css('display', 'block');
                $(this).addClass('ui-ph-active');
            })
        }
    },

    _placeholders: 'placeholder' in document.createElement('input'),
    placeholders: function(selector) {
        if (ui._placeholders)   // Browser supports placeholder text
            return;

        $(selector).each(function(index, element){
            var $this, text, label, $label, inputHeight;

            $this = $(this);
            if ($(this.previousSibling).hasClass("ui-ph-label"))
                return;

            text = $this.attr('placeholder');
            if (!text)
                return;

            label = document.createElement("label");
            try {
                label.innerText = text;
                label.textContent = text;
            } catch(ex) {}
            label.setAttribute('class', 'ui-ph-label ui-ph-active');

            $label = $(label);
            inputHeight = $this.outerHeight();
            $label.height(inputHeight);
            $label.width($this.outerWidth());
            $label.css('line-height', inputHeight+'px');

            this.parentNode.insertBefore(label, this);
            $this.addClass('ui-ph');
            $this.addClass('ui-ph-active');
        });
    }
}

$$.ui = ui;
})(social, jQuery);


/*
 * JSON stringify
 */
(function($$, $) {
var json = JSON || {};
json.stringify = JSON.stringify || function (obj) {
    var t = typeof (obj);
    if (t != "object" || obj === null) {
        // simple data type
        if (t == "string") obj = '"'+obj+'"';
        return String(obj);
    }
    else {
        // recurse array or object
        var n, v, json = [], arr = (obj && obj.constructor == Array);
        for (n in obj) {
            v = obj[n]; t = typeof(v);
            if (t == "string") v = '"'+v+'"';
            else if (t == "object" && v !== null) v = JSON.stringify(v);
            json.push((arr ? "" : '"' + n + '":') + String(v));
        }
        return (arr ? "[" : "{") + String(json) + (arr ? "]" : "}");
    }
};

$$.json = json;
})(social, jQuery);



/*
 * Handle access control related menus and dialog.
 */
(function($$, $) {
var acl = {
    showACL: function(event, id) {
        var evt = $.event.fix(event),
            $target = $(evt.target),
            $menu = $target.next()

        if (!$menu.hasClass("ui-menu")) {
            $menu.menu({
                    select: function(event, ui) {
                         $(this).hide();
                         acl.updateACL(id, ui);
                     }
                 })
                 .css("z-index", 1000);
        }

        acl.refreshGroups(id);
        $menu.show().position({
                my: "right top",
                at: "right top",
                of: $target
            }).focus();

        $(document).one("click", function() {$menu.hide();});
        evt.stopPropagation();
    },

    updateACL: function(id, ui) {
        var type = ui.item.children("a").first().attr("_acl"),
            aclObj = {accept:{}},
            str = ui.item.text();
        
        if (type === "public") {
            aclObj.accept.public = true;
        }
        else if (type === "friends") {
            aclObj.accept.friends = true;
        }
        else if (type.match(/^org:/)) {
            aclObj.accept.orgs = type.substr(4).split(",");
        }
        else if (type.match(/^group:/)) {
            aclObj.accept.groups = type.substr(6).split(",");
        }
        else {
            return;
        }

        $("#"+id).attr("value", $$.json.stringify(aclObj));
        $("#"+id+"-label").attr("value", ui.item.text());
    },

    refreshGroups: function(id) {
    }
};
$$.acl = acl;
})(social, jQuery);
