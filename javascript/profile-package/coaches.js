/**
 * Namespace for logic to manage the coach list of a student.
 * This is rendered as a sub-page of the profile page and has access to
 * the Profile namespace.
 */
var Coaches = {
    coachCollection: null,
    requestCollection: null,
    url: "/api/v1/user/coaches",

    /**
     * Whether or not the actor has privileges to mutate the list of coaches
     * for the profile viewing viewed.
     */
    isMutable: false,

    init: function(isMutable) {
        this.isMutable = !!isMutable;

        var template = Templates.get("profile.coaches");
        var context = {
            "profile": Profile.profile.toJSON(),
            "identifier": Profile.profile.get("email") ||
                    Profile.profile.get("username"),
            "isMutable": this.isMutable
        };
        $("#tab-content-coaches").html(template(context));

        this.delegateEvents_();

        return $.ajax({
            type: "GET",
            url: this.url,
            data: Profile.getBaseRequestParams_(),
            dataType: "json",
            success: _.bind(this.onDataLoaded_, this),
            error: function(jqXhr) {
                if (jqXhr.status === 401) {
                    // Unauthorized. There should be no UI flow to have gotten
                    // the user into this state, so it could be they typed
                    // in the URL manually. Just redirect them to the root.
                    Profile.router.navigate(null, true);
                }
            }
        });
    },

    onDataLoaded_: function(users) {
        this.coachCollection = new Coaches.CoachCollection(users);
        // See https://github.com/documentcloud/backbone/issues/814
        // for why markCoachesAsSaved cannot be called in inititialize
        this.coachCollection.markCoachesAsSaved();

        new Coaches.CoachCollectionView({
            collection: Coaches.coachCollection,
            el: "#coach-list-container"
        }).render();
    },

    delegateEvents_: function() {
        $("#tab-content-coaches").on("keyup", "#coach-email",
            _.bind(this.onCoachEmailKeyup_, this));
        $("#tab-content-coaches").on("click", "#add-coach",
            _.bind(this.onAddCoach_, this));
    },

    onCoachEmailKeyup_: function(e) {
        if (e.keyCode === $.ui.keyCode.ENTER) {
            this.onAddCoach_();
        }
    },

    onAddCoach_: function() {
        var email = $.trim($("#coach-email").val());
        if (email) {
            Coaches.disableInput();
            this.coachCollection.addByEmail(email);
        }
    },

    disableInput: function() {
        $("#add-coach").addClass("disabled")
            .prop("disabled", true);

        $("#coach-email").prop("disabled", true);

        $(".coach-throbber").show();
    },

    enableInput: function() {
        $("#add-coach").removeClass("disabled")
            .prop("disabled", false);

        $("#coach-email").prop("disabled", false)
            .focus();

        $(".coach-throbber").hide();
    }
};

Coaches.CoachView = Backbone.View.extend({
    className: "coach-row",
    collection_: null,
    template_: null,

    events: {
        "click .controls .remove": "onRemoveCoach_",
        "click .controls .accept": "onAcceptCoach_",
        "click .controls .deny": "onDenyCoach_",
        "mouseenter .controls .remove": "onMouseEnterRemove_",
        "mouseleave .controls .remove": "onMouseLeaveRemove_"
    },

    initialize: function(options) {
        this.model.bind("change", this.render, this);
        this.collection_ = options.collection;
        this.template_ = Templates.get("profile.coach");
    },

    render: function() {
        var context = this.model.toJSON();
        context["isMutable"] = Coaches.isMutable &&
                !this.model.get("isParentOfLoggedInUser");
        $(this.el).html(this.template_(context));

        // TODO(marcia): Figure out why I need to call this..
        this.delegateEvents();

        return this;
    },

    onRemoveCoach_: function() {
        this.collection_.remove(this.model);
    },

    onAcceptCoach_: function() {
        this.model.set({
            isCoachingLoggedInUser: true,
            isRequestingToCoachLoggedInUser: false
        });
    },

    onDenyCoach_: function() {
        this.collection_.remove(this.model);
    },

    onMouseEnterRemove_: function(evt) {
        this.$(".controls .remove").addClass("orange");
    },

    onMouseLeaveRemove_: function(evt) {
        this.$(".controls .remove").removeClass("orange");
    }

});

Coaches.Coach = ProfileModel.extend({
    /**
     * Override toJSON to delete the id attribute since it is only used for
     * client-side bookkeeping.
     */
    toJSON: function() {
        var json = Coaches.Coach.__super__.toJSON.call(this);
        delete json["id"];
        return json;
    }
});

