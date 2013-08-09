
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
                KAConsole.log("Error: Facebook 'earn' mislukt. " + response.error.message);
            });

        return deferred;
    },

    /** Publish a standard "post" action to user's Facebook Timeline */
    facebookPostBadge: function(url, desc, icon, ext, activity) {
        FB.ui({
            method: "feed",
            name: "Ik heb zojuist de  " + desc + " badge" + (activity ? " in " + activity : "") + " op iktel.nl!",
            link: url,
            picture: (icon.substring(0, 7) === "http://" ? icon : "http://www.iktel.nl/" + icon),
            caption: url,
            description: "Deze kan je ook verdienen als je " + ext
        });
    },

    facebookVideo: function(name, desc, url) {

        FB.ui({
            method: "feed",
            name: name,
            link: "http://www.iktel.nl/" + url,
            picture: "http://www.iktel.nl/images/handtreehorizontal_facebook.png",
            caption: "www.iktel.nl",
            description: desc,
            message: "Ik heb zojuist " + name + " geleerd op iktel.nl"
        });
        return false;

    },

    facebookExercise: function(amount, plural, prof, exer) {

        FB.ui({
            method: "feed",
            name: amount + " vraag/vragen" + plural + " beantwoord!",
            link: "http://www.iktel.nl/exercisedashboard",
            picture: "http://www.iktel.nl/images/proficient-badge-complete.png",
            caption: "www.iktel.nl",
            description: "Ik heb zojuist " + amount + "geantwoord" + plural + " " + prof + " " + exer + " op www.iktel.nl" ,
            message: "Ik heb " + exer + " geoefend op http://www.iktel.nl"
        });
        return false;

    },

    emailBadge: function(url, desc) {

        var subject = "Ik heb zojuist de " + desc + " badge verdiend op iktel.nl!";
        var body = "Kijk zelf op " + url + "!";

        var href = "mailto:?Subject=" + subject + "&amp;Body=" + body;

        return href.replace(/\s/g, "+");
    },

    twitterBadge: function(url, desc) {

        var text = "Ik heb zojuist de " + desc + " badge verdiend op @khanacademie";
        var related = "khanacademie:iktel.nl";

        var href = "http://twitter.com/share?url=" + encodeURIComponent(url) + "&text=" + text + "&related=" + related;

        return href.replace(/\s/g, "+");
    }
};

$(function() {Social.init();});
