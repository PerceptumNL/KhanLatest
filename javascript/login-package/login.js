/**
 * Various utilities related to the login page.
 *
 * This includes common utilities used in various login/account management
 * forms, as well as the app logic for the actual login page.
 */

// TODO(benkomalo): we should probably separate out a lot of the common form
// utilities to a separate file.

// TODO(benkomalo): do more on-the-fly client side validation of things like
// valid usernames or passwords

// Namespace
var Login = Login || {};

/**
 * Initializes the host login page. Note that most of the username/password
 * fields of the login page are hosted in an iframe so it can be sent
 * over https. Google/FB logins are in the outer container.
 */
Login.initLoginPage = function(options) {
    $("#login-facebook").click(function(e) {
        Login.connectWithFacebook(
            options["continueUrl"], true /* requireExtendedPerms */);
    });
};

/**
 * A base URL for the app that can be used to redirect users.
 * This is needed by inner iframes that may be hosted on https
 * domains and need to forward the user to a normal http URL
 * after a successful login, or other account management activity.
 *
 * If non-empty, this must contain a trailing slash.
 */
Login.baseAppUrl = "";

/**
 * Initializes the inner contents (within the iframe) of the login
 * form.
 */
Login.initLoginForm = function(options) {
    Login.baseAppUrl = options["baseAppUrl"] || "";

    if ($("#identifier").val()) {
        // Email/username filled in from previous attempt.
        $("#password").focus();
    } else {
        $("#identifier").focus();
    }

    Login.attachSubmitHandler(Login.loginWithPassword);
};

/**
 * Use Facebook's JS SDK to connect with Facebook.
 * @param {string} continueUrl The URL to redirect to after a successful login.
 * @param {boolean} requireExtendedPerms An optional parameter to indicate
 * whether or not the user needs to grant extended permissions to our app so we
 * can retrieve their e-mail address and publish Open Graph actions to FB.
 */
Login.connectWithFacebook = function(continueUrl, requireExtendedPerms) {
    FacebookUtil.runOnFbReady(function() {
        // TODO(benkomalo): add some visual indicator that we're trying.
        var extendedPerms = requireExtendedPerms ? {"scope": "email"} : undefined;
        FB.login(function(response) {
            if (response) {
                FacebookUtil.fixMissingCookie(response);
            }

            if (response["status"] === "connected") {
                FacebookUtil.markUsingFbLogin();
                var url = continueUrl || "/";
                if (url.indexOf("?") > -1) {
                    url += "&fb=1";
                } else {
                    url += "?fb=1";
                }

                window.location = url;
            } else {
                // TODO(benkomalo): handle - the user didn't login properly in facebook.
            }
       }, extendedPerms);
    });
};

/**
 * Login with a username and password.
 */
Login.loginWithPassword = function() {
    // Hide any previous failed login notification after any other attempt.
    // Use "visibility" so as to avoid any jerks in the layout.
    $("#error-text").css("visiblity", "hidden");

    // Pre-validate.
    if (Login.ensureValid_("#identifier", "Email or username required") &&
            Login.ensureValid_("#password", "Password required")) {
        Login.asyncFormPost(
                $("#login-form"),
                function(data) {
                    // Server responded with 200, but login may have failed.
                    if (data["errors"]) {
                        Login.onPasswordLoginFail(data["errors"]);
                    } else {
                        Login.onPasswordLoginSuccess(data);
                        // Don't re-enable the login button as we're about
                        // to refresh the page.
                    }
                },
                function(data) {
                    // Hard failure - server is inaccessible or having issues
                    // TODO(benkomalo): handle
                });
    }
};

Login.submitDisabled_ = false;
Login.navigatingAway_ = false;

/**
 * Disables form submit on a login attempt, to prevent duplicate tries.
 */
Login.disableSubmit_ = function() {
    $("#submit-button").attr("disabled", true);
    Login.submitDisabled_ = true;
};

/**
 * Restores form submission ability, usually after a response from a server
 * from a login/signup attempt.
 */
Login.enableSubmit_ = function() {
    $("#submit-button").removeAttr("disabled");
    Login.submitDisabled_ = false;
};

/**
 * Handle a failed attempt at logging in with a username/password.
 */
