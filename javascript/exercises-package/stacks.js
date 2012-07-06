/**
 * Model of any (current or in-stack) card
 */
Exercises.Card = Backbone.Model.extend({

    leaves: function(card) {

        return _.map(_.range(4), function(index) {

            return {
                index: index,
                state: (this.get("leavesEarned") > index ? "earned" :
                            this.get("leavesAvailable") > index ? "available" :
                                "unavailable")
            };

        }, this);

    },

    /**
     * Decreases leaves available -- if leaves available is already at this
     * level or lower, noop
     */
    decreaseLeavesAvailable: function(leavesAvailable) {

        var currentLeaves = this.get("leavesAvailable");
        if (currentLeaves) {
            leavesAvailable = Math.min(currentLeaves, leavesAvailable);
        }

        return this.set({ leavesAvailable: leavesAvailable });

    },

    /**
     * @return {boolean} True if this is a card representing the end of a stack.
     */
    isLastCard: function() {
        return _.contains(["endofstack", "endofreview"], this.get("cardType"));
    },

    /**
     * Get the associated latest user exercise object for this card.
     * @param {Card} card
     * @return {Object|undefined} The userExercise object if available.
     */
    getUserExercise: function(card) {
        return Exercises.UserExerciseCache.get(this.get("exerciseName"));
    }

});

/**
 * Collection model of a stack of cards
 */
Exercises.StackCollection = Backbone.Collection.extend({

    model: Exercises.Card,

    peek: function() {
        return this.first();
    },

    pop: function(animationOptions) {
        var head = this.peek();
        this.remove(head, animationOptions);
        return head;
    },

    /**
     * Shrink this stack by removing N cards up to but not including
     * the first card in the stack and the last (end of stack) card.
     */
    shrinkBy: function(n) {

        // Never shrink to less than two cards (first card, end of stack card).
        var targetLength = Math.max(2, this.length - n);

        while (this.length > targetLength) {
            // Remove the second-to-last card until we're done.
            this.remove(this.models[this.length - 2]);
        }

    },

    /**
     * Return the longest streak of cards in this stack
     * that satisfies the truth test fxn.
     * If fxnSkip is supplied, the card won't count towards
     * or break a streak.
     */
    longestStreak: function(fxn, fxnSkip) {

        var current = 0,
            longest = 0;
        fxnSkip = fxnSkip || function() { return false; };

        this.each(function(card) {

            if (!fxnSkip(card)) {

                if (fxn(card)) {
                    current += 1;
                } else {
                    current = 0;
                }

                longest = Math.max(current, longest);

            }

        });

        return longest;

    },

    /**
     * Return a dictionary of interesting, positive stats about this stack.
     */
    stats: function() {

        var totalLeaves = this.reduce(function(sum, card) {
            // Don't count the fourth leaf for now. We're showing it in a different
            // way at the end of the stack. TODO (jasonrr/kamens) remove 4th leaf
            // altogether if we keep this implementation
            return Math.min(3, card.get("leavesEarned")) + sum;
        }, 0);

        var longestStreak = this.longestStreak(
            function(card) {
                return card.get("leavesEarned") >= 3;
            },
            function(card) {
                // Skip any cards w/ 0 leaves available --
                // those don't count.
                return card.get("leavesAvailable") === 0;
            }
        );

        var speedyCards = this.filter(function(card) {
            return card.get("leavesEarned") >= 4;
        }).length;

        return {
            "longestStreak": longestStreak,
            "speedyCards": speedyCards,
            "totalLeaves": totalLeaves
        };
    }

});

/**
 * StackCollection that is automatically cached in localStorage when modified
 * and loads itself from cache on initialization.
 */
