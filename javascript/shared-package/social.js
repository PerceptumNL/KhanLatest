
var Social = {

    init: function() {
        /** We're using a custom Twitter button, this code enables a popup */
        $("body").on("click", ".twitterShare", function(event) {
            var width = 550,
                height = 370,
                left = ($(window).width() - width) / 2,
                top = ($(window).height() - height) / 2,
                url = this.href,
                opts = "status=1" +
                    ",width=" + width +
                    ",height=" + height +
                    ",top=" + top +
                    ",left=" + left;
            window.open(url, "twitter", opts);
            return false;
        });
    },

    /** Allow user to share a badge on Facebook */
    facebookBadge: function(url, desc, icon, ext, activity) {
        var deferred = $.Deferred();

        FB.api(
            "/me/" + KA.FB_APP_NAMESPACE + ":earn?badge=" + url,
            "post",
            function(response) {
                // If the user does not have this permission enabled or
                // some other error occurs
                if (!response || response.error) {
                    deferred.reject(response);
                } else {
                    deferred.resolve(response);
                }
            }
        );

        deferred.
            fail(function(response) {
                // TODO(stephanie): ask user for permissions
                KAConsole.log("Error: Facebook 'earn' action failed. " + response.error.message);
            });

        return deferred;
    },

    /** Publish a standard "post" action to user's Facebook Timeline */
    facebookPostBadge: function(url, desc, icon, ext, activity) {
        FB.ui({
            method: "feed",
            name: "I just earned the " + desc + " badge" + (activity ? " in " + activity : "") + " at Khan Academy!",
            link: url,
            picture: (icon.substring(0, 7) === "http://" ? icon : "http://www.khanacademy.org/" + icon),
            caption: url,
            description: "You can earn this too if you " + ext
        });
    },

    facebookVideo: function(name, desc, url) {

        FB.ui({
            method: "feed",
            name: name,
            link: "http://www.khanacademy.org/" + url,
            picture: "http://www.khanacademy.org/images/handtreehorizontal_facebook.png",
            caption: "www.khanacademy.org",
            description: desc,
            message: "I just learned about " + name + " on Khan Academy"
        });
        return false;

    },

    facebookExercise: function(amount, plural, prof, exer) {

        FB.ui({
            method: "feed",
            name: amount + " question" + plural + " answered!",
            link: "http://www.khanacademy.org/exercisedashboard",
            picture: "http://www.khanacademy.org/images/proficient-badge-complete.png",
            caption: "www.khanacademy.org",
            description: "I just answered " + amount + " question" + plural + " " + prof + " " + exer + " on www.khanacademy.org" ,
            message: "I\'ve been practicing " + exer + " on http://www.khanacademy.org"
        });
        return false;

    },

    emailBadge: function(url, desc) {

        var subject = "I just earned the " + desc + " badge on Khan Academy!";
        var body = "Check it out at " + url + ".";

        var href = "mailto:?Subject=" + subject + "&amp;Body=" + body;

        return href.replace(/\s/g, "+");
    },

    twitterBadge: function(url, desc) {

        var text = "I just earned the " + desc + " badge on @khanacademy";
        var related = "khanacademy:Khan Academy";

        var href = "http://twitter.com/share?url=" + encodeURIComponent(url) + "&text=" + text + "&related=" + related;

        return href.replace(/\s/g, "+");
    }
};

$(function() {Social.init();});
