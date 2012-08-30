/**
 * Logic to deal with with step 2 of the signup process, asking the user
 * for additional information like password and username (after
 * having verified her e-mail address already).
 */

/**
 * Initializes the form for completing the signup process
 */
Login.initCompleteSignupForm = function(options) {
    Login.basePostLoginUrl = (options && options["basePostLoginUrl"]) || "";

    Login.focusOnFirstEmpty([
            "#bijnaam", "#geslacht", "#gebruikersnaam", "#wachtwoord"]);

    Login.attachSubmitHandler(Login.submitCompleteSignup);
};

/**
 * Submits the complete signup attempt if it passes pre-checks.
 */
Login.submitCompleteSignup = function() {
    var valid = Login.ensureValid_("#bijnaam", "Geef je naam op.") &&
            Login.ensureValid_("#gebruikersnaam", "Kies een gebruikersnaam.") &&
            Login.ensureValid_("#wachtwoord", "kies een wachtwoord");

    if (valid) {
        Login.asyncFormPost(
                $("#signup-form"),
                function(data) {
                    // 200 success, but the signup may have failed.
                    if (data["errors"]) {
                        Login.onCompleteSignupError(data["errors"]);
                    } else {
                        Login.onCompleteSignupSucess(data);
                    }
                },
                function(data) {
                    // Hard fail - can't seem to talk to server right now.
                    // TODO(benkomalo): handle.
                });
    }
};

/**
 * Handles a success response to the POST to complete the signup.
 * This will cause the page to refresh and to set the auth cookie.
 */
Login.onCompleteSignupSucess = function(data) {
    Login.onPasswordLoginSuccess(data);
};

/**
 * Handles an error from the server on an attempt to complete
 * the signup - there was probably invalid data in the forms.
 */
Login.onCompleteSignupError = function(errors) {
    var firstFailed = _.find(
            ["bijnaam", "gebruikersnaam", "wachtwoord"],
            function(fieldName) {
                return fieldName in errors;
            });
    if (!firstFailed) {
        // Shouldn't happen, but just in case we get unknown errors.
        $("#error-text").text("Oeps.. Er is iets verkeerd gegaan. Probeer het opnieuw.");
        return;
    }

    // Only show the first failed message and focus to it.
    $("#error-text").text(errors[firstFailed]);
    $("#" + firstFailed).focus();
};

