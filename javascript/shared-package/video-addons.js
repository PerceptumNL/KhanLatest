function onYouTubePlayerStateChange(state) {
    VideoStats.playerStateChange(state);
    $(VideoControls).trigger("playerStateChange", state);
}

var VideoControls = {

    player: null,
    autoPlayEnabled: false,
    autoPlayCallback: null,
    continuousPlayButton: null,

    readyDeferred_: new $.Deferred(),

    initJumpLinks: function(el) {
        $(el || ".video-footer").on("click", ".youTube",
                                    VideoControls.clickYouTubeJump);
    },

    initContinuousPlayLinks: function(parentEl) {
        this.continuousPlayButton = $("a.continuous-play", parentEl);
        this.continuousPlayButton.click(function() {
            VideoControls.setAutoPlayEnabled(!VideoControls.autoPlayEnabled);
        });
        this.setAutoPlayEnabled(VideoControls.autoPlayEnabled);
    },

    initPlaceholder: function(jelPlaceholder, youtubeParams) {
        var jelWrapper = null;

        // Once the youtube player is all loaded and ready, clicking the play
        // button will play inline.
        $(VideoControls).one("playerready", function() {

            // Before any playing, unveil and play the real youtube player
            $(VideoControls).one("beforeplay", function() {

                // Use .left to unhide the player without causing any
                // re-rendering or "pop"-in of the player.
                jelWrapper.css("left", 0);

                jelPlaceholder.find(".youtube-play").css("visibility", "hidden");

            });

            jelPlaceholder.click(function(e) {

                VideoControls.play();
                e.preventDefault();

            });

        });

        // Start loading the youtube player immediately,
        // and insert it wrapped in a hidden container
        var template = Templates.get("shared.youtube-player");

        jelPlaceholder
            .parent()
                .after(
                    $(template(youtubeParams))
                        .wrap("<div class='player-loading-wrapper'/>")
                        .parent()
            );

        jelWrapper = jelPlaceholder.parent().next();
    },

    clickYouTubeJump: function() {
        var seconds = $(this).attr("seconds");
        if (VideoControls.player && seconds) {
            VideoControls.player.seekTo(Math.max(0, seconds - 2), true);
            VideoControls.scrollToPlayer();
        }
    },

    play: function() {
        $(VideoControls).trigger("beforeplay");

        if (VideoControls.player && VideoControls.player.playVideo) {
            VideoControls.player.playVideo();
        }
    },

    pause: function() {
        if (VideoControls.player && VideoControls.player.pauseVideo)
            VideoControls.player.pauseVideo();
    },

    setAutoPlayEnabled: function(enabled) {
    /*
        this.autoPlayEnabled = enabled;
        this.continuousPlayButton.toggleClass("green", enabled);
        if (enabled) {
            this.continuousPlayButton.html("Continuous play is ON");
        } else {
            this.continuousPlayButton.html("Continuous play is OFF");
        }
        */
    },

    setAutoPlayCallback: function(callback) {
        this.autoPlayCallback = callback;
    },

    scrollToPlayer: function() {
        // If user has scrolled below the youtube video, scroll to top of video
        // when a play link is clicked.
        var yTop = $(VideoControls.player).offset().top - 2;
        if ($(window).scrollTop() > yTop) {
            $(window).scrollTop(yTop);
        }
    },

    onYouTubeBlocked: function(callback) {
        $("<img width=0 height=0>")
            .error(callback)
            .attr("src", "http://www.youtube.com/favicon.ico?" + Math.random())
            .appendTo("#page-container");
    },

    initThumbnails: function() {
        $("#thumbnails")
            .cycle({
                fx: "scrollHorz",
                timeout: 0,
                speed: 550,
                slideResize: 0,
                easing: "easeInOutBack",
                startingSlide: 0,
                prev: "#arrow-left",
                next: "#arrow-right",
                before: function() {
                    $(this).find("div.pending").each(function() {
                        $(this).css("background-image", "url('" + $(this).data("src") + "')");
                    });
                }
            })
            .css({ width: "" }) // We want #thumbnails to be full width even though the cycle plugin doesn't
            .find(".thumbnail_link")
                .click(VideoControls.thumbnailClick).end();

        this.initThumbnailHover($("#thumbnails"));
    },

    initThumbnailHover: function(parentEl) {
        // Queue:false to make sure all of these run at the same time
        var animationOptions = {duration: 150, queue: false};

        parentEl
            .find(".thumbnail_td")
                .hover(
                        function() {
                            $(this)
                                .find(".thumbnail_label").animate({ marginTop: -78 }, animationOptions).end()
                                .find(".thumbnail_teaser").animate({ height: 45 }, animationOptions);
                        },
                        function() {
                            $(this)
                                .find(".thumbnail_label").animate({ marginTop: -32 }, animationOptions).end()
                                .find(".thumbnail_teaser").animate({ height: 0 }, animationOptions);
                        }
            );
    },

    thumbnailClick: function() {
        var jelParent = $(this).parents("td").first();
        var youtubeId = jelParent.attr("data-youtube-id");
        if (youtubeId) {
            VideoControls.playVideo(youtubeId, jelParent.attr("data-key"), true);

            $("#thumbnails td.selected").removeClass("selected");
            jelParent.addClass("selected");

            return false;
        }
    },

    playVideo: function(youtubeId, videoKey, forcePlayBegin) {
        if (VideoControls.player && youtubeId) {
            $(VideoControls).trigger("beforeplay");

            if (forcePlayBegin || this.autoPlayEnabled) {
                VideoControls.player.loadVideoById(youtubeId, 0, "default");
            } else {
                VideoControls.player.cueVideoById(youtubeId, 0, "default");
            }
            VideoControls.scrollToPlayer();
        }
        VideoStats.startLoggingProgress(videoKey);
    },

    /**
     * Invokes a function (typically on the player) and ensures that the invoke
     * is done only after the player is ready.
     */
    invokeWhenReady: function(func) {
        this.readyDeferred_.then(func);
    },

    setPlayer: function(player) {
        this.player = player;
        this.readyDeferred_.resolve();
    }
};

