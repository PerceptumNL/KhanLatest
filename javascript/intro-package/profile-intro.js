/**
 * Out-of-the-box experience logic for the profile page.
 * Dependent on the contents of profile-package.
 *
 * The first time a user visits their profile page, we walk them through
 * a full tutorial about all of the pieces.
 *
 * For the rollout of the discussion history tab, we walk existing users
 * through a subset of the full tutorial, highlighting just the discussion tab.
 * This is the case when "showDiscussionIntro" is true.
 */

if (typeof Profile !== "undefined") {
    Profile.showIntro_ = function() {
        if (Profile.profile.isPhantom()) {
            // For phantom users, don't show a tour flow, but a single dialog
            // with clear call-to-action to login.
            guiders.createGuider({
                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Nee bedankt",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Cool! laat mij nu inloggen!",
                        onclick: function() {
                            var postLoginUrl = "/postlogin?continue=" +
                                    encodeURIComponent(window.location.href);
                            window.location.href = "/login?continue=" +
                                    encodeURIComponent(postLoginUrl);
                        },
                        classString: "simple-button green"
                    }
                ],
                title: "Login om je je profiel op te slaan en te personaliseren!",
                description: "Jouw profielpagina laat je precies zijn welke " +
                             "vooruitgang jij hebt geboekt op Khan Academie. Als je " +
                             "inlogt, kun je jouw profiel aanpassen en delen " +
                             "met je vrienden!",
                overlay: true
            }).show();

            // The "show()" call above kicks off the guides tutorial. The system
            // can then progress to the next defined guide.

            return;
        }

        var isFullyEditable = Profile.profile.isFullyEditable();
        var showDiscussionIntro = Profile.showDiscussionIntro;

        // If we are only giving the limited discussion tab tutorial, skip these
        // steps. However, if we are giving the full tutorial, show them.
        if (!showDiscussionIntro) {

            guiders.createGuider({
                id: "Welkom",
                next: "basic-profile",

                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Nee, bedankt, Ik weet wat ik doe.",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Cool. Geef me een rondleiding! ",
                        classString: "simple-button green"
                    }
                ],
                title: "Welkom op jouw profielpagina!",
                description: "Hier kun je jouw behaalde resultaten delen, " +
                             "je voortgang bijhouden, " +
                             "en door je discussie geschiedenis bladeren.",
                overlay: true
            }).show();

            guiders.createGuider({
                id: "basis-profiel",
                next: "display-case",

                attachTo: ".basic-user-info",
                highlight: ".basic-user-info",
                overlay: true,
                position: 3,
                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Close",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Volgende",
                        classString: "simple-button green"
                    }
                ],
                title: "Het gaat allemaal over jou.",
                description: isFullyEditable ?
                    "Je kunt op een afbeelding klikken om een avatar te kiezen " +
                    "en op je gebruikersnaam om je echte naam in te stellen. " :
                    "Je kunt op een afbeelding klikkken om een jouw avatar te kiezen."
            });

            guiders.createGuider({
                id: "display-case",
                next: "more-info",

                attachTo: ".display-case-cover",
                highlight: ".sticker-book",
                overlay: true,
                position: 6,
                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Sluit",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Meer! Laat me meer zien.",
                        classString: "simple-button green"
                    }
                ],
                title: "Laat zien wat je bereikt hebt.",
                description: "Je kunt tot vijf badges laten zien aan anderen  " +
                             "in je eigen glanzende prijzenkast!"
            });

            guiders.createGuider({
                id: "more-info",
                next: "discussion-history",

                attachTo: ".accomplishments-statistics-section",
                highlight: ".accomplishments-statistics-section",
                overlay: true,
                position: 3,
                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Sluit",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Wauw! Wat is er nog meer?",
                        classString: "simple-button green"
                    }
                ],
                title: "Check je status.",
                description: "Bekijk je badges en krijg inzicht in je statistieken. " +
                             "Deze tabjes kunnen alleen jij en je coach zien."
            });

        }

        // For both the full tutorial and the discussion tab tutorial, we will show
        // the discussion tab step here.

        var discussionGuide =
          guiders.createGuider({
            id: "discussion-history",
            next: "privacy-settings",

            attachTo: ".community-discussion",
            highlight: ".community-discussion",
            overlay: true,
            position: 3,
            // Discussion tutorial: single ok button
            // Full tutorial, full access: close + next buttons
            // Full tutorial, limited access: close button
            buttons:
                (showDiscussionIntro ?
                [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "Ok, bedankt!",
                    classString: "simple-button green"
                }] :
                isFullyEditable ?
                [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "Sluit",
                    classString: "simple-button"
                },
                {
                    action: guiders.ButtonAction.NEXT,
                    text: "Volgende",
                    classString: "simple-button green"
                }] :
                [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "Ok! Laat mij de pagina ontdekken!",
                    classString: "simple-button green"
                }]
            ),
            title: "Praat erover!",
            description: "Zowel jij als de community kunnen door jouw openbare " +
                         "vragen, antwoorden, en commentaar. Delen wat " +
                         "we geleerd hebben is waar het om gaat binnen de community!" +
                         "<br><br>Check hier de coole discussie pagina's over " +
                         "deze mensen:<br>" +
                         "<ul style='list-style-position: inside; " +
                             "list-style-type: disc;'>" +
                         "<li><a href='/profile/Sphairistrike/discussion' " +
                                "target='_blank'>Greg Boyle</a> " +
                                "(Art History fan)</li>" +
                         "<li><a href='/profile/britcruise/discussion' " +
                                "target='_blank'>Brit Cruise</a> " +
                                "(Khan Academy's very own)</li>" +
                         "<li><a href='/profile/Skywalker94/discussion' " +
                                "target='_blank'>Skywalker94</a> " +
                                "(over 1400 answers!)</li></ul>"
        });

        // In the case of giving just the discussion tutorial, we need to kick
        // off the guides tutorial.
        if (showDiscussionIntro) {
            discussionGuide.show();
        }

        // This tutorial step is only shown for the full tutorial when the user also
        // has permission to make their profile public.
        if (isFullyEditable && !showDiscussionIntro) {
            guiders.createGuider({
                id: "privacy-settings",

                attachTo: ".edit-visibility.visibility-toggler",
                highlight: ".user-info, .edit-visibility.visibility-toggler",
                overlay: true,
                position: 5,
                buttons: [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "Hou mijn profiel nog prive.",
                    classString: "simple-button"
                },
                {
                    onclick: function() {
                                 guiders.hideAll();
                                 Profile.userCardView.toggleProfileVisibility();
                             },
                    text: "Maak mijn profiel openbaar",
                    classString: "simple-button green"
                }],
                title: "Deel met de Wereld " +
                       "<span style='font-size:65%'>(alleen als je dat wilt)" +
                       "</span>",
                description: "Maak je profiel openbaar en deel de informatie " +
                             "hier uitgelicht. Je kunt het altijd weer op prive zetten."
            });
        }
    };
}
