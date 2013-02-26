function addCommas(nStr) // to show clean number format for "people learning right now" -- no built in JS function
{
    nStr += "";
    var x = nStr.split(".");
    var x1 = x[0];
    var x2 = x.length > 1 ? "." + x[1] : "";
    var rgx = /(\d+)(\d{3})/;
    while (rgx.test(x1)) {
        x1 = x1.replace(rgx, "$1" + "," + "$2");
    }
    return x1 + x2;
}

function validateEmail(sEmail) {
    var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return sEmail.match(re);
}

function addAutocompleteMatchToList(list, match, kind, reMatch, first) {
    var o = {
        "label":(kind == 'exercise') ? match.display_name : match.title,
        "title":(kind == 'exercise') ? match.display_name : match.title,
        "value":match.topic_url || match.relative_url || match.ka_url,
        "key":match.key,
        "kind":kind,
        "firstOfItsKind":first
    };
    if (reMatch)
        o.label = o.label.replace(reMatch, "<b>$1</b>");

    list[list.length] = o;
}

function initAutocomplete(selector, fTopics, fxnSelect, fIgnoreSubmitOnEnter, options) {
    options = $.extend({
        includeVideos:true,
        includeExercises:true,
        addTypePrefix:true
    }, options);
    var autocompleteWidget = $(selector).autocomplete({
        delay:150,
        source:function (req, fxnCallback) {

            var term = $.trim(req.term);
            if (!term) {
                fxnCallback([]);
                return;
            }

            // Get autocomplete matches
            $.getJSON("/api/v1/autocomplete", {"q":term}, function (data) {

                var matches = [];

                if (data != null) {
                    var reMatch = null;

                    // Try to find the "scent" of the match.  If regexp fails
                    // to compile for any input reason, ignore.
                    try {
                        reMatch = new RegExp("(" + data.query + ")", "i");
                    }
                    catch (e) {
                        reMatch = null;
                    }

                    // Add topic and video matches to list of autocomplete suggestions
                    // For the first of each kind, set firstOfItsKind to true

                    if (fTopics) {
                        for (var ix = 0; ix < data.topics.length; ix++) {
                            addAutocompleteMatchToList(matches, data.topics[ix], "topic", reMatch, ix == 0);
                        }
                    }
                    if (options.includeVideos) {
                        for (var ix = 0; ix < data.videos.length; ix++) {
                            addAutocompleteMatchToList(matches, data.videos[ix], "video", reMatch, ix == 0);
                        }
                    }
                    if (options.includeExercises) {
                        for (var ix = 0; ix < data.exercises.length; ix++) {
                            addAutocompleteMatchToList(matches, data.exercises[ix], "exercise", reMatch, ix == 0);
                        }
                    }
                }
                fxnCallback(matches);

            });
        },
        focus:function () {
            return false;
        },
        select:function (e, ui) {
            if (fxnSelect)
                fxnSelect(ui.item);
            else
                window.location = ui.item.value;
            return false;
        },
        open:function (e, ui) {
            var jelMenu = $(autocompleteWidget.data("autocomplete").menu.element);
            var jelInput = $(this);

            var pxRightMenu = jelMenu.offset().right + jelMenu.outerWidth();
            var pxRightInput = jelInput.offset().right + jelInput.outerWidth();

            if (pxRightMenu > pxRightInput) {
                // Keep right side of search input and autocomplete menu aligned
                jelMenu.offset({
                    right:pxRightInput - jelMenu.outerWidth(),
                    top:jelMenu.offset().top
                });
            }
        }
    }).bind("keydown.autocomplete", function (e) {
            if (!fIgnoreSubmitOnEnter && e.keyCode == $.ui.keyCode.ENTER || e.keyCode == $.ui.keyCode.NUMPAD_ENTER) {
                if (!autocompleteWidget.data("autocomplete").selectedItem) {
                    // If enter is pressed and no item is selected, default autocomplete behavior
                    // is to do nothing.  We don't want this behavior, we want to fall back to search.
                    $(this.form).submit();
                }
            }
        });

    autocompleteWidget.data("autocomplete")._renderItem = function (ul, item) {
        // Customize the display of autocomplete suggestions
        var jLink = $("<a></a>").html(item.label);
        var spacerNode = $("<div class='autocomplete-spacer'><span class='autocomplete-empty'>&nbsp;</span></div>");

        if (options.addTypePrefix) {
            var prefixSpan = $("<span class='autocomplete-type'>&nbsp;</span>").prependTo(jLink);
            // Apply a label only to the first appearance of a given type and add some space to separate types
            if (item.firstOfItsKind) {
                prefixSpan.html(item.kind);
                jLink = jLink.addClass("autocomplete-first-" + item.kind).before(spacerNode);
            }
        }

        jLink.find("a").attr("data-tag", "Autocomplete");

        return $("<li></li>")
            .data("item.autocomplete", item)
            .append(jLink)
            .appendTo(ul);
    };

    autocompleteWidget.data("autocomplete").menu.select = function (e) {
        // jquery-ui.js's ui.autocomplete widget relies on an implementation of ui.menu
        // that is overridden by our jquery.ui.menu.js.  We need to trigger "selected"
        // here for this specific autocomplete box, not "select."
        this._trigger("selected", e, { item:this.active });
    };
}