Exercises.CachedStackCollection = Exercises.StackCollection.extend({

    sessionId: null,

    uid: null,

    initialize: function(models, options) {

        this.sessionId = options ? options.sessionId : null;
        this.uid = options && options.uid;

        // Try to load models from cache
        if (!models) {
            this.loadFromCache();
        }

        this
            .bind("add", this.cache, this)
            .bind("remove", this.cache, this);

        return Exercises.StackCollection.prototype.initialize.call(this, models, options);

    },

    cacheKey: function() {
        if (!this.sessionId) {
            throw "Missing session id for cache key";
        }

        return [
            "cachedstack",
            this.sessionId
        ].join(":");
    },

    loadFromCache: function() {

        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        var modelAttrs = LocalStore.get(this.cacheKey());
        if (modelAttrs) {

            if (modelAttrs.uid) {
                this.uid = modelAttrs.uid;
            }

            _.each(modelAttrs.cards || modelAttrs, function(attrs) {
                this.add(new Exercises.Card(attrs));
            }, this);

        }

    },

    cache: function() {

        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        LocalStore.set(this.cacheKey(), {uid: this.uid, cards: this.models});
    },

    /**
     * Delete this stack from localStorage
     */
    clearCache: function() {

        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        LocalStore.del(this.cacheKey());
    },

    getUid: function() {

        // TODO(david): Ideally, this collection should be wrapped in a model.
        return this.uid;
    }

});

/**
 * View of a stack of cards
 */
Exercises.StackView = Backbone.View.extend({

    template: Templates.get("exercises.stack"),

    initialize: function(options) {

        // deferAnimation is a wrapper function used to insert
        // any animations returned by fxn onto animationOption's
        // list of deferreds. This lets you chain complex
        // animations (see Exercises.nextCard).
        var deferAnimation = function(fxn) {
            return function(model, collection, options) {
                var result = fxn.call(this, model, collection, options);

                if (options && options.deferreds) {
                    options.deferreds.push(result);
                }

                return result;
            };
        };

        this.collection
            .bind("add", deferAnimation(function(card) {
                return this.animatePush(card);
            }), this)
            .bind("remove", deferAnimation(function() {
                return this.animatePop();
            }), this);

        return Backbone.View.prototype.initialize.call(this, options);
    },

    render: function() {

        var collectionContext = _.map(this.collection.models, function(card, index) {
            return this.viewContext(card, index);
        }, this);

        this.$el.html(this.template({cards: collectionContext}));

        return this;

    },

    viewContext: function(card, index) {
        return _.extend(card.toJSON(), {
            index: index,
            frontVisible: this.options.frontVisible,
            cid: card.cid,
            leaves: card.leaves()
        });
    },

    /**
     * Animate popping card off of stack
     */
    animatePop: function() {

        return this.$el
            .find(".card-container")
                .first()
                    .slideUp(360, function() { $(this).remove(); });

    },

    /**
     * Animate pushing card onto head of stack
     */
    animatePush: function(card) {

        var context = this.viewContext(card, this.collection.length);

        var jel = this.$el
            .find(".stack")
                .prepend(
                    $(Templates.get("exercises.card")(context))
                        .css("display", "none")
                )
                .find(".card-container")
                    .first()
                    // delay is used to slow down anybody waiting on this
                    // animation. See comment below.
                        .delay(250);

        // Don't immediately slideDown as part of the first animation that
        // happens after card insertion. This causes a rare and hard-to-track
        // browser crash in Chrome.
        //
        // TODO(kamens): remove this. All of this particular animation code
        // should be going away with the power mode team's move to their new
        // card UI, at which point we won't have to stress about this any more.
        setTimeout(function() {
            jel.slideDown(200);
        }, 50);

        return jel;

    }

});

/**
 * View of the single, currently-visible card
 */
