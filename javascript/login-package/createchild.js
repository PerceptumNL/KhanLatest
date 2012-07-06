/**
 * Logic to handle the form for creating a child account.
 */

/**
 * Initializes the page for creating a child account.
 */
Login.initCreateChildForm = function(options) {
    Login.baseAppUrl = options["baseAppUrl"] || "";

    Login.initBirthdayPicker("#birthday-picker");
    Login.focusOnFirstEmpty(["#username", "#password"]);
    Login.attachSubmitHandler(Login.submitCreateChild);

    _.each($(".icon"), function(icon) {
        var content = $(icon).prop("title");
        // TODO(benkomalo): find an appropriate class/style for this
        $(icon).qtip({
            content: {
                text: content
            },
            style: "ui-tooltip-light",
            position: {
                my: "top right",
                at: "bottom left"
            },
            hide: {
                fixed: true,
                delay: 150
            }
        });
    });
};

/**
 * Submits the form to create a child account.
 */
Login.submitCreateChild = function() {
    var valid = Login.ensureValid_("#username", "Please pick a username.") &&
            Login.ensureValid_("#password", "We need a password from you.");

    if (valid) {
        Login.asyncFormPost(
                $("#create-child-form"),
                function(data) {
                    // 200 success, but the creation may have failed.
                    if (data["errors"]) {
                        Login.onCreateChildError(data["errors"]);
                    } else {
                        Login.onCreateChildSuccess(data);
                    }
                },
                function(data) {
                    // Hard fail - can't seem to talk to server right now.
                    // TODO(benkomalo): handle.
                });
    }
};

/**
 * Handles a successful response from a server after having created a child account.
 */
Login.onCreateChildSuccess = function(data) {
    // TODO(benkomalo): This should auto-select the "My child" tab
    // in the destination and give a "success" prompt.

    // Send the user to the "manage students" list, where their newly
    // created child will be listed.
    window.top.location = Login.baseAppUrl + "students";
};

/**
 * Handles a server error in an attempt to create a child account.
 */
Login.onCreateChildError = function(errors) {
    // Look for the first failure among the free-form inputs.
    var firstFailed = _.find(
            ["username", "password"],
            function(fieldName) {
                return fieldName in errors;
            });
    if (firstFailed) {
        $("#error-text").text(errors[firstFailed]);
        $("#" + firstFailed).focus();
    } else {
        // Something else failed - just show the first error message and
        // leave the focus where it is.
        $("#error-text").text(_.values(errors)[0]);
    }
};

