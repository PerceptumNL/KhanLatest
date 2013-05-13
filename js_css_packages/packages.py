#
# The list of static JS and CSS files served and the packages they belong to.
# This file is munged and auto-regenerated at deploy time!
# See deploy/compress.py to ensure that changes made here are not incompatible
# with that deploy process.
#

transformations = {}


def register_conditional_file(debug_name, prod_name):
    """ Registers a file that has two versions: one for debug and one for
    production.

    This will return the name of the debug file, and include the transformation
    necessary for production in a global "transformations" map.
    """
    transformations[debug_name] = prod_name
    return debug_name

javascript = {
    "shared": {
        "files": [
            # general purpose libs
            "jquery.js",
            "jquery-ui-1.8.16.custom.js",
            "jquery.ui.menu.js",
            "jquery.timeago.js",
            "jquery.placeholder.js",
            "jquery.hoverflow.js",
            "jquery.qtip.js",
            "underscore.js",
            "underscore-extras.js",
            "keyhandling.js",
            "backbone.js",
            register_conditional_file("handlebars.js", "handlebars.vm.js"),
            "templates.js",
            "bootstrap-alerts.js",
            "bootstrap-modal.js",
            "dropdown.js",
            "jquery.mousewheel.js",
            "autolink.js",
            "../../gae_bingo/static/js/gae_bingo.js",
            register_conditional_file("less-dev.js", None),
            register_conditional_file("less-1.3.0.js", None),

            # application code & templates:
            "small-exercise-icon.handlebars",
            "skill-bar.handlebars",
            "share-links.handlebars",
            "user-badge.handlebars",
            "badge.handlebars",
            "badge-notifications.handlebars",
            "cookies.js",
            "console.js",
            "pageutil.js",
            "facebookutil.js",
            "video-addons.js",
            "api.js",
            "backbone-extensions.js",
            "social.js",
            "promos.js",
            "youtube-player.handlebars",
            "api-version-mismatch.handlebars",
            "generic-dialog.handlebars",
            "knowledgemap-exercise.handlebars",
            "knowledgemap-admin-exercise.handlebars",
            "goal-summary-area.handlebars",
            "goalbook-row.handlebars",
            "goalbook.handlebars",
            "goal-objectives.handlebars",
            "goal-new.handlebars",
            "goal-new-dialog.handlebars",
            "goal-new-custom-dialog.handlebars",
            "goal-create.handlebars",
            "goals.js",
            "goal-new.js",
            "topics.js",
            "localStorage.js",
            "analytics.js",
            "profile-model.js",
            "hover-card.js",
            "hover-card-view.js",
            "hover-card.handlebars",
            "topic-browser-pulldown.handlebars",
            "handlebars-extras.js",
            "scratchpad-list.handlebars",
            "scratchpads.js",
            "visit-tracking.js",
        ]
    },
    "video": {
        "files": [
            "video.js",
            "thumbnail.handlebars",
            "related-video-link.handlebars",
            "modal-video.handlebars",
            "video-nav.handlebars",
            "video-description.handlebars",
            "video-header.handlebars",
            "video-footer.handlebars",
            "video-flv-player.handlebars",
            "modalvideo.js",
        ]
    },
    "moderation": {
        "files": [
            "moderation.js",
            "queue.handlebars",
            "queue.js",
            "mod-controls.handlebars",
        ]
    },
    "discussion": {
        "files": [
            "discussion.js",
            "questions.js",
            "comments.js",
            "questions-area.handlebars",
            "thread.handlebars",
            "question.handlebars",
            "answer.handlebars",
            "question-guide.handlebars",
            "page-controls.handlebars",
            "vote-controls.handlebars",
            "flag-controls.handlebars",
            "mod-controls.handlebars",
            "author-controls.handlebars",
            "visit-profile-promo.handlebars",
        ]
    },
    "socrates": {
        "files": [
            "underscore.string.js",
            "../topicsadmin-package/jquery.ui.draggable.js",
            "jquery.ui.resizable.js",
            "inputtext.handlebars",
            "socrates-nav.handlebars",
            "submit-area.handlebars",
            "poppler.js",
            "socrates.js",
        ]
    },
    "topic": {
        "files": [
            "content-topic-videos.handlebars",
            "root-topic-view.handlebars",
            "subtopic-nav.handlebars",
            "topic-page.js",
        ]
    },

    # Socrates questions. For now, they're here.
    # todo(dmnd) In the long run they should move somewhere else, perhaps
    # to another repository.
    "xyAuNHPsq-g": {"allfiles": True},
    "-a_w0_VAo6U": {"allfiles": True},
    "3XOt1fjWKi8": {"allfiles": True},
    "U2ovEuEUxXQ": {"allfiles": True},

    "slickgrid": {
        "files": [
            "jquery.event.drag-2.0.min.js",
            "slick.core.js",
            "slick.grid.js",
        ]
    },

    "homepage": {
        "files": [
            "jquery.easing.1.3.js",
            "jquery.cycle.all.min.js",
            "waypoints.min.js",
            "videolist.handlebars",
            "homepage.js",
            "ga_social_tracking.js",
        ]
    },
    "exercisestats": {
        "files": [
            "highcharts.js",
        ]
    },
    "login": {
        "files": [
            "bday-picker.js",
            "login.js",
            "signup-success.handlebars",
            "signup.js",
            "completesignup.js",
            "createchild.js",

            # Used for password change forms
            "settings.js",
        ]
    },
    "profile": {
        "files": [
            "jquery.address-1.4.min.js",
            "jquery.expander.js",
            "highcharts.js",
            "activity-graph.js",
            "focus-graph.js",
            "exercises-over-time-graph.js",
            "handlebars-helpers.js",
            "avatar-picker.handlebars",
            "avatar-picker.js",
            "username-picker.handlebars",
            "username-picker.js",
            "user-card-view.js",
            "user-card.handlebars",
            "profile.handlebars",
            "suggested-activity.handlebars",
            "recent-activity-list.handlebars",
            "recent-activity-exercise.handlebars",
            "recent-activity-badge.handlebars",
            "recent-activity-video.handlebars",
            "recent-activity-goal.handlebars",
            "graph-date-picker.handlebars",
            "vital-statistics.handlebars",
            "coaches.js",
            "coach.handlebars",
            "no-coaches.handlebars",
            "coaches.handlebars",
            "discussion-count.handlebars",
            "discussion-sort-links.handlebars",
            "discussion-tab-links.handlebars",
            "discussion-awards-block.handlebars",
            "discussion-award-icon.handlebars",
            "discussion-answers.handlebars",
            "discussion-questions.handlebars",
            "discussion-comments.handlebars",
            "discussion-notifications.handlebars",
            "discussion-statistics.handlebars",
            "discussion-questions-suggestions.handlebars",
            "discussion-answers-suggestions.handlebars",
            "achievements.handlebars",
            "badge-container.handlebars",
            "badge-compact.handlebars",
            "badge-display-case.handlebars",
            "empty-badge-picker.handlebars",
            "badges.js",
            "profile-goals.handlebars",
            "exercise_progress.handlebars",
            "profile-goals.js",
            "profile.js",
            "profile-discussion.js"
        ]
    },
    "intro": {
        "files": [
            "guiders.js",
            "profile-intro.js",
            "exercises-intro.js",
        ]
    },
    "maps": {
        "files": [
            "fastmarkeroverlay.js",
            "knowledgemap-topic.handlebars",
            "models.js",
            "views.js",
            "knowledgemap.js",
            "bootstrap-tooltip.js",
            "bootstrap-popover.js",
        ]
    },
    "mobile": {
        "files": [
            "jquery.js",
            "jquery.mobile-1.0a4.1.js",
            "mobile.js",
            "../shared-package/cookies.js",
            "../shared-package/video-addons.js",
            "../shared-package/api.js",
        ]
    },
    "studentlists": {
        "files": [
            "studentlists.js",
            "classprofile.js",
            "class-goals.js",
            "class-progress-report.js",
            "class-progress-column.handlebars",
            "class-progress-summary.handlebars",
            "class-progress-summary.js",
            "class-goals.handlebars",
            "class-progress-report.handlebars",
        ]
    },
    "donate": {
        "files": [
            "donate.js",
        ]
    },
    "stories": {
        "files": [
            "bootstrap-modal.js",
            "story.handlebars",
            "story-full.handlebars",
            "seedrandom.js",
            "events.js",
            "stories.js",
        ]
    },
    "commoncore": {
        "files": [
            "jquery.sticky.js",
        ]
    },
    "exercises": {
        "files": [
            "exercise.handlebars",
            "exercise-header.handlebars",
            "stack.handlebars",
            "card.handlebars",
            "current-card.handlebars",
            "card-leaves.handlebars",
            "problem-template.handlebars",
            "end-of-stack-card.handlebars",
            "end-of-review-card.handlebars",
            "happy-picture-card.handlebars",
            "calculating-card.handlebars",
            "handlebars-helpers.js",
            "exercises.js",
            "stacks.js",
            "bottomless-queue.js",
            "user-exercise-cache.js",
        ]
    },
    "exercise-content": {
        "base_path": "../khan-exercises",
        "base_url": "/khan-exercises",
        "files": [
            "khan-exercise.js",
            "utils/algebra-intuition.js",
            "utils/angles.js",
            "utils/answer-types.js",
            "utils/ast.js",
            "utils/calculator.js",
            "utils/calculus.js",
            "utils/congruency.js",
            "utils/constructions.js",
            "utils/convert-values.js",
            "utils/d3.js",
            "utils/derivative-intuition.js",
            "utils/exponents.js",
            "utils/expressions.js",
            "utils/expr-helpers.js",
            "utils/expr-normal-form.js",
            "utils/factoring-expressions.js",
            "utils/functional.js",
            "utils/geom.js",
            "utils/graphie-3d.js",
            "utils/graphie-geometry.js",
            "utils/graphie-helpers-arithmetic.js",
            "utils/graphie-helpers.js",
            "utils/graphie-polygon.js",
            "utils/graphie.js",
            "utils/hints.js",
            "utils/interactive.js",
            "utils/jquery.adhesion.js",
            "utils/jquery.mobile.vmouse.js",
            "utils/khanscript.js",
            "utils/math-format.js",
            "utils/math.js",
            "utils/math-model.js",
            "utils/matrix.js",
            "utils/mean-and-median.js",
#            "utils/nba.js",
            "utils/parabola-intuition.js",
            "utils/polynomials.js",
            "utils/probability.js",
            "utils/proofs.js",
            "utils/qhints.js",
            "utils/raphael.js",
            "utils/scratchpad.js",
            "utils/simplify.js",
            "utils/simplifying-expressions.js",
            "utils/slice-clone.js",
            "utils/stat.js",
            "utils/steps-helpers.js",
            "utils/subhints.js",
            "utils/tmpl.js",
            "utils/triangle-congruence.js",
            "utils/word-problems.js",
            "utils/spin.js",
            "utils/time.js",
            "utils/unit-circle.js",
            "utils/liesbeth-helpers.js",
        ]
    },
    "scratchpads": {
        "files": [
            # Oni execution environment
            "oni-apollo.js",

            # The Ace editor
            "ace.js",
            "ace-mode-javascript.js",
            "ace-theme-textmate.js",
            "ace-theme-twilight.js",

            # Code execution and result display
            "processing-1.3.6.js",
            "jshint.js",

            # Audio recording and playback
            "soundcloud.js",
            "soundmanager2.js",

            # jQuery Plugins
            "jquery-ui.js",
            "colorpicker.js",
            "jquery.button.js",
            "jquery.tipbar.js",
            "jquery.hotnumber.js",

            # Templates
            "explorations.handlebars",
            "tutorial-sidebar.handlebars",

            # Initialization
            "editor.js",
            "record.js",
            "canvas.js",
            "output.js",
            "scratchpad-ui.js",
        ]
    },
    "topicsadmin": {
        "files": [
            "jquery.ui.draggable.js",
            "jquery.ui.droppable.js",
            "jquery.ui.sortable.js",
            "jquery.dynatree.js",
            "jquery.contextMenu.js",
            "jquery.ajaxq-0.0.1.js",
            "edit-version.handlebars",
            "edit-topic.handlebars",
            "create-video.handlebars",
            "create-video-preview.handlebars",
            "edit-video.handlebars",
            "create-exercise.handlebars",
            "edit-exercise.handlebars",
            "add-existing-item.handlebars",
            "create-url.handlebars",
            "edit-url.handlebars",
            "list-versions.handlebars",
            "list-versions-item.handlebars",
            "search-topics.handlebars",
            "import-export.handlebars",
            "topics-admin.js",
        ]
    },

    "knowledgemap": {
        "files": [
            "../../khan-exercises/utils/raphael.js",
            "../topicsadmin-package/jquery.ui.draggable.js",
            "../topicsadmin-package/jquery.ui.sortable.js",
            "kmap-editor.js",
        ]
    },

    "highcharts": {
        "files": [
            "highcharts.js"
        ]
    },

    "raphael": {
        "base_path": "../khan-exercises",
        "base_url": "/khan-exercises",
        "files": [
            "utils/raphael.js",
        ]
    },

    "analytics": {
        "files": [
            "jquery-1.9.1.min.js",
            "bootstrap.js",
            "problemlog.js",
            "raphael-min.js",
            "popup.js",
        ]
    }
}

