/**
 * Code to handle the profile info changer.
 */
UsernamePickerView = Backbone.View.extend({
    id: "username-picker-container",
    setPublicAfterSave_: false,
    savePending_: false,

    /**
     * Whether or not the nickname is acceptable/valid to try and save.
     */
    nicknameFieldAcceptable_: true,

    /**
     * Whether or not the username field is acceptable. Note that an empty
     * username, while invalid, is acceptable in the field if the user
     * had not selected one prior to opening this view.
     */
    usernameFieldAcceptable_: true,

    events: {
        "keypress .nickname": "onNicknameKeypress_",
        "keypress .username": "onUsernameKeypress_",
        "click :input": "onInputClick_",
        "click #save-profile-info": "onSaveClick_",
        "click #cancel-profile-info": "onCancelClicked_"
    },

    delegateEvents: function(events) {
        $(this.el)
                .on(Keys.textChangeEvents,
                    ".nickname",
                    Keys.wrapTextChangeHandler(this.onNicknameInput_, this))
                .on(Keys.textChangeEvents,
                    ".username",
                    Keys.wrapTextChangeHandler(this.onUsernameInput_, this));
        UsernamePickerView.__super__.delegateEvents.call(this, events);
    },

    onInputClick_: function(e) {
        // Force focus on the input after a click. This is to work around
        // the fact that in IE, the input can sometimes not get focus,
        // even though the user is properly typing in it. Since only
        // events with focus fire keyup events, we would otherwise miss them.
        $(e.target).focus();
    },

    initialize: function() {
        this.template = Templates.get("profile.username-picker");
        this.shouldShowUsernameWarning_ = false;
        this.model.bind("validate:nickname", this.onValidateNickname_, this);
        this.model.bind("validate:username", this.onValidateUsername_, this);
        this.model.bind("savesuccess", this.onSaveSuccess_, this);
        this.model.bind("error", this.onSaveRejected_, this);
    },

    render: function() {
        // TODO: Make idempotent
        // maybe making the resetFields_ function obsolete
        var context = {
                username: this.model.get("username"),
                nickname: this.model.get("nickname")
            },
            html = this.template(context);

        $(this.el).html(html)
            .addClass("modal fade hide")
            .modal({
                keyboard: true,
                backdrop: true
            })
            .bind("hidden", _.bind(this.resetFields_, this))
            .bind("shown", _.bind(this.onPickerShown_, this));
        return this;
    },

    onCancelClicked_: function() {
        this.toggle();
    },

    toggle: function(setPublic) {
        $(this.el).modal("toggle");
        this.setPublicAfterSave_ = setPublic;
        if (setPublic) {
            $(".notification.info").show();
            $("#save-profile-info").val("Save and make profile public");
        }
    },

    resetFields_: function() {
        var nickname = this.model.get("nickname"),
            username = this.model.get("username");

        this.nicknameFieldAcceptable_ = true;
        this.usernameFieldAcceptable_ = true;
        this.$(".notification").hide();
        this.$(".nickname").val(nickname);
        this.$(".username").val(username);
        this.$(".example-username").text(username);
        this.$(".sidenote").text("").removeClass("success").removeClass("error");
        this.$("#save-profile-info").prop("disabled", false).val("Save");
    },

    onPickerShown_: function() {
        // If the user already has a username, be sure that we warn them about
        // the holding period that happens if they change it.
        Promos.hasUserSeen("Username change warning", function(hasSeen) {
            this.shouldShowUsernameWarning_ = !hasSeen;
        }, this);
    },

    onNicknameInput_: function(e) {
        this.model.validateNickname(this.getFormValue_(".nickname"));
    },

    onNicknameKeypress_: function(e) {
        if (e.keyCode === $.ui.keyCode.ENTER) {
            // Treat enter as "tab" to the next field.
            this.$(".username").focus();
        }
    },

    onUsernameKeypress_: function(e) {
        if (e.keyCode === $.ui.keyCode.ENTER) {
            if (!this.$("#save-profile-info").prop("disabled")) {
                this.$("#save-profile-info").click();
            }
            this.model.validateUsername(this.getFormValue_(".username"));
        }
    },

    onUsernameInput_: function(e) {
        this.$("#save-profile-info").prop("disabled", true);
        if (this.shouldShowUsernameWarning_ && this.model.get("username")) {
            $(".notification.error").show();
            Promos.markAsSeen("Username change warning");
            this.shouldShowUsernameWarning_ = false;
        }
        this.$(".example-username").text(this.getFormValue_(".username"));

        this.showSidenote_(".username-row", "Checking...");
        this.debouncedValidateUsername_();
    },

    debouncedValidateUsername_: _.debounce(function() {
        this.model.validateUsername(this.getFormValue_(".username"));
    }, 1000),

    syncSaveButtonState_: function() {
        this.$("#save-profile-info").prop(
                "disabled",
                !this.usernameFieldAcceptable_ || !this.nicknameFieldAcceptable_);
    },

    onValidateNickname_: function(isValid) {
        if (isValid) {
            this.showSidenote_(".nickname-row", "");
        } else {
            this.showSidenote_(".nickname-row", "Can't leave empty.", false);
        }

        this.usernameFieldAcceptable_ = isValid;
        this.syncSaveButtonState_();
    },

    onValidateUsername_: function(message, isValid) {
        this.showSidenote_(".username-row", message, isValid);

        // Accept the username if it's unchanged or if it's changed to
        // a valid value. Note that users may start with no username, which
        // is itself an "invalid" value (empty), but it's acceptable here
        // since we don't require they select a new username.
        this.usernameFieldAcceptable_ =
                this.getFormValue_(".username") === this.model.get("username") ||
                isValid;
        this.syncSaveButtonState_();
    },

    getFormValue_: function(selector) {
        return $.trim(this.$(selector).val());
    },

    /**
     * Show the message in the specified row's sidenote.
     * If isValid === true, show a green checkmark (success),
     * if isValid === false, show a red x (error),
     * otherwise, don't show any such indicator.
     */
    showSidenote_: function(rowSelector, message, isValid) {
        var jelSidenote = this.$(rowSelector).find(".sidenote"),
            message = message || "";

        // Note that isValid may be undefined, in which case neither class
        // is enabled.
        jelSidenote.toggleClass("success", isValid === true);
        jelSidenote.toggleClass("error", isValid === false);
        jelSidenote.text(message);
    },

    onSaveClick_: function() {
        var nickname = this.getFormValue_(".nickname"),
            username = this.getFormValue_(".username"),
            attrs = {
                nickname: nickname,
                username: username
            };

        if (this.setPublicAfterSave_) {
            attrs.isPublic = true;
        }

        var usernameChange = username != this.model.get("username");
        this.model.save(attrs);

        $("#save-profile-info").prop("disabled", true);
        if (usernameChange) {
            // Keep the modal open and wait for a save success, since this
            // is an important, ocean-boiling operation.
            $("#save-profile-info").val("Saving...");
            this.savePending_ = true;
        } else {
            this.toggle();
        }
    },

    onSaveSuccess_: function() {
        if (this.savePending_) {
            $(this.el).modal("hide");
            this.savePending_ = false;
        }
    },
    onSaveRejected_: function() {
        // No difference in behavior right now.
        this.onSaveSuccess_();
    }
});
