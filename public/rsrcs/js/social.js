
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
        currentUri = social.parseUri(social._fetchUriOldPath),
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
    var uri = social.parseUri(str),
        deferred = null,
        tail = '', isFullPage = false;

    /* Ignore the first event that we get upon page load */
    if (social._fetchUriOldPath) {
        if (social._fetchUriOldPath != uri.path) {
            tail = uri.query? "&_fp=1": "?_fp=1";
            isFullPage = true;
        }
        deferred = $.get('/ajax' + str + tail);

        /* Updated only after a successful response */
        deferred.then(function() {
            social._fetchUriOldPath = uri.path;
            if (_gaq)
                _gaq.push(['_trackPageview', uri.path]);

            if (isFullPage)
                $$.chatUI.init();
        });
    } else {
        social._fetchUriOldPath = uri.path;
    }

    /* Update address in the navigation bar */
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

    clearBusyClass = function(){busyIndicator.removeClass("busy");};
    deferred.then(clearBusyClass, clearBusyClass);
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
        // Do not collect inputs that were already disabled. So that
        // reenabling the form inputs wont disturb the form elements in anyway.
        $inputs = $this.find(':input:not(:disabled)').attr("disabled", true);
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
                   request.status == 404 || request.status == 418 ||
                   request.status == 400) {
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
        self.fetchUri(event.value, true);
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
            timestamp = item.getAttribute("data-ts")
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

    window.setInterval(function() {
        $('.timetoexpiry').each(function(idx, item) {
            timestamp = item.getAttribute("data-ts");
            tooltip = item.getAttribute("title");

            current = new Date();
            current = current.getTime()/1000;
            delta = parseInt(timestamp) - current;

            if ($(item).data("endts") !== undefined) {
                enddelta = parseInt($(item).data("endts")) - current;
            }

            if (delta <= 0) {
                item.innerHTML = "in progress";
                if ($(item).data("endts") && enddelta < 0) {
                    item.innerHTML = "over";
                }
            }
            else if (delta < 3600) {
                var minutes = Math.floor(delta/60);
                if (minutes < 1) {
                    item.innerHTML = "now";
                }else{
                    item.innerHTML = minutes + " minute"+ (minutes==1?"":"s");
                }
            }else if ((delta > 3600) && (delta < 86400)) {
                var hours = Math.floor(delta/3600);
                item.innerHTML = hours + " hour"+ (hours==1?"":"s");
            }
        })
    }, 30000);
},


