function KnowledgeMapInitGlobals() {

    window.KnowledgeMapGlobals = {

        colors: {
            blue: "#0080C9",
            green: "#8EBE4F",
            red: "#E35D04",
            gray: "#FFFFFF"
        },

        iconClasses: {
            exercise: {
                Proficient: "node-complete",
                Review: "node-review",
                Suggested: "node-suggested",
                Normal: "node-not-started"
            }
        },

        coordsHome: { lat: -2.064844, lng: 0.736268, zoom: 6, when: 0 },
        latMin: 90,
        latMax: -90,
        lngMin: 180,
        lngMax: -180,
        nodeSpacing: {lat: 0.392, lng: 0.35},
        options: {
            getTileUrl: function(coord, zoom) {
                // Sky tiles example from
                // http://gmaps-samples-v3.googlecode.com/svn/trunk/planetary-maptypes/planetary-maptypes.html
                return "/images/map-tiles/field_" + Math.floor(Math.random() * 4 + 1) + ".jpg";
            },
            tileSize: new google.maps.Size(256, 256),
            maxZoom: 9,
            minZoom: 6,
            isPng: false
        },

        xyToLatLng: function(x, y) {
            return new google.maps.LatLng(
                    -1 * (y - 1) * KnowledgeMapGlobals.nodeSpacing.lat, x * KnowledgeMapGlobals.nodeSpacing.lng
            );
        }
    };
}

function KnowledgeMapDrawer(container, knowledgeMap) {
    var self = this;

    this.container = container;
    this.knowledgeMap = knowledgeMap;

    this.init = function() {

        $("#" + this.container + " .toggle-drawer").click(function() { self.toggle(); return false;});

        $(window).resize(function() {self.resize();});
        this.resize();
    };

    this.isExpanded = function() {
        var sCSSLeft = $("#" + this.container + " .dashboard-drawer").css("left").toLowerCase();
        return sCSSLeft === "0px" || sCSSLeft === "auto" || sCSSLeft === "";
    };

    this.toggle = function() {

        if (this.fToggling) return;

        var fExpanded = this.isExpanded();

        var jelDrawer = $("#" + this.container + " .dashboard-drawer");
        var leftDrawer = fExpanded ? -1 * (jelDrawer.width() + 20) : 0;

        var jelTitle = $("#" + this.container + " .dashboard-title");
        var leftTitle = fExpanded ? -1 * (jelTitle.width() + 10) : 5;

        jelTitle.animate({left: leftTitle}, 500);

        this.fToggling = true;
        jelDrawer.animate({left: leftDrawer}, 500, function() {self.fToggling = false;});

        if (self.knowledgeMap) {
            var leftMap = (fExpanded ? 0 : 340);
            $("#" + this.container + " .map-canvas").animate(
                {marginRight: leftMap + "px", left: leftMap + "px"},
                500,
                _.bind(self.triggerResize, self));
        }
    };

    this.resize = function() {
        var context = $("#" + this.container);

        // Resize map contents
        var jelMapContent = $(".dashboard-drawer", context)
            .add(".dashboard-drawer-inner", context)
            .add(".dashboard-map", context);

        var containerHeight = $(window).height();
        var yTopPadding = jelMapContent.offset().top;
        var yBottomPadding = $("#end-of-page-spacer").outerHeight(true);
        var newHeight = containerHeight - (yTopPadding + yBottomPadding);

        jelMapContent.height(newHeight);

        // Account for padding in the dashboard drawer and review link
        var adjustment = 20 + $("#dashboard-review-exercises").height();
        var jelDrawerInner = $(".dashboard-drawer-inner", context);
        jelDrawerInner.height(jelDrawerInner.height() - adjustment);

        self.triggerResize();
    };

    this.triggerResize = function() {
        if (self.knowledgeMap && self.knowledgeMap.map) {
            google.maps.event.trigger(self.knowledgeMap.map, "resize");
        }
    };

    this.init();
}

