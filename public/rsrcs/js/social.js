
/*
 * Put all our stuff into a single namespace.
 * Accessible as "social", "$$" and "jQuery.social"
 */

(function(window, $) { if (!window.social) {
var social = {
_historyHasStates: false,

/*
 * Preprocess all ajax requests:
 * 1. Add a request argument to indicate current page
 * 2. Add a token for csrf busting (read from cookie)
 */
_sendingAjaxRequest: function(evt, xhr, options) {
    var uri = social.parseUri(options.url),
        method = options.type,
        data = options.data || '',
        cookies = document.cookie.split(';'),
        currentUri = social.parseUri($.address.value()),
        separator = null, csrfToken = null, payload = null;

    if (!social._historyHasStates && (currentUri.path == '' || currentUri.path == '/'))
        currentUri = social.parseUri(window.location.href);

    for (var i=0; i<cookies.length; i++) {
        var cookie = $.trim(cookies[i]);
        if (cookie.indexOf('token') == 0)
            csrfToken = decodeURIComponent(cookie.substring(6));
    }

    payload = "_pg=" + currentUri.path + "&_tk=" + csrfToken;
    separator = uri.query? "&": "?";
    options.url = options.crossDomain? options.url:options.url + separator + payload;
},

/*
 * parseUri:
 * Based on http://blog.stevenlevithan.com/archives/parseuri
 */
parseUri: function parseUri(str) {
    var matches = /^(?:([^:\/?#]+):)?(?:\/\/((?:(([^:@]*)(?::([^:@]*))?)?@)?([^:\/?#]*)(?::(\d*))?))?((((?:[^?#\/]*\/)*)([^?#]*))(?:\?([^#]*))?(?:#(.*))?)/.exec(str),
        keys = ["source","protocol","authority","userInfo","user","password","host","port","relative","path","directory","file","query","anchor"],
        uri = {};

    var i = 14;
    while (i--) uri[keys[i]] = matches[i];

    return uri;
},

/*
 * fetchUri:
 * To be used when a request would also add an entry in browser history
 */
_fetchUriOldPath: null,
fetchUri: function _fetchUri(str, ignoreHistory) {
    uri = social.parseUri(str);
    deferred = null;
    if (social._fetchUriOldPath) {
        tail = '';
        if (social._fetchUriOldPath != uri.path)
            tail = uri.query? "&_fp=1": "?_fp=1";

        deferred = $.get('/ajax' + str + tail);
    }
    social._fetchUriOldPath = uri.path;

    if (ignoreHistory === undefined || !ignoreHistory)
        $.address.value(str);

    return deferred;
},

/*
 * setBusy:
 * Indicates busy status on the closest matching '.busy-indicator' node
 * based on an ajax request
 */
setBusy: function _setBusy(deferred, node) {
    busyIndicator = null;
    if (!deferred)
        return;

    if (node.hasClass('busy-indicator'))
        busyIndicator = node;
    else if (bi = node.attr("data-bi"))
        busyIndicator = $('#' + bi);
    else
        busyIndicator = node.closest('.busy-indicator');

    busyIndicator.addClass("busy");
    deferred.done(function(){busyIndicator.removeClass("busy");});
},

/*
 * _initAjaxRequests:
 * Initialize ajax requests and history handling
 */
_initAjaxRequests: function _initAjaxRequests() {
    var self = this;

    /* Async Get */
    $("a.ajax,button.ajax").live("click", function() {
        var node = $(this),
            deferred = null,
            url = null;

        if (url = node.attr('data-ref'))
            deferred = $.get('/ajax' + url);
        else if ((url = node.attr('href')) || (url = node.attr('data-href')))
            deferred = self.fetchUri(url);

        self.setBusy(deferred, node);
        return false;
    });

    /* Async Post */
    $("a.ajaxpost,button.ajaxpost").live("click", function() {
        var node = $(this),
            url = node.attr('data-ref');
        parsed = social.parseUri(url);

        deferred = $.post('/ajax' + parsed.path, parsed.query);

        self.setBusy(deferred, node);
        return false;
    });

    /* Async form submit */
    $('form.ajax').live("submit", function() {
        var $this = $(this),
            validate, deferred, enabler, $inputs;

        if ($this.attr("disabled"))
            return false;

        validate = jQuery.Event('html5formvalidate');
        if ($this.data('html5form')) {
            $this.trigger(validate);
            if (validate.isDefaultPrevented())
                return false;
        }

        deferred = $.post('/ajax' + $this.attr('action'),
                          $this.serialize());

        self.setBusy(deferred, $this)

        // Prevent accidental resubmission by disabling the
        // form till we get a response from the server.
        $this.attr("disabled", true);
        $inputs = $this.find(":input").attr("disabled", true);
        enabler = function() {
            $inputs.removeAttr("disabled");
            $this.removeAttr("disabled");
        };
        deferred.then(enabler, enabler);

        $this.trigger('restorePlaceHolders');
        return false;
    });

    /* Search form is actually submitted over GET */
    $('#search').live("submit", function() {
        if (this.hasAttribute("disabled"))
            return false;

        var $this = $(this);
        var validate = jQuery.Event('html5formvalidate');
        if ($this.data('html5form')) {
            $this.trigger(validate);
            if (validate.isDefaultPrevented())
                return false;
        }

        var uri = '/search?'+$this.serialize(),
            deferred = $.fetchUri(uri);

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

        $this.trigger('restorePlaceHolders');
        return false;
    });


    /* Global ajax error handler */
    $(document).ajaxError(function(event, request, settings, thrownError) {
        if (request.status == 401) {
            currentUri = self.parseUri(window.location);
            currentUri = escape(currentUri.relative)
            window.location = '/signin?_r='+currentUri;
        } else if (request.status == 500 || request.status == 403 ||
                   request.status == 404 || request.status == 418) {
            $$.alerts.error(request.responseText);
        } else {
            if (window.console){
                console.log("An error occurred while fetching: "+settings.url+" ("+request.status+")");
            }
        }
        $('.busy-indicator.busy').removeClass('busy');
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
        self.fetchUri(event.value, true)
    });

    /* By default we always request script */
    $.ajaxSetup({dataType: 'script'});

    /* Preprocessing for all ajax requests.  Add "_pg" and "_tk" */
    $('html').ajaxSend(self._sendingAjaxRequest);
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


_initUpdatesCheck: function _initUpdatesCheck() {
    //window.setInterval(function() {
    //    $.get('/ajax/notifications/new');
    //}, 30000)
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
                            } catch(ex) {
                                if (window.console)
                                    console.log(ex);
                            }
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
social._initUpdatesCheck();

$.social = window.social = window.$$ = social;
}})(window, jQuery);




/*
 * Custom loading for the share block (publisher)
 * TODO: Handle extra options for showing buttons etc;
 */
(function($$, $) { if (!$$.publisher) {
var publisher = {
    load: function(obj) {
        // Tab selection
        $('.selected-publisher').removeClass('selected-publisher');
        $('#publisher-'+obj.publisherName).addClass('selected-publisher');

        // Enable HTML5 features
        $('#share-form').html5form({messages: 'en'});

        // Auto expand textareas
        $('#sharebar textarea').autogrow();
    }
};

$$.publisher = publisher;
}})(social, jQuery);




/*
 * Callback to be called when one or more conversations are loaded
 * into the view. Initializes the item's display - the comment form etc;
 */
(function($$, $) { if (!$$.convs) {
var convs = {
    load: function(obj) {
        // HTML5 form and Auto expand comment boxes
        $('.comment-input').autogrow().closest('form').html5form({messages:'en'});
        $('.conv-tags-input').closest('form').html5form({messages:'en'});
    },

    editTags: function(convId, addTag) {
        var $wrapper = $('#conv-tags-wrapper-'+convId),
            $input = $wrapper.find('.conv-tags-input')

        $wrapper.addClass('editing-tags');
        if (!$input.hasClass('ui-autocomplete-input')) {
            $input.autocomplete({
                source: '/auto/tags?itemId='+convId,
                minLength: 2,
                select: function(event, ui) {
                            if (ui && ui.item) {
                                $input = $(this);
                                $input.val(ui.item.value);
                                $input.closest('form').submit();
                            }
                        }
            });
        }

        convs.showHideComponent(convId, 'tags', true);
        if (addTag)
          $input.select().focus();
    },

    doneTags: function(convId) {
        $('#conv-tags-wrapper-'+convId).removeClass('editing-tags');
        if ($('#conv-tags-'+convId).children().length == 0)
            convs.showHideComponent(convId, 'tags', false);
    },

    comment: function(convId) {
        convs.showHideComponent(convId, 'comments', true);
        $('#comment-form-'+convId).find('.comment-input').select().focus();
    },

    showItemLikes: function(itemId) {
        var dialogOptions = {
            id: 'likes-dlg-'+itemId
        };
        $$.dialog.create(dialogOptions);
        $.get('/ajax/item/likes?id='+itemId);
    },

    showHideComponent: function(convId, component, show) {
        var className = 'no-'+component,
            wrapper = $('#conv-meta-wrapper-'+convId);

        if (show && wrapper.hasClass(className)) {
            wrapper.removeClass(className);
            convs._commentFormVisible(convId);
        } else if (!show && !wrapper.hasClass(className)) {
            wrapper.addClass(className);
        }
    },

    /* Reset the sizes of autogrow-backplane */
    /* XXX: This copied some code from jquery.autogrow-textarea.js directly */
    _commentFormVisible: function(convId) {
        var input = $('.comment-input', '#comment-form-wrapper-'+convId);
        if (input.next().hasClass('autogrow-backplane')) {
            backplane = input.next();
            backplane.width(input.width() - parseInt(input.css('paddingLeft')) - parseInt(input.css('paddingRight')));
        }
    },

    embed: function(convId) {
        var $embedFrame = $('#embed-frame-'+convId),
            width = $embedFrame.css('width'),
            height = $embedFrame.css('height'),
            frame = '<iframe src="/embed/link?id='+convId+
                    '" height="'+height+'" width="'+width+
                    '" frameborder="0"></iframe>';

        $embedFrame.append($(frame))
                   .css('display', 'block')
                   .prev().css('display', 'none')
                   .nextAll('.link-summary').css('display', 'none');
    },

    remove: function(convId, commentId) {
        if (commentId === "undefined" || convId == commentId)
            $('#conv-'+convId).slideUp('fast', function(){$(this).remove();});
        else
            $('#comment-'+commentId).slideUp('fast', function(){$(this).remove();});
    },

    expandText: function(event) {
        var evt = $.event.fix(event),
            $target = $(evt.target),
            $container = $target.parent();

        $container.find('.text-full').css('display', 'inline');
        $container.find('.text-collapser').css('display', 'block');
        $container.find('.text-preview').css('display', 'none');
        $container.find('.text-expander').css('display', 'none');
    },

    collapseText: function(event) {
        var evt = $.event.fix(event),
            $target = $(evt.target),
            $container = $target.parent();

        $container.find('.text-preview').css('display', 'inline');
        $container.find('.text-expander').css('display', 'inline');
        $container.find('.text-full').css('display', 'none');
        $container.find('.text-collapser').css('display', 'none');
    }
};

$$.convs = convs;
}})(social, jQuery);


(function($$, $){ if (!$$.feedback) {
var feedback = {
    _mood: null,
    showFeedback: function() {
        feedback._mood = 'happy';
        var dialogOptions = {
            id: 'feedback-dlg',
            buttons: [
                {
                    text:'Submit',
                    click : function() {
                        comment = $("#feedback-desc").val();
                        $.post("/ajax/feedback", {comment:comment, mood:feedback._mood});
                        $$.dialog.close(this, true)
                    }
                },
                {
                    text: 'Cancel',
                    click: function() {
                        $$.dialog.close(this, true)
                    }
                }
            ]
        };
        $$.dialog.create(dialogOptions);
        $.get('/ajax/feedback', function() {feedback.mood('happy');});
    },

    _descriptionLabels: {
        happy: 'Please describe what you liked',
        sad: 'Please describe your problem below',
        idea: 'Please describe your idea'
    },
    _titles: {
        happy: 'flocked.in made me happy!',
        sad: 'flocked.in made me sad',
        idea: 'I have an idea for flocked.in'
    },

    mood: function(mood) {
        feedback._mood = mood;

        $('.feedback-mood-selected').removeClass('feedback-mood-selected');
        $('#feedback-'+mood).addClass('feedback-mood-selected');

        $('#feedback-dlg-title').text(feedback._titles[mood]);
        $('#feedback-type').text(feedback._descriptionLabels[mood]);
        $('#feedback-desc').focus()
    }
};
$$.feedback = feedback;
}})(social, jQuery);


/*
 * Elements of the UI
 */
(function($$, $){ if (!$$.ui) {
var ui = {
    init: function() {
        /* Check if the browser is supported */
        var ua = $.browser,
            c = 0,
            ver = parseFloat(ua.version.replace(/\./g, function() {
                              return (c++ == 1) ? '' : '.';
                            }));
        if (ua.msie && ver < 8 && document.documentMode) {
          $('#compatibility-mode').css('display', 'block');
        } else if (ua.msie && ver >= 8 ||
                   ua.webkit && ver >= 530  ||
                   ua.opera && ver >= 10.10 ||
                   ua.mozilla && ver >= 1.9) {
          // Supported Browsers
        } else {
          $('#unsupported-browser').css('display', 'block');
        }

        /* Add a scroll to bottom handler */
        $(window).scroll(function(){
            if ($(window).scrollTop() > $(document).height() - (50 + $(window).height())){
                $nextPageLoad = $('#next-page-load');
                if (!$nextPageLoad.attr('requested')) {
                    $nextPageLoad.click();
                    $nextPageLoad.attr('requested', true);
                }
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
        /* HTML5 form emulation for search form */
        $("#searchbox").autocomplete({
            source: '/auto/searchbox',
            minLength: 3,
            select: function(event, obj){
                var url = obj.item.href;
                if (url !== undefined) {
                    $$.fetchUri(url);
                    event.target.value = "";
                    return false;
                }
                return true;
            }
        }).closest('form').html5form({messages:'en'});
    },

    showPopup: function(event, right, above){
        var evt = $.event.fix(event),
            $target = $(evt.target),
            $menu = $target.next();

        if (!$menu.hasClass("ui-menu")) {
            $menu.menu({
                    select: function(event, ui) {
                         $(this).hide();
                     }
                 })
                 .css("z-index", 2000);
        }

        atX = myX = right? "right": "left";
        myY = above? "bottom": "top";
        atY = above? "top": "bottom";
        $menu.show().position({
                my: myX + " " + myY,
                at: atX + " " + atY,
                of: $target
            }).focus();

        $(document).one("click", function() {$menu.hide();});
        evt.stopPropagation();
        evt.preventDefault();
    },

    bindFormSubmit: function(selector) {
        //Force form submits via ajax posts when form contains a input file.
        $(selector).submit(function() {
            $this = $(this);
            if ($this.data('html5form')) {
                var validate = jQuery.Event('html5formvalidate');
                $this.trigger(validate);
                if (validate.isDefaultPrevented())
                    return false;
            }

            $.ajax(this.action, {
                     type: "POST",
                     dataType: "script",
                     data: $(selector+' :input').serializeArray(),
                     files: $(":file", this),
                     processData: false
                 }).complete(function(data) {
                     $(selector).find(":file").val("");
                 }).success(function(data) {});
            $this.trigger('restorePlaceHolders');
            return false;
        });
    }
}

$$.ui = ui;
}})(social, jQuery);


/* File uploads and related handling */
(function($$, $){ if (!$$.files) {
var files = {
    removeFromShare: function(fileId) {
        $('#upload-'+fileId).remove();
        $('#upload-input-'+fileId).remove();
        $.post("/ajax/file/remove", {id: fileId});
    },

    getNameFromPath: function(strFilepath) {
        var objRE = new RegExp(/([^\/\\]+)$/),
            strName = objRE.exec(strFilepath);

        return strName? strName[0]: null;
    },

    init: function(id){
        var _self = this;

        $("#"+id+" :file").change(function() {
            var form = $(this.form), d, mimeType = null, filename = null;

            /* Get basic information about the files */
            if (this.files !== undefined && this.files[0] !== undefined) {
                filename = this.files[0].name || this.files[0].fileName;
                mimeType = this.files[0].type || '';
                d = $.post('/files/form',
                           {"name":filename, "mimeType":mimeType}, "json");
            }
            if (!filename) {
                filename = _self.getNameFromPath(this.value);
                d = $.post('/files/form', {"name":filename}, "json");
            }

            d.then(function(data) {
                var fileInputs, uploadXhr, uploadedContainer;

                fileInputs = form.find(':file');
                files.prepareUploadForm(form, data);
                uploadXhr =
                    $.ajax(form.prop("action"), {
                            type: "POST",
                            dataType: "json",
                            files: fileInputs,
                            data: form.find(":input:not(:hidden)").serializeArray(),
                            processData: false
                        })
                     .success(function(data) {
                            var hiddenInputs = [], uploaded = [],
                                fileId, fileInfo, inputItem, listItem,
                                textToInsert;

                            for (fileId in data.files) {
                                fileInfo = data.files[fileId];
                                fileSize = parseInt(fileInfo[2])/1000;
                                inputItem = "<input type='hidden' id='upload-input-" +
                                              fileId + "' name='fId' value='"+ fileId +"'/>";
                                listItem = "<div id='upload-"+fileId+"' class='uploaded-file'>" +
                                              "<span class='uploaded-file-name'>"+fileInfo[1]+"</span>" +
                                              "<button type='button' class='uploaded-file-del' onclick='" +
                                                  "$$.files.removeFromShare(\""+fileId+"\")'/>" +
                                              "<span class='uploaded-file-meta'>"+fileSize.toFixed(2)+
                                                  "&nbsp;<abbr title='Kilobytes'>kB</abbr></span>"

                                hiddenInputs.push(inputItem);
                                uploaded.push(listItem);
                            }

                            $('#'+id+'-uploaded').append(hiddenInputs.join(''))
                                                 .append(uploaded.join('')); })
                     .complete(function(data) {
                            fileInputs.val("");
                        });
                $$.setBusy(uploadXhr, $('#'+id+'-wrapper'));
            }, function (err) {
                if (window.console)
                    console.log(err);
            })
        });
    },

    prepareUploadForm: function(form, map){
        var dataMap = $.parseJSON(map);
        $.each(dataMap[0], function(k, val) {
            if (k == "action") {
                form.attr("action", val);
            } else if (k == "fields") {
                $.each(val, function(idx, field) {
                    form.find('input[name="'+field.name+'"]').remove();
                    $("<input type='hidden'>").attr("name", field.name)
                                              .attr("value", field.value)
                                              .prependTo(form);
                });
            }
        });
    }
}

$$.files = files;
}})(social, jQuery);



/*
 * JSON stringify
 */
(function($$, $) { if (!$$.json) {
var jsonObj = window.JSON || {};
if (!jsonObj.stringify) {
    jsonObj.stringify = function (obj) {
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
                else if (t == "object" && v !== null) v = jsonObj.stringify(v);
                json.push((arr ? "" : '"' + n + '":') + String(v));
            }
            return (arr ? "[" : "{") + String(json) + (arr ? "]" : "}");
        }
    }
};

$$.json = jsonObj;
}})(social, jQuery);


/*
 * Dialogs
 */
(function($$, $) { if (!$$.dialog) {
var dialog = {
    _counter: 0,
    _dialogs: {},

    _options: {
        position: {
            my: 'center top',
            at: 'center top',
            of: window,
            offset: '0 200px'
        },
        buttons: [
            {
                text: 'Close',
                click: function() {
                    $$.dialog.close(this, true);
                }
            }
        ],
        destroyOnEscape: true
    },

    _template: '<div class="ui-dlg-outer" tabindex="0">' +
                 '<div class="ui-dlg-inner">' +
                   '<div class="ui-dlg-contents"/>' +
                 '</div>' +
               '</div>',

    createButtons: function($dialog, dlgId, options) {
        if (!options.buttons || !$.isArray(options.buttons) ||
             options.buttons.length == 0)
            return;

        $('#'+dlgId+'-buttonbox').remove();   // Remove if buttons already exist
        var $buttonBox = $("<div>").addClass("ui-dlg-buttonbox")
                                   .attr('id', dlgId+'-buttonbox')
                                   .appendTo($dialog.find('.ui-dlg-inner')),
            $buttonset = $("<div>").addClass("ui-dlg-buttonset")
                                   .attr('id', dlgId+'-buttonset')
                                   .appendTo($buttonBox);

        $.each(options.buttons, function(idx, props) {
            if (typeof props !== "object")
                return;

            $("<button type='button'>").attr(props, true)
                            .unbind("click")
                            .click(function() {
                                props.click.apply($dialog, arguments);
                            })
                            .addClass('button')
                            .appendTo($buttonset);
        });
    },

    create: function(obj) {
        var $template = $(dialog._template),
            options = $.extend({}, dialog._options, obj)
            dlgId = options.id || "dialog-" + dialog._counter,
            self = this;

        if (dialog._dialogs[dlgId]) {
            $template = dialog._dialogs[dlgId];
            $template.focus().show();
        } else {
            $template.attr('id', dlgId + '-outer').attr('dlgId', dlgId);
            $('.ui-dlg-inner', $template).attr('id', dlgId + '-inner');
            $('.ui-dlg-contents', $template).attr('id', dlgId);

            if (options.destroyOnEscape) {
                $template.keydown(function(event) {
                    if (event.which == 27)
                        self.close($template, true);
                });
            }

            dialog._dialogs[dlgId] = $template;
            dialog.createButtons($template, dlgId, options);
            $template.appendTo(document.body).focus();
        }

        $template.css('z-index', 1000+dialog._counter)
        $('#'+dlgId+'-inner').position(options.position);

        dialog._counter += 1;
    },

    close: function(dlg, destroy) {
        var $dialog, id;
        if (typeof dlg == "string") {
            $dialog = dialog._dialogs[dlg];
            id = dlg;
        } else {
            $dialog = dlg;
            id = dlg.attr('dlgId');
        }

        if (!$dialog.length)
            return;

        $dialog.hide();
        if (destroy) {
            $dialog.remove();
            delete dialog._dialogs[id];
        }
    },

    closeAll: function(destroy) {
        $.each(dialog._dialogs, function(key, value) {
            value.hide();
            if (destroy)
                value.remove();
        });
        dialog._dialogs = {};
    }
};

// Close all dialogs when we navigate to a different page.
$.address.change(function(event) {
    dialog.closeAll(true);
});

$$.dialog = dialog;
}})(social, jQuery);


/*
 * Sidemenu related utilities
 */
(function($$, $) { if (!$$.menu) {
var menu = {
    selectItem: function(itemId) {
        var selected = $('.sidemenu-selected'),
            itemSelector = '#'+itemId+'-sideitem';

        if (selected.is(itemSelector))
            return;

        selected.removeClass('sidemenu-selected');
        $(itemSelector).addClass('sidemenu-selected');
    },

    counts: function(obj) {
        $.each(obj, function(key, value) {
            var $item = $('#'+key+'-sideitem'),
                $counter = $item.children('.new-count');

            if ($counter.length == 0 && value > 0) {
                $counter = $('<div class="new-count"></div>');
                $counter.appendTo($item);
            }

            if (value > 0)
                $counter.text(value);
            else
                $counter.remove();
        });
    }
};
$$.menu = menu;
}})(social, jQuery);


/*
 * Cache for lazy load.
 * List of groups, list of online users, list of notifications etc;
 */
(function($$, $) { if (!$$.data) {
var data = {
    _data: {},  // Local cache of data

    wait: function(url, method) {
        var self = this;
        /*
         * Always fetch the data till we have a proper
         * way to cache and refresh our caches.
         *
        if (self._data[url] !== undefined) {
            method(self._data[url]);
            return;
        }
        */
        var deferred = $.get(url, null, null, "json"),
            success = function(data) {
                self._data[url] = data;
                method(self._data[url]);
            },
            failure = function() {
                method([]);
            }
        deferred.then(success, failure);
    }
};

$$.data = data;
}})(social, jQuery);




/*
 * Handle access control related menus and dialog.
 */
(function($$, $) { if (!$$.acl) {
var acl = {
    showACL: function(event, id) {
        var evt = $.event.fix(event),
            $target = $("#" + id + "-button"),
            $menu = $target.next()

        if (!$menu.hasClass("ui-menu")) {
            $menu.menu({
                     select: function(event, ui) {
                         $(this).hide();
                         acl.updateACL(id, ui);
                     }
                 })
                 .css("z-index", 2000);
        }

        acl.refreshGroups(id);
        $menu.show().position({
                my: "right top",
                at: "right bottom",
                of: $target
            }).focus();

        $(document).one("click", function() {$menu.hide();});
        evt.stopPropagation();
        evt.preventDefault();
    },

    switchACL: function(id, type, entityId, entityName){
        var aclObj = {accept:{}}
        if (type == "group"){
            aclObj.accept.groups = [entityId];
            $("#"+id).attr("value", $$.json.stringify(aclObj));
            $("#"+id+"-label").text(entityName);
            $("#"+id+"-label").attr("disabled", 'disabled');
        }
        return ;

    },

    updateACL: function(id, ui) {
        var type = ui.item.children("a").first().attr("data-acl"),
            aclObj = {accept:{}},
            str = ui.item.find(".acl-title").text();
            tooltip = ui.item.find(".acltip").text();

        if (type === "public") {
            aclObj.accept.pub = true;
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

        $("#"+id+"-tooltip").text(tooltip);
        $("#"+id).attr("value", $$.json.stringify(aclObj));
        $("#"+id+"-label").text(str);
    },

    /* Update list of groups displayed in the menu */
    refreshGroups: function(id) {
        var groupsSeparator = $("#"+id+"-groups-sep");

        groupsSeparator.nextUntil('#'+id+'-custom-sep').remove();
        groupsSeparator.after("<li class='acl-busy-item'><i>Loading...</i></li>")

        $$.data.wait("/auto/mygroups", (function(groups) {
            items = [];
            $.each(groups || [], function(i, g) {
                items.push('<li><a class="acl-item" data-acl="group:' + g.id + '">' +
                           '<span class="acl-title">' + g.name + '</span>' +
                           '<div class="acltip" style="display:none;">' + g.name + '</div>' +
                           '</a></li>');
            });

            if (items.length) {
                groupsSeparator.next().replaceWith(items.join(""));
                $("#"+id+"-menu").menu("refresh")
                groupsSeparator.css('display', 'block');
            } else {
                groupsSeparator.css('display', 'none');
                groupsSeparator.next().remove();
            }
        }).bind(this));
    }
};
$$.acl = acl;
}})(social, jQuery);


/*
 * Messaging related routines
 * Handle adding, removing users from composer etc
 */
(function($$, $) { if (!$$.messaging) {
var messaging = {
    autoFillUsers: function(){
        $('.conversation-composer-field-recipient').autocomplete({
            source: '/auto/users',
            minLength: 2,
            select: function( event, ui ) {
                $('.conversation-composer-recipients').append(
                    $$.messaging.formatUser(ui.item.value, ui.item.uid));
                var rcpts = jQuery.trim($('#recipientList').val());
                rcpts = (rcpts == "") ? ui.item.uid: rcpts+","+ui.item.uid
                $('#recipientList').val(rcpts)
                this.value = "";
                return false;
        }
        });
    },
    removeUser: function(self, user_id){
        var recipients = $('#recipientList').val().split(",");
        var rcpts = jQuery.grep(recipients, function (a) { return a != user_id; });
        $('#recipientList').val(rcpts.join(","))
        $(self).parent().remove();
    },
    formatUser: function(user_string, user_id){
        return "<div class='conversation-composer-recipient-wrapper tag'>"+
            "<span class='conversation-composer-recipient-label'>"+ user_string +"</span>"+
            "<span class='conversation-composer-recipient-remove button-link' "+
                "onclick='$$.messaging.removeUser(this, \""+user_id+"\")'>X</span></div>"
    }
};

$$.messaging = messaging;
}})(social, jQuery);


/*
 * Event Plugin related routines
 * Formatting date times, merging date times etc.
 */
(function($$, $) { if (!$$.events) {
var events = {
    formatTimein12: function(dateObj){
        //Format time in AM/PM format derived from a date object
        var currentHours = dateObj.getHours();
        var currentMinutes = dateObj.getMinutes();

        currentMinutes = ( currentMinutes < 10 ? "0" : "" ) + currentMinutes;
        // Choose either "AM" or "PM" as appropriate
        var timeOfDay = ( currentHours < 12 ) ? "AM" : "PM";

        // Convert the hours component to 12-hour format if needed
        currentHours = ( currentHours > 12 ) ? currentHours - 12 : currentHours;

        // Convert an hours component of "0" to "12"
        currentHours = ( currentHours == 0 ) ? 12 : currentHours;
        return currentHours + ":" + currentMinutes + timeOfDay
    },
    RSVP: function(itemId, response){
        //Add routine for submitting an RSVP
        var postdata = 'type=event&id='+itemId+'&response='+response;
        $.post('/ajax/event/rsvp', postdata)
    },
    removeUser: function(self, user_id){
        var invitees = $('#inviteeList').val().split(",");
        var rcpts = jQuery.grep(invitees, function (a) { return a != user_id; });
        $('#inviteeList').val(rcpts.join(","))
        $(self).parent().remove();
    },
    formatUser: function(user_string, user_id){
        return "<div class='tag'>"+
            "<span class='conversation-composer-recipient-label'>"+ user_string +"</span>"+
            "<span class='conversation-composer-recipient-remove button-link' "+
                "onclick='$$.events.removeUser(this, \""+user_id+"\")'>X</span></div>";
    },
    showEventInvitees: function(itemId) {
        var dialogOptions = {
            id: 'invitee-dlg-'+itemId
        };
        $$.dialog.create(dialogOptions);
        $.get('/ajax/event/invitee?id='+itemId);
    },
    prepareDateTimePickers: function(){
        var currentTime = new Date();
        // Set the Display Strings
        $('#eventstartdate').datepicker({ minDate: currentTime,
            changeMonth: true, altField: '#startDate', altFormat: '@',
            onSelect: function(selectedDate){
                var instance = $(this).data("datepicker")
                var date = $.datepicker.parseDate(
                                    instance.settings.dateFormat ||
                                        $.datepicker._defaults.dateFormat,
                                    selectedDate, instance.settings );
                $('#eventenddate').datepicker("option", "minDate", date)
            }
        });
        $('#eventenddate').datepicker({ minDate: currentTime,
            changeMonth: true, altField: '#endDate', altFormat: '@'});
        $('#eventstartdate').datepicker('setDate', new Date());
        $('#eventenddate').datepicker('setDate', new Date());

        $("#allDay").change(function(){
            $('#startTimeWrapper, #endTimeWrapper').toggle()
        })
    }
};

$$.events = events;
}})(social, jQuery);


/*
 * Error, warning and info alerts
 */
(function($$, $) { if (!$$.alerts) {
var alerts = {
    error: function(msg) {
        alerts._message(msg, "error");
    },
    warning: function(msg) {
        alerts._message(msg, "warning");
    },
    info: function(msg) {
        alerts._message(msg, "info");
    },

    _timeout: 5000,
    _messageNum: 0,
    _message: function(msg, cls) {
        var $alertbar = $('#alertbar'),
            $newalert = $('<div class="alert alert-'+cls+'">'+msg+'</div>'),
            msgId = "alert-id" + (alerts._messageNum + 1);

        alerts._messageNum += 1;
        $alertbar.children(':first').removeClass('first-child');
        $newalert.attr('id', msgId).addClass('first-child')
                 .prependTo($alertbar)
                 .hide()
                 .click(function() {
                   alerts._clearMessage(msgId);
                 }).slideDown('fast');

        setTimeout(function(){alerts._clearMessage(msgId)}, alerts._timeout);
    },

    _clearMessage: function(msgId) {
        $('#'+msgId).slideUp().remove()
    },
    _clearAll: function() {
        $('#alertbar').empty();
    }
};

// Close all alerts when we navigate to a different page.
$.address.change(function(event) {
    alerts._clearAll();
});

$$.alerts = alerts;
}})(social, jQuery);


/*
 * Settings/Edit Profile
 */
(function($$, $) { if (!$$.settings) {
var settings = {
    _openFormDialog: function(id, url) {
        var dialogOptions = {
            id: id,
            buttons: [
                {
                    text:'Submit',
                    click : function() {
                        query = $(':input', '#'+id+'-center').serialize();
                        $.post(url, query);
                    }
                },
                {
                    text: 'Cancel',
                    click: function() {
                        $$.dialog.close(this, true);
                    }
                }
            ]
        };
        $$.dialog.create(dialogOptions);
        $.get(url);
    },
    editEmp: function(companyId) {
        if (!companyId)
            companyId = '';
        settings._openFormDialog('addemp-dlg', '/ajax/settings/company?id='+companyId);
    },
    editEdu: function(schoolId) {
        if (!schoolId)
            schoolId = '';
        settings._openFormDialog('addedu-dlg', '/ajax/settings/school?id='+schoolId);
    }
}
$$.settings = settings;
}})(social, jQuery);

