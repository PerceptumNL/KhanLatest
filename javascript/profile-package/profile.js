/**
 * Code to handle the logic for the profile page.
 */
// TODO: clean up all event listeners. This page does not remove any
// event listeners when tearing down the graphs.

var Profile = {
    version: 0,
    email: null,  // Filled in by the template after script load.
    fLoadingGraph: false,
    fLoadedGraph: false,
    profile: null,
    userCardView: null,

    /**
     * Whether the viewer of this profile page has access to modify
     * the settings of the user (only available for parent accounts or
     * for non-child accounts viewing their own profile).
     */
    isSettingsAvailable: false,

    /**
     * Whether the viewer of this profile page has access to view
     * discussion activity by this user.
     */
    isDiscussionAvailable: false,

    /**
     * Whether the viewer of this profile page has access to read the list
     * of coaches for this user.
     */
    isCoachListReadable: false,

    /**
     * Whether the viewer of this profile page has access to modify the list
     * of coaches for this user.
     */
    isCoachListWritable: false,

    /**
     * Whether we can collect sensitive information like the user's
     * name. Users under 13 without parental consent should not be able
     * to enter data.
     */
    isDataCollectible: false,

    /**
     * Whether we show the discussion-specific tutorial intro. If this value
     * is true, we will not show the full profile tutorial, only the very
     * limited "discussion tab" tutorial.
     */
    showDiscussionIntro: false,

    /**
     * The root segment of the URL for the profile page for this user.
     * Will be of the form "/profile/<identifier>" where identifier
     * can be a username, or other identifier sent by the server.
     */
    profileRoot: "",

    /**
     * Overridden w profile-intro.js if necessary
     */
    showIntro_: function() {},

    /**
     * Called to initialize the profile page. Passed in with JSON information
     * rendered from the server. See templates/viewprofile.html for details.
     */
    init: function(json) {
        this.profile = new ProfileModel(json.profileData);
        this.profile.bind("savesuccess", this.onProfileUpdated_, this);
        this.showDiscussionIntro = json.showDiscussionIntro;
        this.isCoachListReadable = json.isCoachListReadable;
        this.isCoachListWritable = json.isCoachListWritable;
        this.isDiscussionAvailable = json.isDiscussionAvailable;
        this.isSettingsAvailable = json.isSettingsAvailable;
        this.displayExplorations = json.displayExplorations;

        var root = json.profileRoot;

        if (window.location.pathname.indexOf("@") > -1) {
            // Note the path should be encoded so that @ turns to %40. However,
            // there is a bug (https://bugs.webkit.org/show_bug.cgi?id=30225)
            // that makes Safari always return the decoded part. Also, if
            // the user manually types in an @ sign, it will be returned
            // decoded. So we need to be robust to this.
            root = decodeURIComponent(root);
        }

        this.profileRoot = root;
        this.isDataCollectible = json.isDataCollectible;
        this.secureUrlBase = json.secureUrlBase;
        UserCardView.countVideos = json.countVideos;
        UserCardView.countExercises = json.countExercises;

        Profile.render();

        Profile.router = new Profile.TabRouter({routes: this.buildRoutes_()});

        // Trigger page load events
        Profile.router.bind("all", Analytics.handleRouterNavigation);

        Backbone.history.start({
            pushState: true,
            root: this.profileRoot
        });

        Profile.showIntro_();

        // Remove goals from IE<=8
        $(".lte8 .goals-accordion-content").remove();

        // Init Highcharts global options
        Highcharts.setOptions({
            credits: {
                enabled: false
            },
            title: {
                text: ""
            },
            subtitle: {
                text: ""
            }
        });

        var navElementHandler = _.bind(this.onNavigationElementClicked_, this);
        // Delegate clicks for tab navigation
        $(".profile-navigation").delegate("a",
                "click", navElementHandler);

        // Delegate clicks for vital statistics time period navigation
        $("#tab-content-vital-statistics").delegate(".graph-date-picker a",
                "click", navElementHandler);

        $("#tab-content-goals").delegate(".graph-picker .type a",
                "click", navElementHandler);

        // Delegate clicks for recent badge-related activity
        $(".achievement .ach-text").delegate("a", "click", function(event) {
            if (!event.metaKey) {
                event.preventDefault();
                Profile.router.navigate("achievements", true);
                $("#achievement-list ul li#category-" + $(this).data("category")).click();
            }
        });

        // Delegate clicks for discussion navigation
        $(".discussion-link")
            .on("click", navElementHandler);

        // Delegate clicks for sorting in discussion
        $(".discussion-sort-links a").on("click", function(event) {
            event.preventDefault();
            var jobj = $(this);
            var jparent = jobj.parent(".discussion-sort-links");
            jparent.find("a").removeClass("selected");
            jobj.addClass("selected");
            Profile.Discussion.sort(jparent.data("feedbackType"),
                jobj.data("value"));
        });

        // Delegate clicks for more-buttons in discussion
        $(".more-button").on("click", function(event) {
            event.preventDefault();
            Profile.Discussion.loadMore(
                $(this).data("feedbackType"));
        });

        // Delegate event handler for tracking clicks on
        // individual questions, answers and comments
        $(".discussion-block, #questions, #answers, #comments")
            .on("click", ".discussion-item a.covering-link",
                Profile.Discussion.trackItemClick);
    },

    /**
     * All the tabs that you could encounter on the profile page.
     */
    subRoutes: {
        "achievements": "showAchievements",
        "goals/:type": "showGoals",
        "goals": "showGoals",
        "vital-statistics": "showVitalStatistics",
        "vital-statistics/problems/:exercise": "showExerciseProblems",
        "vital-statistics/:graph/:timePeriod": "showVitalStatisticsForTimePeriod",
        "vital-statistics/:graph": "showVitalStatistics",
        "coaches": "showCoaches",
        "discussion": "showDiscussion",
        "discussion/questions": "showQuestions",
        "discussion/answers": "showAnswers",
        "discussion/comments": "showComments",
        "discussion/notifications": "showNotificationsTab",

        "explorations": "showExplorations",

        // Not associated with any tab highlighting.
        "settings": "showSettings",

        "": "showDefault",
        // If the user types /profile/username/ with a trailing slash
        // it should work, too
        "/": "showDefault",

        // If any old or crazy vital-statistics route is passed that we no longer support
        // and therefore hasn't matched yet, just show the default vital statistics graph.
        "vital-statistics/*path": "showVitalStatistics",

        // A minor hack to ensure that if the user navigates to /profile without
        // her username, it still shows the default profile screen. Note that
        // these routes aren't relative to the root URL, but will still work.
        "profile": "showDefault",
        "profile/": "showDefault",
        // And for the mobile app... hopefully we can find a better fix.
        "profile?view=mobile": "showDefault"
    },

    /**
     * Generate routes hash to be used by Profile.router
     */
    buildRoutes_: function() {
        var routes = this.subRoutes;
        var n = this.profileRoot.length;

        // Yet another hack: we want to allow /profile/bob to navigate
        // to the profile root, even though the root is /profile/bob/.
        // To do this, we create a pathName without leading/trailing
        // slash to show the default page.
        if (this.profileRoot.lastIndexOf("/") === n - 1) {
            var profileRootNoSlash = this.profileRoot.substr(1, n - 2);
            routes[profileRootNoSlash] = "showDefault";
        }
        return routes;
    },

    /**
     * Handle a change to the profile root.
     */
    onProfileUpdated_: function() {
        var username = this.profile.get("username");
        if (username && Profile.profileRoot != ("/profile/" + username + "/")) {
            // Profile root changed - we need to reload the page since
            // Backbone.router isn't happy when the root changes.
            window.location.replace("/profile/" + username + "/");
        }
    },

    TabRouter: Backbone.Router.extend({
        showDefault: function() {
            Profile.populateActivity().then(function() {
                // Pre-fetch badges, after the activity has been loaded, since
                // they're needed to edit the display-case.
                if (Profile.profile.isEditable()) {
                    Profile.populateAchievements();
                }
            });
            $("#tab-content-user-profile").show().siblings().hide();
            this.activateRelatedTab($("#tab-content-user-profile").attr("rel"));
            this.updateTitleBreadcrumbs();
        },

        showVitalStatistics: function(graph, exercise, timePeriod) {
            var exercise = exercise || "addition_1";
            // Note: the URL's must include the trailing ? so that parameters
            // tacked on later will work.
            var hrefLookup = {
                    "activity": "/profile/graph/activity?",
                    "focus": "/profile/graph/focus?",
                    "skill-progress-over-time": "/profile/graph/exercisesovertime?",
                    "skill-progress": "/api/v1/user/exercises?",
                    "problems": "/profile/graph/exerciseproblems?" +
                                            "exercise_name=" + exercise
                },
                timePeriodLookup = {
                    "today": "&dt_start=today",
                    "yesterday": "&dt_start=yesterday",
                    "last-week": "&dt_start=lastweek&dt_end=today",
                    "last-month": "&dt_start=lastmonth&dt_end=today"
                },
                graph = !!(hrefLookup[graph]) ? graph : "activity",
                timePeriod = !!(timePeriodLookup[timePeriod]) ? timePeriod : "last-week",
                timeURLParameter = timePeriodLookup[timePeriod],
                href = hrefLookup[graph] + timeURLParameter;

            // Known bug: the wrong graph-date-picker item is selected when
            // server man decides to show 30 days instead of the default 7.
            // See redirect_for_more_data in util_profile.py for more on this tragedy.
            $("#tab-content-vital-statistics").show()
                .find(".vital-statistics-description ." + graph).show()
                    .find(".graph-date-picker .tabrow .last-week").addClass("selected")
                        .siblings().removeClass("selected").end()
                    .end()
                    .siblings().hide().end()
                .end().siblings().hide();

            this.activateRelatedTab($("#tab-content-vital-statistics").attr("rel") + " " + graph);
            var prettyGraphName = graph.replace(/-/gi, " ");
            this.updateTitleBreadcrumbs([prettyGraphName]);

            if (Profile.profile.isActivityAccessible()) {
                // If we have access to the profiled person's email, load real data.
                Profile.loadGraph(href, Profile.getBaseRequestParams_());
            } else {
                // Otherwise, show some fake stuff.
                Profile.renderFakeGraph(graph, timePeriod);
            }
        },

        showExerciseProblems: function(exercise) {
            this.showVitalStatistics("problems", exercise);
        },

        showVitalStatisticsForTimePeriod: function(graph, timePeriod) {
            this.showVitalStatistics(graph, null, timePeriod);
            $(".vital-statistics-description ." + graph + " ." + timePeriod).addClass("selected")
                .siblings().removeClass("selected");
        },

        showAchievements: function() {
            Profile.populateAchievements();
            $("#tab-content-achievements").show()
                .siblings().hide();
            this.activateRelatedTab($("#tab-content-achievements").attr("rel"));
            this.updateTitleBreadcrumbs(["Successen"]);
        },

        showGoals: function(type) {
            type = type || "current";
            Profile.populateGoals();

            GoalProfileViewsCollection.showGoalType(type);

            $("#tab-content-goals").show()
                .siblings().hide();
            this.activateRelatedTab($("#tab-content-goals").attr("rel"));
            this.updateTitleBreadcrumbs(["Doelen"]);
        },

        showCoaches: function() {
            Profile.populateCoaches();

            $("#tab-content-coaches").show()
                .siblings().hide();

            this.activateRelatedTab("communitie coaches");
            this.updateTitleBreadcrumbs(["Coaches"]);

            if (Profile.profile.get("isPhantom")) {
                Profile.showNotification("no-coaches-for-phantoms");
            }
        },

        showDiscussion: function(type) {
            type = type || "discussion";

            if (type === "answers") {
                this.updateTitleBreadcrumbs(["Discussie", "Antwoorden"]);
                Profile.Discussion.populateTab("questions");
            }

            else if (type === "questions") {
                this.updateTitleBreadcrumbs(["Discussie", "Vragen"]);
                Profile.Discussion.populateTab("questions");
            }

            else if (type === "comments") {
                this.updateTitleBreadcrumbs(["Discussie", "opmerkingen"]);
                Profile.Discussion.populateTab("comments");
            }

            else if (type === "notifications") {
                this.updateTitleBreadcrumbs(["Discussie", "Opmerkingen"]);
                Profile.Discussion.populateNotifications();
            }

            else {
                this.updateTitleBreadcrumbs(["Discussie"]);
                Profile.Discussion.populateSummary();
            }

            // Show the respective tab, including:
            // #tab-content-discussion, #tab-content-questions,
            // #tab-content-answers, #tab-content-comments
            $("#tab-content-" + type).show()
                .siblings().hide();

            $(".graph-picker").find("." + type).addClass("selected")
                .siblings().removeClass("selected");

            this.activateRelatedTab("community discussion");
        },
        showAnswers: function() {
            this.showDiscussion("answers");
        },
        showQuestions: function() {
            this.showDiscussion("questions");
        },
        showComments: function() {
            this.showDiscussion("comments");
        },
        showNotificationsTab: function() {
            this.showDiscussion("notifications");
        },

        showExplorations: function() {
            if (!Profile.displayExplorations) {
                return this.showDefault();
            }

            $("#tab-content-explorations").show()
                .siblings().hide();

            this.activateRelatedTab("community explorations");
            this.updateTitleBreadcrumbs(["Ontdekkingen"]);

            Profile.populateExplorations();
        },

        settingsIframe_: null,
        showSettings: function() {
            // TODO(benkomalo): maybe settings shouldn't be under a profile
            // URL and should be a dedicated URL...
            if (!Profile.isSettingsAvailable) {
                // This shouldn't happen as there are no UI affordances to get
                // here for someone else's profile, but guard against someone
                // typing in a settings URL for someone else.
                Profile.router.navigate(null, true);
                return;
            }

            // Password change forms need to happen in an iframe since it needs
            // to be POST'ed to a different domain (with https), and redirected
            // back with information on error/success.
            if (!Profile.settingsIframe_) {
                var params = "";
                if (!Profile.profile.get("isSelf")) {
                    params = "?username=" + Profile.profile.get("username");
                }
                Profile.settingsIframe_ = $("<iframe></iframe>")
                        .attr("src", "/pwchange" + params)
                        .attr("frameborder", "0")
                        .attr("scrolling", "no")
                        .attr("allowtransparency", "yes")
                        .attr("id", "settings-iframe")
                        .attr("class", "settings-iframe")
                        .appendTo($("#tab-content-settings"));
            }

            // Show.
            $("#tab-content-settings").show().siblings().hide();
            this.activateRelatedTab("");
            this.updateTitleBreadcrumbs(["Instellingen"]);
        },

        activateRelatedTab: function(rel) {
            $(".profile-navigation a").removeClass("active-tab");
            $("a[rel='" + rel + "']").addClass("active-tab");
        },

        /**
         * Updates the title of the profile page to show breadcrumbs
         * based on the parts in the specified array. Will always pre-pend the profile
         * nickname.
         * @param {Array.<string>} parts A list of strings that will be HTML-escaped
         *     to be the breadcrumbs.
         */
        updateTitleBreadcrumbs: function(parts) {
            $(".profile-notification").hide();

            var sheetTitle = $(".profile-sheet-title"),
                mixpanelEventName = "Profile";

            if (parts && parts.length) {
                var visibleTabs = ["Discussion"];
                var rootCrumb = Profile.profile.get("nickname") || "Profile",
                    crumbs = parts.join(" » ");

                sheetTitle
                    .find(".nickname").text(rootCrumb).end()
                    .find(".page-title").text(" » " + crumbs).end()
                    .show();

                mixpanelEventName += " " + crumbs;

                if (!Profile.profile.isActivityAccessible() &&
                    _.indexOf(visibleTabs, parts[0]) === -1) {
                        Profile.showNotification("public");
                }
            } else {

                // If the profile is private, hide the landing page.
                if (!Profile.profile.get("isPublic") &&
                        !Profile.profile.isActivityAccessible()) {
                    Profile.showNotification("empty-landing-page");
                }

                sheetTitle
                    .find("span").text("").end()
                    .hide();
            }

            // Trigger separate events for each sheet for easier comparisons
            Analytics.trackSingleEvent(mixpanelEventName);
        }
    }),

    /**
     * Navigate the router appropriately,
     * either to change profile sheets or vital-stats time periods.
     */
    onNavigationElementClicked_: function(e) {
        // TODO: Make sure middle-click + windows control-click Do The Right Thing
        // in a reusable way
        if (!e.metaKey) {
            e.preventDefault();
            var route = $(e.currentTarget).attr("href");
            // The navigation elements have the profileRoot in the href, but
            // Router.navigate should be relative to the root.
            if (route.indexOf(this.profileRoot) === 0) {
                route = route.substring(this.profileRoot.length);
            }
            Profile.router.navigate(route, true);
        }
    },

    /**
     * Fetches graph data from the server for the given graph URL.
     * @param {string} href The base graph URL to fetch data for.
     * @param {Object} baseParams An optional parameter for additional
     *     parameters to be sent along with the server request.
     */
    loadGraph: function(href, baseParams) {
        var apiCallbacksTable = {
            "/api/v1/user/exercises": this.renderExercisesTable,
            "/api/v1/exercises": this.renderFakeExercisesTable_
        };
        if (!href) {
            return;
        }

        if (this.fLoadingGraph) {
            _.delay(function() {
                Profile.loadGraph(href, baseParams);
            }, 200);
            return;
        }

        this.fLoadingGraph = true;
        this.fLoadedGraph = false;

        var apiCallback = null;
        for (var uri in apiCallbacksTable) {
            if (href.indexOf(uri) > -1) {
                apiCallback = apiCallbacksTable[uri];
            }
        }

        $.ajax({
            type: "GET",
            url: Timezone.append_tz_offset_query_param(href),
            data: baseParams || {},
            dataType: apiCallback ? "json" : "html",
            success: function(data) {
                Profile.finishLoadGraph(data, apiCallback);
            },
            error: function() {
                Profile.finishLoadGraphError();
            }
        });
        $("#graph-content").html("");
        Profile.showThrobber("graph", true);
    },

    finishLoadGraph: function(data, apiCallback) {
        this.fLoadingGraph = false;
        this.hideThrobber("graph", true);

        var start = (new Date).getTime();
        if (apiCallback) {
            apiCallback(data);
        } else {
            $("#graph-content").html(data);
        }
        var diff = (new Date).getTime() - start;
        KAConsole.log("API call rendered in " + diff + " ms.");

        this.fLoadedGraph = true;
    },

    finishLoadGraphError: function() {
        this.fLoadingGraph = false;
        this.hideThrobber("graph", true);
        this.showNotification("error-graph");
    },

    renderFakeGraph: function(graphName, timePeriod) {
        if (graphName === "activity") {
            ActivityGraph.render(null, timePeriod);
            Profile.fLoadedGraph = true;
        } else if (graphName === "focus") {
            FocusGraph.render();
            Profile.fLoadedGraph = true;
        } else if (graphName === "skill-progress") {
            Profile.loadGraph("/api/v1/exercises");
        } else {
            ExerciseGraphOverTime.render();
            Profile.fLoadedGraph = true;
        }
    },

    generateFakeExerciseTableData_: function(exerciseData) {
        // Generate some vaguely plausible exercise progress data
        return _.map(exerciseData, function(exerciseModel) {
            // See models.py -- hPosition corresponds to the node's vertical position
            var position = exerciseModel["hPosition"],
                totalDone = 0,
                states = {},
                rand = Math.random();
            if (position < 10) {
                if (Math.random() < 0.9) {
                    totalDone = 1;
                    if (rand < 0.5) {
                        states["proficient"] = true;
                    } else if (rand < 0.7) {
                        states["reviewing"] = true;
                    }
                }
            } else if (position < 17) {
                if (Math.random() < 0.6) {
                    totalDone = 1;
                    if (rand < 0.4) {
                        states["proficient"] = true;
                    } else if (rand < 0.7) {
                        states["reviewing"] = true;
                    } else if (rand < 0.75) {
                        states["struggling"] = true;
                    }
                }
            } else {
                if (Math.random() < 0.1) {
                    totalDone = 1;
                    if (rand < 0.2) {
                        states["proficient"] = true;
                    } else if (rand < 0.5) {
                        states["struggling"] = true;
                    }
                }
            }
            return {
                "exerciseModel": exerciseModel,
                "totalDone": totalDone,
                "exerciseStates": states
            };
        });
    },

    renderFakeExercisesTable_: function(exerciseData) {
        // Do nothing if the user switches sheets before /api/v1/exercises responds
        // (The other fake sheets are rendered randomly client-side)

        if (Profile.fLoadedGraph) {
            return;
        }

        var fakeData = Profile.generateFakeExerciseTableData_(exerciseData);

        Profile.renderExercisesTable(fakeData, false);

        $("#module-progress").addClass("empty-chart");
    },

    /**
     * Renders the exercise blocks given the JSON blob about the exercises.
     */
    renderExercisesTable: function(data, bindEvents) {
        var templateContext = [],
            bindEvents = (bindEvents === undefined) ? true : bindEvents,
            isEmpty = true,
            exerciseModels = [];


        for (var i = 0, exercise; exercise = data[i]; i++) {
            var stat = "Not started";
            var color = "";
            var states = exercise["exerciseStates"];
            var totalDone = exercise["totalDone"];

            if (totalDone > 0) {
                isEmpty = false;
            }

            if (states["reviewing"]) {
                stat = "Review";
                color = "review light";
            } else if (states["proficient"]) {
                // TODO: handle implicit proficiency - is that data in the API?
                // (due to proficiency in a more advanced module)
                stat = "Proficient";
                color = "proficient";
            } else if (states["struggling"]) {
                stat = "Struggling";
                color = "struggling";
            } else if (totalDone > 0) {
                stat = "Started";
                color = "started";
            }

            if (!color) {
                color = "transparent";
            }
            var model = exercise["exerciseModel"];
            exerciseModels.push(model);
            templateContext.push({
                "name": model["name"],
                "color": color,
                "status": stat,
                "shortName": model["shortDisplayName"] || model["displayName"],
                "displayName": model["displayName"],
                "progress": Math.floor(exercise["progress"] * 100) + "%",
                "totalDone": totalDone
            });
        }

        if (isEmpty) {
            Profile.renderFakeExercisesTable_(exerciseModels);
            Profile.showNotification("empty-graph");
            return;
        }

        var template = Templates.get("profile.exercise_progress");
        $("#graph-content").html(template({ "exercises": templateContext }));

        if (bindEvents) {
            Profile.hoverContent($("#module-progress .student-module-status"));
            $("#module-progress .student-module-status").click(function(e) {
                $("#info-hover-container").hide();
                // Extract the name from the ID, which has been prefixed.
                var exerciseName = this.id.substring("exercise-".length);
                Profile.router.navigate("vital-statistics/problems/" + exerciseName, true);
            });
        }
    },

    /**
     * Slide down the progress bar into view
     */
    showThrobber: function(which, animated) {
        if (animated) {
            $("#" + which + "-progress-bar")
                .progressbar({value: 100})
                .slideDown("fast");
        }
        else {
            $("#" + which + "-progress-bar")
                .progressbar({value: 100})
                .show();
        }
    },

    /**
     * Slide up the progress bar out of view
     */
    hideThrobber: function(which, animated) {
        if (animated) {
            $("#" + which + "-progress-bar").slideUp("fast");
        }
        else {
            $("#" + which + "-progress-bar").hide();
        }
    },

    /**
     * Show a profile notification
     * Expects the class name of the div to show, such as "error-graph"
     */
    showNotification: function(className) {
        var jel = $(".profile-notification").removeClass("uncover-nav")
                    .removeClass("cover-top");

        if (className === "empty-graph") {
            jel.addClass("uncover-nav");
        } else if (className === "empty-landing-page") {
            jel.addClass("cover-top");
        }

        jel.show()
            .find("." + className).show()
            .siblings().hide();
    },

    hoverContent: function(elements, containerSelector) {
        var lastHoverTime,
            mouseX,
            mouseY;

        containerSelector = containerSelector || "#graph-content";

        elements.hover(
            function(e) {
                var hoverTime = +(new Date()),
                    el = this;
                lastHoverTime = hoverTime;
                mouseX = e.pageX;
                mouseY = e.pageY;

                setTimeout(function() {
                    if (hoverTime !== lastHoverTime) {
                        return;
                    }

                    var hoverData = $(el).children(".hover-data"),
                        html = $.trim(hoverData.html());

                    if (html) {
                        var jelContainer = $(containerSelector),
                            leftMax = jelContainer.offset().left + jelContainer.width() - 150,
                            left = Math.min(mouseX + 15, leftMax),
                            jHoverEl = $("#info-hover-container");

                        if (jHoverEl.length === 0) {
                            jHoverEl = $('<div id="info-hover-container"></div>').appendTo("body");
                        }

                        jHoverEl
                            .html(html)
                            .css({left: left, top: mouseY + 5})
                            .show();
                    }
                }, 100);
            },
            function(e) {
                lastHoverTime = null;
                $("#info-hover-container").hide();
            }
        );
    },

    render: function() {
        var profileTemplate = Templates.get("profile.profile");
        Handlebars.registerHelper("graph-date-picker-wrapper", function(block) {
            this.graph = block.hash.graph;
            return block(this);
        });
        Handlebars.registerPartial("profile_graph-date-picker",
            Templates.get("profile.graph-date-picker"));
        Handlebars.registerPartial("profile_vital-statistics",
            Templates.get("profile.vital-statistics"));
        Handlebars.registerPartial("profile_discussion-sort-links",
            Templates.get("profile.discussion-sort-links"));
        Handlebars.registerPartial("profile_discussion-tab-links",
            Templates.get("profile.discussion-tab-links"));
        Handlebars.registerPartial("profile_discussion-award-icon",
            Templates.get("profile.discussion-award-icon"));

        $("#profile-content").html(profileTemplate({
            profileRoot: this.profileRoot,
            profileData: this.profile.toJSON(),
            isCoachListReadable: this.isCoachListReadable,
            isDiscussionAvailable: this.isDiscussionAvailable,
            countVideos: UserCardView.countVideos,
            countExercises: UserCardView.countExercises,
            displayExplorations: this.displayExplorations
        }));

        // Show only the user card tab,
        // since the Backbone default route isn't triggered
        // when visiting khanacademy.org/profile
        $("#tab-content-user-profile").show().siblings().hide();

        Profile.populateUserCard();

        this.profile.bind("change:nickname", function(profile) {
            var nickname = profile.get("nickname") || "Profile";
            $("#profile-tab-link").text(nickname);
            $(".top-header-links .user-name a").text(nickname);
        });
        this.profile.bind("change:avatarSrc", function(profile) {
            var src = profile.get("avatarSrc");
            $(".profile-tab-avatar").attr("src", src);
            $("#user-info .user-avatar").attr("src", src);
        });
    },

    userCardPopulated_: false,
    populateUserCard: function() {
        if (Profile.userCardPopulated_) {
            return;
        }
        Profile.userCardView = new UserCardView({model: this.profile});
        $(".user-info-container").html(Profile.userCardView.render().el);

        var publicBadgeList = new Badges.BadgeList(
                this.profile.get("publicBadges"));
        publicBadgeList.setSaveUrl("/api/v1/user/badges/public");
        var displayCase = new Badges.DisplayCase({ model: publicBadgeList });
        $(".sticker-book").append(displayCase.render().el);
        Profile.displayCase = displayCase;

        Profile.userCardPopulated_ = true;
    },

    achievementsDeferred_: null,
    populateAchievements: function() {
        if (Profile.achievementsDeferred_) {
            return Profile.achievementsDeferred_;
        }
        // Asynchronously load the full badge information in the background.
        return Profile.achievementsDeferred_ = $.ajax({
            type: "GET",
            url: "/api/v1/user/badges",
            data: Profile.getBaseRequestParams_(),
            dataType: "json",
            success: function(data) {
                if (Profile.profile.isEditable()) {
                    // The display-case is only editable if you're viewing your
                    // own profile

                    // TODO: save and cache these objects
                    var fullBadgeList = new Badges.UserBadgeList();

                    var collection = data["badgeCollections"];
                    $.each(collection, function(i, categoryJson) {
                        $.each(categoryJson["userBadges"], function(j, json) {
                            fullBadgeList.add(new Badges.UserBadge(json));
                        });
                    });
                    Profile.displayCase.setFullBadgeList(fullBadgeList);
                }

                // TODO: make the rendering of the full badge page use the models above
                // and consolidate the information

                var badgeInfo = [
                        {
                            icon: "/images/badges/meteorite-medium.png",
                            className: "bronze",
                            label: "Meteorite"
                        },
                        {
                            icon: "/images/badges/moon-medium.png",
                            className: "silver",
                            label: "Moon"
                        },
                        {
                            icon: "/images/badges/earth-medium.png",
                            className: "gold",
                            label: "Earth"
                        },
                        {
                            icon: "/images/badges/sun-medium.png",
                            className: "diamond",
                            label: "Sun"
                        },
                        {
                            icon: "/images/badges/eclipse-medium.png",
                            className: "platinum",
                            label: "Black Hole"
                        },
                        {
                            icon: "/images/badges/master-challenge-blue.png",
                            className: "master",
                            label: "Challenge"
                        }
                    ];

                Handlebars.registerHelper("toMediumIconSrc", function(category) {
                    return badgeInfo[category].icon;
                });

                Handlebars.registerHelper("toBadgeClassName", function(category) {
                    return badgeInfo[category].className;
                });

                Handlebars.registerHelper("toBadgeLabel", function(category, fStandardView) {
                    var label = badgeInfo[category].label;

                    if (fStandardView) {
                        if (label === "Challenge") {
                            label += " Patches";
                        } else {
                            label += " Badges";
                        }
                    }
                    return label;
                });

                Handlebars.registerPartial(
                        "profile_badge-container",
                        Templates.get("profile.badge-container"));

                $.each(data["badgeCollections"], function(collectionIndex, collection) {
                    $.each(collection["userBadges"], function(badgeIndex, userBadge) {
                        userBadge = Badges.addUserBadgeContext(userBadge);
                    });
                });

                // TODO: what about mobile-view?
                data.fStandardView = true;

                var achievementsTemplate = Templates.get("profile.achievements");
                $("#tab-content-achievements").html(achievementsTemplate(data));

                $("#achievements #achievement-list > ul li").click(function() {
                     var category = $(this).attr("id");
                     var clickedBadge = $(this);

                     $("#badge-container").css("display", "");

                     clickedBadge.siblings().removeClass("selected");

                     if ($("#badge-container > #" + category).is(":visible")) {
                        if (clickedBadge.parents().hasClass("standard-view")) {
                            $("#badge-container > #" + category).slideUp(300, function() {
                                    $("#badge-container").css("display", "none");
                                    clickedBadge.removeClass("selected");
                                });
                        }
                        else {
                            $("#badge-container > #" + category).hide();
                            $("#badge-container").css("display", "none");
                            clickedBadge.removeClass("selected");
                        }
                     }
                     else {
                        var jelContainer = $("#badge-container");
                        var oldHeight = jelContainer.height();
                        $(jelContainer).children().hide();
                        if (clickedBadge.parents().hasClass("standard-view")) {
                            $(jelContainer).css("min-height", oldHeight);
                            $("#" + category, jelContainer).slideDown(300, function() {
                                $(jelContainer).animate({"min-height": 0}, 200);
                            });
                        } else {
                            $("#" + category, jelContainer).show();
                        }
                        clickedBadge.addClass("selected");
                     }
                });

                $("abbr.timeago").timeago();

                // Start with meteorite badges displayed
                $("#category-0").click();

                // TODO: move into profile-goals.js?
                var currentGoals = window.GoalBook.map(function(g) { return g.get("title"); });
                _($(".add-goal")).map(function(elt) {
                    var button = $(elt);
                    var badge = button.closest(".achievement-badge");
                    var goalTitle = badge.find(".achievement-title").text();

                    // remove +goal button if present in list of active goals
                    if (_.indexOf(currentGoals, goalTitle) > -1) {

                        button.remove();

                    // add +goal behavior to button, once.
                    } else {
                        button.one("click", function() {
                            var goalObjectives = _(badge.data("objectives")).map(function(exercise) {
                                return {
                                    "type" : "GoalObjectiveExerciseProficiency",
                                    "internal_id" : exercise
                                };
                            });

                            var goal = new Goal({
                                title: goalTitle,
                                objectives: goalObjectives
                            });

                            window.GoalBook.add(goal);

                            goal.save()
                                .fail(function(err) {
                                    var error = err.responseText;
                                    button.addClass("failure")
                                        .text("oh no!").attr("title", "This goal could not be saved.");
                                    KAConsole.log("Error while saving new badge goal", goal);
                                    window.GoalBook.remove(goal);
                                })
                                .success(function() {
                                    button.text("Goal Added!").addClass("success");
                                    badge.find(".energy-points-badge").addClass("goal-added");
                                });
                        });
                    }
                });
            }
        });
    },

    goalsDeferred_: null,
    populateGoals: function() {
        if (Profile.goalsDeferred_) {
            return Profile.goalsDeferred_;
        }

        if (Profile.profile.isActivityAccessible()) {
            Profile.goalsDeferred_ = $.ajax({
                type: "GET",
                url: "/api/v1/user/goals",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",
                success: function(data) {
                    GoalProfileViewsCollection.render(data);
                }
            });
        } else {
            Profile.renderFakeGoals_();
            Profile.goalsDeferred_ = new $.Deferred();
            Profile.goalsDeferred_.resolve();
        }
        return Profile.goalsDeferred_;
    },

    renderFakeGoals_: function() {
        var exerciseGoal = new Goal(Goal.defaultExerciseProcessGoalAttrs_),
            videoGoal = new Goal(Goal.defaultVideoProcessGoalAttrs_),
            fakeGoalBook = new GoalCollection([exerciseGoal, videoGoal]),
            fakeView = new GoalProfileView({model: fakeGoalBook});

        $("#profile-goals-content").append(fakeView.show().addClass("empty-chart"));
    },

    coachesDeferred_: null,
    populateCoaches: function() {
        if (Profile.coachesDeferred_) {
            return Profile.coachesDeferred_;
        }

        Profile.coachesDeferred_ = Coaches.init(Profile.isCoachListWritable);

        return Profile.coachesDeferred_;
    },

    populateExplorations: function() {
        if (!Profile.explorationsDeferred_) {
            // TODO(jlfwong): This throbber keeps showing up as a grey bar
            // without the orange animation - fix that
            Profile.showThrobber("explorations", true);

            var data = Profile.getBaseRequestParams_();

            // TODO(jlfwong): Conform the scratchpad system to use camelCase
            delete data["casing"];

            Profile.explorationsDeferred_ = new ScratchpadList().fetchForUser({
                data: data,
                success: function(scratchpadList) {
                    Profile.hideThrobber("explorations", true);

                    var $scratchpads = $("#scratchpads");

                    if (scratchpadList.length === 0) {
                        $scratchpads.html(
                            "<p>You don't have any <a href='/explore/new'>" +
                            "Scratchpads</a>!</p> <p>To get started you can " +
                            "<a href='/explore'>browse through</a> a list of " +
                            "existing explorations and modify them until " +
                            "you've made something awesome.</p>" +
                            "<p><a href='/explore'>" +
                            "<input type='button' class='simple-button green'" +
                            " value='Browse Explorations' /></a></p>"
                        );

                    } else {
                        new ScratchpadListView({
                            collection: scratchpadList,
                            el: $scratchpads,
                            sortBy: function(s) {
                                // Sort the scratchpads list by the creation
                                // time of the latest revision, newest to
                                // oldest.
                                //
                                // created is a JS Date, so -created will be
                                // a negative millisecond timestamp.
                                return -s.get("revision").get("created");
                            }
                        }).render();
                    }
                }
            });
        }

        return Profile.explorationsDeferred_;
    },

    populateSuggestedActivity: function(activities) {
        var suggestedTemplate = Templates.get("profile.suggested-activity");

        var attachProgress = function(activity) {
            activity.progress = activity.progress || 0;
        };
        _.each(activities["exercises"] || [], attachProgress);
        _.each(activities["videos"] || [], attachProgress);
        $("#suggested-activity").append(suggestedTemplate(activities));
    },

    populateRecentActivity: function(activities) {
        var listTemplate = Templates.get("profile.recent-activity-list"),
            exerciseTemplate = Templates.get("profile.recent-activity-exercise"),
            badgeTemplate = Templates.get("profile.recent-activity-badge"),
            videoTemplate = Templates.get("profile.recent-activity-video"),
            goalTemplate = Templates.get("profile.recent-activity-goal");

        var badgeModels = _.chain(activities).
            filter(function(a) { return a.sType === "Badge"; }).
            map(function(a) { return new Backbone.Model(a.badge); }).
            value();

        Handlebars.registerHelper("renderActivity", function(activity) {
            _.extend(activity, {profileRoot: Profile.profileRoot});

            if (activity.sType === "Exercise") {
                return exerciseTemplate(activity);
            } else if (activity.sType === "Badge") {
                // prepare share links
                Badges.ShareLinksView.addShareLinks(activity.badge);
                return badgeTemplate(activity);
            } else if (activity.sType === "Video") {
                return videoTemplate(activity);
            } else if (activity.sType === "Goal") {
                return goalTemplate(activity);
            }

            return "";
        });

        $("#recent-activity").append(listTemplate(activities))
            .find("span.timeago").timeago().end();

        _.each(Profile.shareViews, function(v) { v.undelegateEvents(); });
        // attach share links views
        var $shareEls = $("#recent-activity").find(".share-links");
        Profile.shareViews = _.map($shareEls, function(el, i) {
            return new Badges.ShareLinksView({
                el: el,
                model: badgeModels[i]
            });
        }, this);
    },

    activityDeferred_: null,
    populateActivity: function() {
        if (Profile.activityDeferred_) {
            return Profile.activityDeferred_;
        }

        Profile.showThrobber("recent-activity", false);

        if (Profile.profile.isActivityAccessible()) {
            Profile.activityDeferred_ = $.ajax({
                type: "GET",
                url: "/api/v1/user/activity",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",
                success: function(data) {
                    $("#activity-loading-placeholder").fadeOut(
                        "slow", function() {
                            $(this).hide();
                        });
                    Profile.populateSuggestedActivity(data.suggested);
                    Profile.populateRecentActivity(data.recent);
                    $("#activity-contents").show();
                }
            });
        } else {
            Profile.activityDeferred_ = new $.Deferred();
            Profile.activityDeferred_.resolve();
        }
        return Profile.activityDeferred_;
    },

    /**
     * Return an object to be used in an outgoing XHR for user profile data
     * (e.g. activity graph data).
     * This includes an identifier for the current profile being viewed at,
     * and other common properties.
     */
    getBaseRequestParams_: function() {
        var params = {
            "casing": "camel"
        };
        if (Profile.profile.get("email")) {
            params["email"] = Profile.profile.get("email");
        } else if (Profile.profile.get("username")) {
            params["username"] = Profile.profile.get("username");
        } else if (Profile.profile.get("userKey")) {
            params["userKey"] = Profile.profile.get("userKey");
        }
        return params;
    }
};