$(function () {
    // Configure the search form
    if ($(".page-search input[type=text]").placeholder().length) {
        initAutocomplete(".page-search input[type=text]", true);
    }

    $(".page-search").submit(function (e) {
        // Only allow submission if there is a non-empty query.
        return !!$.trim($(this).find("input[type=text]").val());
    });

    // On any update to the user's nickname/points/badge area,
    // reinitialize the user dropdown.
    $("#user-info").on("userUpdate",function () {

        $(this).find(".dropdown-toggle")
            .dropdown(
            // Config dropdown on click for mobile, hover otherwise
            KA.isMobileCapable ? null : "hover"
        );

    }).trigger("userUpdate");
});

var Badges = {
    /**
     * Create, render, and animate the notification for badges earned
     *
     * @param {Object} data
     */
    show:function (data) {
        if (this.badgesEarnedView == null) {
            this.badgesEarned = new Backbone.Collection(data.badges);
            this.badgesEarnedView = new Badges.Notifications({
                model:this.badgesEarned
            });
            $('body').append(this.badgesEarnedView.el);
        } else {
            this.badgesEarned.reset(data.badges);
        }

        this.badgesEarnedView.show();
    },

    showMoreContext:function (el) {
        var jelLink = $(el).parents(".badge-context-hidden-link");
        var jelBadge = jelLink.parents(".achievement-badge");
        var jelContext = $(".badge-context-hidden", jelBadge);

        if (jelLink.length && jelBadge.length && jelContext.length) {
            $(".ellipsis", jelLink).remove();
            jelLink.html(jelLink.text());
            jelContext.css("display", "");
            jelBadge.find(".achievement-desc").addClass("expanded");
            jelBadge.css("min-height", jelBadge.css("height")).css("height", "auto");
            jelBadge.nextAll(".achievement-badge").first().css("clear", "both");
        }
    }

};

/**
 * This view renders a badge notification, and attaches subviews for every
 * .share-links present. Note that this view handles rendering of the subviews;
 * the subviews attach to existing DOM elements and exist purely for
 * encapsulating the share logic and qtip UI.
 */
Badges.Notifications = Backbone.View.extend({
    template:Templates.get("shared.badge-notifications"),

    className:"badge-award-container",

    // TODO(stephanie): use ".share-email" instead of .emailShare
    events:{
        "click .hide-badge":"hide"
    },

    initialize:function () {
        this.render();

        this.model.bind('reset', this.render, this);
    },

    templateJSON:function () {
        return this.model.map(function (badge) {
            return Badges.ShareLinksView.addShareLinks(badge.toJSON());
        }, this);
    },

    render:function () {
        _.each(this.subviews, function (v) {
            v.undelegateEvents();
        });
        this.subviews = [];
        this.$el.html(this.template(this.templateJSON()));
        this.$el.css("display", "none");
        this.$(".timeago").timeago();

        // attach subviews
        this.subviews = _.map(this.$(".share-links"), function (el, i) {
            return new Badges.ShareLinksView({
                el:el,
                model:this.model.at(i)
            });
        }, this);
    },

    show:function () {
        this.render();
        // TODO(stephanie): link .achievement-badge to badge page using KA.getUserProfile().get("profileRoot") + "achievements"

        // todo(dmnd) what is the purpose of this 100ms delay?
        setTimeout(_.bind(this.animate, this), 100);
    },

    animate:function () {

        // TODO(stephanie): remove global references
        var $elContainer = $("#page-container-inner");
        var $elTarget = $(".badge-target");
        var top = $elTarget.offset().top + $elTarget.height() + 5;

        this.$el.css("visibility", "hidden").css("display", "");
        this.$el.css("left", $elContainer.offset().left + ($elContainer.width() / 2) - (this.$el.width() / 2)).css("top", -1 * this.$el.height());
        var topBounce = top + 10;
        this.$el.css("display", "").css("visibility", "visible");
        this.$el.animate({top:topBounce}, 300, _.bind(function () {
            this.$el.animate({top:top}, 100);
        }, this));
    },

    hide:function (e) {
        this.$el.animate({top:-1 * this.$el.outerHeight() - 10}, 300,
            'easeInOutCubic');
        _.each(this.subviews, function (v) {
            v.hide();
        });
    }
});