Exercises.CurrentCardView = Backbone.View.extend({

    template: Templates.get("exercises.current-card"),

    model: null,

    events: {
        "click .to-dashboard": "toDashboard",
        "click .more-stacks": "toMoreStacks",
        "click #show-topic-details": "showTopicDetails"
    },

    initialize: function(options) {
        this.attachEvents();
        return Backbone.View.prototype.initialize.call(this, options);
    },

    onModelChange: function(info, options) {
        if (options.updateLeaves) {
            this.updateLeaves();
        }
    },

    attachEvents: function() {
        this.model.bind("change", this.onModelChange, this);
    },

    detachEvents: function() {
        this.model.unbind("change", this.onModelChange);
    },

    /**
     * Renders the current card appropriately by card type.
     */
    render: function() {

        switch (this.model.get("cardType")) {

            case "problem":
                this.renderProblemCard();
                break;

            case "endofstack":
                this.renderEndOfStackCard();
                break;

            case "endofreview":
                this.renderEndOfReviewCard();
                break;

            case "happypicture":
                this.renderHappyPictureCard();
                break;

            default:
                throw "Trying to render unknown card type";

        }

        return this;
    },

    viewContext: function() {
        return _.extend(this.model.toJSON(), {
            leaves: this.model.leaves()
        });
    },

    /**
     * Renders the base card's structure, including leaves
     */
    renderCardContainer: function() {
        this.$el.html(this.template(this.viewContext()));
    },

    /**
     * Renders the card's type-specific contents into contents container
     */
    renderCardContents: function(templateName, optionalContext) {

        var context = _.extend({}, this.viewContext(), optionalContext);

        this.$el
            .find(".current-card-contents")
                .html(
                    $(Templates.get(templateName)(context))
                );

        this.delegateEvents();

    },

    /**
     * Waits for API requests to finish, then runs target fxn
     */
    runAfterAPIRequests: function(fxn) {

        function tryRun() {
            if (Exercises.pendingAPIRequests > 0) {

                // Wait for any outbound API requests to finish.
                setTimeout(tryRun, 500);

            } else {

                // All API calls done, run target fxn
                fxn();

            }
        }

        tryRun();

    },

    renderCalculationInProgressCard: function() {

        if ($(".calculating-end-of-stack").is(":visible")) {
            // If the calculation in progress card is already visible,
            // bail.
            return;
        }

        this.renderCardContainer();
        this.renderCardContents("exercises.calculating-card");

        // Animate the first 8 cards into place -- others just go away
        setTimeout(function() {

            $(".complete-stack .card-container").each(function(ix, el) {
                if (ix < 8) {
                    $(el).addClass("into-pocket").addClass("into-pocket-" + ix);
                } else {
                    $(el).css("display", "none");
                }
            });

        }, 500);

        // Fade in/out our various pieces of "calculating progress" text
        var fadeInNextText = function(jel, egg) {

            // allows the loop to recycle when the nextMessage === []
            var messages = $(".calc-text-spin span");
            if (!jel || !jel.length) {
                jel = messages;
            }

            // display either jel or the egg if it was passed in
            var thisMessage = (egg == null) ? jel.first() : $(egg);
            var nextMessage = jel.next("span:not(.egg)");

            // send egg as second parameter if a tiny die lands just so
            var r = Math.random();
            var nextEgg = _.find(jel.filter(".egg"), function(elt) {
                var p = $(elt).data("prob");
                return (r >= p[0]) && (r < p[1]);
            });

            // fade out thisMessage and display egg || nextMessage
            thisMessage.fadeIn(600, function() {
                thisMessage.delay(1000).fadeOut(600, function() {
                    fadeInNextText(nextMessage, nextEgg);
                });
            });
        };

        // recalculate cumulative probabilities for each egg
        var eggs = $(".calc-text-spin span.egg");
        for (var i = 0, head = 0; i < eggs.length; i += 1) {
            tail = head + $(eggs[i]).data("prob");
            $(eggs[i]).data("prob", [head, tail]);
            head = tail;
        }

        fadeInNextText();

   },

    /**
     * Renders a "calculations in progress" card, waits for API requests
     * to finish, and then renders the requested card template.
     */
    renderCardAfterAPIRequests: function(templateName, optionalContextFxn, optionalCallbackFxn) {

        // Start off by showing the "calculations in progress" card...
        this.renderCalculationInProgressCard();

        // ...and wait a bit for dramatic effect before trying to show the
        // requested card.
        setTimeout(function() {
            Exercises.currentCardView.runAfterAPIRequests(function() {

                optionalContextFxn = optionalContextFxn || function() {};
                Exercises.currentCardView.renderCardContents(templateName, optionalContextFxn());

                if (optionalCallbackFxn) {
                    optionalCallbackFxn();
                }

            });
        }, 2200);

    },

    /**
     * Renders a new card showing an exercise problem via khan-exercises
     */
    renderProblemCard: function() {

        // khan-exercises currently both generates content and hooks up
        // events to the exercise interface. This means, for now, we don't want
        // to regenerate a brand new card when transitioning between exercise
        // problems.

        // TODO: in the future, if khan-exercises's problem generation is
        // separated from its UI events a little more, we can just rerender
        // the whole card for every problem.

        if (!$("#problemarea").length) {

            this.renderCardContainer();
            this.renderCardContents("exercises.problem-template");

            // Tell khan-exercises to setup its DOM and event listeners
            $(Exercises).trigger("problemTemplateRendered");

            //TODO (jasonrr): remove this when we remove the what happened UI
            $(".streak-transition").hoverIntent(
                function() {
                    $(this).addClass("hover");
                },
                function() {
                    $(this).removeClass("hover");
                }
            );

        }

        this.renderExerciseInProblemCard();

        // Update leaves since we may have not generated a brand new card
        this.updateLeaves();

    },

    renderExerciseInProblemCard: function() {

        var nextUserExercise = Exercises.nextUserExercise();
        if (nextUserExercise) {
            // khan-exercises is listening and will fill the card w/ new problem contents
            $(Exercises).trigger("readyForNextProblem", {userExercise: nextUserExercise});
        }

    },

    /**
     * Renders a new card showing end-of-stack statistics
     */
    renderEndOfStackCard: function() {

        this.renderCalculationInProgressCard();

        // Example "endOfStack" listener: exercises-intro.js
        $(Exercises).trigger("endOfStack");

        // First wait for all API requests to finish
        this.runAfterAPIRequests($.proxy(function() {

            var topicUserExercises = [];

            if (!Exercises.practiceMode && !Exercises.reviewMode) {
                Exercises.apiRequest({
                    url: "/api/v1/user/topic/" + encodeURIComponent(Exercises.topic.get("id")) + "/exercises",
                    type: "GET",
                    success: function(data) {
                        _.each(data, function(userExercise) {
                            topicUserExercises[topicUserExercises.length] = userExercise;
                        });
                    }
                });
            }

            this.renderCardAfterAPIRequests(
                "exercises.end-of-stack-card",
                function() {

                    // Collect various progress stats about both the current stack
                    // and the current topic -- will be rendered by end of
                    // stack card.
                    var unstartedExercises = _.filter(topicUserExercises, function(userExercise) {
                            return !userExercise.exerciseStates.proficient && userExercise.totalDone === 0;
                        }),
                        proficientExercises = _.filter(topicUserExercises, function(userExercise) {
                            return userExercise.exerciseStates.proficient;
                        }),
                        startedExercises = _.filter(topicUserExercises, function(userExercise) {
                            return !userExercise.exerciseStates.proficient && userExercise.totalDone > 0;
                        }),
                        progressStats = Exercises.sessionStats.progressStats();

                    // Proficient exercises in which proficiency was just
                    // earned in this current stack need to be marked as such.
                    //
                    // TODO: if we stick with this everywhere, we probably want
                    // to change the actual review model algorithm to stop
                    // setting recently-earned exercises into review state so
                    // quickly.
                    _.each(proficientExercises, function(userExercise) {
                        userExercise.exerciseStates.justEarnedProficiency = _.any(progressStats.progress, function(stat) {
                            return stat.exerciseStates.justEarnedProficiency && stat.name == userExercise.exercise;
                        });
                    });

                    return _.extend(
                        {
                            "practiceMode": Exercises.practiceMode,
                            "proficient": proficientExercises.length,
                            "total": topicUserExercises.length,
                            startedExercises: startedExercises,
                            unstartedExercises: unstartedExercises,
                            proficientExercises: proficientExercises
                        },
                        progressStats,
                        Exercises.completeStack.stats()
                    );

                },
                function() {

                    Exercises.completeStackView.$el.hide();
                    Exercises.currentCardView.$el
                        .find(".stack-stats p, .small-exercise-icon, .review-explain")
                            .each(Exercises.currentCardView.attachTooltip)
                            .end()
                        .find(".default-action")
                            .focus();

                }
            );

        }, this));
    },

    /**
     * Renders a new card showing end-of-review statistics
     */
    renderEndOfReviewCard: function() {

        this.renderCalculationInProgressCard();

        // First wait for all API requests to finish
        this.runAfterAPIRequests(function() {

            var reviewsLeft = 0;

            // Then send another API request to see how many reviews are left --
            // and we'll change the end of review card's UI accordingly.
            Exercises.apiRequest({
                url: "/api/v1/user/exercises/reviews/count",
                type: "GET",
                success: function(data) { reviewsLeft = data; }
            });

            // And finally wait for the previous API call to finish before
            // rendering end of review card.
            Exercises.currentCardView.renderCardAfterAPIRequests(
                "exercises.end-of-review-card",
                function() {
                    // Pass reviews left info into end of review card
                    return _.extend({}, Exercises.completeStack.stats(), {reviewsLeft: reviewsLeft});
                },
                function() {
                    Exercises.completeStackView.$el.hide();
                    Exercises.currentCardView.$el
                        .find(".default-action")
                            .focus();
                }
            );

        });

    },

    /**
     * Renders a new card showing a leeeeeetle surprise
     */
    renderHappyPictureCard: function() {
        this.renderCardContainer();
        this.renderCardContents("exercises.happy-picture-card");

        this.$el
            .find("#next-question-button")
                .click(function() {
                    Exercises.nextCard();
                })
                .focus();
    },

    attachTooltip: function() {
        $(this).qtip({
            content: {
                text: $(this).data("desc")
            },
            style: {
                classes: "ui-tooltip-light leaf-tooltip"
            },
            position: {
                my: "bottom center",
                at: "top center"
            },
            events: {
                show: function(e, api) {

                    var target = $(api.elements.target);
                    if (target.is(".leaf")) {
                        // If we're hovering a leaf and the full leaf icon
                        // is currently being animated, don't show the tooltip.
                        if (parseInt(target.find(".full-leaf").css("opacity"), 10) != 1) {
                            e.preventDefault();
                        }
                    }

                }
            },
            show: {
                delay: 200,
                effect: {
                    length: 0
                }
            },
            hide: {
                delay: 0
            }
        });
    },

    /**
     * Show full details about the current topic
     * (starts out hidden to highlight stack-only details.
     */
    showTopicDetails: function() {
        $(".current-topic").slideDown();
        $("#show-topic-details").hide();
    },

    /**
     * Navigate to exercise dashboard
     */
    toDashboard: function() {
        window.location = "/exercisedashboard";
    },

    /**
     * Navigate to more stacks of the current type.
     * TODO: in the future, this can be done quick'n'javascript-y.
     */
    toMoreStacks: function() {
        window.location.assign(window.location.href);
    },

    /**
     * Update the currently available or earned leaves in current card's view
     */
    updateLeaves: function() {
        this.$el
            .find(".leaves-container")
                .html(
                    $(Templates.get("exercises.card-leaves")(this.viewContext()))
                )
                .find(".leaf")
                    .each(this.attachTooltip);

        if (this.model.get("done")) {

            $(".leaves-container").show();
            //TODO: This probably doesn't belong here
            $(".current-card").addClass("done");

            setTimeout(function() {
                $(".leaves-container .earned .full-leaf").addClass("animated");
            }, 1);

        } else {

            $(".current-card").removeClass("done");

        }
    },

    /**
     * Animate current card to right-hand completed stack
     */
    animateToRight: function() {
        this.$el.addClass("shrinkRight");

        // These animation fxns explicitly return null as they are used in deferreds
        // and may one day have deferrable animations (CSS3 animations aren't
        // deferred-friendly).
        return null;
    },

    /**
     * Animate card from left-hand completed stack to current card
     */
    animateFromLeft: function() {
        this.$el
            .removeClass("notransition")
            .removeClass("shrinkLeft");

        // These animation fxns explicitly return null as they are used in deferreds
        // and may one day have deferrable animations (CSS3 animations aren't
        // deferred-friendly).
        return null;
    },

    /**
     * Move (unanimated) current card from right-hand stack to left-hand stack between
     * toRight/fromLeft animations
     */
    moveLeft: function() {
        this.$el
            .addClass("notransition")
            .removeClass("shrinkRight")
            .addClass("shrinkLeft");

        // These animation fxns explicitly return null as they are used in deferreds
        // and may one day have deferrable animations (CSS3 animations aren't
        // deferred-friendly).
        return null;
    }

});

