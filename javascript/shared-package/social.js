
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
            name: "Ik heb zojuist de  " + desc + " badge" + (activity ? " in " + activity : "") + " op Iktel!",
            link: url,
            picture: (icon.substring(0, 7) === "http://" ? icon : "http://www.khanacademie.nl/" + icon),
            caption: url,
            description: "Deze kan je ook verdienen als je " + ext
        });
    },

    facebookVideo: function(name, desc, url) {

        FB.ui({
            method: "feed",
            name: name,
            link: "http://www.khanacademie.nl/" + url,
            picture: "http://www.khanacademie.nl/images/handtreehorizontal_facebook.png",
            caption: "www.khanacademie.nl",
            description: desc,
            message: "Ik heb zojuist " + name + " geleerd op Iktel"
        });
        return false;

    },

    facebookExercise: function(amount, plural, prof, exer) {

        FB.ui({
            method: "feed",
            name: amount + " vraag/vragen" + plural + " beantwoord!",
            link: "http://www.khanacademie.nl/exercisedashboard",
            picture: "http://www.khanacademie.nl/images/proficient-badge-complete.png",
            caption: "www.khanacademie.nl",
            description: "Ik heb zojuist " + amount + "geantwoord" + plural + " " + prof + " " + exer + " op www.khanacademie.nl" ,
            message: "Ik heb " + exer + " geoefend op http://www.khanacademie.nl"
        });
        return false;

    },

    emailBadge: function(url, desc) {

        var subject = "Ik heb zojuist de " + desc + " badge verdiend op Iktel!";
        var body = "Kijk zelf op " + url + "!";

        var href = "mailto:?Subject=" + subject + "&amp;Body=" + body;

        return href.replace(/\s/g, "+");
    },

    twitterBadge: function(url, desc) {

        var text = "Ik heb zojuist de " + desc + " badge verdiend op @khanacademie";
        var related = "khanacademie:Iktel";

        var href = "http://twitter.com/share?url=" + encodeURIComponent(url) + "&text=" + text + "&related=" + related;

        return href.replace(/\s/g, "+");
    }
};

$(function() {Social.init();});
