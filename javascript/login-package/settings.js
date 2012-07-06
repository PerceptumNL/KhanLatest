
/**
 * Utilities for changing a user's password.
 * This is intended to be used in a minimal form, usually in an iframe.
 */
var Settings = {

    init: function() {
        $("#password2").on(
                "keypress",
                function(e) {
                    if (e.keyCode === $.ui.keyCode.ENTER) {
                        e.preventDefault();
                        Settings.submitForm_();
                    }
                });

        // Focus on the first empty field (existing password on normal pw
        // changes, the first password on pw resets)
        if ($("#existing").get(0)) {
            $("#existing").focus();
        } else {
            $("#password1").focus();
        }

        $("#submit-settings").click(_.bind(Settings.onClickSubmit_, Settings));
    },

    onClickSubmit_: function(e) {
        e.preventDefault();
        this.submitForm_();
    },

    submitForm_: function() {
        if (!this.validate_()) {
            return;
        }

        $("#submit-settings")
            .val("Submitting...")
            .prop("disabled", true);

        // We can't use $.ajax to send - we have to actually do a form POST
        // since the requirement of sending over https means we'd
        // break same-origin policies of browser XHR's
        $("#pw-change-form")
            .find("#continue")
                .val(window.location.href)
                .end()
            .submit();
    },

    // Must be consistent with what's on the server in auth/passwords.py
    MIN_PASSWORD_LENGTH: 8,

    validate_: function() {
        var password1 = $("#password1").val();
        var password2 = $("#password2").val();

        // Check basic length.
        if (password1.length < Settings.MIN_PASSWORD_LENGTH) {
            $(".message-container").addClass("error").text("The new password is too short");
            $("#password1").focus();
            return false;

        // Check matching.
        } else if (password2 !== password1) {
            $(".message-container").addClass("error").text("The passwords don't match");
            $("#password1").focus();
            return false;
        }

        // We're good!
        $(".message-container").text("");
        return true;
    }
};
