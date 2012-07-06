var GoalProfileView = Backbone.View.extend({
    template: Templates.get("profile.profile-goals"),
    needsRerender: true,

    initialize: function() {
        this.model.bind("change", this.render, this);
        this.model.bind("reset", this.render, this);
        this.model.bind("remove", this.render, this);
        this.model.bind("add", this.render, this);

        // only hookup event handlers if the view allows edits
        if (this.options.readonly) {
            return;
        }

        $(this.el)
            // edit titles
            .delegate("input.goal-title", "focusout", $.proxy(this.changeTitle, this))
            .delegate("input.goal-title", "keypress", $.proxy(function(e) {
                if (e.which == "13") { // enter
                    e.preventDefault();
                    this.changeTitle(e);
                    $(e.target).blur();
                }
            }, this))
            .delegate("input.goal-title", "keyup", $.proxy(function(e) {
                if (e.which == "27") { // escape
                    e.preventDefault();

                    // restore old title
                    var jel = $(e.target);
                    var goal = this.model.get(jel.closest(".goal").data("id"));
                    jel.val(goal.get("title"));

                    jel.blur();
                }
            }, this))

            // show abandon button on hover
            .delegate(".goal", "mouseenter mouseleave", function(e) {
                var el = $(e.currentTarget);
                if (e.type == "mouseenter") {
                    el.find(".goal-description .summary-light").hide();
                    el.find(".goal-description .goal-controls").show();
                } else {
                    el.find(".goal-description .goal-controls").hide();
                    el.find(".goal-description .summary-light").show();
                }
            })
            // respond to abandon button
            .delegate(".abandon", "click", $.proxy(this.abandon, this));
    },

    changeTitle: function(e, options) {
        var jel = $(e.target);
        var goal = this.model.get(jel.closest(".goal").data("id"));
        var newTitle = jel.val();
        if (newTitle !== goal.get("title")) {
            goal.save({title: newTitle});
        }
    },

    show: function() {
        // render if necessary
        if (this.needsRerender) {
            this.render();
        }
        return $(this.el).show();
    },

    hide: function() {
        $(this.el).hide();
    },

    render: function() {
        var jel = $(this.el);
        // delay rendering until the view is actually visible
        this.needsRerender = false;
        var json = _.pluck(this.model.models, "attributes");
        jel.html(this.template({
            goals: json,
            isCurrent: (this.options.type == "current"),
            isCompleted: (this.options.type == "completed"),
            isAbandoned: (this.options.type == "abandoned"),
            readonly: this.options.readonly,
            colors: this.options.colors
        }));

        // attach a NewGoalView to the new goals html
        var newGoalEl = this.$(".goalpicker");
        if (newGoalEl.length > 0) {
            this.newGoalsView = new NewGoalView({
                el: newGoalEl,
                model: this.model
            });
        }

        Profile.hoverContent(jel.find(".objective"), "#profile-goals-content");
        return jel;
    },

    abandon: function(evt) {
        var goalEl = $(evt.target).closest(".goal");
        var goal = this.model.get(goalEl.data("id"));
        if (!goal) {
            // haven't yet received a reponse from the server after creating the
            // goal. Shouldn't happen too often, so just show a message.
            alert("Please wait a few seconds and try again. If this is the second time you've seen this message, reload the page");
            return;
        }

        if (confirm("Abandoning a goal is permanent and cannot be undone. Do you really want to abandon this goal?")) {
            // move the model to the abandoned collection
            this.model.remove(goal);
            goal.set({"abandoned": true});
            AbandonedGoalBook.add(goal);

            // persist to server
            goal.save().fail(function() {
                KAConsole.log("Warning: failed to abandon goal", goal);
                AbandonedGoalBook.remove(goal);
                this.model.add(goal);
            });
        }
    }
});

var GoalProfileViewsCollection = {
    views: {},

    render: function(data) {
        var viewingOwnGoals = Profile.profile.get("isSelf"),
            current_goals = [],
            completed_goals = [],
            abandoned_goals = [];

        $.each(data, function(idx, goal) {
            if (goal.completed) {
                if (goal.abandoned) {
                    abandoned_goals.push(goal);
                } else {
                    completed_goals.push(goal);
                }
            } else {
                current_goals.push(goal);
            }
        });
        if (viewingOwnGoals) {
            GoalBook.reset(current_goals);
        } else {
            CurrentGoalBook = new GoalCollection(current_goals);
        }

        CompletedGoalBook = new GoalCollection(completed_goals);
        AbandonedGoalBook = new GoalCollection(abandoned_goals);

        $("#profile-goals-content").html('<div id="current-goals-list"></div><div id="completed-goals-list"></div><div id="abandoned-goals-list"></div>');

        this.views.current = new GoalProfileView({
            el: "#current-goals-list",
            model: viewingOwnGoals ? GoalBook : CurrentGoalBook,
            type: "current",
            readonly: !viewingOwnGoals
        });
        this.views.completed = new GoalProfileView({
            el: "#completed-goals-list",
            model: CompletedGoalBook,
            type: "completed",
            readonly: true
        });
        this.views.abandoned = new GoalProfileView({
            el: "#abandoned-goals-list",
            model: AbandonedGoalBook,
            type: "abandoned",
            readonly: true
        });

        if (viewingOwnGoals) {
            $(".new-goal").addClass("green").removeClass("disabled").click(function(e) {
                e.preventDefault();
                window.newGoalDialog.show();
            });
        }

        // Because we wait for a response from /api/v1/user/goals to render the collection,
        // a view can be selected by the user before they exist (either by
        // navigating directly to /profile/username/goals/abandoned or clicking quickly).
        var jel = $("#tab-content-goals .graph-picker .type"),
            selectedType = "current";
        $.each(this.views, function(index, view) {
            if (jel.filter("." + view.options.type).hasClass("selected")) {
                selectedType = view.options.type;
                return false;
            }
        });

        this.showGoalType(selectedType);
    },

    showGoalType: function(type) {
        var view = this.views[type];
        if (view) {
            view.show().siblings().hide();
        }

        $(".graph-picker").find("." + type).addClass("selected")
            .siblings().removeClass("selected");
    }
};
