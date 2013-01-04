var ProgressSummaryView = function() {
    var fInitialized = false,
        template = Templates.get("studentlists.class-progress-summary"),
        statusInfo = {
                "not-started": {
                    fShowOnLeft: true,
                    order: 0},
                struggling: {
                    fShowOnLeft: true,
                    order: 1},
                started: {
                    fShowOnLeft: false,
                    order: 2},
                proficient: {
                    fShowOnLeft: false,
                    order: 3},
                review: {
                    fShowOnLeft: false,
                    order: 4}
            },
        updateFilterTimeout = null;

    function toPixelWidth(num) {
        return Math.round(200 * num / Profile.numStudents);
    }

    function filterSummaryRows() {
        updateFilterTimeout = null;
        var filterText = $("#student-progresssummary-search").val();
        var filterList = ClassProfile.tokenizeFilterText(filterText);

        $(".exercise-row").each(function(index) {
            var jel = $(this),
                exerciseName = jel.find(".exercise-name span").html();
            if (ClassProfile.matchText(exerciseName, filterList)) {
                jel.show();
            } else {
                jel.hide();
            }
        });
    }

    function init() {
        fInitialized = true;

        // Register partials and helpers
        Handlebars.registerPartial("studentlists_class-progress-column", Templates.get("studentlists.class-progress-column"));

        Handlebars.registerHelper("toPixelWidth", function(num) {
            return toPixelWidth(num);
        });

        Handlebars.registerHelper("toNumberOfStudents", function(num) {
            if (toPixelWidth(num) < 20) {
                return "";
            }
            return num;
        });

        Handlebars.registerHelper("toDisplay", function(status) {
            if (status === "not-started") {
                return "unstarted";
            }
            return status;
        });

        Handlebars.registerHelper("progressColumn", function(block) {
            this.progressSide = block.hash.side;
            return block.fn(this);
        });

        Handlebars.registerHelper("progressIter", function(progress, block) {
            var result = "",
                fOnLeft = (block.hash.side === "left");

            $.each(progress, function(index, p) {
                if (fOnLeft === statusInfo[p.status].fShowOnLeft) {
                    result += block.fn(p);
                }
            });

            return result;
        });

        // Delegate clicks to expand rows and load student graphs
        $("#graph-content").delegate(".exercise-row", "click", function(e) {
            var jRow = $(this),
                studentLists = jRow.find(".student-lists");

            if (studentLists.is(":visible")) {
                jRow.find(".segment").each(function(index) {
                    var jel = $(this),
                        width = jel.data("width"),
                        span = width < 20 ? "" : jel.data("num");
                    jel.animate({width: width}, 350, "easeInOutCubic")
                        .find("span").html(span);
                });

                studentLists.fadeOut(100, "easeInOutCubic");
            } else {
                jRow.find(".segment").animate({width: 100}, 450, "easeInOutCubic", function() {
                    var jel = $(this),
                        status = jel.data("status");
                    jel.find("span").html(status);
                });

                studentLists.delay(150).fadeIn(650, "easeInOutCubic");
            }
        });

        $("#stats-filters").delegate("#student-progresssummary-search", "keyup", function() {
            if (updateFilterTimeout == null) {
                updateFilterTimeout = setTimeout(filterSummaryRows, 250);
            }
        });
    }

    return {
        render: function(context) {
            if (!fInitialized) {
                init();
            }

            Profile.numStudents = context.num_students;

            $.each(context.exercises, function(index, exercise) {
                exercise.progress.sort(function(first, second) {
                    return statusInfo[first.status].order - statusInfo[second.status].order;
                });
            });

            $("#graph-content").html(template(context));
        }
    };
};