// enum-style object for the states returned by the Youtube Player API.
// see player.getPlayerState() at
// https://developers.google.com/youtube/js_api_reference
var VideoPlayerState = {
    // UNCHANGED is not part of the Youtube player API. It's fired by a timeout
    // to force video logging to update.
    UNCHANGED: -2,

    // All remaining states are part of the Youtube player API.
    UNSTARTED: -1,
    ENDED: 0,
    PLAYING: 1,
    PAUSED: 2,
    BUFFERING: 3,
    VIDEO_CUED: 5
};

var VideoStats = {

    dPercentGranularity: 0.1,
    dPercentLastSaved: 0.0,
    fSaving: false,
    consecutiveFailures: 0,
    player: null,
    intervalId: null,
    fAlternativePlayer: false,
    fEventsAttached: false,
    cachedDuration: 0, // For use by alternative FLV player
    cachedCurrentTime: 0, // For use by alternative FLV player
    dtLastSaved: null,
    sVideoKey: null,
    sYoutubeId: null,
    playing: false, //ensures pause and end events are idempotent

    /**
     * A cache of the last point value saved.
     * A value of -1 indicates that no value has been saved and we don't
     * know the points earned for the current video.
     */
    pointsSaved: -1,

    getSecondsWatched: function() {
        if (!this.player) return 0;
        return this.player.getCurrentTime() || 0;
    },

    getSecondsWatchedSinceSave: function() {
        var secondsPageTime = ((new Date()) - this.dtLastSaved) / 1000.0;
        return Math.min(secondsPageTime, this.getSecondsWatched());
    },

    POINTS_BASE: 750,
    REQUIRED_PERCENTAGE_FOR_FULL_VIDEO_POINTS: 0.9,

    /**
     * Computes an estimate of the points for the current video.
     * Returns -1 if no reasonable estimate can be made.
     * This logic must be in sync with the code in the server at points.py
     */
    getPointsEstimate: function() {
        if (this.pointsSaved < 0) {
            return -1;
        }
        var duration = this.player.getDuration() || 0;
        if (duration <= 0) {
            return -1;
        }

        var secondsSinceSave = this.getSecondsWatchedSinceSave();
        var percentSinceSave = Math.min(1.0, secondsSinceSave / duration);
        var percentTotal = percentSinceSave + (this.pointsSaved / this.POINTS_BASE);
        if (percentTotal > this.REQUIRED_PERCENTAGE_FOR_FULL_VIDEO_POINTS) {
            percentTotal = 1.0;
        }

        return Math.ceil(this.POINTS_BASE * percentTotal);
    },

    getPercentWatched: function() {
        if (this.player == null || this.player.getDuration == null) {
            return 0;
        }

        var duration = this.player.getDuration() || 0;
        if (duration <= 0) {
            return 0;
        }

        return Math.min(1.0, this.getSecondsWatched() / duration);
    },

    startLoggingProgress: function(sVideoKey, sYoutubeId) {

        if (sYoutubeId) {
            this.sYoutubeId = sYoutubeId;
            this.sVideoKey = null;
        } else if (sVideoKey) {
            this.sVideoKey = sVideoKey;
            this.sYoutubeId = null;
        } else {
            return; // no key given, can't log anything.
        }

        this.dPercentLastSaved = 0;
        this.cachedDuration = 0;
        this.cachedCurrentTime = 0;
        this.dtLastSaved = new Date();

        if (this.fEventsAttached) return;

        // Listen to state changes in player to detect final end of video
        if (this.player) this.listenToPlayerStateChange();
        // If the player isn't ready yet or if it is replaced in the future,
        // listen to the state changes once it is ready/replaced.
        $(this).on("playerready.videostats",
            _.bind(this.listenToPlayerStateChange, this));

        if (this.intervalId === null) {
            // Every 10 seconds check to see if we've crossed over our percent
            // granularity logging boundary
            this.intervalId = setInterval(function() {
                VideoStats.playerStateChange(VideoPlayerState.UNCHANGED);
            }, 10000);
        }

        this.fEventsAttached = true;
    },

    stopLoggingProgress: function() {
        // unhook event handler initializer
        $(this).unbind("playerready.videostats");

        // send a final pause event
        this.playerStateChange(VideoPlayerState.PAUSED);

        // now unhook playback polling
        if (this.intervalId !== null) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        // cannot unhook statechange handler as there is no removeEventListener

        this.fEventsAttached = false;
    },

    listenToPlayerStateChange: function() {
        if (!this.fAlternativePlayer && !this.player.fStateChangeHookAttached) {
            // YouTube player is ready, add event listener
            this.player.addEventListener("onStateChange", "onYouTubePlayerStateChange");

            // Multiple calls should be idempotent
            this.player.fStateChangeHookAttached = true;
        }
    },

    checkVideoComplete: function() {
        var state = this.player.getPlayerState();
        if (state === VideoPlayerState.ENDED) {
            if (VideoControls.autoPlayCallback) {
                VideoControls.autoPlayCallback();
            } else {
                VideoControls.setAutoPlayEnabled(false);
            }
        } else if (state === VideoPlayerState.PAUSED) {
            VideoControls.setAutoPlayEnabled(false);
        }
    },

    playerStateChange: function(state) {
        var self = this;
        var playing = this.playing || this.fAlternativePlayer;
        if (state === VideoPlayerState.UNCHANGED) { // playing normally
            var percent = this.getPercentWatched();

            // Save after we hit certain intervals of video watching.
            if (percent > (this.dPercentLastSaved + this.dPercentGranularity)) {
                this.save();
            } else if (this.playing) {
                // If we hit the max video points for the first time, force a save,
                // since showing an estimate might entice the user to close the browser
                // thinking they finished (and it not having actually saved).
                var threshold = this.REQUIRED_PERCENTAGE_FOR_FULL_VIDEO_POINTS;
                if (this.dPercentLastSaved < threshold && percent >= threshold) {
                    this.save();
                } else {
                    var estimate = this.getPointsEstimate();
                    if (estimate >= 0) {
                        this.updatePointsDisplay(estimate);
                    }
                }
            }
        } else if (state === VideoPlayerState.ENDED && playing) {
            this.playing = false;
            this.save();

            if (VideoControls.autoPlayEnabled) {
                setTimeout(function() { self.checkVideoComplete() }, 500);
            } else {
                VideoControls.setAutoPlayEnabled(false);
            }

            if (this.analyticsActivity) {
                this.analyticsActivity.parameters["Percent (end)"] = this.dPercentLastSaved;
                Analytics.trackActivityEnd(this.analyticsActivity);
                this.analyticsActivity = null;
            }
        } else if (state === VideoPlayerState.PAUSED && playing) {
            this.playing = false;
            if (this.getSecondsWatchedSinceSave() > 1) {
                this.save();
            }

            if (VideoControls.autoPlayEnabled) {
                setTimeout(function() { self.checkVideoComplete() }, 500);
            } else {
                VideoControls.setAutoPlayEnabled(false);
            }

            if (this.analyticsActivity) {
                this.analyticsActivity.parameters["Percent (end)"] = this.dPercentLastSaved;
                Analytics.trackActivityEnd(this.analyticsActivity);
                this.analyticsActivity = null;
            }
        } else if (state === VideoPlayerState.PLAYING) {
            this.playing = true;
            this.dtLastSaved = new Date();
            this.dPercentLastSaved = this.getPercentWatched();

            if (!this.analyticsActivity) {
                var id = "";
                if (this.sVideoKey !== null) {
                    id = this.sVideoKey;
                } else if (this.sYoutubeId !== null) {
                    id = this.sYoutubeId;
                }
                this.analyticsActivity = Analytics.trackActivityBegin("Video Play", {
                    "Video ID": id,
                    "Percent (begin)": this.dPercentLastSaved
                });
//                gae_bingo.bingo(["topic_pages_started_video"]);

            }
        }
        // If state is buffering, unstarted, or cued, don't do anything
    },

    // TODO(benkomalo): move this temporary check elsewhere and beef it up.
    // Right now it relies on a global variable set in page_template.html
    // for the user's nickname.
    isPhantom_: function() {
        return !window.USERNAME;
    },

    save: function() {

        if (this.fSaving) {
            return;
        }

        // Make sure cookies are enabled, otherwise this totally won't work
        if (!areCookiesEnabled()) {
            KAConsole.log("Cookies appear to be disabled. Not logging video progress.");
            return;
        }

        if (this.isPhantom_() && this.consecutiveFailures >= 3) {
            KAConsole.log("Not sending video log request due to too many failures");
            return;
        }

        this.fSaving = true;
        var percent = this.getPercentWatched();
        var dtLastSavedBeforeError = this.dtLastSaved;
        var id = 0;

        var data = {
            last_second_watched: this.getSecondsWatched(),
            seconds_watched: this.getSecondsWatchedSinceSave(),
            casing: "camel"
        };

        if (this.sVideoKey !== null) {
            data.video_key = this.sVideoKey;
        } else if (this.sYoutubeId !== null) {
            id = this.sYoutubeId;
        }

        $.ajax({type: "GET",
                url: "/api/v1/user/videos/" + id + "/log_compatability",
                data: data,
                success: function(data) {
                    VideoStats.finishSave(data, percent);
                    VideoStats.consecutiveFailures = 0;
                },
                error: function() {
                    // Restore pre-error stats so user can still get full
                    // credit for video even if GAE timed out on a request
                    VideoStats.fSaving = false;
                    VideoStats.dtLastSaved = dtLastSavedBeforeError;
                    VideoStats.consecutiveFailures++;
                }
        });

        this.dtLastSaved = new Date();
    },

    /* Use qtip2 (http://craigsworks.com/projects/qtip2/) to create a tooltip
     * that looks like the ones on youtube.
     *
     * Example:
     * VideoStats.tooltip('#points-badge-hover', '0 of 500 points');
     */
    tooltip: function(selector, content) {
        $(selector).qtip({
            content: {
                text: content
            },
            style: {
                classes: "ui-tooltip-youtube"
            },
            position: {
                my: "top center",
                at: "bottom center"
            },
            hide: {
                fixed: true,
                delay: 150
            }
        });
    },

    finishSave: function(json, percent) {
        VideoStats.fSaving = false;
        VideoStats.dPercentLastSaved = percent;

        if (json && json.actionResults.userVideo) {
            video = json.actionResults.userVideo;
            if (window.Video && Video.updateVideoPoints) {
                Video.updateVideoPoints(video.points);
            } else {
                this.updatePointsSaved(video.points);
            }

            if (video.completed) {
                var id = "";
                if (this.sVideoKey !== null) {
                    id = this.sVideoKey;
                } else if (this.sYoutubeId !== null) {
                    id = this.sYoutubeId;
                }
                Analytics.trackSingleEvent("Video Complete", {
                    "Video ID": id
                });
//                gae_bingo.bingo(["topic_pages_completed_video"]);
            }
        }
    },

    /**
     * Updates the number of points the video has earned, as saved to
     * the server.
     */
    updatePointsSaved: function(points) {
        this.pointsSaved = points;
        this.updatePointsDisplay(points);
    },

    /**
     * Update the points in the visible display of the video player.
     */
    updatePointsDisplay: function(points) {
        var jelPoints = $(".video-energy-points");
        if (jelPoints.length) {
            var hoverData = jelPoints.data("title");
            if (hoverData) {
                jelPoints.data("title", hoverData.replace(/^\d+/, points));
            }
            $(".video-energy-points-current", jelPoints).text(points);

            // Replace the old tooltip with an updated one.
            if (hoverData) {
                VideoStats.tooltip("#points-badge-hover", jelPoints.data("title"));
            }
        }
    },

    prepareAlternativePlayer: function() {

        this.player = $("#flvPlayer").get(0);
        if (!this.player) return;

        // Simulate the necessary YouTube APIs for the alternative player
        this.player.getDuration = function() { return VideoStats.cachedDuration; };
        this.player.getCurrentTime = function() { return VideoStats.cachedCurrentTime; };

        this.fAlternativePlayer = true;
    },

    cacheStats: function(time, duration) {

        // Only update current time if it exists, not if video finished
        // and scrubber went back to 0.
        var currentTime = parseFloat(time);
        if (currentTime) {
            this.cachedCurrentTime = currentTime;
        }

        this.cachedDuration = parseFloat(duration);
    }
};