Coaches.CoachCollection = Backbone.Collection.extend({
    model: Coaches.Coach,

    initialize: function() {
        this.bind("add", this.save, this);
        this.bind("remove", this.save, this);
        this.bind("change", this.save, this);
    },

    comparator: function(model) {
        // TODO(marcia): Once we upgrade to Backbone 0.9,
        // we could define this as a sort instead of a sortBy
        // http://documentcloud.github.com/backbone/#Collection-comparator
        var isCoaching = model.get("isCoachingLoggedInUser"),
            email = model.get("email").toLowerCase();

        // Show pending requests before coaches,
        // then order alphabetically
        return (isCoaching ? "b" : "a") + " " + email;
    },

    findByEmail: function(email) {
        return this.find(function(model) {
            return model.get("email") === email;
        });
    },

    addByEmail: function(email) {
        var attrs = {
                email: email,
                isCoachingLoggedInUser: true
            };

        var model = this.findByEmail(email);

        if (model) {
            if (model.get("isCoachingLoggedInUser")) {
                // Already a coach
                var message = email + " is already your coach.";
                this.trigger("showError", message);
            } else {
                // Åccept the pending coach request
                model.set({isCoachingLoggedInUser: true});
            }
        } else {
            // Add the coach to the collection
            this.add(attrs);
        }
    },

    save: function() {
        this.debouncedSave_();
    },

    debouncedSave_: _.debounce(function() {
        var options = {
            url: Coaches.url,
            contentType: "application/json",
            success: _.bind(this.onSaveSuccess_, this),
            error: _.bind(this.onSaveError_, this)
        };

        options["data"] = JSON.stringify(this.toJSON());

        Backbone.sync("update", null, options);
    }, 750),

    onSaveSuccess_: function() {
        this.markCoachesAsSaved();
        this.trigger("saveSuccess");
        Coaches.enableInput();
    },

    onSaveError_: function() {
        this.removeUnsavedCoaches_();
        this.trigger("saveError");
    },

    increasingId: 0,

    /**
     * Mark which coach models have been saved to server,
     * which lets us remove un-saved / invalid coaches on error.
     */
    markCoachesAsSaved: function() {
        this.each(function(model) {
            // Backbone models without an id are considered
            // to be new, as in not yet saved to server.
            // Append an increasing number since collections cannot have
            // models with the same id, as of Backbone 0.9
            model.set({id: "marks-model-as-saved-on-server" + this.increasingId++},
                    {silent: true});
        }, this);
    },

    removeUnsavedCoaches_: function() {
        var modelsToRemove = this.filter(function(model) {
            return model.isNew();
        });

        // Don't trigger saves when removing invalid coaches
        this.remove(modelsToRemove, {silent: true});

        // Trigger removal from view
        _.each(modelsToRemove, _.bind(function(model) {
                this.trigger("removeFromView", model);
            }, this));
    }
});

Coaches.CoachCollectionView = Backbone.View.extend({
    rendered_: false,
    onlyAddingCoaches_: true,

    initialize: function(options) {
        this.coachViews_ = [];

        this.collection.each(this.onAdd_, this);

        this.collection.bind("add", this.onAdd_, this)
            .bind("remove", this.onRemove_, this)
            .bind("removeFromView", this.onRemove_, this);

        this.collection.bind("add", this.handleEmptyNotification_, this)
            .bind("remove", this.handleEmptyNotification_, this)
            .bind("removeFromView", this.handleEmptyNotification_, this);

        this.collection.bind("saveSuccess", this.onSaveSuccess_, this)
            .bind("saveError", this.onSaveError_, this)
            .bind("showError", this.showError_, this);
    },

    onSaveSuccess_: function() {
        // Clear textfield only if we successfully added a coach,
        // as opposed to removing a coach.
        if (this.onlyAddingCoaches_) {
            $("#coach-email").val("");
        }
        this.onlyAddingCoaches_ = true;
    },

    onSaveError_: function() {
        this.showError_("We couldn't find anyone with that email.");
    },

    onAdd_: function(model) {
        var coachView = new Coaches.CoachView({
            model: model,
            collection: this.collection
        });
        this.coachViews_.push(coachView);
        if (this.rendered_) {
            $(this.el).prepend(coachView.render().el);
        }
    },

    onRemove_: function(model) {
        var viewToRemove = _.find(this.coachViews_, function(view) {
                return view.model === model;
            });

        if (viewToRemove) {
            this.onlyAddingCoaches_ = false;

            this.coachViews_ = _.without(this.coachViews_, viewToRemove);

            if (this.rendered_) {
                $(viewToRemove.el).fadeOut(function() {
                    viewToRemove.remove();
                });
            }
        }
    },

    showEmptyNotification_: function() {
        if (!this.emptyNotification_) {
            var template = Templates.get("profile.no-coaches");
            this.emptyNotification_ = $("<div>").addClass("empty-notification").html(template());
            $(this.el).append(this.emptyNotification_);
        }
        this.$(".empty-notification").show();
    },

    handleEmptyNotification_: function() {
        if (this.collection.isEmpty()) {
            this.showEmptyNotification_();
        } else {
            this.$(".empty-notification").hide();
        }
    },

    showError_: function(message) {
        $(".coaches-section .notification.error").text(message)
            .show()
            .delay(2000)
            .fadeOut(function() {
                $(this).text("");
            });

        Coaches.enableInput();
    },

    render: function() {
        this.rendered_ = true;
        $(this.el).empty();

        this.handleEmptyNotification_();

        _.each(this.coachViews_, function(view) {
            $(this.el).append(view.render().el);
        }, this);

        return this;
    }
});
