/**
 * A component to display a list of avatars and select one for
 * the current user.
 *
 * Avatars are pre-defined from a list that a user has access to.
 * The mechanics of which avatars are accessable are externalized
 * and not specific to this implementation.
 */

/** Namespace. */
var Avatar = Avatar || {};


/**
 * The main UI component which displays a modal dialog to select
 * a list of avatars for an image.
 * @constructor
 */
Avatar.Picker = function(userModel) {
    /**
     * The container element of the dialog.
     */
    this.el = null;

    /**
     * The root element of the dialog contents.
     */
    this.contentEl = null;

    /**
     * The underlying model for the user profile that gets modified
     * when an avatar is selected.
     */
    this.userModel = userModel;

    /**
     * The list of avatars bucketed by category. This corresponds
     * directly to the JSON returned by the server (see fetchData_)
     */
    this.avatarData_ = [];
};

Avatar.Picker.template = Templates.get("profile.avatar-picker");

/**
 * Renders the contents of the picker and displays it.
 */
Avatar.Picker.prototype.getTemplateContext_ = function() {
    // Dummy data for now. Replace with the real thing.
    return {
        selectedSrc: this.userModel.get("avatarSrc"),
        categories: this.avatarData_
    };
};

/**
 * Binds event handlers necessary to make this interactive.
 */
Avatar.Picker.prototype.bindEvents_ = function() {
    $(this.el).delegate(
            ".category-avatars .avatar",
            "click",
            _.bind(this.onAvatarSelected_, this))
        .delegate(
            ".category-avatars .avatar",
            "mouseenter",
            function(ev) { $(ev.currentTarget).not(".locked").addClass("hover"); })
        .delegate(
            ".category-avatars .avatar",
            "mouseleave",
            function(ev) { $(ev.currentTarget).removeClass("hover"); });

    this.userModel.bind("change:avatarSrc",
            _.bind(this.onAvatarChanged_, this));
};

/**
 * Handles a selection to an avatar in the list.
 */
Avatar.Picker.prototype.onAvatarSelected_ = function(ev) {
    if ($(ev.currentTarget).hasClass("locked")) {
        return;
    }

    var src = $(ev.currentTarget).find("img.avatar-preview").attr("src");
    var name = $(ev.currentTarget).attr("data");
    if (src && name) {
        this.userModel.set({
            "avatarName": name,
            "avatarSrc": src
        });
    }
};

/**
 * Handles a change to the selected avatar.
 */
Avatar.Picker.prototype.onAvatarChanged_ = function() {
    var newSrc = this.userModel.get("avatarSrc");
    $(this.contentEl)
            .find(".avatar")
                .removeClass("selected")
            .end()
            .find("img.avatar-preview[src='" + newSrc + "']")
                .parent(".avatar").addClass("selected");
};

/**
 * Fetches the list of avatars from the server.
 */
Avatar.Picker.prototype.fetchData_ = function() {
    $.ajax({
        method: "GET",
        url: "/api/v1/avatars",
        data: { casing: "camel" },
        success: _.bind(this.onDataLoaded_, this),
        error: function() {
            // TODO: handle
        }
    });
};

/**
 * Handles a successful response from the server for the list of avatars.
 */
Avatar.Picker.prototype.onDataLoaded_ = function(data) {
    this.avatarData_ = data;

    // Note that this will just render hidden if the dialog is
    // not visible. That's OK.
    $(this.contentEl).html(
            Avatar.Picker.template(this.getTemplateContext_()));

    // Sync UI to initial state.
    this.onAvatarChanged_();

};

/**
 * Renders the contents of the picker and displays it.
 */
Avatar.Picker.prototype.show = function() {
    if (!this.el) {
        var rootJel = $("<div class='avatar-picker modal fade hide'></div>");
        var contentJel = rootJel;
        this.el = rootJel.get(0);
        this.contentEl = contentJel.get(0);
        this.bindEvents_();
        this.fetchData_();
    }

    $(this.contentEl).html(
            Avatar.Picker.template(this.getTemplateContext_()));

    // Sync UI to initial state.
    this.onAvatarChanged_();

    $(this.el).modal({
        keyboard: true,
        backdrop: true,
        show: true
    }).on("hidden", _.bind(this.onHide_, this));
};

/**
 * Handles a hiding of the picker, and saves the data.
 */
Avatar.Picker.prototype.onHide_ = function() {
    this.userModel.save();
};

