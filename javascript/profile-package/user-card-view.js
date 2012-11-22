UserCardView = Backbone.View.extend({
    className: "user-card",

    events: {
        "click .add-remove-coach": "onAddRemoveCoachClicked_"
     },

     editEvents: {
         "click .avatar-pic-container": "onAvatarClick_",
         "click .edit-display-case": "onEditDisplayCaseClicked_",
         "click .edit-avatar": "onAvatarClick_",
         "click .edit-visibility": "toggleProfileVisibility"
     },

     fullEditEvents: {
         "click .nickname-container": "onEditBasicInfoClicked_",
         "click .edit-basic-info": "onEditBasicInfoClicked_"
     },

    initialize: function() {
        this.template = Templates.get("profile.user-card");

        this.model.bind("change:avatarSrc", _.bind(this.onAvatarChanged_, this));
        this.model.bind("change:isCoachingLoggedInUser",
                _.bind(this.onIsCoachingLoggedInUserChanged_, this));
        this.model.bind("change:nickname", function(model) {
                $(".nickname").text(model.get("nickname"));
        });
        this.model.bind("change:isPublic", this.onIsPublicChanged_);

        /**
         * The picker UI component which shows a dialog to change the avatar.
         * @type {Avatar.Picker}
         */
        this.avatarPicker_ = null;
        this.usernamePicker_ = null;
    },

    /**
     * Updates the source preview of the avatar. This does not affect the model.
     */
    onAvatarChanged_: function() {
        this.$("#avatar-pic").attr("src", this.model.get("avatarSrc"));
    },

    render: function() {
        var json = this.model.toJSON();
        // TODO: this data isn't specific to any profile and is more about the library.
        // It should probably be moved out eventially.
        json["countExercises"] = UserCardView.countExercises;
        json["countVideos"] = UserCardView.countVideos;
        $(this.el).html(this.template(json)).find("abbr.timeago").timeago();

        this.delegateEditEvents_();

        return this;
    },

    onDropdownOpen_: function() {
        this.$(".dropdown-toggle").addClass("toggled");
    },

    onDropdownClose_: function() {
        this.$(".dropdown-toggle").removeClass("toggled");
    },

    delegateEditEvents_: function() {
        if (this.model.isEditable()) {
            this.bindQtip_();

            if (this.model.isFullyEditable()) {
                _.extend(this.editEvents, this.fullEditEvents);
            }
            this.delegateEvents(this.editEvents);
            this.$(".dropdown-toggle").dropdown()
                .bind("open", _.bind(this.onDropdownOpen_, this))
                .bind("close", _.bind(this.onDropdownClose_, this));
        }
    },

    bindQtip_: function() {
        this.$(".edit-visibility").qtip({
            content: {
                text:
                    "Als je jouw profiel openbaar maakt zal" +
                    "de informatie op deze kaart " +
                    "zichtbaar zijn voor iedereen die jouw profiel bezoekt.",
                title: {
                    text: "Profiel Privacy Instelling"
                }
            },
            style: {
                classes: "ui-tooltip-light ui-tooltip-shadow",
                width: "250px"
            },
            position: {
                my: "top right",
                at: "bottom center"
            },
            show: {
                delay: 500
            },
            hide: {
                fixed: true,
                delay: 150
            }
        });
    },

    onAvatarClick_: function(e) {
        if (!this.avatarPicker_) {
            this.avatarPicker_ = new Avatar.Picker(this.model);
        }
        this.avatarPicker_.show();
    },

    onAddRemoveCoachClicked_: function(e) {
        var options = {
            success: _.bind(this.onAddRemoveCoachSuccess_, this),
            error: _.bind(this.onAddRemoveCoachError_, this)
        };

        this.model.toggleIsCoachingLoggedInUser(options);
    },

    onAddRemoveCoachSuccess_: function(data) {
        // TODO: message to user
    },

    onAddRemoveCoachError_: function(data) {
        // TODO: message to user

        // Because the add/remove action failed,
        // toggle back to original client-side state.
        this.model.toggleIsCoachingLoggedInUser();
    },

    /**
     * Toggles the display of the add/remove coach buttons.
     * Note that only one is showing at any time.
     */
    onIsCoachingLoggedInUserChanged_: function() {
        this.$(".add-remove-coach").toggle();
    },

    onEditBasicInfoClicked_: function(evt, setPublic) {
        if (!this.usernamePicker_) {
            this.usernamePicker_ = new UsernamePickerView({model: this.model});
            $("body").append(this.usernamePicker_.render().el);
        }
        this.usernamePicker_.toggle(setPublic);
    },

    onEditDisplayCaseClicked_: function(e) {
        // TODO: Consider handling outside-the-widget dismissal clicks differently
        e.stopPropagation();
        $(".display-case-cover").click();
    },

    toggleProfileVisibility: function(e) {
        if (!this.model.get("username")) {
            // Profiles can't be made public until the user acquires a
            // username first. Pop up the dialog to do that.
            this.onEditBasicInfoClicked_(null, true);
            return;
        }
        var isPublic = this.model.get("isPublic");
        this.model.save({ isPublic: !isPublic });
    },

    onIsPublicChanged_: function(model, isPublic) {
        var jel = $(".visibility-toggler");
        if (isPublic) {
            jel.removeClass("private")
                .addClass("public")
                .text("Profile is public");
        } else {
            jel.removeClass("public")
                .addClass("private")
                .text("Profiel is prive");
        }
        jel.effect("bounce");
    }

});

// TODO: these should probably go into some other place about the library.
/**
 * The total number of videos in the Khan Academy library.
 */
UserCardView.countVideos = 0;

/**
 * The total number of exercises in the Khan Academy library.
 */
UserCardView.countExercises = 0;
