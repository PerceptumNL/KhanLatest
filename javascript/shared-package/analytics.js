/**
 * A set of utilities to track user interactions on the website (using MixPanel).
 *
 * Events can be either instantaneous or have a duration, and only one
 * non-instantaneous event can be occurring at a time. If another event is begun,
 * the previous event is ended automatically.
 *
 * The utility also attempts to resend events that happen just before the page is
 * unloaded or on pages that are unloaded before the sending script is fully loaded.
 *
 * NOTE: If you substantially change the data being sent up to MixPanel (such as
 * changing event names or properties) you will want to bump the version number
 * in Analytics.getVersionNumber() below so we can filter by that version in the
 * dashboard.
 *
 */

(function() {

    // TODO(benkomalo): do this in a more appropriate common library.
    // Patch Date.now for IE8.
    var getNow = Date.now || function() {
        return +(new Date);
    };

    var currentPage = null;
    var currentPageLoadTime = 0;
    var currentTrackingActivity = null;
    var eventQueue = [];

    // Internal utility to make sure events get tracked even if the page is unloaded
    var analyticsStore = {
        persistData: {
            timestamp: 0,
            events: {},
            trackingProperties: {}
        },

        // On page load, load the persist data from sessionStorage and try to send any events
        // that didn't get sent last time.
        loadAndSendPersistData: function() {
            if (window.sessionStorage) {
                var persistData = null;
                try {
                    persistData = $.parseJSON(sessionStorage.getItem("ka_analytics"));
                } catch (e) { }

                var currentTimeMS = getNow();

                // Time out persist data after a minute
                if (persistData && (currentTimeMS - persistData.timestamp) < 60 * 1000) {
                    var self = this;
                    this.persistData = persistData;
                    this.trackingProperties = this.trackingProperties || {};

                    _.each(persistData.events, function(event) {
                        mpq.track(event.name, event.parameters, function() {
                            self.clearEvent(event);
                        });
                    });
                }
            }
        },

        // Add an event to the queue to get sent to MixPanel
        addEvent: function(event) {
            var self = this;

            this.persistData.events[event.id] = event;
            self.storePersistData();

            // Send to tracker (may silently fail)
            mpq.track(event.name, event.parameters, function() {
                self.clearEvent(event);
            });
        },

        // Once an event is successfully sent, clear it from the queue
        clearEvent: function(event) {
            // If tracking succeeds, remove from persist data
            delete this.persistData.events[event.id];
            this.storePersistData();
            KAConsole.log("Successfully sent event " + event.name + " (" + event.id + ")");
        },

        // Save the queue to sessionStorage
        storePersistData: function() {
            if (window.sessionStorage) {
                this.persistData.timestamp = getNow();
                var persistDataJSON = JSON.stringify(this.persistData);

                sessionStorage.setItem("ka_analytics", persistDataJSON);
            }
        },

        // Store a property for use in later events
        setTrackingProperty: function(name, value) {
            this.persistData.trackingProperties[name] = value;
            this.storePersistData();
        },

        // Retrieve a property set earlier
        getTrackingProperty: function(name) {
            return this.persistData.trackingProperties[name];
        }
    };

    window.Analytics = {

        getVersionNumber: function() {
            return 1;
        },

        // Called once on every page load (if MixPanel is enabled)
        trackInitialPageLoad: function(startTime) {
            var landingPage = (document.referrer.split("/")[2] === "www.khanacademy.org");

            analyticsStore.loadAndSendPersistData();

            // Send the final event before unloading the page
            $(window).unload(function() {
                Analytics._trackActivityEnd(getNow());
            });

            // Add event handler for decorated links
            $("body").on("click", "a", function(event) {
                var tag = $(this).attr("data-tag");
                if (tag) {
                    var href = $(this).attr("href");
                    Analytics.trackSingleEvent("Link Click", {
                        "Link Tag": tag,
                        "Href": href
                    });
                }
            });

            this.trackPageLoad(startTime, landingPage);

            var self = this;
            _.each(eventQueue, function(event) {
                self.trackSingleEvent(event.name, event.parameters);
            });

            // 4 hour timeout: stop collecting analytics
            setTimeout(function() {
                // End whatever activity is currently going on
                var currentTimeMS = getNow();
                Analytics._trackActivityEnd(currentTimeMS);

                // Disable further sending of events
                currentPage = null;
            }, 4 * 60 * 60 * 1000);
        },

        // Called once on arriving at a page (if MixPanel is enabled)
        // Differs from trackInitialPageLoad because using a Backbone Router
        // to navigate will trigger trackPageLoad.
        trackPageLoad: function(startTime, landingPage) {
            var currentTimeMS = getNow();
            var loadTimeS = (startTime > 0) ? Math.floor((currentTimeMS - startTime) / 1000.0) : 0;

            analyticsStore.addEvent({
                id: "Page Load" + currentTimeMS,
                name: "Page Load",
                parameters: {
                    "Page": window.location.pathname,
                    "Load Time (s)": loadTimeS
                }
            });
            if (landingPage) {
                analyticsStore.addEvent({
                    id: "Landing Page Load" + currentTimeMS,
                    name: "Landing Page Load",
                    parameters: {
                        "Landing Page": window.location.pathname
                    }
                });
                analyticsStore.setTrackingProperty("Session Start", currentTimeMS);
                analyticsStore.setTrackingProperty("Session Pages", 1);
            } else {
                var pageCount = analyticsStore.getTrackingProperty("Session Pages");
                if (pageCount) {
                    analyticsStore.setTrackingProperty("Session Pages", pageCount + 1);
                }
            }

            currentPage = window.location.pathname;
            currentPageLoadTime = currentTimeMS;
            this.trackActivityBegin("Page View", {});
        },

        handleRouterNavigation: function(eventName) {
            if (eventName.indexOf("route:") != 0) {
                return;
            }
            if (!currentPage) {
                return;
            }

            if (window.location.pathname !== currentPage) {
                Analytics.trackPageLoad(0, false);
            }
        },

        // Call this function in response to a user starting an interaction.
        // Returns the event object to use if you want to modify the parameters
        // or track the end of the event.
        // This will automatically preempt the previously active activity.
        trackActivityBegin: function(eventName, parameters) {
            if (!currentPage) {
                return null;
            }

            var currentTimeMS = getNow();

            this._trackActivityEnd(currentTimeMS);

            parameters._startTime = currentTimeMS;

            KAConsole.log("Started tracking activity " + eventName + " (" + currentTimeMS + ")");

            currentTrackingActivity = {
                id: eventName + currentTimeMS,
                name: eventName,
                parameters: parameters
            };
            return currentTrackingActivity;
        },

        // Track the end of the event if it is the currently active event &
        // restart the default Page View activity.
        trackActivityEnd: function(event) {
            if (event == currentTrackingActivity) {
                var currentTimeMS = getNow();
                this._trackActivityEnd(currentTimeMS);

                // Go back to "Page View" mode because nothing else is active
                this.trackActivityBegin("Page View", {});
            }
        },

        // Internal function to track the end of the current event
        _trackActivityEnd: function(endTime) {
            if (currentTrackingActivity) {
                var activity = currentTrackingActivity;

                // Calculate event duration
                var durationS = Math.floor((endTime - activity.parameters._startTime) / 1000.0);
                var pageTimeS = Math.floor((endTime - currentPageLoadTime) / 1000.0);
                var sessionTimeMS = analyticsStore.getTrackingProperty("Session Start");

                activity.parameters[activity.name + " Page"] = currentPage;
                activity.parameters[activity.name + " Duration (s)"] = durationS;
                activity.parameters[activity.name + " Page Time (s)"] = pageTimeS;
                delete activity.parameters._startTime;

                if (sessionTimeMS) {
                    var sessionTimeS = Math.floor((endTime - sessionTimeMS) / 1000.0);
                    var sessionPageCount = analyticsStore.getTrackingProperty("Session Pages");
                    activity.parameters[activity.name + " Session Time (s)"] = sessionTimeS;
                    activity.parameters[activity.name + " Session Pages"] = sessionPageCount;
                }

                KAConsole.log("Stopped tracking activity " + activity.name + " after " + durationS + " sec.");

                analyticsStore.addEvent(activity);

                currentTrackingActivity = null;
            }
        },

        // Track an instantaneous event with no duration.
        trackSingleEvent: function(eventName, parameters) {
            parameters = parameters || {};
            if (!currentPage) {
                eventQueue.push({name: eventName, parameters: parameters});
                return;
            }

            var currentTimeMS = getNow();

            parameters["Page"] = currentPage;
            parameters[eventName + " Page Time (s)"] = Math.floor((currentTimeMS - currentPageLoadTime) / 1000.0);

            var event = {
                id: eventName + currentTimeMS,
                name: eventName,
                parameters: parameters
            };

            KAConsole.log("Tracking single event " + eventName + " (" + currentTimeMS + ")");

            analyticsStore.addEvent(event);
        }
    };
})();

