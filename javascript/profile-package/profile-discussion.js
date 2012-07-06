/**
 * Code to handle the logic for the profile discussion tab.
 * Dependent on profile-package/profile.js.
 */

if (typeof Profile !== "undefined") {
    Profile.Discussion = {
        expanderSettings: {
            slicePoint: 500,
            expandText: "(more)",
            userCollapseText: ""
        },

        /**
          * Attaches an onclick event handler
          * to track clicks on individual q/a/c.
          */
        trackItemClick: function(event) {
            var jel = $(this);

            // Track if the item was clicked on the summary page,
            // or on an individual tab.
            var location;
            // On the summary page, the items are inside
            // #discussion-summary.
            if (jel.parents("#discussion-summary").length > 0) {
                location = "Summary";
            } else {
                location = "Tab";
            }

            // Popularity. Set the popularity of the post based on vote range.
            var popularity;
            var votes = jel.data("votes");
            if (votes < 1) {
                popularity = "Downvoted";
            } else if (votes === 1) {
                popularity = "No votes";
            } else if (votes <= 10) {
                popularity = "Some votes (<= 10)";
            } else {
                popularity = "Popular (> 10)";
            }

            // Who visited the link?
            var who;
            if (Profile.profile.get("isSelf")) {
                who = "Author";
            } else {
                who = "Non-Author";
            }

            Analytics.trackSingleEvent(
                "Profile » Discussion » Item Click", {
                    "Feedback Type": jel.data("feedbackType"),
                    "Popularity": popularity,
                    "Location": location,
                    "User": who
            });
        },

        /**
          * Populates the summary view in the Profile Discussion Tab.
          */
        summaryDeferred_: null,
        summary_: null,

        awards_: null,
        awardsDeferred_: false,

        stats_: null,
        statsDeferred_: false,
        populateSummary: function() {
            var self = Profile.Discussion;

            if (self.summaryDeferred_) {
                return self.summaryDeferred_;
            }

            Profile.showThrobber("discussion");
            self.summaryDeferred_ = $.ajax({
                type: "GET",
                url: "/api/v1/user/discussion/summary",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",
                success: function(response) {
                    Profile.hideThrobber("discussion");
                    $("#discussion-summary").show();

                    // Cache stuff.
                    self.summary_ = response;

                    self.stats_ = response.statistics;
                    self.statsDeferred_ = response.statistics;

                    self.awards_ = response.badges;
                    self.awardsDeferred_ = true;

                    // Start filling up the page.
                    self.populateAwards();
                    self.populateStats();
                    self.populateBlock("questions");
                    self.populateBlock("answers");
                    self.populateBlock("comments");
                    self.updateBlockHeaders();
                }
            });
        },

        fetchAwards: function(onSuccess) {
            var self = Profile.Discussion;

            self.awardsDeferred_ = $.ajax({
                type: "GET",
                url: "/api/v1/user/discussion/badges",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",

                success: function(response) {
                    // Cache the response.
                    self.awards_ = response;
                    onSuccess(response);
                }
            });
        },

        populateAwards: function() {
            var self = Profile.Discussion;

            Profile.hideThrobber("discussion-awards-block");

            if (self.awards_.length === 0) {
                self.populateEmptyBlock("discussion-awards");
                return;
            }

            var template = Templates.get("profile.discussion-awards-block");
            $("#discussion-awards").html(template(self.awards_));
        },

        /**
          * Populates individual Discussion items (Questions/Answers/Comments)
          * with relevant badge icons.
          */
        populateAwardIcons: function(type, where) {
            var self = Profile.Discussion;

            if (self.awardsDeferred_) {
                // Possible containers include tabs:
                // #questions, answers and #comments
                // and blocks:
                // #questions-block, #answers-block and #comments-block
                var containerSelector = "#" + type;

                if (where === "block") {
                    containerSelector += "-block";
                }

                // Form the selector for the container of the award icons.
                // data-loaded is true if the container has already been filled.
                // data-feedback-key is the unique key for each feedback.
                var prependToSelector = containerSelector +
                    " .discussion-award-small-icons" +
                    "[data-feedback-type=" + type + "]";

                // Cache the feedback keys because we'll later need to mark them
                // as filled.
                var keys = [];

                _.each(self.awards_, function(award) {
                    if (award.feedbackKeys) {
                        var template = Templates.get("profile.discussion-award-icon");

                        _.each(award.feedbackKeys, function(key) {
                            if (_.indexOf(keys, key) === -1) {
                                keys.push(key);
                            }
                            $(prependToSelector +
                                "[data-loaded=false][data-feedback-key=" + key + "]")
                                .append(template(award));
                        });
                    }
                });

                // Mark as filled.
                _.each(keys, function(key) {
                    $(prependToSelector + "[data-feedback-key=" + key + "]")
                    .attr("data-loaded", true);
                });
            }

            else {
                self.fetchAwards(function() {
                    self.populateAwardIcons(type, where);
                });
            }
        },

        fetchStats: function(onSuccess) {
            var self = Profile.Discussion;

            self.statsDeferred_ = $.ajax({
                type: "GET",
                url: "/api/v1/user/discussion/statistics",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",

                success: function(response) {
                    // Cache the response.
                    self.stats_ = response;
                    onSuccess(response);
                }
            });
        },

        populateStats: function() {
            var self = Profile.Discussion;
            var template = Templates.get("profile.discussion-statistics");
            $("#discussion-statistics-block").append(template(self.stats_));
        },

        /**
          * Populates a discussion block i.e. Answer, Question or Comment blocks
          * shown on the Discussion page.
          */
        populateBlock: function(type) {
            var self = Profile.Discussion;
            // Populate discussion blocks including:
            // #questions-block, #answers-block and #comments-block
            var jcontainer = $("#" + type + "-block");

            if (self.summary_[type].length === 0) {
                self.populateEmptyBlock(type);
                return;
            }

            var template = Templates.get("profile.discussion-" + type);

            jcontainer.append(template(self.summary_[type]));

            jcontainer.find(".timeago").timeago();
            jcontainer.find(".discussion-title, .discussion-indent")
                .expander(self.expanderSettings);

            self.populateAwardIcons(type, "block");
        },

        /**
         * Send an API request to fetch discussion (questions/comments/answers).
         */
        fetch: function(type, meta, onSuccess) {
            var data = Profile.getBaseRequestParams_();
            _.extend(data, meta);

            return $.ajax({
                type: "GET",
                url: "/api/v1/user/" + type,
                data: data,
                dataType: "json",
                success: onSuccess
            });
        },

        /**
          * Initialize a discussion tab with data.
          */
        tab_: {},
        initTab: function(type) {
            Profile.Discussion.tab_[type] = {
                empty: false,
                deferred: null,
                page: 1,
                sort: 1,
                complete: false,
                data: []
            };
        },

        /**
         * Updates a discussion tab with new content.
         */
        updateTabContent: function(type, response) {
            var self = Profile.Discussion;
            var template = Templates.get("profile.discussion-" + type);

            // Append response to respective tab, including:
            // #questions, #answers and #comments
            var jcontainer = $("#" + type);

            jcontainer.append(template(response));

            jcontainer.find(".timeago").timeago();
            jcontainer.find(".discussion-title, .discussion-indent")
                .expander(self.expanderSettings);

            self.populateAwardIcons(type);
        },

        /**
         * Checks if all the data has been loaded.
         * If yes, marks tab's data as complete and updates UI.
         */
        isTabComplete: function(type, response) {
            var self = Profile.Discussion;

            // Since the total count of feedback items may not always
            // match the fetched count, mark as complete when the
            // fetched response count is less than 10 (feedback items
            // fetched per page).
            if (response.length < 10) {
                self.tab_[type].complete = true;
            }

            self.showMoreButton(!self.tab_[type].complete, type);
            self.updateMoreButton(false, type);
            // TODO(ankit): This is called redundantly on every tab fetch.
            // It should only be called once.
            self.updateTabHeader(type);
        },

        /**
         * Caches response and updates UI on fetching
         * data for a tab.
         */
        onTabFetch: function(type, response) {
            var self = Profile.Discussion;

            // Cache the formatted data.
            self.tab_[type].data = self.tab_[type].data.concat(response);

            if (!self.stats_) {
                self.fetchStats(function() {
                    self.isTabComplete(type, response);
                });
            }

            else {
                self.isTabComplete(type, response);
            }

            self.updateTabContent(type, response);
        },

        /**
         * Populates a Discussion tab i.e. an individual Answers, Questions
         * Comments page with data. Only shows the first 10 results to start
         * with.
         */
        populateTab: function(type) {
            var self = Profile.Discussion;

            // This hides the throbber if it was visible when the user switched tabs
            Profile.hideThrobber(type, false);

            if (self.tab_[type] === undefined) {
                self.initTab(type);
            }

            if (self.tab_[type].empty) {
                self.populateEmptyTab(type);
                return;
            }

            if (self.tab_[type].deferred) {
                return self.tab_[type].deferred;
            }

            Profile.showThrobber(type, true);

            self.tab_[type].deferred = self.fetch(type, {
                    "page": self.tab_[type].page,
                    "sort": self.tab_[type].sort
                },

                function(response) {
                    Profile.hideThrobber(type, false);

                    if (response.length === 0) {
                        self.tab_[type].empty = true;
                        self.populateEmptyTab(type);
                    }

                    self.onTabFetch(type, response);
                });
        },

        /**
         * Populate a Discussion tab with more paginated data.
         * Called when the "More" button is clicked in a tab.
         */
        loadMore: function(type) {
            var self = Profile.Discussion;

            self.updateMoreButton(true, type);

            self.tab_[type].page++;
            self.tab_[type].deferred = self.fetch(type, {
                    "page": self.tab_[type].page,
                    "sort": self.tab_[type].sort
                },

                function(response) {
                    self.onTabFetch(type, response);
                });
        },

        /**
         * Sort a Discussion tab based on vote count (sort=1)
         * or date (sort=2).
         */
        sort: function(type, sort) {
            var self = Profile.Discussion;

            if (sort === self.tab_[type].sort) {
                return;
            }

            // Sort the existing data if all of it has been fetched.
            if (self.tab_[type].complete) {
                self.tab_[type].sort = sort;

                // Sort by vote count.
                if (sort === 1) {
                    self.tab_[type].data.sort(function(a, b) {
                        if (a.sumVotesIncremented > b.sumVotesIncremented) {
                            return -1;
                        }

                        else if (a.sumVotesIncremented < b.sumVotesIncremented) {
                            return 1;
                        }

                        else {
                            if (new Date(a.date) < new Date(b.date)) {
                                return 1;
                            }

                            else {
                                return -1;
                            }
                        }
                    });
                }

                // Sort by date.
                else {
                    self.tab_[type].data =
                    _.sortBy(self.tab_[type].data, function(item) {
                        return item.date;
                    }).reverse();
                }

                // Reset UI.
                $("#" + type).html("");
                self.updateTabContent(type, self.tab_[type].data);
                return;
            }

            // If all of the data is not available, send a new request.

            // Reset tab data.
            self.initTab(type);
            self.tab_[type].sort = sort;

            // Reset the UI of the respective tab including:
            // #questions, #answers and #comments
            $("#" + type).html("");

            // Hide the respective more button including:
            // #questions-more, #answers-more and #comments-more
            $("#" + type + "-more").hide();

            self.populateTab(type);
        },

        /**
          * Updates the visibility of the More button in the specified
          * Discussion tab.
          */
        showMoreButton: function(isVisible, type) {
            var self = Profile.Discussion;

            // Mark respective More button's status ncluding:
            // #questions-more, #answers-more and #comments-more
            var jbtn = $("#" + type + "-more");

            if (isVisible) {
                jbtn.show();
            } else {
                jbtn.hide();
            }
        },

        /**
          * Update the text of More button to indicate its current
          * status.
          */
        updateMoreButton: function(isLoading, type) {
            // Mark respective More button's status including:
            // #questions-more, #answers-more and #comments-more
            var jbtn = $("#" + type + "-more");

            if (isLoading) {
                jbtn.html("Loading...");
            } else {
                jbtn.html("More");
            }
        },

        /**
          * Updates the discussion headers in discussion tabs.
          */
        updateTabHeader: function(type) {
            var self = Profile.Discussion;
            var template = Templates.get("profile.discussion-count");
            var countSelector = ".discussion-count";

            // Update the header of a tab, including:
            // #questions-header, #answers-header and #comments-header
            $("#" + type + "-header " + countSelector).html(template({
                count: self.stats_[type]
            }));
        },

        /**
          * Updates the discussion block headers.
          */
        updateBlockHeaders: function() {
            var self = Profile.Discussion;
            var template = Templates.get("profile.discussion-count");
            var countSelector = ".discussion-count";

            $("#questions-block-header " + countSelector).html(template({
                count: self.stats_.questions
            }));
            $("#answers-block-header " + countSelector).html(template({
                count: self.stats_.answers
            }));
            $("#comments-block-header " + countSelector).html(template({
                count: self.stats_.comments
            }));
        },

        // Suggestions for all types are the same right now.
        suggestions_: null,
        fetchSuggestions: function(type, onSuccess) {
            var self = Profile.Discussion;

            if (self.suggestions_) {
                onSuccess(self.suggestions_);
                return;
            }

            $.ajax({
                type: "GET",
                url: "/api/v1/user/" + type + "/suggestions",
                data: Profile.getBaseRequestParams_(),
                dataType: "json",

                success: function(response) {
                    // Cache the response.
                    self.suggestions_ = response;
                    onSuccess(response);
                }
            });
        },

        updateEmptyMessage: function(type, jcontainer, response) {
            var template =
                Templates.get("profile.discussion-" + type + "-suggestions");
            jcontainer.html(template(response)).show();
        },

        populateEmptyBlock: function(type) {
            var self = Profile.Discussion;
            var jcontainer = $("#" + type + "-block .discussion-message");

            // We don't have any suggestions for comments yet.
            if ((type === "answers" || type === "questions") &&
                    Profile.profile.get("isActivityAccessible")) {

                self.fetchSuggestions(type, function(response) {
                    self.updateEmptyMessage(type, jcontainer, response);
                });

            } else {
                jcontainer.show();
            }
        },

        emptyTabPopulated_: {},
        populateEmptyTab: function(type) {
            var self = Profile.Discussion;
            var jcontainer;

            if (self.emptyTabPopulated_[type]) {
                return;
            }

            var originalType = type;

            if (type === "notifications") {
                // Suggestions for notifications are same as answers.
                type = "questions";
                jcontainer = $("#notifications .discussion-message");
            } else {
                // Populate the respective discussion tab, including:
                // #discussion-questions, #discussion-answers,
                // #discussion-comments.
                jcontainer = $("#discussion-" + type + " .discussion-message");
            }

            // We don't have any suggestions for comments yet.
            if (type !== "comments" && Profile.profile.get("isActivityAccessible")) {
                self.fetchSuggestions(type, function(response) {
                    self.updateEmptyMessage(type, jcontainer, response);
                    self.emptyTabPopulated_[originalType] = true;
                });
            } else {
                jcontainer.show();
            }
        },

        notificationsDeferred_: null,
        noNotifications_: false,
        populateNotifications: function() {
            var self = Profile.Discussion;

            // This hides the throbber if it was visible when the user switched tabs
            Profile.hideThrobber("notifications");

            if (self.noNotifications_) {
                self.populateEmptyTab("notifications");
                return;
            }

            if (self.notificationsDeferred_) {
                return self.notificationsDeferred_;
            }

            if (Profile.profile.isActivityAccessible()) {
                Profile.showThrobber("notifications", true);

                self.notificationsDeferred_ = $.ajax({
                    type: "GET",
                    url: "/api/v1/user/notifications",
                    data: Profile.getBaseRequestParams_(),
                    dataType: "json",

                    success: function(response) {
                        Profile.hideThrobber("notifications");

                        if (response.questions.length === 0) {
                            self.noNotifications_ = true;
                            self.populateEmptyTab("notifications");
                            return;
                        }

                        var template = Templates.get("profile.discussion-notifications");
                        $("#notifications")
                            .append(template(response.questions))
                            .find(".timeago").timeago();

                        // Highlight the questions that have new notifications
                        self.highlight($(".unread"));
                    }
                });
            } else {
                self.notificationsDeferred_ = new $.Deferred();
                self.notificationsDeferred_.resolve();
            }

            return self.notificationsDeferred_;
        },

        // TODO(ankit): This should be a generic utility we can
        // use elsewhere.
        highlight: function(jel) {
            var initialPause = 500;
            var rampOn = 500;
            var hiOn = 300;
            var rampOff = 300;

            jel.delay(initialPause)
                .animate({"backgroundColor": "#edf2df"}, rampOn)
                .delay(hiOn)
                .animate({"backgroundColor": "#f4f7ed"}, rampOff);
        }
    };
}