_initUpdatesCheck: function _initUpdatesCheck() {
    window.setInterval(function() {
        $.get('/ajax/notifications/new');
    }, 30000)
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


/* Pubsub: Based on https://gist.github.com/705311 */
var o = jQuery({});
jQuery.each({
        "subscribe" : "bind",
        "unsubscribe" : "unbind",
        "publish" : "trigger"
    }, function ( fn, api ) {
        social[ fn ] = function() {
            o[ api ].apply( o, arguments );
        };
    });

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

        $('#share-form').submit(function() {
            if ($('#sharebar-attach-wrapper').hasClass('busy')) {
                $$.alerts.info("Please wait while your files are being uploaded")
                return false
            }
        })
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
        $('.init-conv-item').each(function(i) {
            var $convItem = $(this),
                convId = $convItem.attr('data-convid'),
                $commentWrap = $('#comment-form-wrapper-'+convId),
                $commentInput = $commentWrap.find('.comment-input');

            $commentInput.autogrow();
            $commentWrap.children('form').html5form({messages:'en'});
            $('#comment-form-'+convId).submit(function() {
                if ($('#comment-attach-'+convId+'-wrapper').hasClass('busy')) {
                    $$.alerts.info("Please wait while your files are being uploaded")
                    return false
                }
            })

            $commentWrap.focusin(function(event) {
                                   var $attachForm = $('#comment-attach-'+convId);

                                   if ($attachForm.attr('data-inited') !== '1') {
                                       $$.files.init('comment-attach-'+convId);
                                       $attachForm.attr('data-inited', '1');
                                   }

                                   $attachForm.closest('.file-attach-wrapper').css('display', 'block');
                                   $('#comment-attach-'+convId+'-uploaded').css('display', 'block');
                                 });
                        /*
                         * TODO: Fix this code to hide the attach form correctly.
                        .focusout(function(event) {
                                   var $attachForm = $('#comment-attach-'+convId);
                                       $uploaded = $('#comment-attach-'+convId+'-uploaded');

                                   if ($commentInput.val() == '' && $uploaded.children().length == 0) {
                                       $attachForm.css('display', 'none');
                                       $uploaded.css('display', 'none');
                                   }
                                 });
                         */

            $convItem.find('.conv-tags-input').html5form({messages:'en'});
            $convItem.removeClass('init-conv-item');
        });
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
        var tag = $('#addtag-form-'+convId+' .conv-tags-input').val();
        var placeholder = $('#addtag-form-'+convId+' .conv-tags-input').attr('placeholder')
        if( tag != "" && tag != placeholder) {
            var d = $.post("/ajax/item/tag", {
                            id: convId,
                            tag: tag
                    });
            d.then(function() {
                if ($('#conv-tags-'+convId).children().length == 0){
                    convs.showHideComponent(convId, 'tags', false);
                }
                else {
                    convs.showHideComponent(convId, 'tags', true);
                }
            })
            $('#conv-tags-wrapper-'+convId).removeClass('editing-tags');
        } else {
            $('#conv-tags-wrapper-'+convId).removeClass('editing-tags');
            if ($('#conv-tags-'+convId).children().length == 0){
                convs.showHideComponent(convId, 'tags', false);
            }
        }
        $('#addtag-form-'+convId+' .conv-tags-input').val('');
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
        if (commentId === undefined || convId == commentId)
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
    },

    showItemReportDialog: function(itemId) {
        var dialogOptions = {
            id: 'report-dlg-'+itemId,
            buttons: [
                {
                    text:'Report',
                    click : function() {
                        comment = $("#conv-report-comment").val();
                        id = $("#conv-report-id").val();
                        action = $("#conv-report-action").val();
                        $.post("/ajax/item/report/report", {
                            id:id,
                            action:action,
                            comment:comment
                        });
                        $$.dialog.close(this, true)
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
        $.get('/ajax/item/showReportDialog?id='+itemId);
    },

    reviewRequired: function(template, convId) {
        var form = null,
            dlgTemplate = '<div class="ui-dlg-outer" tabindex="0">' +
                            '<div class="ui-dlg-inner">' +
                              '<div class="ui-dlg-contents">' +
                                template +
                              '</div>' +
                            '</div>' +
                          '</div>',
            dialogOptions = {
                id: 'review-required-dlg',
                template: dlgTemplate,
                buttons: [
                    {
                        text: 'Post It',
                        click: function() {
                            var review = $('<input type="hidden" name="_review" value="1"/>'),
                                form = convId? $('#comment-form-'+convId) : $('#sharebar');
                            form.append(review).submit();
                            $$.dialog.close(this, true);
                        }
                    },
                    {
                        text: 'Edit Post',
                        click: function() {
                            $$.dialog.close(this, true);
                            if (convId)
                                $('#comment-form-'+convId).find('.comment-input').focus();
                            else
                                $('#sharebar').find(':input:visible:first').focus();
                        }
                    }
                ]
            };
        $$.dialog.create(dialogOptions);
    },

    filterFeed: function($target, ui) {
        var item = ui.item.children("a").first(),
            type = item.attr("data-ff"),
            str = item.text(),
            currentUri = social.parseUri(window.location.href),
            queryParts = currentUri.query? currentUri.query.split('&'): new Array(),
            newQueryParts = new Array(),
            ignore = false, newUri = '';

        for (var i = 0; i < queryParts.length; i++) {
            var fragmentParts = queryParts[i].split('=');
            if (fragmentParts[0] !== "type")
                newQueryParts.push(queryParts[i]);
            else if (fragmentParts[1] === type)
                ignore = true;
        }

        if (!ignore) {
            newQueryParts.push('type=' + type);
            newUri = currentUri.path + '?' + newQueryParts.join('&') +
                     (currentUri.anchor !== undefined? '#' + currentUri.anchor : '');
            social.fetchUri(newUri);
        }
    },

    showFilterMenu: function(event) {
        var evt = $.event.fix(event),
            $target = $(evt.target),
            $menu = $target.next()

        if (!$menu.hasClass("ui-menu")) {
            $menu.menu({
                     selected: function(event, ui) {
                         $(this).hide();
                         convs.filterFeed($target, ui);
                     }
                 })
                 .css("z-index", 2000);
        }

        var extras = $menu.outerWidth() - $menu.width();
        $menu.css("width", $target.outerWidth() - extras);

        $menu.slideDown('fast').position({
                my: "left top",
                at: "left top",
                of: $target
            }).focus();

        $(document).one("click", function() {$menu.hide();});
        evt.stopPropagation();
        evt.preventDefault();
    },

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
            if ($(window).scrollTop() > $('#mainbar').height() - (50 + $(window).height())){
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

        /*
        $('#sharebar').live('focusin',function(event){
          $('#sharebar-actions-wrapper').css('display', 'inline-block');
          $('#sharebar-attach').css('display', 'block');
          $('#sharebar-attach-uploaded').css('display', 'block');
        });
        */

        /* Power up the cometd connections. */
        $$.config = window.social_config;
        $$.comet.init();
        $$.chatUI.init();

        /* Add a handler to window unload */
        $(window).unload(ui.uninit);
    },

    uninit: function() {
        $$.comet.uninit();
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
                 }).error(function(data) {});
            $this.trigger('restorePlaceHolders');
            return false;
        });
    },
    addGroup: function(){
        var dialogOptions = {
            id: 'addgroup-dlg',
            buttons: [
                {
                    text:'Create New Group',
                    click : function() {
                        $('#add-group-form-submit').trigger('click');
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
        init = function() {
            $$.ui.bindFormSubmit('#add-group-form');
            $('#add-group-form').html5form({messages: 'en'});
        };
        var d = $.get('/ajax/groups/create');
        d.then(init);
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
        $.post("/ajax/files/remove", {id: fileId});
    },

    getNameFromPath: function(strFilepath) {
        var objRE = new RegExp(/([^\/\\]+)$/),
            strName = objRE.exec(strFilepath);

        return strName? strName[0]: null;
    },

    init: function(id){
        var self = this;

        $("#"+id).submit(function() {
            //Since the form is by itself never used to submit. So, always
            // cancel all submits. Actual submits are performed by the iframe
            // plugin.
            return false
        })

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
                filename = self.getNameFromPath(this.value);
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
        destroyOnEscape: true,
        template: '<div class="ui-dlg-outer" tabindex="0">' +
                     '<div class="ui-dlg-inner">' +
                       '<div class="ui-dlg-contents"/>' +
                     '</div>' +
                   '</div>'
    },

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
        var options = $.extend({}, dialog._options, obj),
            $template = $(options.template),
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
                     selected: function(event, ui) {
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

    /*
     * XXX: switchACL is currently used only to switch to groups
     *      in the group profile page.
     */
    switchACL: function(id, type, entityId, entityName){
        var aclObj = {accept:{}}
        if (type == "group"){
            aclObj.accept.groups = [entityId];
            $("#"+id).attr("value", $$.json.stringify(aclObj));
            $("#"+id+"-label").text(entityName);
            $("#"+id+"-label").attr("disabled", 'disabled');
            $("#"+id+"-button").addClass("acl-button-disabled");
            $("#"+id+"-tooltip").closest('.tooltip').css('visibility', 'hidden');
        }
        return ;
    },

    updateACL: function(id, ui) {
        var type = ui.item.children("a").first().attr("data-acl"),
            aclObj = {accept:{}},
            str = ui.item.find(".acl-title").text();
            tooltip = ui.item.find(".acltip").text();

        if (type.match(/^org:/))
            aclObj.accept.orgs = type.substr(4).split(",");
        else if (type.match(/^group:/))
            aclObj.accept.groups = type.substr(6).split(",");
        else
            return;

        $("#"+id+"-tooltip").text(tooltip);
        $("#"+id).attr("value", $$.json.stringify(aclObj));
        $("#"+id+"-label").text(str);

        if (type.match(/^group:/))
            $("#"+id+"-tooltip").closest('.tooltip').css('visibility', 'hidden');
        else
            $("#"+id+"-tooltip").closest('.tooltip').css('visibility', 'visible');
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
 */
(function($$, $) { if (!$$.messaging) {
var messaging = {
    compose: function(rcpt, subject, body) {
        var dialogOptions = {
            id: 'msgcompose-dlg',
            buttons: [
                {
                    text:'Send',
                    click : function() {
                        if ($('.tagedit-list.dlgform > .tagedit-listelement-old').length > 0){
                            $('#msgcompose-form-submit').trigger('click');
                        }else{
                            $$.alerts.error("Recipients field cannot be empty");
                        }
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
        $.get('/ajax/messages/write',
              {"recipients":rcpt, "subject":subject, "body":body});
    },
    initComposer: function() {
        $('#msgcompose-rcpts').tagedit({
            autocompleteURL: '/auto/users',
            additionalListClass: 'dlgform',
            breakKeyCodes: [13, 44, 32],
            allowEdit: false,
            allowAdd: false,
            autocompleteOptions: {
                    select: function( event, ui ) {
                            $(this).val(ui.item.value).trigger('transformToTag', [ui.item.uid]);
                            return false;
                    }
            }
        });
        $$.files.init('msgcompose-attach');
        $('#msgcompose-form').html5form({messages: 'en'});
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
    RSVP: function(itemId, response){
        //Add routine for submitting an RSVP
        var postdata = 'id='+itemId+'&response='+response;
        $.post('/ajax/event/rsvp', postdata)
    },
    showEventAttendance: function(itemId, type) {
        var dialogOptions = {
            id: 'invitee-dlg-'+itemId
        };
        $$.dialog.create(dialogOptions);
        $.get('/ajax/event/attendance?id='+itemId+'&type='+type);
    },
    prepareDateTimePickers: function(){
        var currentTime = new Date();

        // Instantiate Date pickers
        $('#startdate').datepicker({ minDate: currentTime,
            dateFormat:'D, d M yy',
            onSelect: function (selectedDate){
                var instance = $( this ).data( "datepicker" );
                var date = $.datepicker.parseDate(
                            instance.settings.dateFormat ||
                            $.datepicker._defaults.dateFormat,
                            selectedDate, instance.settings );

                $('#enddate').datepicker( "option", 'minDate', date );
                events.updateHiddenDateTimes();
            }
        });
        $('#startdate').change(function() {
            var instance = $( this ).data( "datepicker" );
            var selectedDate = $(this).val();
            var date = $.datepicker.parseDate(
                        instance.settings.dateFormat ||
                        $.datepicker._defaults.dateFormat,
                        selectedDate, instance.settings );
            $('#enddate').datepicker( "option", 'minDate', date );
            events.updateHiddenDateTimes();
        });
        $('#enddate').datepicker({ minDate: currentTime,
            dateFormat:'D, d M yy',
            onSelect: function (selectedDate){
                var instance = $( this ).data( "datepicker" );
                var date = $.datepicker.parseDate(
                            instance.settings.dateFormat ||
                            $.datepicker._defaults.dateFormat,
                            selectedDate, instance.settings );

                $('#startdate').datepicker( "option", 'maxDate', date );
                events.updateHiddenDateTimes();
            }
        });
        $('#enddate').change(function() {
            var instance = $( this ).data( "datepicker" );
            var selectedDate = $(this).val();
            var date = $.datepicker.parseDate(
                        instance.settings.dateFormat ||
                        $.datepicker._defaults.dateFormat,
                        selectedDate, instance.settings );
            $('#startdate').datepicker( "option", 'maxDate', date );
            events.updateHiddenDateTimes();
        });

        //Set Initial dates for both the pickers
        $('#startdate').datepicker('setDate', currentTime);
        var preSetEndDateTime = new Date();
        preSetEndDateTime.setHours(currentTime.getHours() + 1);
        $('#enddate').datepicker('setDate', preSetEndDateTime);

        //Selecting all day toggles the time pickers
        $("#allDay").change(function(){
            $('.time-picker').toggle()
        })

        //Instantiate time pickers
        $( "#starttime" ).timepicker({'currentTime':currentTime.getTime(),
                                     'appendTo':$('#starttime').parents('.time-picker')});
        $( "#endtime" ).timepicker({'currentTime':preSetEndDateTime.getTime(),
                                     'appendTo':$('#endtime').parents('.time-picker')});
        $( "#starttime" ).bind( "timepickerselected", function(event, ui) {
            events.setWidgetDateTime('starttime', ui.item.timestamp);
        });
        $( "#endtime" ).bind( "timepickerselected", function(event, ui) {
            events.setWidgetDateTime('endtime', ui.item.timestamp);
        });

        //Set the hidden datetime values
        var seconds = $( "#starttime" ).data('timepicker').parseTimeString($('#starttime-picker').val())
        events.setWidgetDateTime("starttime", seconds);
        var seconds = $( "#endtime" ).data('timepicker').parseTimeString($('#endtime-picker').val())
        events.setWidgetDateTime("endtime", seconds);

    },
    autoFillUsers: function(){
        $('#placeholder-hidden').autoGrowInput({comfortZone: 15, minWidth: 1, maxWidth: 20000});
        $('#event-invitee').tagedit({
            autocompleteURL: '/auto/users',
            additionalListClass: 'sb-inputwrap last',
            breakKeyCodes: [13, 44, 32],
            allowEdit: false,
            allowAdd: false,
            autocompleteOptions: {
                    select: function( event, ui ) {
                            $(this).val(ui.item.value).trigger('transformToTag', [ui.item.uid]);
                            return false;
                    }
            },
            placeHolderWidth: $('#placeholder-hidden').width(),
            maxWidth: 535
        });
    },
    setWidgetDateTime: function(id, seconds) {
        if (id == "starttime") {
            var date = $('#startdate').val();
        }else {
            var date = $('#enddate').val();
        }
        var datestamp = new Date(date);
        datestamp.setHours(0)
        datestamp.setMinutes(0)
        datestamp.setSeconds(0)
        var timestamp = datestamp.getTime()/1000 + parseInt(seconds, 10)
        $((id == 'starttime')?'#startDate':'#endDate').val(timestamp*1000);
    },
    updateHiddenDateTimes: function() {
        var seconds = $( "#endtime" ).data('timepicker').parseTimeString($('#endtime-picker').val())
        events.setWidgetDateTime("endtime", seconds);

        var seconds = $( "#starttime" ).data('timepicker').parseTimeString($('#starttime-picker').val())
        events.setWidgetDateTime("starttime", seconds);
    },
    prepareAgendaDatePicker: function(start_date) {
        var start = new Date(start_date);

        $( "#agenda-start" ).datepicker({
                showOn: "button",
                buttonImage: "rsrcs/img/calendar.gif",
                buttonImageOnly: true,
                dateFormat:'D, d M yy',
                altField: '#agenda-start-date',
                altFormat: 'yy-mm-dd'
        });
        $( "#agenda-start" ).datepicker('setDate', start);
        $('#agenda-start').change(function() {
            var view = $('#agenda-view').val(),
                start = $('#agenda-start-date').val(),
                uri = '/event?start='+start+'&view='+view
            $$.fetchUri(uri);
        });
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



/*
 * User Invite/add/Remove etc
 */
(function($$, $) { if (!$$.users) {
var users = {
    invite: function() {
        var dialogOptions = {
            id: 'invitepeople-dlg',
            buttons: [
                {
                    text:'Invite',
                    click : function() {
                        $('#invite-people-form-submit').trigger('click');
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
        init = function() {
            $('#invite-people-form').html5form({messages: 'en'});
            $('#invite-people').delegate('.form-row:last','focus',function(event){
                $(event.target.parentNode).clone().appendTo('#invite-people').find('input:text').blur();
            });
        };
        var d = $.get('/ajax/people/invite');
        d.then(init);
    },
    add: function() {
        var dialogOptions = {
            id: 'addpeople-dlg',
            buttons: [
                {
                    text:'Add Users',
                    click : function() {
                        var formId = $("#add-user-form-id").val();
                        $('#' + formId + "-submit").trigger('click');
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
        var d = $.get('/ajax/admin/add');
        d.then(function(){
            $('#add-user-form').html5form({messages: 'en'});
            $$.ui.bindFormSubmit('#add-users-form');
        })
    },

    remove: function(userId) {
        var dialogOptions = {
            id: 'removeuser-dlg',
            buttons: [
                {
                    text:'Confirm',
                    click : function() {
                        $.post("/ajax/admin/delete", {id:userId, deleted:'deleted'});
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
        $.get('/ajax/admin/delete?id='+userId);
    }
}
$$.users = users;
}})(social, jQuery);



/*
 * XXX: Temporarily disabled!
 *  Comet Handling.
(function($$, $) { if (!$$.comet) {
var comet = {
    connected: false,

    _connectResponse: function(message) {
        if ($.cometd.isDisconnected()) {
            comet.connected = false;
            $$.publish('cometd.connect.disconnected');
            if (window.console)
                console.log('COMETD Disconnected');
        }
        else {
            var wasConnected = comet.connected;
            comet.connected = message.successful === true;
            if (!wasConnected && comet.connected) {
                $$.publish('cometd.connect.connected');
                if (window.console)
                    console.log('COMETD Connected');
            } else if (wasConnected && !comet.connected) {
                $$.publish('cometd.connect.broken');
                if (window.console)
                    console.log('COMETD Broken');
            }
        }
    },

    _handshakeResponse: function(message) {
        if (message.successful) {
            // Initialized
            // Later, subscribe to /notify/<userId>
        }
    },

    _subscribeResponse: function(message) {
        if (message.channel === "/notify/"+$$.config.myId) {
            if (!message.successful) {
                // Subscription Error
            }
        }
    },

    _inited: false,
    init: function() {
        if (comet._inited)
            return;

        var self = this;
        $.cometd.configure({
            url: $$.config.cometdURL,
            logLevel: 'info'
        });

        $.cometd.addListener('/meta/handshake', self._handshakeResponse);
        $.cometd.addListener('/meta/connect', self._connectResponse);
        $.cometd.addListener('/meta/subscribe', self._subscribeResponse);

        $.cometd.handshake();
        comet._inited = true;
    },

    uninit: function() {
        if (comet._inited)
            $.cometd.reload();
    }
};
$$.comet = comet;
}})(social, jQuery);
 */


/*
 * XXX: Temporarily disabled
 * Instant Messaging
(function($$, $) { if (!$$.chat) {
var chat = {
    user2room: {},  // userId to roomObj
    room2user: {},  //roomId to userId
    rooms: {},      // roomId to roomObj
    users: [],      // Roster - array of user objects
    userMap: {},    // UserId to user object
    status: "offline",
    _subscriptions: [],

    handleMyNotifications: function(message) {
        var messageType = message.data.type;
        if (messageType == "room") {
            // Room related notify is sent only when a new room is being
            // created
            var createdBy = message.data.from,
                roomId = message.data.room,
                userId = message.data.to,
                messageObj = message.data.message,
                roomObj = null;

            if (createdBy == $$.config.myId) {
                // This is a notification about the room that
                // I created. Already have a roomObj but roomId isn't
                // set on it.
                roomObj = chat.user2room[userId];
                roomObj.updateRoom(roomId);

                chat.room2user[roomId] = userId;
                chat.rooms[roomId] = roomObj;
                roomObj.startChat(messageObj);
            } else {
                // I may have chatted with this person in the past,
                // so dig up the roomObj and update the object
                userId = createdBy;
                if (userId in chat.user2room) {
                    roomObj = chat.user2room[userId];
                    roomObj.updateRoom(roomId);
                    chat.rooms[roomId] = roomObj;
                    chat.room2user[roomId] = userId;
                } else {
                    roomObj = new ChatSession(userId);
                    roomObj.updateRoom(roomId);
                    chat.rooms[roomId] = roomObj;
                    chat.room2user[roomId] = userId;
                    chat.user2room[userId] = roomObj;
                }
                roomObj.startChat(messageObj);
            }
        }
    },

    handlePresence: function(message) {
        var userId = message.data.userId;
        chat.userMap[userId] = message.data

        if (userId != $$.config.myId) {
            $$.chatUI.updateRosterList(userId);
            $$.chatUI.updateWindowStatus(userId);
        }
    },

    chatWith: function(userId) {
        if (userId == $$.config.myId)
            return;

        var roomObj;
        if (userId in this.user2room) {
            roomObj = this.user2room[userId];
        } else {
            roomObj = new ChatSession(userId);
            this.user2room[userId] = roomObj;
            // We do not have the roomId so we have nothing to store. The room
            // id is received when the user actually makes the post.
        }

        roomObj.startChat();
    },

    signin: function(status) {
        if (chat.status != "offline" || status == "offline")
            return;

        var d = $.post("/ajax/presence", {"status":status})
        d.then(function() {
            chat.status = status;
            $$.chatUI.updateMyStatus(status);
            $.get("/ajax/presence",
               function(users) {
                    $.each(users, function(idx, user) {
                            var userId = user["userId"],
                                remoteStatus = user["status"];
                            chat.userMap[userId] = user;
                            if (userId in chat.user2room)
                                chat.user2room[userId].updateRemoteStatus(remoteStatus);
                        });
                    chat.users = users;
                    myPresenceSub = $.cometd.subscribe('/presence/'+$$.config.myId, chat.handlePresence);
                    orgPresenceSub = $.cometd.subscribe('/presence/'+$$.config.orgId, chat.handlePresence);
                    notifySub = $.cometd.subscribe('/notify/'+$$.config.myId, chat.handleMyNotifications);

                    chat._subscriptions.push(myPresenceSub);
                    chat._subscriptions.push(orgPresenceSub);
                    chat._subscriptions.push(notifySub);
                    $$.chatUI.updateRosterList();
                }, "json");
        });

        return d;
    },

    signout: function() {
        d = $.post("/ajax/presence", {"status":"offline"});
        d.then(function() {
            $.each(chat._subscriptions, function(idx, subscription) {
                    $.cometd.unsubscribe(subscription);
                });
            chat._subscriptions = [];
            chat.status = "offline";
            $$.chatUI.updateMyStatus("offline");

            chat.users = [];
            chat.userMap = {};
            $$.chatUI.updateRosterList();

            $.each(chat.user2room, function(userId, roomObj) {
                    roomObj.updateLocalStatus('offline');
                });
        });
        return d;
    }
}

function ChatSession(userId) {
    var self = this,
        myId = $$.config.myId;

    this._username = chat.userMap[userId]['name'];
    this._myname = chat.userMap[myId]['name'];
    this._roomSubscriptions = [];
    this.fromId = myId;
    this.toId = userId;
    this.roomId = "";
    this.dialog = null;
    this.remoteUserOffline = false;
    this.localUserOffline = false;
    this._subscribedRoomIds = [];

    this.updateRoom = function(roomId) {
        if (roomId != self.roomId)
            self.roomId = roomId;
    };

    this.send = function(text) {
        if (!text || !text.length) return;

        function _send(data) {
          $.post("/ajax/chat", data, function(response) {}, "json");
        }

        if (self.roomId === "")
            _send({'from': self.fromId, 'to': self.toId, 'message': text});
        else {
            var postData = {'from': self.fromId, 'to': self.toId, 'message': text, 'room': self.roomId}
            if (self._subscribedRoomIds.indexOf(self.roomId) < 0) {
                var listener = $.cometd.addListener('/meta/subscribe', function(message) {
                        if (message.subscription == "/chat/"+self.roomId) {
                            if (message.successful) {
                                _send(postData);
                                $.cometd.removeListener(listener);
                                self._roomSubscriptions.push(subscription);
                                self._subscribedRoomIds.push(self.roomId);
                            } else {
                                // Handle Error
                            }
                        }
                    }),
                    subscription = $.cometd.subscribe('/chat/'+self.roomId, self.receive);
                chat._subscriptions.push(subscription);
            } else {
                _send(postData);
            }
        }
    };

    this.startChat = function(message) {
        if (message != undefined) {
            self.dialog = $$.chatUI.create(self.toId, false);
            $$.chatUI.updateMessage(self.toId, message);
        } else {
            self.dialog = $$.chatUI.create(self.toId, true);
        }

    };

    this.receive = function(message) {
        $$.chatUI.updateMessage(self.toId, message.data);
    };

    this._updateWindowStatus = function() {
        var $template = self.dialog,
            reason = '';

        if (!self.localUserOffline && !self.remoteUserOffline) {
            $('.roster-msg-box', $template).toggleClass('roster-msg-box-show', false);
            $('.roster-chat-input', $template).prop("disabled", false);
        }
        else {
            reason = self.localUserOffline? 'You are currently offline'
                                          : self._username + ' is currently offline';
            $('.roster-chat-input', $template).prop("disabled", true);
            $('.roster-msg-box', $template).html(reason);
            $('.roster-msg-box', $template).toggleClass('roster-msg-box-show', true);
        }
    };

    this.updateRemoteStatus = function(status) {
        self.remoteUserOffline = status === 'offline';
        if (self.dialog)
            $('.roster-chat-status-icon', self.dialog).removeClass($$.chatUI.allClassesString)
                                                      .addClass('roster-status-'+status);
        self._updateWindowStatus();
    };

    this.updateLocalStatus = function(status) {
        if (status === 'offline') {
            self.localUserOffline = true;
            self.unsubscribe();
            self.updateRemoteStatus(status);
        } else {
            self.localUserOffline = false;
            self._updateWindowStatus();
        }
    };

    this.unsubscribe = function() {
        $.each(self._roomSubscriptions, function(i, s) {
                    $.cometd.unsubscribe(s);
                });
        self._subscribedRoomIds = [];
        self._roomSubscriptions = [];
    };
}

$$.chat = chat;
}})(social, jQuery);


(function($$, $) { if (!$$.chatUI) {
var chatUI = {
    _counter: 0,
    _dialogs: {},
    allClassesString: "roster-status-available roster-status-offline roster-status-busy roster-status-away",

    template: '<div class="roster-dlg-outer" tabindex="0">' +
                 '<div class="roster-dlg-inner">' +
                   '<div class="roster-dlg-contents">' +
                       '<div class="roster-dlg-title">' +
                            '<div class="roster-chat-status-icon">&nbsp;</div>'  +
                            '<div class="roster-chat-name"></div>'  +
                            '<div class="roster-chat-actions roster-chat-actions-maximized">' +
                                '<span class="roster-chat-actions-maximize">&#9635;</span>' +
                                '<span class="roster-chat-actions-minimize">_</span>' +
                                '<span class="roster-chat-actions-remove">x</span>' +
                            '</div>'  +
                            '<div class="clear"></div>' +
                        '</div>' +
                       '<div class="roster-dlg-center">'+
                           '<ul class="roster-chat-logs"></ul>' +
                           '<span class="roster-msg-box"></span>' +
                           '<textarea class="roster-chat-input" tabindex="0"></textarea>' +
                       '</div>' +
                 '</div>' +
               '</div>',

    _inited: false,
    init: function() {
        if (chatUI._inited) {
            chatUI.updateMyStatus($$.chat.status);
            chatUI.updateRosterList();
        } else {
            $('#roster-loading').css('display', 'block');
            $('#roster').css('display', 'none');

            // Wait till we are connected to the cometd before enabling chat.
            function chatConnected() {
                if (chatUI._inited) {
                    // When connection to cometd is restored, signin using current status
                    if ($$.chat.status != 'offline') {
                        currentStatus = $$.chat.status;

                        // Set status to offline so signin will actually signin
                        $$.chat.status = 'offline';
                        $$.chat.signin(currentStatus);
                    }

                    $('#roster-error').remove();
                    $('#roster-loading').css('display', 'none');
                    $('#roster').css('display', 'block');
                }
                else {
                    // Use server status to signin
                    statusOnServer = '';
                    d = $.get('/ajax/chat/mystatus', '', function(data) {statusOnServer = data.status}, "json");
                    d.then(function() {
                        var d2 = null;
                        // signout if comet has reloaded or if my status is offline as per server
                        if ($.cometd.isReload() || statusOnServer == 'offline')
                            d2 = $$.chat.signout(false);

                        // signin with previous status
                        if (statusOnServer != 'offline') {
                            if (d2)
                                d2.then(function() { $$.chat.signin(statusOnServer) });
                            else
                                $$.chat.signin(statusOnServer);
                        }

                        $('#roster-error').remove();
                        $('#roster-loading').css('display', 'none');
                        $('#roster').css('display', 'block');
                        chatUI._inited = true;
                    });
                }
            }
            function chatDisconnected() {
                $$.chat.signout(false);
            }
            function chatConnectionBroken() {
                $('<div id="roster-error">Chat servers are currently not reachable</div>').insertBefore('#roster');
                $('#roster').css('display', 'none');
                chatUI.updateMyStatus('offline');
            }

            if ($$.comet.connected)
                chatConnected();

            $$.subscribe('cometd.connect.connected', chatConnected);
            $$.subscribe('cometd.connect.broken', chatConnectionBroken);
            $$.subscribe('cometd.connect.disconnected', chatDisconnected);
        }
    },

    create: function(userId, focus) {
        var $template,
            dlgId = "chat-" + userId,
            self = this;

        if (chatUI._dialogs[dlgId]) {
            $template = chatUI._dialogs[dlgId];
            $('.roster-chat-name', $template).html($$.chat.userMap[userId]['name']);
            $template.show();
        } else {
            $template = $(this.template);
            $template.attr('id', dlgId + '-outer').attr('dlgId', dlgId);
            $('.roster-dlg-inner', $template).attr('id', dlgId + '-inner');
            $('.roster-dlg-contents', $template).attr('id', dlgId);
            $('.roster-dlg-title', $template).attr('id', dlgId + '-title');
            $('.roster-chat-logs', $template).attr('id', dlgId + '-logs');
            $('.roster-chat-name', $template).html($$.chat.userMap[userId]['name']);

            $template.keydown(function(event) {
                if (event.which == 27) {
                    self.close($template, true);
                }
            });

            $('.roster-chat-actions-remove', $template).click(function() {
                self.close($template, true);
            })

            $('.roster-chat-actions-minimize', $template).click(function() {
                $('.roster-dlg-center', $template).toggle();
                $('.roster-chat-actions', $template).removeClass('roster-chat-actions-maximized');
                $('.roster-chat-actions', $template).addClass('roster-chat-actions-minimized');
            })

            $('.roster-chat-actions-maximize', $template).click(function() {
                $('.roster-dlg-center', $template).toggle();
                $('.roster-chat-actions', $template).removeClass('roster-chat-actions-minimized');
                $('.roster-chat-actions', $template).addClass('roster-chat-actions-maximized');
            })

            $('.roster-chat-input', $template).keydown(function(e) {
                if (e.keyCode == 13) {
                    var roomObj = $$.chat.user2room[userId],
                        text = $(this).val();
                    $(this).val('');
                    roomObj.send(text);
                    e.preventDefault();
                    return false;
                }
            });

            chatUI._dialogs[dlgId] = $template;
            $template.appendTo('body');
            $template.css('z-index', 5000+chatUI._counter)

            var right = 230*chatUI._counter;
            $('#'+dlgId+'-outer').css({left: '', right: right+"px", bottom: 0})
            chatUI._counter += 1;
        }

        this.updateWindowStatus(userId);
        if (focus)
            $('.roster-chat-input', $template).focus();

        return $template;
    },

    close: function(dlg, destroy) {
        var $dialog, id;
        if (typeof dlg == "string") {
            $dialog = chatUI._dialogs[dlg];
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
            chatUI._counter -= 1;
            delete chatUI._dialogs[id];
        }
    },

    closeAll: function() {
        $.each(chatUI._dialogs, function(key, value) {
            value.hide();
            value.remove();
        });
        chatUI._dialogs = {};
        chatUI._counter = 0;
    },

    updateMessage: function(dlgId, message) {
        chatUI.create(dlgId, false);  // Show the dialog, if not already visible.

        var timestamp = new Date(parseInt(message.timestamp)*1000),
            hours = timestamp.getHours(),
            AMPM = hours > 12 ? "PM" : "AM",
            minutes = timestamp.getMinutes(),
            minuteString = minutes < 10 ? "0"+minutes : minutes,
            dateString = '';

        hours = hours > 12 ?  hours-12: hours;
        dateString = hours + ":" + minuteString + " " + AMPM;

        var ul = $("#chat-"+dlgId+"-outer .roster-chat-logs"),
            tmpl = '<li class="chat-message-' + message.from + '"><div class="chat-avatar-wrapper">'+
                    '<img src="' + message.avatar + '"/></div>' +
                    '<div class="chat-message-wrapper">' +
                        '<div class="chat-message-from">' + message.from +
                        '</div><div class="chat-message">' + message.message +
                   '</div></div><div><abbr class="chat-message-time"' + message.timestamp + '">' +
                   dateString + '</abbr></div><div class="clear"></div></li>',
            ulHeight = ul.prop('scrollHeight');

        $(tmpl).appendTo(ul);
        ul.scrollTop(ulHeight);
    },

    updateRosterList: function() {
        // {"userId": userId, 'status': status, 'name': name, 'avatar': 'avatar'}
        var tmpl = '<div class="roster-item">' +
                     '<div class="roster-item-icon">' +
                       '<div class="roster-icon-holder">' +
                         '<img class="roster-avatar"/>' +
                       '</div>' +
                     '</div>' +
                     '<div class="roster-item-name"></div>' +
                     '<div class="roster-item-title"></div>' +
                     '<div class="icon roster-status-icon ">&nbsp;</div>' +
                     '<div class="clear"></div>' +
                   '</div>',
            allUsers = [],
            orderedStatuses = ["available", "busy", "away", "x-away"];

        $.each($$.chat.userMap, function(key, user) {
            if (key == $$.config.myId || user.status == "offline")
                return
            allUsers.push([key, user]);
        });
        allUsers.sort(function(a, b) {
            var userA = a[1], userB = b[1];
            if (userA.status == userB.status)
                return userA.name > userB.name;
            return orderedStatuses.indexOf(userA.status) > orderedStatuses.indexOf(userB.status);
        });

        $("#roster-container .roster-list").empty();
        $.each(allUsers, function(idx, userIdAndUser) {
            var $tmpl = $(tmpl),
                userId = userIdAndUser[0],
                user = userIdAndUser[1];
            $('.roster-item', $tmpl).attr('id', 'user-'+userId);
            $('.roster-avatar', $tmpl).attr('src', user.avatar);
            $('.roster-item-name', $tmpl).html(user.name);
            $('.roster-item-title', $tmpl).html(user.title);
            $('.roster-status-icon', $tmpl).addClass('roster-status-'+user.status);
            $("#roster-container .roster-list").append($tmpl);
            $tmpl.click(function() {
                $$.chat.chatWith(userId);
            });
        });
    },

    updateMyStatus: function(status) {
        $("#user-online-status-icon").attr("src", "/rsrcs/img/"+status+".png");
        $("#user-online-status-text").html(status);

        // Update status on any existing sessions
        $.each($$.chat.user2room, function(i, r) {
                r.updateLocalStatus(status);
            });
    },

    updateWindowStatus: function(userId) {
        roomObj = $$.chat.user2room[userId];
        if (roomObj)
            roomObj.updateRemoteStatus($$.chat.userMap[userId]['status']);
    },

    setStatus: function(status) {
        if ($$.chat.status !== "offline") {
            $$.chat.status = status;
            var d = $.post("/ajax/presence", {"status":status});
            d.then(function() {
                chatUI.updateMyStatus(status);
            })
        } else {
            $$.chat.signin(status)
        }
    },

    showStatusList: function(event, id) {
        var evt = $.event.fix(event),
            $target = $("#" + id + "-button"),
            $menu = $target.next()

        if (!$menu.hasClass("ui-menu")) {
            $menu.menu().css("z-index", 2000);
        }

        $menu.show().position({
                my: "left top",
                at: "left bottom",
                offset: "-3 0",
                of: $target
            }).focus();

        $(document).one("click", function() {$menu.hide();});
        evt.stopPropagation();
        evt.preventDefault();
    }
}
$$.chatUI = chatUI;
}})(social, jQuery);
 */