/**
 * This view represents the actual share links that appear on a
 * Badge.Notifications and inside activity views on the profile page.
 */
Badges.ShareLinksView = Backbone.View.extend({
    template:Templates.get("shared.share-links"),

    events:{
        "click .emailShare":"shareEmail",
        "click .twitterShare":"shareTwitter",
        "click .facebookShare":"shareFacebook"
    },

    /**
     * Use Google analytics and Mixpanel to track badge shares
     * @param {string} action How the badge was shared (ex: "Share Twitter")
     */
    trackShare:function (action) {
        var description = this.model.get("description");
        var badgeCategory = this.model.get("badgeCategory");
        if (window._gaq) {
            // syntax:["_trackEvent", category, action, label, value]
            _gaq.push(["_trackEvent", "Badges", action, description,
                badgeCategory]);
        }
        // Using Mixpanel to track share
        var analyticsParams = {};
        analyticsParams["Description"] = description;
        analyticsParams["Badge Category"] = badgeCategory;
        analyticsParams["Name"] = this.model.get("name");
        analyticsParams["Points"] = this.model.get("points");

        Analytics.trackSingleEvent("Badges " + action, analyticsParams);
    },

    shareEmail:function (e) {
        this.trackShare("Share Email");
    },

    shareTwitter:function (e) {
        this.trackShare("Share Twitter");
    },

    shareFacebook:function (e) {
        if (!window.FB) {
            // if Facebook isn't loaded, ignore
            KAConsole.log("Ignored button click as window.FB not present.");
            return;
        }

        // if the button has already been pressed, ignore
        if (this.alreadySharedOnFacebook) {
            KAConsole.log("Ignored duplicate share attempt.");
            return;
        }

        // users are not allowed to share without a Khan Academy account
        if (!window.USERNAME) {
            // prompt phantom user to log in or sign up
            this.showQTip("<a href='/login?continue=/profile' class='simple-button qtip-button green'>Log in</a> to claim your badge on Facebook.");
            return;
        }

        // find out which badge to share
        var badge = this.model;
        var badgeSlug = badge.get("slug");

        // if the user is logged in via Facebook
        var isUsingFbLogin = window.USERNAME && FacebookUtil.isUsingFbLogin();

        // if user is logged in through Facebook and the cookie indicates
        // they have granted publish_stream permission, try to publish a
        // custom OpenGraph "earn badge" action to user's Facebook Timeline
        if (isUsingFbLogin && FacebookUtil.hasPublishStreamPermission()) {
            this.openGraphShare(badgeSlug);

        } else {

            // attempt to log in to prompt user for publish_stream permission.
            // use _.bind to ensure that 'this' is set to the right context
            // when the callback is executed.
            FB.login(_.bind(function (response) {
                // TODO(stephanie): refactor out this redundant error checking
                if (!response || response.error || !response.authResponse) {
                    var code = response && response.error ?
                        response.error.code : null;
                    this.handleFacebookErrors(code);

                } else if (response) {

                    // check the permissions to see if the user granted it
                    FB.api("/me/permissions", "get", _.bind(function (response) {

                        if (!response || response.error) {
                            var code = response && response.error ?
                                response.error.code : null;
                            this.handleFacebookErrors(code);

                        } else {

                            var permissionGranted = response.data && response.data[0] && response.data[0].publish_stream === 1;
                            if (permissionGranted) {

                                FacebookUtil.setPublishStreamPermission(true);
                                // need to bind 'this' to the right context
                                this.openGraphShare(badgeSlug);

                                // permission was not granted
                            } else {

                                FacebookUtil.setPublishStreamPermission(false);

                                // TODO: bundle this into handleErrors?
                                this.showQTip("Sorry, je moet toestemming geven om dit op Facebook te delen. Probeer nogmaals.");
                                KAConsole.log("FB OpenGraph badge share failed - permission denied.");
                            }
                        }

                    }, this));

                }
            }, this), {"scope":"email,publish_stream"});
        }
    },

    handleFacebookErrors:function (code) {
        // permission denied error
        if (code === 200) {
            FacebookUtil.setPublishStreamPermission(false);
            this.showQTip("Sorry, je moet toestemming geven om dit op Facebook te delen. Probeer nogmaals.");

            // duplicate OG post error
        } else if (code === 3501) {
            this.setShared("Deze badge staat al op je tijdlijn.");

            // TODO: find out other error codes
        } else {
            this.showQTip("Sorry, we konden dit niet delen. Probeer het nogmaals.");
        }
    },

    handleErrors:function (jqXHR) {
        var msg = jqXHR.responseText;
        var status = jqXHR.status;
        KAConsole.log(msg);

        // Khan Academy permission error
        if (status === 401) {
            this.showQTip("Sorry, badges die je nog niet hebt behaald kun je ook niet delen.");
            return;

            // Open Graph error
        } else if (status === 400) {

            var re = /(#)(\d+)/;
            var matches = re.exec(msg);

            if (matches) {
                var code = matches[2];
                this.handleFacebookErrors(parseInt(code));
                return;
            }
        }
        this.showQTip("Sorry, we konden dit niet delen. Probeer het nogmaals.");
    },

    /**
     * Send request to Khan Academy API to publish an Open Graph "earn" action.
     */
    openGraphShare:function (badgeSlug) {
        this.showQTip("<img src='/images/spinner-arrows-bg-1c1c1c.gif' style='margin-right: 5px; position: relative; top: 1px'> Sharing on Facebook...", true);
        $.ajax({
            type:"POST",
            url:"/api/v1/user/badges/" + badgeSlug + "/opengraph-earn",
            success:_.bind(this.finishShare, this),
            error:_.bind(this.handleErrors, this)
        });
    },

    setShared:function (message) {
        this.alreadySharedOnFacebook = true;
        this.$(".facebookShare").contents().last().replaceWith("Shared");
        this.showQTip(message);
    },

    finishShare:function () {
        this.setShared("Deze badge zal nu op je tijdlijn verschijnen!");
        this.trackShare("Share Facebook Open Graph");
        KAConsole.log("OG post succeeded!");
    },

    /** Shows a qtip notification indicating that sharing has succeeded. */
    showQTip:function (message, disableHide) {
        var $fbButton = this.$(".facebookShare");

        var options = {
            content:message,
            position:{
                my:"left bottom",
                at:"top right"
            },
            show:{
                ready:true
            },
            style:'ui-tooltip-shadow ui-tooltip-rounded ui-tooltip-youtube',
            hide:{
                delay:5000
            },
            events:{
                // remove the delay the first time the tooltip is hidden
                hidden:_.bind(this.removeHideDelay, this)
            }
        };

        if (disableHide) {
            options.hide = false;
            delete options.events;
        } else {
            // after 2s remove the delay - it's been on the screen long enough
            // at this point.
            setTimeout(_.bind(function () {
                this.hide();
                this.removeHideDelay();
            }, this), 5000);
        }

        this.$(".facebookShare").qtip(options);
    },

    removeHideDelay:function () {
        this.$(".facebookShare").qtip('api').set('hide.delay', 0);
    },

    hide:function () {
        var api = this.$(".facebookShare").qtip('api');
        if (api) {
            api.hide();
        }
    }
}, {
    /** Extends the badge object with email and twitter share links. */
    addShareLinks:function (badgeObject) {
        var url = badgeObject.absoluteUrl;
        var desc = badgeObject.description;
        badgeObject.emailLink = Social.emailBadge(url, desc);
        badgeObject.twitterLink = Social.twitterBadge(url, desc);
        return badgeObject;
    }
});

var Notifications = {

    show:function (sNotificationContainerHtml) {
        var jel = $(".notification-bar");

        if (sNotificationContainerHtml) {
            var jelNew = $(sNotificationContainerHtml);
            jel.empty().append(jelNew.children());
        }

        $(".notification-bar-close a").click(function () {
            Notifications.hide();
            return false;
        });

        if (!jel.is(":visible")) {
            setTimeout(function () {

                jel
                    .css("visibility", "hidden")
                    .css("display", "")
                    .css("top", -jel.height() - 2)// 2 for border and outline
                    .css("visibility", "visible");

                // Queue:false to make sure all of these run at the same time
                var animationOptions = {duration:350, queue:false};

                $(".notification-bar-spacer").animate({ height:35 }, animationOptions);
                jel.show().animate({ top:0 }, animationOptions);

            }, 100);
        }
    },
    showTemplate:function (templateName) {
        var template = Templates.get(templateName);
        this.show(template());
    },

    hide:function () {
        var jel = $(".notification-bar");

        // Queue:false to make sure all of these run at the same time
        var animationOptions = {duration:350, queue:false};

        $(".notification-bar-spacer").animate({ height:0 }, animationOptions);
        jel.animate(
            { top:-jel.height() - 2 }, // 2 for border and outline
            $.extend({}, animationOptions,
                { complete:function () {
                    jel.empty().css("display", "none");
                } }
            )
        );

        $.post("/notifierclose");
    }
};

var DemoNotifications = { // for demo-notification-bar (brown and orange, which informs to logout after demo

    show:function (sNotificationContainerHtml) {
        var jel = $(".demo-notification-bar");

        if (sNotificationContainerHtml) {
            var jelNew = $(sNotificationContainerHtml);
            jel.empty().append(jelNew.children());
        }

        if (!jel.is(":visible")) {
            setTimeout(function () {

                jel
                    .css("visibility", "hidden")
                    .css("display", "")
                    .css("top", -jel.height() - 2)// 2 for border and outline
                    .css("visibility", "visible");

                // Queue:false to make sure all of these run at the same time
                var animationOptions = {duration:350, queue:false};

                $(".notification-bar-spacer").animate({ height:35 }, animationOptions);
                jel.show().animate({ top:0 }, animationOptions);

            }, 100);
        }
    }
};

var Timezone = {
    tz_offset:null,

    append_tz_offset_query_param:function (href) {
        if (href.indexOf("?") > -1)
            href += "&";
        else
            href += "?";
        return href + "tz_offset=" + Timezone.get_tz_offset();
    },

    get_tz_offset:function () {
        if (this.tz_offset == null)
            this.tz_offset = -1 * (new Date()).getTimezoneOffset();
        return this.tz_offset;
    }
};

// not every browser has Date.prototype.toISOString
// https://developer.mozilla.org/en/JavaScript/Reference/Global_Objects/Date#Example.3a_ISO_8601_formatted_dates
if (!Date.prototype.toISOString) {
    Date.prototype.toISOString = function () {
        var pad = function (n) {
            return n < 10 ? "0" + n : n;
        };
        return this.getUTCFullYear() + "-" +
            pad(this.getUTCMonth() + 1) + "-" +
            pad(this.getUTCDate()) + "T" +
            pad(this.getUTCHours()) + ":" +
            pad(this.getUTCMinutes()) + ":" +
            pad(this.getUTCSeconds()) + "Z";
    };
}

// some browsers can't parse ISO 8601 with Date.parse
// http://anentropic.wordpress.com/2009/06/25/javascript-iso8601-parser-and-pretty-dates/
var parseISO8601 = function (str) {
    // we assume str is a UTC date ending in 'Z'
    var parts = str.split("T"),
        dateParts = parts[0].split("-"),
        timeParts = parts[1].split("Z"),
        timeSubParts = timeParts[0].split(":"),
        timeSecParts = timeSubParts[2].split("."),
        timeHours = Number(timeSubParts[0]),
        _date = new Date();

    _date.setUTCFullYear(Number(dateParts[0]));
    _date.setUTCMonth(Number(dateParts[1]) - 1);
    _date.setUTCDate(Number(dateParts[2]));
    _date.setUTCHours(Number(timeHours));
    _date.setUTCMinutes(Number(timeSubParts[1]));
    _date.setUTCSeconds(Number(timeSecParts[0]));
    if (timeSecParts[1]) {
        _date.setUTCMilliseconds(Number(timeSecParts[1]));
    }

    // by using setUTC methods the date has already been converted to local time(?)
    return _date;
};

var MailingList = {
    init:function (sIdList) {
        var jelMailingListContainer = $("#mailing_list_container_" + sIdList);
        var jelMailingList = $("form", jelMailingListContainer);
        var jelEmail = $(".email", jelMailingList);

        jelEmail.placeholder().change(function () {
            $(".error", jelMailingListContainer).css("display", (!$(this).val() || validateEmail($(this).val())) ? "none" : "");
        }).keypress(function () {
                if ($(".error", jelMailingListContainer).is(":visible") && validateEmail($(this).val()))
                    $(".error", jelMailingListContainer).css("display", "none");
            });

        jelMailingList.submit(function (e) {
            if (validateEmail(jelEmail.val())) {
                $.post("/mailing-lists/subscribe", {list_id:sIdList, email:jelEmail.val()});
                jelMailingListContainer.html("<p>Klaar!</p>");
            }
            e.preventDefault();
            return false;
        });
    }
};

var CSSMenus = {

    active_menu:null,

    init:function () {
        // Make the CSS-only menus click-activated
        $(".noscript").removeClass("noscript");
        $(document).delegate(".css-menu > ul > li", "click", function () {
            if (CSSMenus.active_menu)
                CSSMenus.active_menu.removeClass("css-menu-js-hover");

            if (CSSMenus.active_menu && this == CSSMenus.active_menu[0])
                CSSMenus.active_menu = null;
            else
                CSSMenus.active_menu = $(this).addClass("css-menu-js-hover");
        });

        $(document).bind("click focusin", function (e) {
            if (CSSMenus.active_menu &&
                $(e.target).closest(".css-menu").length === 0) {
                CSSMenus.active_menu.removeClass("css-menu-js-hover");
                CSSMenus.active_menu = null;
            }
        });

        // Make the CSS-only menus keyboard-accessible
        $(document).delegate(".css-menu a", {
            focus:function (e) {
                $(e.target)
                    .addClass("css-menu-js-hover")
                    .closest(".css-menu > ul > li")
                    .addClass("css-menu-js-hover");
            },
            blur:function (e) {
                $(e.target)
                    .removeClass("css-menu-js-hover")
                    .closest(".css-menu > ul > li")
                    .removeClass("css-menu-js-hover");
            }
        });
    }
};
$(CSSMenus.init);

var IEHtml5 = {
    init:function () {
        // Create a dummy version of each HTML5 element we use so that IE 6-8 can style them.
        var html5elements = ["header", "footer", "nav", "article", "section", "menu"];
        for (var i = 0; i < html5elements.length; i++) {
            document.createElement(html5elements[i]);
        }
    }
};
IEHtml5.init();

var VideoViews = {
    init:function () {
        // Fit calculated early Feb 2012
        var estimatedTotalViews = -4.792993409561827e9 + 3.6966675231488018e-3 * (+new Date());

        var totalViewsString = addCommas("" + Math.round(estimatedTotalViews));

        $("#page_num_visitors").append(totalViewsString);
        $("#page_visitors").css("display", "inline");
    }
};
$(VideoViews.init);


var Throbber = {
    jElement:null,

    show:function (jTarget, fOnLeft) {
        if (!Throbber.jElement) {
            Throbber.jElement = $("<img style='display:none;' src='/images/throbber.gif' class='throbber'/>");
            $(document.body).append(Throbber.jElement);
        }

        if (!jTarget.length) return;

        var offset = jTarget.offset();

        var top = offset.top + (jTarget.height() / 2) - 8;
        var left = fOnLeft ? (offset.left - 16 - 4) : (offset.left + jTarget.width() + 4);

        Throbber.jElement.css("top", top).css("left", left).css("display", "");
    },

    hide:function () {
        if (Throbber.jElement) Throbber.jElement.css("display", "none");
    }
};

var SearchResultHighlight = {
    doReplace:function (word, element) {
        // Find all text elements
        textElements = $(element).contents().filter(function () {
            return this.nodeType != 1;
        });
        textElements.each(function (index, textElement) {
            var pos = textElement.data.toLowerCase().indexOf(word);
            if (pos >= 0) {
                // Split text element into three elements
                var highlightText = textElement.splitText(pos);
                highlightText.splitText(word.length);

                // Highlight the matching text
                $(highlightText).wrap('<span class="highlighted" />');
            }
        });
    },
    highlight:function (query) {
        $(".searchresulthighlight").each(function (index, element) {
            SearchResultHighlight.doReplace(query, element);
        });
    }
};

// This function detaches the passed in jQuery element and returns a function that re-attaches it
function temporaryDetachElement(element, fn, context) {
    var el, reattach;
    el = element.next();
    if (el.length > 0) {
        // This element belongs before some other element
        reattach = function () {
            element.insertBefore(el);
        };
    } else {
        // This element belongs at the end of the parent's child list
        el = element.parent();
        reattach = function () {
            element.appendTo(el);
        };
    }
    element.detach();
    var val = fn.call(context || this, element);
    reattach();
    return val;
}

var globalPopupDialog = {
    visible:false,
    bindings:false,

    // Size can be an array [width,height] to have an auto-centered dialog or null if the positioning is handled in CSS
    show:function (className, size, title, html, autoClose) {
        var css = (!size) ? {} : {
            position:"relative",
            width:size[0],
            height:size[1],
            marginLeft:(-0.5 * size[0]).toFixed(0),
            marginTop:(-0.5 * size[1] - 100).toFixed(0)
        }
        $("#popup-dialog")
            .hide()
            .find(".dialog-frame")
            .attr("class", "dialog-frame " + className)
            .attr('style', '')// clear style
            .css(css)
            .find(".description")
            .html('<h3>' + title + '</h3>')
            .end()
            .end()
            .find(".dialog-contents")
            .html(html)
            .end()
            .find(".close-button")
            .click(function () {
                globalPopupDialog.hide();
            })
            .end()
            .show()

        if (autoClose && !globalPopupDialog.bindings) {
            // listen for escape key
            $(document).bind('keyup.popupdialog', function (e) {
                if (e.which == 27) {
                    globalPopupDialog.hide();
                }
            });

            // close the goal dialog if user clicks elsewhere on page
            $('body').bind('click.popupdialog', function (e) {
                if ($(e.target).closest('.dialog-frame').length === 0) {
                    globalPopupDialog.hide();
                }
            });
            globalPopupDialog.bindings = true;
        } else if (!autoClose && globalPopupDialog.bindings) {
            $(document).unbind('keyup.popupdialog');
            $('body').unbind('click.popupdialog');
            globalPopupDialog.bindings = false;
        }

        globalPopupDialog.visible = true;
        return globalPopupDialog;
    },
    hide:function () {
        if (globalPopupDialog.visible) {
            $("#popup-dialog")
                .hide()
                .find(".dialog-contents")
                .html('');

            if (globalPopupDialog.bindings) {
                $(document).unbind('keyup.popupdialog');
                $('body').unbind('click.popupdialog');
                globalPopupDialog.bindings = false;
            }

            globalPopupDialog.visible = false;
        }
        return globalPopupDialog;
    }
};

(function () {
    var messageBox = null;

    popupGenericMessageBox = function (options) {
        if (messageBox) {
            $(messageBox).modal('hide').remove();
        }

        options = _.extend({
            buttons:[
                { title:'OK', action:hideGenericMessageBox }
            ]
        }, options);

        var template = Templates.get("shared.generic-dialog");
        messageBox = $(template(options)).appendTo(document.body).modal({
            keyboard:true,
            backdrop:true,
            show:true
        }).get(0);

        _.each(options.buttons, function (button) {
            $('.generic-button[data-id="' + button.title + '"]', $(messageBox)).click(button.action);
        });
    }

    hideGenericMessageBox = function () {
        if (messageBox) {
            $(messageBox).modal('hide');
        }
        messageBox = null;
    }
})();

function dynamicPackage(packageName, callback, manifest) {
    var self = this;
    this.files = [];
    this.progress = 0;
    this.last_progress = 0;

    dynamicPackageLoader.loadingPackages[packageName] = this;
    _.each(manifest, function (filename) {
        var file = {
            "filename":filename,
            "content":null,
            "evaled":false
        };
        self.files.push(file);
        $.ajax({
            type:"GET",
            url:filename,
            data:null,
            success:function (content) {
                KAConsole.log("Received contents of " + filename);
                file.content = content;

                self.progress++;
                callback("progress", self.progress / (2 * self.files.length));
                self.last_progress = self.progress;
            },
            error:function (xml, status, e) {
                callback("failed");
            },
            dataType:"html"
        });
    });

    this.checkComplete = function () {
        var waiting = false;
        _.each(this.files, function (file) {
            if (file.content) {
                if (!file.evaled) {
                    var script = document.createElement("script");
                    if (file.filename.indexOf(".handlebars") > 0)
                        script.type = "text/x-handlebars-template"; // This hasn't been tested
                    else
                        script.type = "text/javascript";

                    script.text = file.content;

                    var head = document.getElementsByTagName("head")[0] || document.documentElement;
                    head.appendChild(script);

                    file.evaled = true;
                    KAConsole.log("Evaled contents of " + file.filename);

                    self.progress++;
                }
            } else {
                waiting = true;
                return _.breaker;
            }
        });

        if (waiting) {
            if (self.progress != self.last_progress) {
                callback("progress", self.progress / (2 * self.files.length));
                self.last_progress = self.progress;
            }
            setTimeout(function () {
                self.checkComplete();
            }, 500);
        } else {
            dynamicPackageLoader.loadedPackages[packageName] = true;
            delete dynamicPackageLoader.loadingPackages[packageName];
            callback("complete");
        }
    };

    this.checkComplete();
}

var dynamicPackageLoader = {
    loadedPackages:{},
    loadingPackages:{},
    currentFiles:[],

    load:function (packageName, callback, manifest) {
        if (this.loadedPackages[packageName]) {
            if (callback)
                callback(packageName);
        } else {
            new dynamicPackage(packageName, callback, manifest);
        }
    },

    packageLoaded:function (packageName) {
        return this.loadedPackages[packageName];
    },

    setPackageLoaded:function (packageName) {
        this.loadedPackages[packageName] = true;
    }
};

$(function () {
    $(document).delegate("input.blur-on-esc", "keyup", function (e, options) {
        if (options && options.silent) return;
        if (e.which == "27") {
            $(e.target).blur();
        }
    });
});

// An animation that grows a box shadow of the review hue
$.fx.step.reviewExplode = function (fx) {
    var val = fx.now + fx.unit;
    $(fx.elem).css("boxShadow",
        "0 0 " + val + " " + val + " " + "rgba(227, 93, 4, 0.2)");
};

var HeaderTopicBrowser = {
    init:function () {
        // Use hoverIntent to hide the dropdown (which handles the delay)
        // but it has to be set on the whole subheader so we still use
        // mouseenter to show it.
        var hoverIntentActive = false;
        $("#navbar").hoverIntent({
            over:function () {
                hoverIntentActive = true;
            },
            out:function () {
                $("#navbar .watch-link.dropdown-toggle").dropdown("close");
                hoverIntentActive = false;
            },
            timeout:400
        });
        $("#navbar .watch-link.dropdown-toggle")
            .on('mouseenter', function () {
                $(this).dropdown("open");
            })
            .on('mouseleave', function () {
                if (!hoverIntentActive) {
                    $(this).dropdown("close");
                }
            })
            .on('click', function () {
                location.href = $(this).attr("href");
            });

        // Use hoverIntent to keep the menus selected/open
        // even if you temporarily leave the item bounds.
        $("#navbar .topic-browser-menu > li")
            .hoverIntent(this.hoverIntentHandlers(50, 0.5, true))
            .children("ul")
            .children("li")
            .hoverIntent(this.hoverIntentHandlers(0, 0, false))
    },

    hoverIntentHandlers:function (timeout, sensitivityX, setActive) {
        // Intentionally create one closure per <ul> level so each has
        // its own selected element

        // activeEl is the currently focused <li> element. The focus is
        // maintained until the out() function is called, even if other
        // <li> elements get an over() call.
        var activeEl = null;

        // nextEl is the element currently being hovered over in the case
        // that activeEl isn't giving up focus. When activeEl gives up
        // focus it moves to the current nextEl.
        var nextEl = null;

        return {
            over:function () {
                if (this == activeEl) {
                    return;
                }
                if (activeEl) {
                    // Don't grab focus until activeEl gives it up.
                    nextEl = this;
                } else {
                    // There is no activeEl, so grab focus now.
                    $(this).addClass("hover-active");
                    if (setActive) {
                        // Setting child-active overrides the hover CSS
                        $("#navbar ul.topic-browser-menu")
                            .addClass("child-active")
                            .removeClass("none-active");
                    }
                    activeEl = this;
                }
            },
            out:function () {
                if (activeEl == this) {
                    $(this).removeClass("hover-active");
                    if (nextEl) {
                        // Transfer the focus to nextEl and keep child-active on
                        $(nextEl).addClass("hover-active");
                        activeEl = nextEl;
                        nextEl = null;
                    } else {
                        // Clear the focus
                        activeEl = null;
                        if (setActive) {
                            // Setting none-active re-enables the hover CSS
                            $("#navbar ul.topic-browser-menu")
                                .removeClass("child-active")
                                .addClass("none-active");
                        }
                    }
                } else {
                    if (this == nextEl) {
                        // If this element was queued up for focus, clear it
                        // to prevent an element getting focus and never losing
                        // it.
                        nextEl = null;
                    }
                }
            },
            timeout:timeout,
            directionalSensitivityX:sensitivityX
        };
    }
};