function KnowledgeMap(params) {

    if (typeof google === "undefined") {
        alert("Zorg dat browser extensies of add-on's die google.com blokkeren worden uitgeschakeld,\n" +
                "dit is nodig om iktel.nl oefeningen te tonen.\n\nSchakel extensies en add-on's uit en herstart je browser.");
        return;
    }

    if (!window.KnowledgeMapGlobals)
        KnowledgeMapInitGlobals();

    if (!window.com || !window.com.redfin)
        FastMarkerOverlayInit();

    var self = this;

    // This handler exists as a hook to override what happens when an
    // exercise node is clicked. By default, it does nothing.
    this.nodeClickHandler = function(exercise, evt) {
        return true;
    };
    this.updateFilterTimout = null;

    // Models
    this.modelsByName = {}; // fast access to Exercise and Topic models by name
    this.topicPolylineModels = []; // polylines for topics connections
    this.filterSettings = new Backbone.Model({"filterText": "---", "userShowAll": false});
    this.numSuggestedExercises = 0;

    // Views
    this.nodeRowViews = [];
    this.nodeMarkerViews = {};

    // Map
    this.map = null;
    this.overlay = null;
    this.dictNodes = {};
    this.dictEdges = {};
    this.markers = [];
    this.topicPolylines = [];
    this.latLngBounds = null;
    this.fFirstDraw = true;
    this.fCenterChanged = false;
    this.fZoomChanged = false;
    this.fDragging = false;

    this.admin = !!params.admin;
    this.newGoal = !!params.newGoal;

    this.init = function(params) {
        this.containerID = (!!params.container) ? ("#" + params.container) : null;
        this.elementTable = {};

        if (!params.hideDrawer)
            this.drawer = new KnowledgeMapDrawer(params.container, this);


        if (!this.admin) {
            self.getElement("exercise-all-exercises").click(function() { self.toggleShowAll(); });
        }

        this.filterSettings.set({"userShowAll": this.admin});

        Handlebars.registerPartial("knowledgemap-exercise", Templates.get("shared.knowledgemap-exercise")); // TomY TODO do this automatically?

        // Initial setup of topic list
        if (params.topic_graph_json) {
            _.map(params.topic_graph_json.topics, function(dict) {
                dict.admin = this.admin;

                // Index nodes by name
                var topic = new KnowledgeMapModels.Topic(dict);
                this.modelsByName[topic.get("name")] = topic;
                return topic;

            }, this);

            this.topicPolylineModels = _.map(params.topic_graph_json.polylines, function(dict) {
                return new KnowledgeMapModels.Polyline(dict);
            });
        }

        // Initial setup of exercise list from embedded data
        _.map(params.graph_dict_data, function(dict) {
            var invalidForGoal = (
                dict.goal_req ||
                dict.status === "Behaald" ||
                dict.status === "Herhalen"
            );

            if (self.newGoal && invalidForGoal) {
                dict.invalidForGoal = true;
            }

            dict.admin = this.admin;

            // Index nodes by name
            var exercise = new KnowledgeMapModels.Exercise(dict);
            this.modelsByName[exercise.get("name")] = exercise;
            return exercise;

        }, this);

        this.initSidebar();
        this.initMap();
        this.initFilter();
    };

    this.initSidebar = function() {
        var suggestedExercisesContent = this.admin ? null : this.getElement("suggested-exercises-content");
        var allExercisesContent = this.getElement("all-exercises-content");

        // ensure blank elements take up the right amount of space
        var createEl = function() {
            return $("<div>", {"class": "exercise-badge"});
        };

        _.each(this.modelsByName, function(model) {

            // Create views
            var element,
                viewType = model.viewType();

            if (model.get("isSuggested")) {
                element = createEl();
                element.appendTo(suggestedExercisesContent);
                this.nodeRowViews.push(new viewType({
                    model: model,
                    el: element,
                    type: "suggested",
                    admin: this.admin,
                    parent: this
                }));
                this.numSuggestedExercises++;
            }

            element = createEl();
            element.appendTo(allExercisesContent);
            this.nodeRowViews.push(new viewType({
                model: model,
                el: element,
                type: "all",
                admin: this.admin,
                parent: this
            }));
        }, this);

        // use lazy rendering unless all exercises are showing
        if (!this.filterSettings.get("userShowAll")) {
            this.getElement("dashboard-drawer-inner.fancy-scrollbar")
                .on("scroll.inflateVisible", $.proxy(this.inflateVisible, this));
        }

        var handler = function(evt) {
            // as doFilter is running while elements are detached, dimensions
            // will not work. Record the dimensions before we call it.
            var row = _.find(this.nodeRowViews, function(row) { return row.visible; });

            var rowHeight;
            if (row) {
                rowHeight = row.$el.outerHeight(/* includeMargin */ true);
            } else {
                // use a guess because doFilter can't determine this for itself
                rowHeight = 86;
            }
            var screenHeight = this.getElement("dashboard-drawer-inner.fancy-scrollbar").height();

            temporaryDetachElement(this.getElement("exercise-list"), function() {
                this.doFilter(evt, rowHeight, screenHeight);
            }, this);
        };

        this.filterSettings.bind("change", handler, this);
    };

    // this inflates all remaining visible rows. We could maybe improve it more
    // by only inflating the next screenful, but for now just do them all.
    this.queryRowsRendered = false;
    this.inflateVisible = function(evt) {
        if (this.queryRowsRendered) return;
        _.each(this.nodeRowViews, function(rowView) {
            if (rowView.visible && !rowView.inflated) {
                rowView.inflate();
            }
        });
        this.queryRowsRendered = true;

        var inflatedAll = (this.filterSettings.get("userShowAll") &&
                           this.filterSettings.get("filterText"));
        if (inflatedAll) {
            $(".dashboard-drawer-inner.fancy-scrollbar").off("scroll.inflateVisible");
        }
    };

    this.doFilter = function(evt, rowHeight, screenHeight) {
        // only render the rows that are on screen. Overshoot by a little to be
        // sure.
        rowHeight = rowHeight || 0;
        screenHeight = screenHeight || $(".dashboard-drawer-inner.fancy-scrollbar").height();
        screenHeight *= 1.3;

        var renderedHeight = 0;

        var userShowAll = this.filterSettings.get("userShowAll");
        var filterText = this.filterSettings.get("filterText");
        var bounds = this.map.getBounds();
        if (bounds)
            bounds = KnowledgeMapViews.NodeMarker.extendBounds(bounds);

        _.each(this.nodeRowViews, function(row) {

            var exerciseName = row.model.get("lowercaseName");

            // single letter filters have lots of matches, so require exercise
            // name to start with filter
            var filterMatches;
            if (filterText.length == 1) {
                filterMatches = exerciseName[0] == filterText;
            }
            else {
                filterMatches = exerciseName.indexOf(filterText) >= 0;
            }

            var allowVisible = filterText || userShowAll || row.options.type != "all";
            row.visible = allowVisible && filterMatches;

            if (row.visible) {
                // only actually inflate if it's going to be on screen
                if (renderedHeight < screenHeight || this.admin) {
                    if (!row.inflated) {
                        row.inflate();
                    }
                }
                // use css() because show() is somewhat slow
                row.$el.css("display", "block");

                if (rowHeight === 0) {
                    rowHeight = row.$el.outerHeight(/* includeMargin */ true);
                }
                renderedHeight += rowHeight;
            } else {
                row.$el.css("display", "none");
            }

            // filter the item off the map view
            if (row.options.type == "all" && this.nodeMarkerViews[row.nodeName]) {
                this.nodeMarkerViews[row.nodeName].setFiltered(!filterMatches, bounds);
            }
        }, this);

        // let scroll and finishRenderingNodes listeners finish the work later
        this.queryRowsRendered = false;
        this.queryNodesRendered = false;
    };

    this.initMap = function() {
        _.each(this.modelsByName, function(model) {
            // Update map graph
            this.addNode(model.toJSON());
            _.each(model.get("prereqs"), function(prereq) {
                this.addEdge(model.get("name"), prereq);
            }, this);
        }, this);

        var mapElement = this.getElement("map-canvas");
        this.map = new google.maps.Map(mapElement.get(0), {
            mapTypeControl: false,
            streetViewControl: false,
            scrollwheel: true
        });

        var knowledgeMapType = new google.maps.ImageMapType(KnowledgeMapGlobals.options);
        this.map.mapTypes.set("knowledge", knowledgeMapType);
        this.map.setMapTypeId("knowledge");

        // copy over the defaults
        var coords = $.extend({}, KnowledgeMapGlobals.coordsHome);

        // overwrite defaults with localStorage values (if any)
        var localCoords = $.parseJSON(window.localStorage["map_coords:" + USERNAME] || "{}");
        $.extend(coords, localCoords);

        // prefer server values if they're more fresh
        if (params.mapCoords && params.mapCoords.when > coords.when) {
            coords = params.mapCoords;
        }

        if (this.newGoal || this.admin) {
            // Goal and admin UIs always start at exercise-level, for now, until
            // topics are supported.
            coords.zoom = KnowledgeMapGlobals.options.maxZoom - 1;
        }

        this.map.setCenter(new google.maps.LatLng(coords.lat, coords.lng));
        this.map.setZoom(coords.zoom);

        this.layoutGraph();
        this.drawOverlay();

        this.latLngBounds = new google.maps.LatLngBounds(
            new google.maps.LatLng(KnowledgeMapGlobals.latMin, KnowledgeMapGlobals.lngMin),
            new google.maps.LatLng(KnowledgeMapGlobals.latMax, KnowledgeMapGlobals.lngMax));

        _.bindAll(this, "onCenterChange", "onIdle", "finishRenderingNodes", "onDragStart", "onDragEnd");
        google.maps.event.addListener(this.map, "center_changed", this.onCenterChange);
        google.maps.event.addListener(this.map, "idle", this.onIdle);
        google.maps.event.addListener(this.map, "center_changed", this.finishRenderingNodes);
        google.maps.event.addListener(this.map, "dragstart", this.onDragStart);
        google.maps.event.addListener(this.map, "dragend", this.onDragEnd);

        this.delegateNodeEvents();

        this.giveNasaCredit();
        $(window).on("beforeunload", $.proxy(this.saveMapCoords, this));
    };

    this.setNodeClickHandler = function(handler) {
        this.nodeClickHandler = handler;
    };

    /**
     * Delegate all node event listeners to the map's outer container,
     * which never changes. This protects us from needing to reattach
     * node event handlers every time nodes are redrawn due to
     * zoom and pan, which makes for a faster map.
     */
    this.delegateNodeEvents = function() {

        var callViewHandler = function(handler) {
            return function(evt) {
                var view = self.nodeMarkerViews[$(this).attr("data-id")];
                if (view) {
                    view[handler](evt);
                }
            };
        };

        $(".dashboard-map").delegate(".nodeLabel", {
            "click": callViewHandler("click"),
            "mouseenter": function(evt) {
                if (!this.createdPopover) {
                    $(this)
                        .popover({html:true, animation: false, delay: { show: 0, hide: 0 }})
                        .popover("show");
                    this.createdPopover = true;
                }
                return callViewHandler("mouseenter").call(this, evt);
            },
            "mouseleave": callViewHandler("mouseleave")
        });

    };

    this.panToNode = function(dataID) {
        var node = this.dictNodes[dataID];

        // Set appropriate zoom level if necessary
        if (this.map.getZoom() != node.preferredZoom)
            this.map.setZoom(node.preferredZoom);

        // Move the node to the center of the view
        this.map.panTo(node.latLng);
    };

    this.escapeSelector = function(s) {
        return s.replace(/(:|\.)/g, "\\$1");
    };

    this.giveNasaCredit = function() {
        // Setup a copyright/credit line, emulating the standard Google style
        // From
        // http://code.google.com/apis/maps/documentation/javascript/demogallery.html?searchquery=Planetary
        var creditNode = $("<div class='creditLabel'>Image Credit: SDSS, DSS Consortium, NASA/ESA/STScI</div>");
        creditNode[0].index = 0;
        this.map.controls[google.maps.ControlPosition.BOTTOM_RIGHT].push(creditNode[0]);
    };

    this.layoutGraph = function() {

        var zoom = this.map.getZoom();

        var self = this;
        $.each(this.dictNodes, function(key, node) {
            self.drawMarker(node, zoom);
        });

        $.each(this.dictEdges, function(key, rgTargets) {
            for (var ix = 0; ix < rgTargets.length; ix++)
            {
                self.drawEdge(self.dictNodes[key], rgTargets[ix], zoom);
            }
        });

        this.drawTopicPolylines();
    };

    this.getMapClass = function() {
        return "dashboard-map zoom" + this.map.getZoom();
    };

    this.drawOverlay = function() {
        var self = this;
        this.overlay = new com.redfin.FastMarkerOverlay(this.map, this.markers);
        this.overlay.drawOriginal = this.overlay.draw;

        /**
         * .draw is called whenever the visible map needs to be rerendered.
         * This happens when panning across large distances or zooming in and
         * out.
         *
         * This function is critical to the map's performance. It should be
         * highly optimized, and we should be hesitant to slow it down for any
         * reason. If you need to add events or styles to individual map nodes,
         * try to do so by attaching styles and delegated event handlers to the
         * outer map container. See delegateNodeEvents as an example.
         */
        this.overlay.draw = function() {

            this.drawOriginal();

            if (!self.fFirstDraw)
            {
                self.onZoomChange();
            }

            $(self.containerID)
                .find(".dashboard-map")
                    .attr("class", self.getMapClass())
                    .end()
                .find(".nodeLabel")
                    .each(function() {

                        var jel = $(this),
                            exerciseName = jel.attr("data-id"),
                            view = self.nodeMarkerViews[exerciseName];

                        if (view) {

                            view.setElement(jel);

                        } else {

                            view = new KnowledgeMapViews.NodeMarker({
                                model: self.modelsByName[exerciseName],
                                el: $(this),
                                parent: self
                            });
                            self.nodeMarkerViews[exerciseName] = view;

                        }
                    });

            self.fFirstDraw = false;
        };
    };

    this.addNode = function(node) {
        this.dictNodes[node.name] = node;
    };

    this.addEdge = function(source, target) {
        if (!this.dictEdges[source]) this.dictEdges[source] = [];
        var rg = this.dictEdges[source];
        rg[rg.length] = {"target": target};
    };

    this.nodeStatusCount = function(status) {
        var c = 0;
        for (var ix = 1; ix < arguments.length; ix++)
        {
            if (arguments[ix].status == status) c++;
        }
        return c;
    };

    this.drawTopicPolylines = function() {

        var visible = this.map.getZoom() == KnowledgeMapGlobals.options.minZoom;

        this.topicPolylines = _.map(this.topicPolylineModels, function(polylineModel) {

            return new google.maps.Polyline({
                path: polylineModel.get("latLngPath"),
                strokeColor: KnowledgeMapGlobals.colors.gray,
                strokeOpacity: 0.48,
                strokeWeight: 1.0,
                clickable: false,
                map: visible ? this.map : null
            });

        }, this);

    };

    this.drawEdge = function(nodeSource, edgeTarget, zoom) {

        var nodeTarget = this.dictNodes[edgeTarget.target];

        // If either of the nodes is missing, don't draw the edge.
        if (!nodeSource || !nodeTarget) return;

        var coordinates = [
            nodeSource.latLng,
            nodeTarget.latLng
        ];

        var countProficient = this.nodeStatusCount("Voltooid", nodeSource, nodeTarget);
        var countSuggested = this.nodeStatusCount("Aangeraden", nodeSource, nodeTarget);
        var countReview = this.nodeStatusCount("Herhalen", nodeSource, nodeTarget);

        var color = KnowledgeMapGlobals.colors.gray;
        var opacity = 0.48;

        if (countProficient == 2)
        {
            color = KnowledgeMapGlobals.colors.blue;
            opacity = 1.0;
        }
        else if (countProficient == 1 && countSuggested == 1)
        {
            color = KnowledgeMapGlobals.colors.green;
            opacity = 1.0;
        }

        edgeTarget.line = new google.maps.Polyline({
            path: coordinates,
            strokeColor: color,
            strokeOpacity: opacity,
            strokeWeight: 1.0,
            clickable: false,
            map: this.getMapForEdge(edgeTarget, zoom)
        });
    };

    this.drawMarker = function(node, zoom) {

        node.latLng = KnowledgeMapGlobals.xyToLatLng(node.x, node.y);

        var lat = node.latLng.lat(),
            lng = node.latLng.lng();

        if (lat < KnowledgeMapGlobals.latMin) KnowledgeMapGlobals.latMin = lat;
        if (lat > KnowledgeMapGlobals.latMax) KnowledgeMapGlobals.latMax = lat;
        if (lng < KnowledgeMapGlobals.lngMin) KnowledgeMapGlobals.lngMin = lng;
        if (lng > KnowledgeMapGlobals.lngMax) KnowledgeMapGlobals.lngMax = lng;

        var html = [];
        html.push("<a href='", node.url, "' data-id='", node.name, "' class='",
            node.className, "' rel='popover' data-content='Maak oefening:<P><strong>",
            node.display_name, "</strong></p>'>");
        if (node.nodeType === "exercise") {
            var classes = KnowledgeMapGlobals.iconClasses.exercise;
            var iconClass = classes[node.status] || classes.Normal;
            html.push("<div class='node-icon ", iconClass, "'></div>");
        } else {
            html.push("<img class='node-icon' src='", node.iconUrl, "'>");
        }
        html.push("<div class='node-text'>", node.display_name, "</div></a>");

        var marker = new com.redfin.FastMarker("marker-" + node.name, node.latLng, html, "", 1, 0, 0);

        this.markers[this.markers.length] = marker;
    };

    this.getMapForEdge = function(edge, zoom) {
        return (zoom != KnowledgeMapGlobals.options.minZoom) ? this.map : null;
    };

    this.highlightNode = function(node_name, highlight) {
        var markerView = this.nodeMarkerViews[node_name];
        if (markerView)
            markerView.setHighlight(highlight);
    };

    this.onZoomChange = function() {

        var zoom = this.map.getZoom();

        if (zoom < KnowledgeMapGlobals.options.minZoom) return;
        if (zoom > KnowledgeMapGlobals.options.maxZoom) return;

        this.fZoomChanged = true;

        //remove all popovers
        $(".popover").remove();

        // Set visibility of exercise-level polylines
        var self = this;
        $.each(this.dictEdges, function(idx, rgTargets) {
            for (var ix = 0; ix < rgTargets.length; ix++)
            {
                var line = rgTargets[ix].line;
                if (line == null) return;

                var map = self.getMapForEdge(rgTargets[ix], zoom);
                if (line.getMap() != map) line.setMap(map);
            }
        });

        // Set visibility of topic-level polylines
        _.each(this.topicPolylines, function(polyline) {
            var visible = zoom === KnowledgeMapGlobals.options.minZoom;

            if (visible !== !!(polyline.getMap())) {
                polyline.setMap(visible ? this.map : null);
            }
        }, this);

    };

    this.getMapCoords = function() {
        var center = this.map.getCenter();

        var coords = {
            "lat": center.lat(),
            "lng": center.lng(),
            "zoom": this.map.getZoom(),
            "when": +(new Date) // Date.now() not present on ie8
        };

        return coords;

    };

    this.saveMapCoords = function() {

        if (this.newGoal) {
            // Don't persist K.M. position when creating new goal
            return;
        }

        // TODO this may not work, could post synchronously to fix, but it's not critical
        $.post("/savemapcoords", this.getMapCoords());
    };

    this.onDragStart = function() {
        this.fDragging = true;
    };

    this.onDragEnd = function() {
        // Turn off dragging flag after this event and
        // any click event associated w/ the current mouseclick
        // are done firing.
        setTimeout($.proxy(function() {
                this.fDragging = false;
            }, this),
        1);
    };

    this.onIdle = function() {

        if (!this.fCenterChanged && !this.fZoomChanged)
            return;

        if (this.newGoal) {
            // Don't persist K.M. position when creating new goal
            return;
        }

        // Panning by 0 pixels forces a redraw of our map's markers
        // in case they aren't being rendered at the correct size.
        this.map.panBy(0, 0);

        if (window.localStorage && window.JSON) {
            var pos = this.getMapCoords();
            window.localStorage["map_coords:" + USERNAME] = JSON.stringify(pos);
        }
    };

    this.queryNodesRendered = true;
    this.finishRenderingNodes = function(evt) {
        if (this.queryNodesRendered) return;
        this.queryNodesRendered = true;

        _.each(this.nodeRowViews, function(row) {
            if (row.options.type == "all" && this.nodeMarkerViews[row.nodeName]) {
                this.nodeMarkerViews[row.nodeName].updateAppearance();
            }
        }, this);
    };

    this.onCenterChange = function() {

        this.fCenterChanged = true;

        var center = this.map.getCenter();
        if (this.latLngBounds.contains(center)) {
            return;
        }

        var C = center;
        var X = C.lng();
        var Y = C.lat();

        var AmaxX = this.latLngBounds.getNorthEast().lng();
        var AmaxY = this.latLngBounds.getNorthEast().lat();
        var AminX = this.latLngBounds.getSouthWest().lng();
        var AminY = this.latLngBounds.getSouthWest().lat();

        if (X < AminX) {X = AminX;}
        if (X > AmaxX) {X = AmaxX;}
        if (Y < AminY) {Y = AminY;}
        if (Y > AmaxY) {Y = AmaxY;}

        this.map.setCenter(new google.maps.LatLng(Y, X));
    };

    // Filtering

    this.initFilter = function() {
        self.getElement("dashboard-filter-text").keyup(function() {
            if (self.updateFilterTimeout == null) {
                self.updateFilterTimeout = setTimeout(function() {
                    self.updateFilter();
                    self.updateFilterTimeout = null;
                }, 250);
            }
        }).placeholder();

        self.getElement("dashboard-filter-clear").click(function() {
            self.clearFilter();
        });
        this.clearFilter();
    };

    this.clearFilter = function() {
        self.getElement("dashboard-filter-text").val("");
        this.updateFilter();
    };

    this.updateFilter = function() {
        var filterText = $.trim(self.getElement("dashboard-filter-text").val().toLowerCase());
        self.filterSettings.set({"filterText": filterText});
        this.postUpdateFilter();
    };

    this.toggleShowAll = function() {
        this.filterSettings.set({"userShowAll": !self.filterSettings.get("userShowAll")});
        this.postUpdateFilter();
    };

    this.postUpdateFilter = function() {
        var counts = { "suggested": 0, "all": 0 };
        var filterText = self.filterSettings.get("filterText");

        $.each(self.nodeRowViews, function(idx, nodeRowView) {
            if (nodeRowView.visible)
                counts[nodeRowView.options.type]++;
        });

        if (filterText && counts.all === 0) {
            self.getElement("exercise-no-results").show();
        } else {
            self.getElement("exercise-no-results").hide();
        }

        // TODO: would be cool to do all this hiding/showing w/ one or two
        // classes on an outer container.
        if (filterText) {
            self.getElement("dashboard-filter-clear").show();
            if (!self.admin) {
                self.getElement("hide-on-dashboard-filter").hide();
                self.getElement("exercise-all-exercises").hide();
            }
            self.getElement("dashboard-all-exercises").find(".exercise-filter-count").html("(Toon " + counts.all + " van " + self.nodeRowViews.length + ")").show();
        } else {
            self.getElement("dashboard-filter-clear").hide();
            self.getElement("dashboard-all-exercises").find(".exercise-filter-count").hide();
            if (!self.admin) {
                self.getElement("hide-on-dashboard-filter").show();
                self.getElement("exercise-all-exercises").show();
                self.getElement("exercise-all-exercises-text").html(self.filterSettings.get("userShowAll") ? "Alles Verbergen" : "Alles Weergeven");
            }
        }
    };

    this.getElement = function(id) {
        if (this.elementTable[id])
            return this.elementTable[id];
        var el = null;
        if (this.containerID)
            el = $(this.containerID + " ." + id);
        else
            el = $("." + id);
        this.elementTable[id] = el;
        if (el.length === 0)
            throw new Error('Ontbrekend element: "' + id + '" in container "' + this.containerID + '"');
        return el;
    };

    this.init(params);
}
