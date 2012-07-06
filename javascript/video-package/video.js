var Video = {

    SHOW_SUBTITLES_COOKIE: "show_subtitles",

    waitingForVideo: null,
    currentVideoPath: null,
    currentVideoData: null,
    rendered: false,
    youtubeBlocked: false,
    pushStateDisabled: false,
    needsUserVideoCSSReload: false,

    init: function(params) {
        var self = this;

        this.videoLibrary = params.videoLibrary || {};
        this.loginURL = params.loginURL;

        if (params.videoTopLevelTopic) {
            this.videoTopLevelTopic = params.videoTopLevelTopic;
            this.rootLength = 1 + params.videoTopLevelTopic.length;

            if (window.history && window.history.pushState && params.videoTopLevelTopic) {
                this.router = new VideoRouter();
                this.router.bind("all", Analytics.handleRouterNavigation);
                Backbone.history.start({
                    pushState: true,
                    root: "/" + params.videoTopLevelTopic + "/"
                });
            } else {
                this.pushStateDisabled = true;
                Video.navigateToVideo(window.location.pathname);
            }
        } else {
            // Used for modal video player
            this.initEventHandlers();
        }

        VideoControls.onYouTubeBlocked(function() {

            var flvPlayerTemplate = Templates.get("video.video-flv-player");
            $("#youtube_blocked")
                .css("visibility", "visible")
                .css("left", "0px")
                .css("position", "relative")
                .html(flvPlayerTemplate({ video_path: self.currentVideoPath }));
            $("#idOVideo").hide();
            $(".subtitles-enable, .transcript-enable")
                .prop("disabled", true)
                .parents("label").addClass("disabled");
            Video.hideSubtitles();
            VideoStats.prepareAlternativePlayer(); // If YouTube is hidden, use the flv player for statistics

            self.youtubeBlocked = true;
        });

    },

    renderTemplates: function(topicData, videoData) {
        var navTemplate = Templates.get("video.video-nav");
        var descTemplate = Templates.get("video.video-description");
        var headerTemplate = Templates.get("video.video-header");
        var footerTemplate = Templates.get("video.video-footer");

        $("span.video-nav").html(navTemplate({topic: topicData.topic, video: videoData}));
        $(".video-title").html(videoData.title);
        $("div.video-description").html(descTemplate({topic: topicData.topic, video: videoData}));
        $("div.video-header").html(headerTemplate({topic: topicData.topic, video: videoData}));
        $("span.video-footer").html(footerTemplate({topic: topicData.topic, video: videoData}));
    },

    renderPage: function(topicData, videoData) {
        var self = this;

        // Fix up data for templating
        if (videoData.related_exercises &&
            videoData.related_exercises.length) {
            videoData.related_exercises[videoData.related_exercises.length - 1].last = true;
        }

        if (!this.rendered) {
            // Initial page load
            this.rendered = true;
        } else {
            // Subsequent page load; send Google Analytics data
            if (window._gaq) {
                _gaq.push(["_trackPageview", window.location.pathname]);
            }

            // Reload user video CSS
            if (this.needsUserVideoCSSReload) {
                var queryString = "?reload=" + new Date().getTime();
                $('link[rel="stylesheet"]').each(function() {
                    if (this.href.indexOf("user_video_css") > -1) {
                        this.href = this.href.replace(/\?.*|$/, queryString);
                    }
                });
                this.needsUserVideoCSSReload = false;
            }

            // Re-render templates
            this.renderTemplates(topicData, videoData);
        }

        // Bingo conversions for reaching a video page
        gae_bingo.bingo(["struggling_videos_landing"]);

        document.title = videoData.title + " | " + topicData.topic.title + " | Khan Academy";

        this.currentVideoData = videoData;
        this.currentVideoPath = videoData.video_path;

        var jVideoDropdown = $("#video_dropdown");
        if (jVideoDropdown.length) {
            jVideoDropdown.css("display", "inline-block");

            var menu = $("#video_dropdown ol").menu();
            // Set the width explicitly before positioning it absolutely to satisfy IE7.
            menu.width(menu.width()).hide().css("position", "absolute");
            menu.bind("menuselect", function(e, ui) {
                if (self.pushStateDisabled) {
                    window.location.replace(ui.item.children("a").attr("href"));
                } else {
                    var fragment = ui.item.children("a").attr("href").substr(self.rootLength);
                    Video.router.navigate(fragment, {trigger: true});
                }
            });
            $(document).bind("click focusin", function(e) {
                if ($(e.target).closest("#video_dropdown").length === 0) {
                    menu.hide();
                }
            });

            var button = $("#video_dropdown > a").button({
                icons: {
                    secondary: "ui-icon-triangle-1-s"
                }
            }).show().click(function(e) {
                if (menu.css("display") === "none") {
                    menu.show().menu(
                        "activate", e,
                        $("#video_dropdown li[data-selected=selected]")
                    ).focus();
                } else {
                    menu.hide();
                }
                e.preventDefault();
            });
        }

        // If the user starts writing feedback, disable autoplay.
        $("span.video-footer").on("focus keydown", "input,textarea", function(event) {
            VideoControls.setAutoPlayEnabled(false);
        });

        if (this.youtubeBlocked) {
           var flvPlayerTemplate = Templates.get("video.video-flv-player");
           $("#youtube_blocked").html(flvPlayerTemplate({ video_path: this.currentVideoPath }));
           VideoStats.prepareAlternativePlayer(); // If YouTube is hidden, use the flv player for statistics
        } else {
            VideoControls.playVideo(videoData.youtube_id, videoData.key, false);
        }

        // Start up various scripts
        Discussion.init();
        Moderation.init();
        Voting.init();
        Comments.init();
        QA.init();

        this.initEventHandlers();
        VideoStats.updatePointsSaved(videoData.videoPoints);

        // Set up next/previous links
        if (!this.pushStateDisabled) {
            $("a.previous-video,a.next-video").click(function(event) {
                if (self.pushStateDisabled) {
                    return true;
                }
                var fragment = $(this).attr("href").substr(self.rootLength);
                Video.router.navigate(fragment, {trigger: true});
                event.stopPropagation();
                return false;
            });

            if (videoData.next_video) {
                // Autoplay to the next video
                var nextVideoFragment = $("a.next-video").attr("href").substr(self.rootLength);
                VideoControls.setAutoPlayCallback(function() {
                    Video.router.navigate(nextVideoFragment, {trigger: true});
                });
            } else {
                // Don't autoplay to next video
                VideoControls.setAutoPlayCallback(null);
            }
        } else {
            // Autoplay is disabled if there is no pushState support
            VideoControls.setAutoPlayCallback(null);
        }

        VideoControls.initContinuousPlayLinks($("span.video-footer"));

        // Preload adjacent videos after 15 seconds
        setTimeout(function() {
            if (videoData.previous_video) {
                Video.loadVideo(topicData.topic.id, videoData.previous_video.readable_id);
            }
            if (videoData.next_video) {
                Video.loadVideo(topicData.topic.id, videoData.next_video.readable_id);
            }
        }, 15000);

        this.waitingForVideo = null;
    },

    updateVideoPoints: function(points) {
        if (this.currentVideoData) {
            this.currentVideoData.videoPoints = points;
        }
        VideoStats.updatePointsSaved(points);
        this.needsUserVideoCSSReload = true;
    },

    initEventHandlers: function() {

        $(".subtitles-enable").on("click", _.bind(Video.toggleSubtitles, Video));
        if (readCookie(this.SHOW_SUBTITLES_COOKIE)) {
            this.showSubtitles();
        }

        var transcript = $(".subtitles-container");
        var transcriptLink = $(".transcript-enable");
        if (transcript.length && transcriptLink.length) {
            InteractiveTranscript.init(transcript);
            transcriptLink.click($.proxy(this._ontranscriptclick, this,
                transcript, transcriptLink));
        }

        // We take the message in the title of the energy points box and place it
        // in a tooltip, and if it's the message with a link to the login we
        // replace it with a nicer link (we don't want to have to pass the url to
        // the templatetag).
        var $points = $(".video-energy-points");
        $points.data("title", $points.attr("title").replace(/Sign in/,
                   "<a href=\"" + this.loginURL + "\">Sign in</a>"))
               .removeAttr("title");

        VideoStats.tooltip("#points-badge-hover", $points.data("title"));

        // enable dropdown menu
        $(".extra-link-bar .dropdown-toggle").
            dropdown("hover");

        // clicks on body close the menu. If the click is on the menu itself,
        // prevent it from being closed.
        $(".extra-link-bar .dropdown-menu").
            on("click", function(ev) {
                ev.originalEvent.leaveDropdownOpen = true;
            });
    },

    navigateToVideo: function(path) {
        // Strip out any query string
        var queryIndex = path.indexOf("?");
        if (queryIndex > -1) {
            path = path.substr(0, queryIndex);
        }

        // Strip out leading slash
        if (path.charAt(0) == "/") {
            path = path.substr(1);
        }

        pathList = [this.videoTopLevelTopic].concat(path.split("/"));
        if (pathList.length >= 3) {
            var video = pathList[pathList.length - 1];
            var topic = pathList[pathList.length - 3];

            this.waitingForVideo = { topic: topic, video: video, url: "/" + this.videoTopLevelTopic + "/" + path };
            this.loadVideo(topic, video);
        }
    },

    loadVideo: function(topic, video) {
        var self = this;
        var descTemplate = Templates.get("video.video-description");
        var waitingForVideo = (Video.waitingForVideo &&
            Video.waitingForVideo.topic == topic &&
            Video.waitingForVideo.video == video);

        if (this.videoLibrary[topic] && this.videoLibrary[topic].videos[video]) {
            if (waitingForVideo) {
                if (this.videoLibrary[topic].videos[video] !== "LOADING") {
                    KAConsole.log("Switching to video: " + video + " in topic " + topic);
                    Video.renderPage(this.videoLibrary[topic], this.videoLibrary[topic].videos[video]);
                    return; // No longer waiting
                }
            } else {
                return; // Nothing to do
            }
        } else {
            KAConsole.log("Loading video: " + video + " in topic " + topic);
            url = "/api/v1/videos/" + topic + "/" + video + "/play" + (this.videoLibrary[topic] ? "" : "?topic=1");

            this.videoLibrary[topic] = this.videoLibrary[topic] || { videos: [] };
            this.videoLibrary[topic].videos[video] = "LOADING";

            $.ajax({
                url: url,
                success: function(json) {
                    var waitingForVideo = (Video.waitingForVideo &&
                        Video.waitingForVideo.topic == topic &&
                        Video.waitingForVideo.video == video);
                    if (json.topic)
                        self.videoLibrary[topic].topic = json.topic;
                    self.videoLibrary[topic].videos[video] = json.video;
                    if (waitingForVideo) {
                        KAConsole.log("Switching to video: " + video + " in topic " + topic);
                        Video.renderPage(self.videoLibrary[topic], json.video);
                    }
                },
                error: function() {
                    var waitingForVideo = (Video.waitingForVideo &&
                        Video.waitingForVideo.topic == topic &&
                        Video.waitingForVideo.video == video);
                    if (waitingForVideo) {
                        window.location.assign(Video.waitingForVideo.url);
                    }
                }
            });
        }

        if (waitingForVideo) {
            $("span.video-nav").html("");
            $("div.video-description").html(descTemplate({video: { title: "Loading..." }, loading: true }));
            $("div.video-header").html("");
            $("span.video-footer").html("");
        }
    },

    _ontranscriptclick: function(transcript, transcriptLink, e) {
        if (transcriptLink.hasClass("disabled")) return;

        if (transcript.is(":visible")) {
            InteractiveTranscript.stop();
            transcript.slideUp("fast");
        } else {
            transcript.slideDown("fast", function() {
                InteractiveTranscript.start();
            });
        }
    },

    toggleSubtitles: function() {
        if ($(".subtitles-warning").is(":visible")) {
            this.hideSubtitles();
        } else {
            this.showSubtitles();
        }
    },


    hideSubtitles: function() {
        eraseCookie(this.SHOW_SUBTITLES_COOKIE);
        Video.hideSubtitleElements();
    },

    hideSubtitleElements: function() {
        $(".subtitles-link").removeClass("toggled");

        // 2012-02-23: unisubs uses !important in their styles, forcing us to
        // follow along when showing and hiding their tab.
        $(".unisubs-videoTab").addClass("display-none-important");

        $(".subtitles-warning").hide();
        Throbber.hide();
    },

    showSubtitleElements: function() {
        $(".subtitles-link").addClass("toggled");
        $(".subtitles-warning").show();

        // 2012-02-23: unisubs uses !important in their styles, forcing us to
        // follow along when showing and hiding their tab.
        $(".unisubs-videoTab").removeClass("display-none-important");
    },

    showSubtitles: function() {
        if (!this.pushStateDisabled) {
            this.pushStateDisabled = true;
        }

        // ensure menu is checked
        $(".subtitles-enable").prop("checked", true);
        createCookie(this.SHOW_SUBTITLES_COOKIE, true, 365);
        Video.showSubtitleElements();

        if ($(".unisubs-videoTab").length === 0) {
            window.setTimeout(function() {
                Throbber.show($(".subtitles-warning"), true);
            }, 1);

            $.getScript("http://s3.www.universalsubtitles.org/js/mirosubs-widgetizer.js", function() {
                // Workaround bug where subtitles are not displayed if video was already playing until
                // video is paused and restarted.  We wait 3 secs to give subtitles a chance to load.
                window.setTimeout(function() {
                    if (VideoControls.player &&
                            VideoControls.player.getPlayerState() === 1 /* playing */) {
                        VideoControls.pause();
                        VideoControls.play();
                    }
                }, 3000);
            });
        }
    }
};

