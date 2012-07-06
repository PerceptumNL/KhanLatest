
/**
 * Utilities for interacting with Facebook and its JS SDK.
 */
var FacebookUtil = {

    init: function() {
        if (!window.FB_APP_ID) {
            return;
        }

        window.fbAsyncInit = function() {
            FB.init({
                appId: FB_APP_ID,
                status: false, // Fetch status conditionally below.
                cookie: true,
                xfbml: true,
                oauth: true
            });

            if (FacebookUtil.isUsingFbLogin()) {
                // Only retrieve the status if the user has opted to login
                // with Facebook
                FB.getLoginStatus(function(response) {
                    if (response.authResponse) {
                        FacebookUtil.fixMissingCookie(response.authResponse);
                    } else {
                        // The user is no longer signed into Facebook - must
                        // have logged out of FB in another window or disconnected
                        // the service in their FB settings page.
                        eraseCookie("fbl");
                    }
                });
            }

            // auth.login is fired when the auth status changes to "connected"
            FB.Event.subscribe('auth.login', function(response) {
                FacebookUtil.setFacebookID(response.authResponse.userID);
            });

            $("#page_logout").click(function(e) {
                var hostname = window.location.hostname;

                // By convention, dev servers lead with "local." in the address
                // even though the domain registered with FB is without it.
                if (hostname.indexOf("local.") === 0) {
                    hostname = hostname.substring(6);
                }

                // The Facebook cookies are set on ".www.khanacademy.org",
                // though older ones are not. Clear both to be safe.
                eraseCookie("fbsr_" + FB_APP_ID);
                eraseCookie("fbsr_" + FB_APP_ID, "." + hostname);
                eraseCookie("fbm_" + FB_APP_ID);
                eraseCookie("fbm_" + FB_APP_ID, "." + hostname);
                eraseCookie("fbl");

                if (FacebookUtil.isUsingFbLogin()) {
                    // If the user used FB to login, log them out of FB, too.
                    try {
                        FB.logout(function() {
                            window.location = $("#page_logout").attr("href");
                        });
                        e.preventDefault();
                        return false;
                    } catch (e) {
                        // FB.logout can throw if the user isn't actually
                        // signed into FB. We can get into this state
                        // in a few odd ways (if they re-sign in using Google,
                        // then sign out of FB in a separate tab).
                        // Just ignore it, and have logout work as normal.
                    }
                }
            });

            FacebookUtil.fbReadyDeferred_.resolve();
        };

        $(function() {
            var e = document.createElement("script"); e.async = true;
            e.src = document.location.protocol + "//connect.facebook.net/en_US/all.js";
            document.getElementById("fb-root").appendChild(e);
        });
    },

    fbReadyDeferred_: new $.Deferred(),
    runOnFbReady: function(func) {
        this.fbReadyDeferred_.done(func);
    },

    isUsingFbLoginCached_: undefined,

    /**
     * Facebook User ID of current logged-in Facebook user. Set by FB.Event
     * subscription to 'auth.login'.
     */
    facebookID: undefined,

    getFacebookID: function() {
        if (window.USERNAME && FacebookUtil.isUsingFbLogin()) {
            return FacebookUtil.facebookID || LocalStore.get("facebookID");
        }
        return null;
    },

    setFacebookID: function(facebookID) {
        FacebookUtil.facebookID = facebookID;
        LocalStore.set("facebookID", facebookID);
    },

    /**
     * Whether or not the user has opted to sign in to Khan Academy
     * using Facebook.
     */
    isUsingFbLogin: function() {
        if (FacebookUtil.isUsingFbLoginCached_ === undefined) {
            FacebookUtil.isUsingFbLoginCached_ = readCookie("fbl") || false;
        }
        return FacebookUtil.isUsingFbLoginCached_;
    },

    /**
     * Indicates that the user has opted to sign in to Khan Academy
     * using Facebook.
     */
    markUsingFbLogin: function() {
        // Generously give 30 days to the fbl cookie, which indicates
        // that the user is using FB to login.
        createCookie("fbl", true, 30);
    },

    /**
     * Use LocalStore to record that the user has given us the "publish_stream"
     * permission on Facebook.
     * @param {boolean} permissionGranted
     */
    setPublishStreamPermission: function(permissionGranted) {
        var data = LocalStore.get("fbPublishStream");
        if (!data) {
            // we're storing data as an object instead of an array for easy
            // lookups
            data = {};
        }
        var facebookID = FacebookUtil.getFacebookID();
        if (facebookID) {
            if (permissionGranted) {
                data[facebookID] = true;
            } else {
                delete data[facebookID];
            }
            LocalStore.set("fbPublishStream", data);
        }
    },

    /**
     * Returns true if the LocalStore indicates the the user has given us the
     * "publish_stream" permission on Facebook.
     */
    hasPublishStreamPermission: function() {
        var data = LocalStore.get("fbPublishStream");
        if (data && data[FacebookUtil.getFacebookID()]) {
            return true;
        }
        return false;
    },

    fixMissingCookie: function(authResponse) {
        // In certain circumstances, Facebook's JS SDK fails to set their cookie
        // but still thinks users are logged in. To avoid continuous reloads, we
        // set the cookie manually. See http://forum.developers.facebook.net/viewtopic.php?id=67438.

        if (readCookie("fbsr_" + FB_APP_ID)) {
            return;
        }

        if (authResponse && authResponse.signedRequest) {
            // Explicitly use a session cookie here for IE's sake.
            createCookie("fbsr_" + FB_APP_ID, authResponse.signedRequest);
        }
    }
};
FacebookUtil.init();

