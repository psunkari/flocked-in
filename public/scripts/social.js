
$("a.ajax").live("click", function() {
    if (this.hasAttribute('_ref'))
        $.getScript('/ajax' + this.getAttribute('_ref'))
    else if (this.hasAttribute('href'))
        $.address.value($(this).attr('href'));

    return false;
})

$(document).ajaxError(function(event, request, settings) {
    alert("Error fetching: " + settings.url);
})

var oldPath = null;
$.address.change(function(event) {
    if (oldPath) {
        tail = '';
        if (oldPath != event.path)
            tail = event.queryString? "&_fp=1": "?_fp=1";

        $.getScript('/ajax' + event.value + tail);
    }
    oldPath = event.path
})

function clearAllBlocks() {
    $('#left').html('');
    $('#right').html('');
    $('#center-header').html('');
    $('#center-contents').html('');
}

// The .bind method from Prototype.js
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

// Load the page in Chunks.
// Takes the already loaded resource ids as argument.
function ChunkLoader(resources) {
    for (var rsrc in resources)
        this._global.push(rsrc);
}
ChunkLoader.prototype = {
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
            if (id in this._resources)
                resources.push(this._resources[id]);

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
                    id in this._loaded || currentWaitTime >= maxWaitTime) {
                    clearInterval(timer);
                    checkResourcesCount();
                } else {
                    currentWaitTime += 20;
                }
            }
            timer = setInterval(checker.bind(this), 20)
        }

        function loadCSS(rsrc) {
            if (!rsrc.id in this._requested)
                $("document").ready(function(){
                    $("head").append('<link rel="stylesheet" type="text/css" href="' + rsrc.url + '"/>');
                    this._requested.push(rsrc.id)
                })
            cssCheckLoaded(rsrc.id);
        }

        for (var rsrc in resources) {
            if (rsrc.id in this._loaded)
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
                this._resources[rsrc.id] = rsrc

        var cleanup = obj.method == "set"? true: false;
        this._loadResources(obj.css || [],
                            this._displayContent.bind(this, obj),
                            cleanup, obj.parent || null);

        this._delayed.push(obj);
        if (obj.last) {
            this._loadResources(obj.js || [], this._runEventHandlers.bind(this));
        }
    },

    _runEventHandlers: function() {
        $.each(this._delayed, function(index, value) {
                if (value.handlers) {
                    handlers = value.handlers;
                    if (handlers.onload)
                        eval(handlers.onload);
                }
            }.bind(this))
        this._delayed = [];
    }
}
loader = new ChunkLoader();