// Called by standard (non-iframe) youtube player upon load.
// See http://code.google.com/apis/youtube/js_api_reference.html
function onYouTubePlayerReady(playerID) {

    // Check .playVideo to ensure that the YouTube JS API is available. Modern
    // browsers see both the OBJECT and EMBED elements, but only one has the
    // API attached to it, e.g., OBJECT for IE9, EMBED for Chrome.
    var player = $(".mirosubs-widget object").get(0);
    if (!player || !player.playVideo) player = document.getElementById("idPlayer");
    if (!player || !player.playVideo) player = document.getElementById("idOVideo");
    if (!player || !player.playVideo) throw new Error("YouTube player not found");

    // Ensure UniSub widget will know about ready players if/when it loads.
    (window.unisubs_readyAPIIDs = window.unisubs_readyAPIIDs || []).push((playerID === "undefined" || !playerID) ? "" : playerID);

    // defer this call as otherwise any exceptions thrown within will be
    // swallowed by flash
    _.defer(function() { connectYouTubePlayer(player); });
}

// Called by (experimental) iframe youtube player upon load.
// Currently only used on iOS devices.
// See http://code.google.com/apis/youtube/iframe_api_reference.html
function onYouTubePlayerAPIReady() {

    if (typeof YT === "undefined" || $("#iframePlayer").length === 0) {
        return;
    }

    // Always give each iframe player a unique id so YT.Player events
    // work properly. Hopefully in less-beta versions of YT's iframe API this
    // won't be necessary.
    //
    onYouTubePlayerAPIReady.players = onYouTubePlayerAPIReady.players || 0;
    $("#iframePlayer").attr("id", "iframePlayer_" + onYouTubePlayerAPIReady.players).data("ready", true);

    var playerJS = new YT.Player("iframePlayer_" + onYouTubePlayerAPIReady.players, {
        events: {
            "onReady": function(e) { connectYouTubePlayer(e.target); },
            "onStateChange": function(e) { onYouTubePlayerStateChange(e.data); }
        }
    });

    $("#page-container-inner")
        .on("pagehide", "div.video", function(a, b) {
            // Remove from DOM whenever leaving a video page
            // so a full refresh is triggered.
            $(a.target).remove();
        });

    // Whenever showing a new video page, making sure onYouTubePlayerAPIReady
    // gets called, even if it's been called previously.
    $("#page-container-inner").on("pageshow", "div.video", function() {
        onYouTubePlayerAPIReady();
    });

    onYouTubePlayerAPIReady.players += 1;
}

function connectYouTubePlayer(player) {

    VideoControls.setPlayer(player);
    VideoStats.player = player;

    // The UniSub (aka mirosubs) widget replaces the YouTube player with a copy
    // and that will cause onYouTubePlayerReady() to be called again.  So, we trigger
    // 'playerready' events on any objects that are using the player so that they can
    // take appropriate action to use the new player.
    $(VideoControls).trigger("playerready");
    $(VideoStats).trigger("playerready");
}
