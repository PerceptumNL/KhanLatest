/**
 * Intro for new exercise users. Currently only used to tease phantom users
 * into logging in.
 * Dependent on the contents of exercises-package.
 */

if (typeof Exercises !== "undefined") {

    /**
     * Show a teaser guider popup after the first stack in any practice or
     * topic encouraging the user to login. Subsequent stacks will not show
     * another popup, but the first stack in every individual exercise or topic
     * will.
     */
    Exercises.showLoginTeaser = function() {

        var contextId = this.contextId();
        if (!contextId) {
            // If for some reason we don't have a context identifier such as
            // "practice:addition_1" or "topic:probability" we just bail from
            // the promo attempt.
            return;
        }

        var userProfile = KA.getUserProfile();
        if (userProfile && !userProfile.get("isPhantom")) {
            // Don't show teasers to logged-in, non-phantom users.
            return;
        }

        // We show one login promo per context id. This means you'll
        // see one promo at the end of your first stack for each exercise
        // or topic, but not for your second, third, ..., stacks.
        var promoName = "Exercise Login Teaser: " + contextId;

        Promos.hasUserSeen(promoName, function(hasSeen) {

            if (!hasSeen) { 

                Promos.markAsSeen(promoName);
                
                var desc = ("Je hebt zojuist een serie goede antwoorden gegeven in een " + 
                    (Exercises.practiceMode ? "nieuwe oefening" : "nieuw onderwerp") +
                    ". Als je inlogt kun je je voortgang opslaan.");

                guiders.createGuider({
                    buttons: [
                        {
                            action: guiders.ButtonAction.CLOSE,
                            text: "Nee bedankt",
                            classString: "simple-button"
                        },
                        {
                            action: guiders.ButtonAction.CLOSE,
                            text: "Cool. Ik wil inloggen!",
                            onclick: function() {
                                var postLoginUrl = "/postlogin?continue=" +
                                        encodeURIComponent(window.location.href);
                                window.location.href = "/login?continue=" +
                                        encodeURIComponent(postLoginUrl);
                            },
                            classString: "simple-button green"
                        }
                    ],
                    title: "Log in om alle voortgang op te slaan!",
                    description: desc,
                    overlay: true
                }).show();

            }

        }, this);

    }

    // Consider showing login teaser whenever a stack ends
    $(Exercises).bind("endOfStack", function() { Exercises.showLoginTeaser(); });
}