window.VideoRouter = Backbone.Router.extend({
    routes: {
        "*path": "video"
    },

    video: function(path) {
        Video.navigateToVideo(path);
    }
});


/*
 * Widget for interactive video subtitles.
 *
 * The video transcript is displayed with the current subtitle "active".
 * Clicking a subtitle jumps to that place in the video. The transcript
 * viewport is scrolled to keep the current subtitle in view.
 */
var InteractiveTranscript = {

    /*
     * The frequency in milliseconds at which to check the visible subtitle.
     */
    POLL_MILLIS: 333,

    /*
     * Whether automatic scrolling is enabled. Turned off when the user is
     * interacting with the transcript.
     */
    autoscroll: true,

    /*
     * The polling interval ID returned by window.setInterval().
     */
    pollIntervalId: null,

    /*
     * The scrollable area containing subtitles.
     */
    viewport: null,

    /*
     * Initialize with the interactive transcript root element. Call only once.
     */
    init: function(root) {
        //TODO: convert to some type of logging that allows for leaving the log
        //lines in for development and auto-stripping them for production.
        //console.log("InteractiveTranscript.init()");
        var viewport = root.find(".subtitles");
        viewport.delegate("a", "click", $.proxy(this._onsubtitleclick, this));
        viewport.hover($.proxy(this._onhover, this));
        this.viewport = viewport;
    },

    /*
     * Begin tracking the active subtitle in the video player.
     */
    start: function() {
        //console.log("InteractiveTranscript.start()");
        this.stop();
        this._pollPlayer();
        this.pollIntervalId = setInterval(
            $.proxy(this._pollPlayer, this), this.POLL_MILLIS);
    },

    /*
     * Stop tracking the active subtitle in the video player.
     */
    stop: function() {
        //console.log("InteractiveTranscript.stop()");
        clearInterval(this.pollIntervalId);
        this.pollIntervalId = null;
    },

    /*
     * Handle mouseenter and mouseleave on the transcript.
     */
    _onhover: function(e) {
        //console.log("InteractiveTranscript._onhover(): type="+e.type);
        this.autoscroll = (e.type === "mouseleave");
    },

    /*
     * Handle click event on a subtitle.
     */
    _onsubtitleclick: function(e) {
        //console.log("InteractiveTranscript._onsubtitleclick()");
        if (!VideoStats.player) {
            return;
        }

        var time = parseFloat($(e.target).parent().data("time"));

        if (!isNaN(time)) {
            VideoStats.player.seekTo(time, true);
            VideoStats.player.playVideo();
        }
    },

    /*
     * Activate the subtitle corresponding to the current video position.
     */
    _pollPlayer: function() {
        //console.log("InteractiveTranscript._pollPlayer()");
        if (!VideoStats.player) {
            return;
        }

        var currTime = VideoStats.player.getCurrentTime(),
            lineTime,
            currSub,
            lines = this.viewport.find("li"),
            len = lines.length,
            i;

        for (i = 0; i < len; i++) {
            lineTime = parseFloat($(lines[i]).data("time"));

            // find the next highest element before stepping back by 1
            if (!isNaN(lineTime) && lineTime > currTime) {
                currSub = (i === 0) ? lines[0] : lines[i - 1];
                break;
            }
        }

        if (!$(currSub).is(".active")) {
            this._setActiveSubtitle(currSub || lines[len - 1]);
        }
    },

    /*
     * Activate the given subtitle.
     */
    _setActiveSubtitle: function(subtitle) {
        //console.log("InteractiveTranscript._setActiveSubtitle()");

        var offsetTop,
            height;

        this.viewport.find(".active").removeClass("active");
        $(subtitle).addClass("active");

        if (this.autoscroll) {
            offsetTop = subtitle.offsetTop;
            height = $(subtitle).height();

            // show three lines above the active line
            this.viewport.stop().animate({
                scrollTop: offsetTop - (height * 3)
            });
        }
    }
};