/**
 * SessionStats stores and caches a list of interesting statistics
 * about each individual stack session.
 */
Exercises.SessionStats = Backbone.Model.extend({

    cacheEnabled: false,
    sessionId: null,

    initialize: function(attributes, options) {

        this.cacheEnabled = true;
        this.sessionId = options ? options.sessionId : null;

        // Try to load stats from cache
        this.loadFromCache();

        // Update exercise stats any time new exercise data is cached locally
        $(Exercises).bind("newUserExerciseData", $.proxy(function(ev, data) {
            this.updateProgressStats(data.exerciseName);
        }, this));

        return Backbone.Model.prototype.initialize.call(this, attributes, options);
    },

    cacheKey: function() {
        if (!this.sessionId) {
            throw "Missing session id for cache key";
        }

        return [
            "cachedsessionstats",
            this.sessionId
        ].join(":");
    },

    loadFromCache: function() {
        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        var attrs = LocalStore.get(this.cacheKey());
        if (attrs) {
            this.set(attrs);
        }
    },

    cache: function() {
        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        if (!this.cacheEnabled) {
            return;
        }

        LocalStore.set(this.cacheKey(), this.attributes);
    },

    clearCache: function() {

        if (!this.sessionId) {
            // Don't cache session-less pages (such as when viewing historical
            // problems)
            return;
        }

        LocalStore.del(this.cacheKey());
    },

    /**
     * Clears cache and disables sessionStats from being accumulated
     * if any more events are fired.
     */
    clearAndDisableCache: function() {
        this.cacheEnabled = false;
        this.clearCache();
    },

    /**
     * Update the start/end/change progress for this specific exercise so we
     * can summarize the user's session progress at the end of a stack.
     */
    updateProgressStats: function(exerciseName) {

        var userExercise = Exercises.UserExerciseCache.get(exerciseName);

        if (userExercise) {

            /**
             * For now, we're just keeping track of the change in progress per
             * exercise
             */
            var progressStats = this.get("progress") || {},

                stat = progressStats[exerciseName] || {
                    name: userExercise.exercise,
                    displayName: userExercise.exerciseModel.displayName,
                    startProficient: userExercise.exerciseStates.proficient,
                    startTotalDone: userExercise.totalDone,
                    start: userExercise.progress
                };

            // Add all current proficiency/review/struggling states
            stat.exerciseStates = userExercise.exerciseStates;

            // Add an extra state to be used when proficiency was just earned
            // during the current stack.
            stat.exerciseStates.justEarnedProficiency = stat.exerciseStates.proficient && !stat.startProficient;

            stat.endTotalDone = userExercise.totalDone;
            stat.end = userExercise.progress;

            // Keep start set at the minimum of starting and current progress.
            // We do this b/c we never want to animate backwards progress --
            // if the user lost ground, just show their ending position.
            stat.start = Math.min(stat.start, stat.end);

            // Set and cache the latest
            progressStats[exerciseName] = stat;
            this.set({"progress": progressStats});
            this.cache();

        }

    },

    /**
     * Return list of stat objects for only those exercises which had at least
     * one problem done during this session, with latest userExercise state
     * from server attached.
     */
    progressStats: function() {

        var stats = _.filter(
                        _.values(this.get("progress") || {}),
                        function(stat) {
                            return stat.endTotalDone && stat.endTotalDone > stat.startTotalDone;
                        }
                    );

        // Attach relevant userExercise object to each stat
        _.each(stats, function(stat) {
            stat.userExercise = Exercises.UserExerciseCache.get(stat.name);
        });

        return { progress: stats };
    }

});

