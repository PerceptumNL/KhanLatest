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
                        text: "No thanks",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "Cool. Let me login now!",
                        onclick: function() {
                            var postLoginUrl = "/postlogin?continue=" +
                                    encodeURIComponent(window.location.href);
                            window.location.href = "/login?continue=" +
                                    encodeURIComponent(postLoginUrl);
                        },
                        classString: "simple-button green"
                    }
                ],
                title: "Log in to save and customize your profile!",
                description: "Your profile page shows you all the great " +
                             "progress you've made on Khan Academy. If you " +
                             "login, you can even customize and share your " +
                             "profile with your friends!",
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
                id: "welcome",
                next: "basic-profile",

                buttons: [
                    {
                        action: guiders.ButtonAction.CLOSE,
                        text: "No, thanks. I know what I'm doing.",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Cool. Show me around!",
                        classString: "simple-button green"
                    }
                ],
                title: "Welcome to your profile page!",
                description: "Here, you can share your achievements, " +
                             "track your progress, " +
                             "and browse your discussion history.",
                overlay: true
            }).show();

            guiders.createGuider({
                id: "basic-profile",
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
                        text: "Next",
                        classString: "simple-button green"
                    }
                ],
                title: "It's all about you.",
                description: isFullyEditable ?
                    "You can click on the image to choose your avatar " +
                    "and on your username to set your real name." :
                    "You can click on the image to choose your avatar."
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
                        text: "Close",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "More! Show me more.",
                        classString: "simple-button green"
                    }
                ],
                title: "Show off your accomplishments.",
                description: "You can select up to five badges to show off in " +
                             "your very own shiny display case!"
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
                        text: "Close",
                        classString: "simple-button"
                    },
                    {
                        action: guiders.ButtonAction.NEXT,
                        text: "Sweet! What else is there?",
                        classString: "simple-button green"
                    }
                ],
                title: "Check your vitals.",
                description: "Check out your badges and visualize your stats. " +
                             "These tabs are only visible to you and your coach."
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
                    text: "OK, thanks!",
                    classString: "simple-button green"
                }] :
                isFullyEditable ?
                [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "Close",
                    classString: "simple-button"
                },
                {
                    action: guiders.ButtonAction.NEXT,
                    text: "Next",
                    classString: "simple-button green"
                }] :
                [{
                    action: guiders.ButtonAction.CLOSE,
                    text: "OK! Let me play with the page!",
                    classString: "simple-button green"
                }]
            ),
            title: "Talk it up!",
            description: "Both you and the community can browse your public " +
                         "questions, answers, and comments. Sharing what " +
                         "we've learned is what our community is all about!" +
                         "<br><br>Check out the cool discussion pages for " +
                         "these folks:<br>" +
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
                    text: "Keep my profile private for now.",
                    classString: "simple-button"
                },
                {
                    onclick: function() {
                                 guiders.hideAll();
                                 Profile.userCardView.toggleProfileVisibility();
                             },
                    text: "Make my profile public!",
                    classString: "simple-button green"
                }],
                title: "Share With The World " +
                       "<span style='font-size:65%'>(but only if you want to)" +
                       "</span>",
                description: "Make your profile public and share the information " +
                             "highlighted here. You can always make it private again."
            });
        }
    };
}