Login.onPasswordLoginFail = function(errors) {
    var text;
    if (errors["badlogin"]) {
        text = "Your login or password is incorrect.";
    } else {
        // Unexpected error. This shouldn't really happen but
        // just in case...
        text = "Error logging in. Please try again.";
    }

    $("#error-text").text(text).css("visibility", "");
    $("#password").val("").focus();
};

/**
 * Handle a successful login response, which includes auth data.
 * This will cause the page to fully reload to a /postlogin URL
 * generated by the server containing the new auth token which will be
 * set as a cookie.
 */
Login.onPasswordLoginSuccess = function(data) {
    var auth = data["auth"];
    var continueUri = data["continue"] || "/";
    window.top.location.replace(
            Login.baseAppUrl +
            "postlogin?continue=" + encodeURIComponent(continueUri) +
            "&auth=" + encodeURIComponent(auth));

    Login.navigatingAway_ = true;
};

/**
 * Validates a field in a login/signup form and displays an error on failure
 * on $("error-text").
 * If validation fails, the field will automatically be focused.
 */
Login.ensureValid_ = function(
        selector, errorText, checkFunc) {
    // By default - check that it's not just empty whitespace.
    checkFunc = checkFunc || function() {
        var value = $(selector).val();
        return !!$.trim(value);
    };
    if (!checkFunc()) {
        $("#error-text").text(errorText);
        $(selector).focus();
        return false;
    }

    // Include whitespace so that empty/non-empty values don't affect layout.
    $("#error-text").html("&nbsp;");
    return true;
};

/**
 * Submits a form in the background via a hidden iframe.
 * Only one form may be in flight at a time, since only a single iframe
 * is used.
 *
 * This is useful so that the page doesn't have to navigate away and we can
 * handle errors more gracefully.
 *
 * Note that this is quite crude and makes no guarantees about history
 * state (on most browsers, each request will likely create a history entry).
 */
Login.asyncFormPost = function(jelForm, success, error) {
    if (Login.submitDisabled_) {
        return;
    }

    Login.disableSubmit_();
    $.ajax({
        "type": "POST",
        "url": jelForm.prop("src"),
        "data": jelForm.serialize(),
        "dataType": "json",
        "success": success,
        "error": error,
        "complete": function() {
            if (!Login.navigatingAway_) {
                Login.enableSubmit_();
            }
        }
    });
};

/**
 * Attaches a submit handler for a form by listening to an ENTER keypress, as
 * well as a button click on the appropriate form fields.
 * By convention, an input with an ID of "password" should be the last field
 * in the form, and is where an ENTER should work, and the submit button
 * should have an ID of "submit-button".
 */
Login.attachSubmitHandler = function(handler) {
    $("#password").on("keypress", function(e) {
        if (e.keyCode === $.ui.keyCode.ENTER) {
            e.preventDefault();
            handler();
        }
    });

    $("#submit-button").click(function(e) {
        e.preventDefault();
        handler();
    });
};

/**
 * Initializes a birthday picker, initializing it to the proper
 * value based on the "date" data attribute.
 * Defaults to January 1, 13 years ago.
 */
Login.initBirthdayPicker = function(selector) {
    var jel = $(selector);
    if (!jel.length) {
        return;
    }

    var dateData = $(selector).data("date");
    var defaultDate;
    if (dateData) {
        var parts = dateData.split("-");
        if (parts.length === 3) {
            var year = parseInt(parts[0], 10);
            var month = parseInt(parts[1], 10) - 1;
            var date = parseInt(parts[2], 10);
            if (!isNaN(year + month + date)) {
                defaultDate = new Date(year, month, date);
            }
        }
    }
    if (!defaultDate) {
        // Jan 1, 13 years ago
        defaultDate = new Date(new Date().getFullYear() - 13, 0, 1);
    }

    jel.birthdaypicker({
        placeholder: false,
        classes: "simple-input ui-corner-all login-input",
        defaultDate: defaultDate
    });
};

/**
 * Iterate through a list of form elements and focus on the first empty one.
 */
Login.focusOnFirstEmpty = function(selectors) {
    var firstEmpty = _.find(
            _.map(selectors, $),
            function(jel) {
                return !jel.val() || jel.val() === "unspecified";
            });

    if (firstEmpty) {
        firstEmpty.focus();
        return true;
    }
    return false;
};
