var KMapEditor = {
    ZOOM_EXERCISES: 8,
    ZOOM_HYBRID: 7,
    ZOOM_TOPICS: 6,

    defaultVersion: [],    // currently-live exercise settings
    editVersion: [],       // exercise setting changes that have been persisted to the edit version
    candidateVersion: [],  // locally modified exercise settings
    defaultMap: {},        // currently-live MapLayout
    editMap: {},           // previously persisted MapLayout
    candidateMap: {},      // locally modified MapLayout

    exercises: null,       // points to one of the three versions above and reflects the active view
    maplayout: null,       // points to one of the three maplayouts above
    readonly: true,        // should be true unless editing the candidate version

    selected: [],
    raphael: {},

    minH: 0,
    minV: 0,
    zoomLevel: 0,

    // exerciseData       /api/v1/exercises
    // changeData         /api/v1/topicversion/edit/changelist
    // defaultMapLayout   /api/v1/topicversion/default/maplayout
    // editMapLayout      /api/v1/topicversion/edit/maplayout
    init: function(exerciseData, changeData, defaultMapLayout, editMapLayout) {
        // resize the map on window resize
        $(window).resize(function() {
            KMapEditor.resize();
        });
        KMapEditor.resize();

        // indicate which view we're in
        if (window.location.hash === "#default") {
            $("span.breadcrumbs_nav>a").removeClass("selected");
            $("span.breadcrumbs_nav>a#select-view-mode").addClass("selected");
        } else if (window.location.hash === "#viewedit") {
            $("span.breadcrumbs_nav>a").removeClass("selected");
        } else {
            $("span.breadcrumbs_nav>a").removeClass("selected");
            $("span.breadcrumbs_nav>a#select-edit-mode").addClass("selected");
        }

        KMapEditor.enableMapPanning();
        KMapEditor.enableMarqueeSelect();

        // Helper method to get exercise by name
        exerciseData.get = function(search) {
            var array = this;
            var index = _.memoize(function(name) {
                var idx = $.map(array, function(ex, n) {
                    if (ex.name === name) {
                        return n;
                    }
                });
                return idx[0];
            })(search);
            return this[index];
        };

        // reference to the default version
        KMapEditor.defaultVersion = exerciseData;
        KMapEditor.defaultMap = defaultMapLayout;

        // Helper method to get topic by name
        $.each([defaultMapLayout, editMapLayout], function(n, layout) {
            if (layout)
                layout.get = function(search) {
                    var array = this.topics;
                    return (search in array) ? array[search] : ""
                };
        })

        // deep copy the default version and apply the edit version's diff to it
        $.extend(true, KMapEditor.editVersion, exerciseData);
        $.each(changeData, function(n, change) {
            if (change.content.kind === "Exercise") {
                var exercise = KMapEditor.editVersion.get(change.content.name);
                $.each(change.content_changes, function(key, val) {
                    try {
                        exercise[key] = val;
                    } catch(e) {
                        console.error("Can't find ex: " + change.content.name);
                    }
                });
            }
        });
        // If there's no edit maplayout, deep copy the default maplayout
        if (editMapLayout == null) {
            $.extend(true, KMapEditor.editMap, defaultMapLayout);
        } else {
            KMapEditor.editMap = editMapLayout;
        }

        // deep copy the edit version to the candidate version
        $.extend(true, KMapEditor.candidateVersion, KMapEditor.editVersion);
        $.extend(true, KMapEditor.candidateMap, KMapEditor.editMap);

        // populate the prereq/covered dropdowns
        KMapEditor.populateExerciseLists();


        $("span.breadcrumbs_nav>a").click(function(event) {
            $("span.breadcrumbs_nav>a").removeClass("selected");
            $(this).addClass("selected");
            if (this.id === "select-view-mode") {
                KMapEditor.viewDefaultVersion();
            } else if (this.id === "select-edit-mode") {
                KMapEditor.editCandidateVersion();
            }
        });

        $("div.zoom-button").click(function(event) {
            var newZoomLevel = KMapEditor.zoomLevel;
            if (this.id === "zoom-exercise") {
                newZoomLevel = KMapEditor.ZOOM_EXERCISES;
            } else if (this.id === "zoom-hybrid") {
                newZoomLevel = KMapEditor.ZOOM_HYBRID;
            } else if (this.id === "zoom-topic") {
                newZoomLevel = KMapEditor.ZOOM_TOPICS;
                // hide the form since we can't edit topics yet :(
                KMapEditor.updateForm(null);
            }
            if (KMapEditor.zoomLevel !== newZoomLevel) {
                KMapEditor.setZoom(newZoomLevel);
                KMapEditor.drawMap();
            }
        });


        $("input[name='pretty_display_name']").bind("keyup", function(event) {
            if (KMapEditor.selected.length === 1) {
                KMapEditor.exercises.get(KMapEditor.selected[0]).pretty_display_name = $(event.target).val();
            }
        });
        $("input[name='file_name']").bind("keyup", function(event) {
            if (KMapEditor.selected.length === 1) {
                KMapEditor.exercises.get(KMapEditor.selected[0]).file_name = $(event.target).val();
            }
        });
        $("#live_yes").click(function(event) {
            KMapEditor.exercises.get(KMapEditor.selected[0]).live = true;
            $("img[src='" + KMapEditor.IMG_SELECTED_DEV + "']")
                .removeClass("ex-dev")
                .addClass("ex-live")
                .attr({"src": KMapEditor.IMG_SELECTED});
        });
        $("#live_no").click(function(event) {
            KMapEditor.exercises.get(KMapEditor.selected[0]).live = false;
            $("img[src='" + KMapEditor.IMG_SELECTED + "']")
                .removeClass("ex-live")
                .addClass("ex-dev")
                .attr({"src": KMapEditor.IMG_SELECTED_DEV});
        });
        $("input[name='short_display_name']").bind("keyup", function(event) {
            if (KMapEditor.selected.length === 1) {
                KMapEditor.exercises.get(KMapEditor.selected[0]).short_display_name = $(event.target).val();
            }
        });
        $("input[name='seconds_per_fast_problem']").bind("keyup", function(event) {
            if (KMapEditor.selected.length === 1) {
                KMapEditor.exercises.get(KMapEditor.selected[0]).seconds_per_fast_problem = $(event.target).val();
            }
        });
        $("#add-prereq").change(function(event) {
            KMapEditor.addPrereq();
        });
        $("#add-cover").change(function(event) {
            KMapEditor.addCover();
        });

        $('#add-video-input').placeholder();
        initAutocomplete("#add-video-input", false, KMapEditor.addVideo, true, {
            includeVideos: true,
            includeExercises: false,
            addTypePrefix: false
        });

        $('#find-exercise').placeholder();
        initAutocomplete("#find-exercise", false, KMapEditor.findExercise, true, {
            includeVideos: false,
            includeExercises: true,
            addTypePrefix: false
        });

        $("#save-button").click(function() {
            $(".exercise-properties input").prop("disabled", true);
            $(".exercise-properties select").prop("disabled", true);
            $("#save-button").removeClass("green");
            $("#save-button").addClass("disabled");
            $("#map-edit-message").text("Saving changes").show();
            var changedTopics = []
            $.each(KMapEditor.candidateMap.topics, function(topicid, topic) {
                if (topic.x != KMapEditor.editMap.get(topicid).x ||
                    topic.y != KMapEditor.editMap.get(topicid).y)
                {
                  changedTopics.push(topic)
                }
            });

            var changedExercises = [];
            $.each(KMapEditor.candidateVersion, function(n, exercise) {
                if (KMapEditor.isDirty(exercise)) {
                    changedExercises.push(exercise);
                }
            });

            if (changedExercises.length === 0 && changedTopics.length === 0) {

                $("#map-edit-message").text("No changes").delay(1000).fadeOut(400);
                $(".exercise-properties input").prop("disabled", false);
                $(".exercise-properties select").prop("disabled", false);
                $("#save-button").addClass("green");
                $("#save-button").removeClass("disabled");
            }

            //Is here to be called after async setting the topics
            function save_exercises() {
                var complete = 0;
                $.each(changedExercises, function(n, exercise) {
                    var change = {
                        "name": exercise.name,
                        "pretty_display_name": exercise.pretty_display_name,
                        "file_name": exercise.file_name,
                        "live": exercise.live,
                        "h_position": exercise.h_position,
                        "v_position": exercise.v_position,
                        "seconds_per_fast_problem": exercise.seconds_per_fast_problem,
                        "short_display_name": exercise.short_display_name,
                        "covers": exercise.covers,
                        "prerequisites": exercise.prerequisites,
                        "related_video_readable_ids": exercise.related_video_readable_ids
                    };

                    $.ajax({
                        url: "/api/v1/topicversion/edit/exercises/" + exercise.name,
                        type: "PUT",
                        data: JSON.stringify(change),
                        contentType: "application/json; charset=utf-8",
                        success: function(result) {
                            complete += 1;
                            $("#map-edit-message").text("Saving changes to exercises (" +
                                    complete + "/" + changedExercises.length + ")");
                            if (complete >= changedExercises.length) {
                                location.reload();
                            }
                        }
                    });
                });
            }
            if (changedTopics.length) {
                var topics = {};
                $.each(KMapEditor.candidateMap.topics, function(n, topic) {
                    topics[topic.standalone_title] = {
                        icon_url: topic.icon_url,
                        id: topic.id,
                        standalone_title: topic.standalone_title,
                        x: topic.x,
                        y: topic.y
                    };
                })
                $.ajax({
                    url: "/api/v1/maplayout",
                    type: "PUT",
                    data: JSON.stringify({ polylines: [], topics: topics}),
                    contentType: "application/json; charset=utf-8",
                    success: function(result) {
                        $("#map-edit-message").text("Saving changes to maplayout");
                        if (changedExercises.length === 0)
                            location.reload();
                        else
                            save_exercises();
                    }
                });
            } else if (changedExercises.length) {
                save_exercises();
            }
            return false;
        });

        // show the default version, edit version, or local changes depending on url fragment
        if (window.location.hash === "#default") {
            KMapEditor.viewDefaultVersion();
        } else if (window.location.hash === "#viewedit") {
            KMapEditor.viewEditVersion();
        } else {
            KMapEditor.editCandidateVersion();
        }
    },

    resize: function() {
        var containerHeight = $(window).height();
        var yTopPadding = $("#map-edit-container").offset().top;
        var newHeight = containerHeight - (yTopPadding + 39);
        $("#map-edit-container").height(newHeight);
    },


    enableMapPanning: function() {
        var moved;
        var startX;
        var startY;
        var panning = false;

        $("#map").bind("mousedown", function(event) {
            if ($(event.target).hasClass("exercise")) {
                return;
            }
            if (!event.shiftKey) {
                startX = event.pageX - parseInt($("#map").css("margin-left"));
                startY = event.pageY - parseInt($("#map").css("margin-top"));
                moved = false;
                panning = true;
                return false;
            }
        });

        $(document).bind("mousemove mouseup", function(event) {
            if (panning) {
                $("#map").css({
                    "margin-top": event.pageY - startY,
                    "margin-left": event.pageX - startX
                });
                if (event.type === "mouseup") {
                    panning = false;
                    if (moved) {
                        KMapEditor.saveMapCoords();
                    } else {
                        KMapEditor.updateForm(null);
                        $(".exercise-label").removeClass("exercise-selected");
                        $("img.ex-live").attr({src: KMapEditor.IMG_LIVE});
                        $("img.ex-dev").attr({src: KMapEditor.IMG_DEV});
                        KMapEditor.selected = [];
                    }
                } else {
                    moved = true;
                }
                return false;
            }
        });
    },

    enableMarqueeSelect: function() {
        var startX;
        var startY;
        var selecting = false;
        var marquee = $("<div>")
            .zIndex(1001)
            .css({
                "position": "absolute",
                "border": "1px red dashed"
            })
            .hide().appendTo($("#map-container"));

        $("#map").bind("mousedown", function(event) {
            if ($(event.target).hasClass("exercise")) {
                return;
            }
            if (event.shiftKey) {
                startX = event.pageX - parseInt($("#map").css("margin-left"));
                startY = event.pageY - parseInt($("#map").css("margin-top"));
                selecting = true;
                marquee.css({
                    "left": (event.pageX - $("#map-container").offset().left) + "px",
                    "top": (event.pageY - $("#map-container").offset().top) + "px",
                    "width": "0",
                    "height": "0"
                }).show();
                return false;
            }
        });

        $(document).bind("mousemove mouseup", function(event) {
            if (selecting) {
                var minx = Math.min(startX + parseInt($("#map").css("margin-left")), event.pageX);
                var maxx = Math.max(startX + parseInt($("#map").css("margin-left")), event.pageX);
                var miny = Math.min(startY + parseInt($("#map").css("margin-top")), event.pageY);
                var maxy = Math.max(startY + parseInt($("#map").css("margin-top")), event.pageY);
                marquee.css({
                    "left": (minx - $("#map-container").offset().left) + "px",
                    "top": (miny - $("#map-container").offset().top) + "px",
                    "width": (maxx - minx) + "px",
                    "height": (maxy - miny) + "px"
                });
                if (event.type === "mouseup") {
                    selecting = false;
                    marquee.hide();
                    var elements = $("div.ui-draggable").map(function(n, el) {
                        if ($(el).offset().left > minx &&
                            $(el).offset().left < maxx &&
                            $(el).offset().top > miny &&
                            $(el).offset().top < maxy) return el;
                    });

                    KMapEditor.selected = [];
                    $(".exercise-label").removeClass("exercise-selected");
                    $("img.ex-live").attr({src: KMapEditor.IMG_LIVE});
                    $("img.ex-dev").attr({src: KMapEditor.IMG_DEV});
                    $(elements).each(function(n, el) {
                        var ex = $(el).data("exercise");
                        if (ex !== undefined) {
                            KMapEditor.selected.push(ex.name);
                            $(el).find(".exercise-label").addClass("exercise-selected");
                            $(el).find("img").attr({src: ex.live ? KMapEditor.IMG_SELECTED : KMapEditor.IMG_SELECTED_DEV});
                        }
                    });
                    if (KMapEditor.selected.length === 1) {
                        KMapEditor.updateForm(KMapEditor.selected[0]);
                    } else {
                        KMapEditor.updateForm(null);
                    }
                }
            }
        });
    },


    viewDefaultVersion: function() {
        this.exercises = this.defaultVersion;
        this.maplayout = this.defaultMap;
        this.readonly = true;
        $(".exercise-properties input").prop("disabled", true);
        $(".exercise-properties select").prop("disabled", true);
        $("#save-button").removeClass("green");
        $("#save-button").addClass("disabled");
        this.drawMap();
        if (this.selected.length === 1) {
            this.updateForm(this.selected[0]);
        }
    },

    viewEditVersion: function() {
        this.exercises = this.editVersion;
        this.maplayout = this.editMap;
        this.readonly = true;
        $(".exercise-properties input").prop("disabled", true);
        $(".exercise-properties select").prop("disabled", true);
        $("#save-button").removeClass("green");
        $("#save-button").addClass("disabled");
        this.drawMap();
        if (this.selected.length === 1) {
            this.updateForm(this.selected[0]);
        }
    },

    editCandidateVersion: function() {
        this.exercises = this.candidateVersion;
        this.maplayout = this.candidateMap;
        this.readonly = false;
        $(".exercise-properties input").prop("disabled", false);
        $(".exercise-properties select").prop("disabled", false);
        $("#save-button").addClass("green");
        $("#save-button").removeClass("disabled");
        this.drawMap();
        if (this.selected.length === 1) {
            this.updateForm(this.selected[0]);
        }
    },

    saveMapCoords: function() {
        var mapTop = parseInt($("#map").css("margin-top"));
        var mapLeft = parseInt($("#map").css("margin-left"));
        var mapHeight = $("#map-container").height();
        var mapWidth = $("#map-container").width() - parseInt($("#map-container").css("left"));
        var pos = {
            lat: (0.392 / KMapEditor.Y_SPACING) * (mapTop - KMapEditor.Y_SPACING * KMapEditor.minH -
                    (mapHeight / 2 - KMapEditor.Y_SPACING)),
            lng: (-0.35 / KMapEditor.X_SPACING) * (mapLeft - KMapEditor.X_SPACING * KMapEditor.minV -
                    ((mapWidth - KMapEditor.LABEL_WIDTH) / 2)),
            when: new Date().getTime(),
            zoom: KMapEditor.zoomLevel
        };
        window.localStorage["map_coords:" + USERNAME] = JSON.stringify(pos);
    },

    createCanvas: function() {
        var localCoords = $.parseJSON(window.localStorage["map_coords:" + USERNAME] || "{}");
        if (localCoords.lat === undefined || localCoords.lng === undefined) {
            localCoords = {
                lat: -1.1,
                lng: 1.2,
                zoom: 8
            }
        }
        this.setZoom(localCoords.zoom);

        this.raphael = Raphael($("#map")[0]);
        this.minV = Math.min.apply(Math, $.map(this.exercises, function(ex) { return ex.v_position })) - 50;
        this.minH = Math.min.apply( Math, $.map(this.exercises, function(ex) { return ex.h_position })) - 50;
        var maxV = Math.max.apply( Math, $.map(this.exercises, function(ex) { return ex.v_position })) + 50;
        var maxH = Math.max.apply( Math, $.map(this.exercises, function(ex) { return ex.h_position })) + 50;
        this.raphael.setSize((maxH - this.minH + 2) * this.X_SPACING, (maxV - this.minV + 2) * this.Y_SPACING);

        var mapHeight = $("#map-container").height();
        var mapWidth = $("#map-container").width() - parseInt($("#map-container").css("left"));
        var xCoord = localCoords.lng / 0.35;
        var yCoord = (localCoords.lat / 0.392);
        $("#map").css({
            "margin-top": (yCoord + this.minH) * this.Y_SPACING + (mapHeight / 2 - this.Y_SPACING),
            "margin-left": (-xCoord + this.minV) * this.X_SPACING + ((mapWidth - this.LABEL_WIDTH) / 2)
        });
    },


    X_SPACING: null,
    Y_SPACING: null,
    ICON_SIZE: null,
    LABEL_WIDTH: null,
    IMG_LIVE: null,
    IMG_DEV: null,
    IMG_SELECTED: null,
    IMG_SELECTED_DEV: null,

    setZoom: function(zoom) {
        this.zoomLevel = Math.min(Math.max(zoom, this.ZOOM_TOPICS), this.ZOOM_EXERCISES);
        $("div.zoom-button").removeClass("zoom-select");
        if (this.zoomLevel === this.ZOOM_EXERCISES) {
            this.X_SPACING = 64;
            this.Y_SPACING = 74;
            this.ICON_SIZE = 26;
            this.LABEL_WIDTH = 60;
            $("div#zoom-exercise").addClass("zoom-select");
        } else if (this.zoomLevel === this.ZOOM_HYBRID) {
            this.X_SPACING = 32;
            this.Y_SPACING = 36;
            this.ICON_SIZE = 10;
            this.LABEL_WIDTH = 10;
            $("div#zoom-hybrid").addClass("zoom-select");
        } else {
            this.X_SPACING = 16;
            this.Y_SPACING = 18;
            this.ICON_SIZE = 40;
            this.LABEL_WIDTH = 80;
            $("div#zoom-topic").addClass("zoom-select");
        }
        this.IMG_LIVE = "/images/node-not-started-" + this.ICON_SIZE + ".png";
        this.IMG_DEV = "/images/node-not-started-" + this.ICON_SIZE + "-faded.png";
        this.IMG_SELECTED = "/images/node-complete-" + this.ICON_SIZE + ".png";
        this.IMG_SELECTED_DEV = "/images/node-complete-" + this.ICON_SIZE + "-faded.png";
        var localCoords = $.parseJSON(window.localStorage["map_coords:" + USERNAME] || "{}");
        localCoords.zoom = this.zoomLevel;
        window.localStorage["map_coords:" + USERNAME] = JSON.stringify(localCoords);
    },

    drawMap: function() {
        $("#map").empty();
        this.createCanvas();

        // drop any existing paths
        $.each(this.exercises, function(n, ex) {
            ex.incoming = [];
            ex.outgoing = [];
        });

        // add topics
        if (this.zoomLevel === this.ZOOM_TOPICS || this.zoomLevel === this.ZOOM_HYBRID) {
            $.each(this.maplayout.topics, function(topicId, topic) {
                var newDiv = $("<div>").appendTo($("#map"));
                topic.div = newDiv;
                newDiv.addClass("exercise");
                newDiv.css({
                    "left": Math.round((topic.x - KMapEditor.minV) * KMapEditor.X_SPACING) + "px",
                    "top": Math.round((topic.y - KMapEditor.minH) * KMapEditor.Y_SPACING - 20) + "px",
                    "width": KMapEditor.LABEL_WIDTH + "px",
                    "cursor": KMapEditor.readonly ? "pointer" : "move"
                });
                $("<img>").attr({
                    src: topic.icon_url + "?4"
                }).appendTo(newDiv);
                $("<div>")
                    .addClass("exercise exercise-label")
                    .css({"font-size": "12px", "width": "80px"})
                    .text(topic.standalone_title).appendTo(newDiv);

                if (KMapEditor.zoomLevel === KMapEditor.ZOOM_HYBRID) {
                    newDiv.css({ "width": "80px", "opacity": 0.5 });
                }
                if (KMapEditor.selected.indexOf(topicId) !== -1) {
                    newDiv.find(".exercise-label").addClass("exercise-selected");
                }
                newDiv.bind("mousedown", function(event) {
                    $(".exercise").zIndex(2);
                    newDiv.zIndex(3);
                    if (event.shiftKey) {
                        KMapEditor.updateForm(null);
                        KMapEditor.selected.push(topicId);
                        newDiv.find(".exercise-label").addClass("exercise-selected");
                    } else if (KMapEditor.selected.length <= 1) {
                        $(".exercise-label").removeClass("exercise-selected");
                        newDiv.find(".exercise-label").addClass("exercise-selected");
                        $("img.ex-live").attr({src: KMapEditor.IMG_LIVE});
                        $("img.ex-dev").attr({src: KMapEditor.IMG_DEV});
                        KMapEditor.updateForm(topic.standalone_title);
                    }
                    $("img").addClass("exercise")
                });
                if (!KMapEditor.readonly) {
                    var hStart, vStart;
                    newDiv.draggable({
                        start: function(event, ui) {
                            hStart = topic.x;
                            vStart = topic.y;
                        },
                        drag: function(event, ui) {
                            topic.x = (ui.position.top + KMapEditor.ICON_SIZE / 2) / KMapEditor.Y_SPACING + KMapEditor.minH;
                            topic.y = ui.position.left / KMapEditor.X_SPACING + KMapEditor.minV;
                        },
                        stop: function(event, ui) {
                            topic.y = Math.round(ui.position.top / KMapEditor.Y_SPACING + KMapEditor.minH);
                            topic.x = Math.round(ui.position.left / KMapEditor.X_SPACING + KMapEditor.minV);

                            var hDelta = topic.x - hStart;
                            var vDelta = topic.y - vStart;
                            $.each(KMapEditor.selected, function(n, topicid) {
                                if (topicid !== topic.standalone_title) {
                                   KMapEditor.maplayout.get(topicid).x += hDelta;
                                   KMapEditor.maplayout.get(topicid).y += vDelta;
                                }
                            });
                            $.each(KMapEditor.selected, function(n, topicid) {
                                KMapEditor.maplayout.get(topicid).div.css({
                                    "left": ((KMapEditor.maplayout.get(topicid).x - KMapEditor.minV) * KMapEditor.X_SPACING) + "px",
                                    "top": ((KMapEditor.maplayout.get(topicid).y - KMapEditor.minH) * KMapEditor.Y_SPACING - KMapEditor.ICON_SIZE / 2) + "px"
                                });
                            });
                        }
                    });
                }
            });
        }

        // add polylines
        if (this.zoomLevel === this.ZOOM_TOPICS) {
            $.each(this.maplayout.polylines, function(topicId, polyline) {
                var path = "";
                $.each(polyline.path, function(n, coordinate) {
                    path += Raphael.format( "L{0},{1}",
                        (coordinate.x - KMapEditor.minV) * KMapEditor.X_SPACING + (KMapEditor.LABEL_WIDTH / 2),
                        (coordinate.y - KMapEditor.minH) * KMapEditor.Y_SPACING)
                });
                path = "M" + path.substr(1);
                KMapEditor.raphael.path(path).attr({"stroke-width": 1, "stroke": "#999"});
            });
        }

        // add exercises
        if (this.zoomLevel === this.ZOOM_EXERCISES || this.zoomLevel === this.ZOOM_HYBRID) {
            $.each(this.exercises, function(n, ex) {
                var newDiv = $("<div>").appendTo($("#map"));
                newDiv.addClass("exercise");
                newDiv.css({
                    "left": ((ex.v_position - KMapEditor.minV) * KMapEditor.X_SPACING) + "px",
                    "top": ((ex.h_position - KMapEditor.minH) * KMapEditor.Y_SPACING - KMapEditor.ICON_SIZE / 2) + "px",
                    "width": KMapEditor.LABEL_WIDTH + "px",
                    "cursor": KMapEditor.readonly ? "pointer" : "move"
                });
                $("<img>").attr({
                    src: ex.live ? KMapEditor.IMG_LIVE : KMapEditor.IMG_DEV,
                    width: KMapEditor.ICON_SIZE,
                    height: KMapEditor.ICON_SIZE
                }).addClass("exercise")
                    .addClass(ex.live ? "ex-live" : "ex-dev")
                    .bind("dragstart", function(event) { event.preventDefault(); })
                    .appendTo(newDiv);

                if (KMapEditor.zoomLevel === KMapEditor.ZOOM_EXERCISES) {
                    $("<div>").addClass("exercise exercise-label")
                        .text(ex.display_name)
                        .css({"width": KMapEditor.LABEL_WIDTH + "px"})
                        .appendTo(newDiv);
                }
                newDiv.data("exercise", ex);
                ex.div = newDiv;

                $.each(ex.prerequisites, function(n, prereq) {
                    KMapEditor.addPath(prereq, ex.name);
                });

                if (KMapEditor.selected.indexOf(ex.name) !== -1) {
                    newDiv.find(".exercise-label").addClass("exercise-selected");
                    newDiv.find("img").attr({src: ex.live ? KMapEditor.IMG_SELECTED : KMapEditor.IMG_SELECTED_DEV});
                }
                newDiv.bind("mousedown", function(event) {
                    $(".exercise").zIndex(2);
                    newDiv.zIndex(3);
                    if (event.shiftKey) {
                        KMapEditor.updateForm(null);
                        KMapEditor.selected.push(ex.name);
                        newDiv.find(".exercise-label").addClass("exercise-selected");
                        newDiv.find("img").attr({src: ex.live ? KMapEditor.IMG_SELECTED : KMapEditor.IMG_SELECTED_DEV});
                    } else if (KMapEditor.selected.length <= 1) {
                        $(".exercise-label").removeClass("exercise-selected");
                        newDiv.find(".exercise-label").addClass("exercise-selected");
                        $("img.ex-live").attr({src: KMapEditor.IMG_LIVE});
                        $("img.ex-dev").attr({src: KMapEditor.IMG_DEV});
                        newDiv.find("img").attr({src: ex.live ? KMapEditor.IMG_SELECTED : KMapEditor.IMG_SELECTED_DEV});
                        KMapEditor.updateForm(ex.name);
                    }
                });
                if (!KMapEditor.readonly) {
                    var hStart, vStart;
                    newDiv.draggable({
                        start: function(event, ui) {
                            hStart = ex.h_position;
                            vStart = ex.v_position;
                        },
                        drag: function(event, ui) {
                            ex.h_position = (ui.position.top + KMapEditor.ICON_SIZE / 2) / KMapEditor.Y_SPACING + KMapEditor.minH;
                            ex.v_position = ui.position.left / KMapEditor.X_SPACING + KMapEditor.minV;
                            $.each(ex.incoming, function(n, incoming) {
                                KMapEditor.delPath(incoming[0], ex.name);
                                KMapEditor.addPath(incoming[0], ex.name);
                            });
                            $.each(ex.outgoing, function(n, outgoing) {
                                KMapEditor.delPath(ex.name, outgoing[0]);
                                KMapEditor.addPath(ex.name, outgoing[0]);
                            });
                        },
                        stop: function(event, ui) {
                            ex.h_position = Math.round(ui.position.top / KMapEditor.Y_SPACING + KMapEditor.minH);
                            ex.v_position = Math.round(ui.position.left / KMapEditor.X_SPACING + KMapEditor.minV);

                            var hDelta = ex.h_position - hStart;
                            var vDelta = ex.v_position - vStart;
                            $.each(KMapEditor.selected, function(n, exid) {
                                if (exid !== ex.name) {
                                    KMapEditor.exercises.get(exid).h_position += hDelta;
                                    KMapEditor.exercises.get(exid).v_position += vDelta;
                                }
                            });

                            $.each(KMapEditor.selected, function(n, exid) {
                                $.each(KMapEditor.exercises.get(exid).incoming, function(n, incoming) {
                                    KMapEditor.delPath(incoming[0], exid);
                                    KMapEditor.addPath(incoming[0], exid);
                                });
                                $.each(KMapEditor.exercises.get(exid).outgoing, function(n, outgoing) {
                                    KMapEditor.delPath(exid, outgoing[0]);
                                    KMapEditor.addPath(exid, outgoing[0]);
                                });
                                KMapEditor.exercises.get(exid).div.css({
                                    "left": ((KMapEditor.exercises.get(exid).v_position - KMapEditor.minV) * KMapEditor.X_SPACING) + "px",
                                    "top": ((KMapEditor.exercises.get(exid).h_position - KMapEditor.minH) * KMapEditor.Y_SPACING - KMapEditor.ICON_SIZE / 2) + "px"
                                });
                            });
                            $("#h_position").text(ex.v_position);
                            $("#v_position").text(ex.h_position);
                        }
                    });
                }
            });
        }

    },

    updateForm: function(exerciseName) {
        if ( exerciseName !== null ) {
            this.selected = [exerciseName];
            if (this.exercises.get(exerciseName) == null) return;
            $(".exercise-properties").show();
            $("#ex-title").html(this.exercises.get(exerciseName).display_name);
            $("input[name=pretty_display_name]").val(this.exercises.get(exerciseName).pretty_display_name);
            $("input[name=file_name]").val(this.exercises.get(exerciseName).file_name);
            if (this.exercises.get(exerciseName).live) {
                $("#live_yes").attr("checked", true);
            } else {
                $("#live_no").attr("checked", true);
            }
            $("input[name=short_display_name]").val(this.exercises.get(exerciseName).short_display_name);
            $("#h_position").text(this.exercises.get(exerciseName).v_position);
            $("#v_position").text(this.exercises.get(exerciseName).h_position);
            $("input[name=seconds_per_fast_problem]").val(this.exercises.get(exerciseName).seconds_per_fast_problem);
            $("#prereqs-container").empty();
            $.each(this.exercises.get(exerciseName).incoming, function(n, prereq) {
                if (KMapEditor.readonly) {
                    $("<div>").html(prereq[0]).appendTo($("#prereqs-container"));
                } else {
                    $("<div>").html(prereq[0] + ' (<a href="#" onclick="KMapEditor.deletePrereq(&quot;' + prereq[0] +
                        '&quot;);return false;">remove</a>)').appendTo($("#prereqs-container"));
                }
            });
            $("#covers-container").empty();
            $.each(this.exercises.get(exerciseName).covers, function(n, cover) {
                if (KMapEditor.readonly) {
                    $("<div>").html(cover).appendTo($("#covers-container"));
                } else {
                    $("<div>").html(cover + ' (<a href="#" onclick="KMapEditor.deleteCover(&quot;' + cover +
                        '&quot;);return false;">remove</a>)').appendTo($("#covers-container"));
                }
            });

            $("#related-video-wait").show();
            $("#related-video-control").hide();

            var populateRelatedVideos = function() {
                $("#video-container").empty();
                $.each(KMapEditor.exercises.get(exerciseName).related_video_readable_ids, function(n, video) {
                    if (KMapEditor.readonly) {
                        $("div").html(video).appendTo($("#video-container"));
                    } else {
                        $("<div id='related-video-" + video + "'>").html(video + ' (<a href="#" onclick="KMapEditor.deleteVideo(&quot;' + video +
                            '&quot;);return false;">remove</a>)').appendTo($("#video-container"));
                    }
                });
                $("#video-container").sortable({
                    update: function(event, ui) {
                        KMapEditor.exercises.get(exerciseName).related_video_readable_ids = 
                            $("#video-container").sortable("toArray").map(function(id){
                                return id.substring(14);
                            })
                    }  
                })

                $("#related-video-wait").hide();
                $("#related-video-control").show();
            };

            if (this.exercises.get(exerciseName).related_video_readable_ids === undefined) {
                $.ajax({
                    url: "/api/v1/exercises/" + exerciseName,
                    type: "GET",
                    dataType: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(exerciseData) {
                        KMapEditor.defaultVersion.get(exerciseName).related_video_readable_ids = exerciseData.related_video_readable_ids.slice();
                        KMapEditor.editVersion.get(exerciseName).related_video_readable_ids = exerciseData.related_video_readable_ids.slice();
                        KMapEditor.candidateVersion.get(exerciseName).related_video_readable_ids = exerciseData.related_video_readable_ids.slice();
                        populateRelatedVideos();
                    }
                });
            } else {
                populateRelatedVideos();
            }
        } else {
            $("#ex-title").html("");
            $(".exercise-properties").hide();
        }
    },

    isDirty: function(exercise) {
        var oldExercise = KMapEditor.editVersion.get(exercise.name);
        return (exercise.live !== oldExercise.live ||
                exercise.pretty_display_name !== oldExercise.pretty_display_name ||
                exercise.file_name !== oldExercise.file_name ||
                exercise.h_position !== oldExercise.h_position ||
                exercise.v_position !== oldExercise.v_position ||
                exercise.seconds_per_fast_problem !== oldExercise.seconds_per_fast_problem ||
                exercise.short_display_name !== oldExercise.short_display_name ||
                JSON.stringify(exercise.covers) !== JSON.stringify(oldExercise.covers) ||
                JSON.stringify(exercise.prerequisites) !== JSON.stringify(oldExercise.prerequisites) ||
                JSON.stringify(exercise.related_video_readable_ids) !== JSON.stringify(oldExercise.related_video_readable_ids));
    },

    addPath: function(src, dst) {
        if (this.exercises.get(src) === undefined) {   
            console.error("Can't find ex: " + src);
            return;
        }
        var set = this.raphael.set();
        set.push(this.raphael.path(Raphael.format( "M{0},{1}L{2},{3}",
                (this.exercises.get(src).v_position - this.minV) * this.X_SPACING + (this.LABEL_WIDTH / 2),
                (this.exercises.get(src).h_position - this.minH) * this.Y_SPACING,
                (this.exercises.get(dst).v_position - this.minV) * this.X_SPACING + (this.LABEL_WIDTH / 2),
                (this.exercises.get(dst).h_position - this.minH) * this.Y_SPACING
            )).attr({
                "stroke-width": 1,
                "stroke": "#999"
            })
        );
        this.exercises.get(dst).incoming.push([src, set]);
        this.exercises.get(src).outgoing.push([dst, set]);
    },

    delPath: function(src, dst) {
        var newOutgoing = $.map(this.exercises.get(src).outgoing, function(ex) { if (ex[0] !== dst) return [ex]; });
        var newIncoming = $.map(this.exercises.get(dst).incoming, function(ex) { if (ex[0] !== src) return [ex]; });
        var outElement = $.map(this.exercises.get(src).outgoing, function(ex) { if (ex[0] === dst) return ex[1]; });
        var inElement = $.map(this.exercises.get(dst).incoming, function(ex) { if (ex[0] === src) return ex[1]; });
        outElement[0].remove();
        inElement[0].remove();
        this.exercises.get(src).outgoing = newOutgoing;
        this.exercises.get(dst).incoming = newIncoming;
    },

    populateExerciseLists: function() {
        var sortedExercises = $.map(this.editVersion, function(ex) { return ex.name; });
        sortedExercises.sort();
        $.each(sortedExercises, function(n, ex) {
            $("<option>").attr("value", ex).text(ex).appendTo($("#add-prereq"));
            $("<option>").attr("value", ex).text(ex).appendTo($("#add-cover"));
        });
    },


    addPrereq: function() {
        this.exercises.get(this.selected[0]).prerequisites.push($("#add-prereq").val());
        this.addPath($("#add-prereq").val(), this.selected[0]);
        this.updateForm(this.selected[0]);
        $("#add-prereq").val(0);
    },

    deletePrereq: function(prereq) {
        this.exercises.get(this.selected[0]).prerequisites =
                $.map(this.exercises.get(this.selected[0]).prerequisites, function(p) {
            if (p !== prereq) {
                return p;
            }
        });
        this.delPath(prereq, this.selected[0]);
        this.updateForm(this.selected[0]);
    },

    addCover: function() {
        this.exercises.get(this.selected[0]).covers.push($("#add-cover").val());
        this.updateForm(this.selected[0]);
        $("#add-cover").val(0);
    },

    deleteCover: function(cover) {
        this.exercises.get(this.selected[0]).covers = $.map(this.exercises.get(this.selected[0]).covers, function(c) {
            if (c !== cover) {
                return c;
            }
        });
        this.updateForm(this.selected[0]);
    },

    addVideo: function(video) {
        KMapEditor.exercises.get(KMapEditor.selected[0]).related_video_readable_ids.push(video.value.slice(7));
        KMapEditor.updateForm(KMapEditor.selected[0]);
        $("#add-video-input").val("");
    },

    deleteVideo: function(video) {
        this.exercises.get(this.selected[0]).related_video_readable_ids = $.map(this.exercises.get(this.selected[0]).related_video_readable_ids, function(v) {
            if (v !== video) {
                return v;
            }
        });
        this.updateForm(this.selected[0]);
    },

    findExercise: function(exercise) {
        ex = KMapEditor.exercises.get(exercise.value.slice(10));
        var mapHeight = $("#map-container").height();
        var mapWidth = $("#map-container").width() - parseInt($("#map-container").css("left"));
        $("#map").css({
            "margin-top": (-ex.h_position + KMapEditor.minH) * KMapEditor.Y_SPACING + (mapHeight / 2 - KMapEditor.Y_SPACING),
            "margin-left": (-ex.v_position + KMapEditor.minV) * KMapEditor.X_SPACING + ((mapWidth - KMapEditor.LABEL_WIDTH) / 2)
        });
        KMapEditor.saveMapCoords();
        KMapEditor.selected = [ex.name];
        KMapEditor.updateForm(ex.name);
        $(".exercise-label").removeClass("exercise-selected");
        $("img.ex-live").attr({src: KMapEditor.IMG_LIVE});
        $("img.ex-dev").attr({src: KMapEditor.IMG_DEV});
        ex.div.find(".exercise-label").addClass("exercise-selected");
        ex.div.find("img").attr({src: ex.live ? KMapEditor.IMG_SELECTED : KMapEditor.IMG_SELECTED_DEV});
        $("#find-exercise").val("");
    }
};


$(document).ready(function() {

    $("#map-edit-message").text("Getting exercise data").show();
    $.getJSON("/api/v1/exercises", function(exerciseData) {
        $("#map-edit-message").text("Getting unpublished changes");
        $.getJSON("/api/v1/topicversion/edit/changelist", function(changeData) {
            $("#map-edit-message").text("Getting default map layout");
            $.getJSON("/api/v1/topicversion/default/maplayout", function(defaultMapLayout) {
                $("#map-edit-message").text("Getting map layout changes");
                $.getJSON("/api/v1/topicversion/edit/maplayout", function(editMapLayout) {
                    $("#map-edit-message").hide();
                    KMapEditor.init(exerciseData, changeData, defaultMapLayout, editMapLayout);
                });
            });
        });
    });


});