stylesheets = {
    "shared": {
        "files": [
            "jquery-ui-1.8.16.custom.css",
            "jquery.qtip.css",
            "reset.css",
            "default.css",
            "navigation.css",
            "menu.css",
            "museo-sans.css",
            "bootstrap-modal.css",
            "goals.css",
            "shared.less",
            "bootstrap-popover.css",
        ],
    },
    "homepage": {
        "files": [
            "homepage.css"
        ]
    },
    "mobile": {
        "files": [
            "jquery.mobile-1.0a4.1.css",
            "mobile.css",
        ]
    },
    "video": {
        "files": [
            "video.css",
            "discussion.css",
            "modalvideo.css",
            "video.less",
        ]
    },
    "moderation": {
        "files": [
            "moderation.css",
        ]
    },
    "socrates": {
        "files": [
            "bootstrap-alerts.css",
            "bootstrap-tables.css",
            "socrates.less",
        ]
    },
    "topic": {
        "files": [
            "topic-page.css",
        ]
    },
    "studentlists": {
        "files": [
            "viewstudentlists.css",
            "viewclassprofile.css",
        ]
    },
    "login": {
        "files": [
            "login.css",
        ]
    },
    "profile": {
        "files": [
            "profile.css",
            "badges.css",
        ]
    },
    "intro": {
        "files": [
            "guiders.css",
            "intro.css",
        ],
    },
    "contribute": {
        "files": [
            "contribute.css",
        ]
    },
    "donate": {
        "files": [
            "donate.css",
        ]
    },
    "stories": {
        "files": [
            "bootstrap.css",
            "stories.css",
        ]
    },
    "scratchpads": {
        "files": [
            "style.less",
            "jquery-ui.css",
            "colorpicker.css",
        ],
    },
    "exercise-content": {
        "base_path": "../khan-exercises/css",
        "base_url": "/khan-exercises/css",
        "files": [
            "khan-exercise.css",
        ]
    },
    "exercises": {
        "files": [
            "stacks.less",
        ]
    },
    "topicsadmin": {
        "files": [
            "ui_dynatree.css",
            "jquery.contextMenu.css",
            "topics-admin.css"
        ]
    },
    "labs": {
        "files": [
            "labs.css",
        ]
    },
    "bootstrap-grids": {
        "files": [
            "grids.css"
        ]
    },
    "bootstrap": {
        "files": [
            "bootstrap.css"
        ]
    },
    "knowledgemap": {
        "files": [
            "kmap_editor.css"
        ]
    },
    "badge": {
        "files": [
            "spotlight.less"
        ]
    },
    "slickgrid": {
        "files": [
            "slick.grid.css",
        ],
    },
    "analytics": {
        "files": [
            "bootstrap.css"
        ]
    }
}
