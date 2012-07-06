/**
 * Handle rendering a flagged feedback queue for moderation.
 * TODO(marcia): Don't show duplicates (as you moderate and then view more)
 * and also support multiple moderators. Probably need to do something smarter
 * than keeping track of offset_
 * TODO(marcia): Support sorting by flag or vote count or _____
 */

/** Namespace. */
var Moderation = Moderation || {};

Moderation.Queue = function() {
    Handlebars.registerPartial("mod-controls",
            Templates.get("moderation.mod-controls"));

    _.bindAll(this, "reset_", "bindEvents_", "fetchSort_", "fetchType_",
        "onDataLoaded_", "fetchData_");
    this.reset_();
};

Moderation.Queue.template_ = Templates.get("moderation.queue");

Moderation.Queue.prototype.reset_ = function(type, sort) {
    // Offset with which we fetch flagged items
    this.offset_ = 0;

    // Type of feedback to fetch, sync'ed with discussion_models.FeedbackType
    this.type_ = type || "question";

    // Default sort should stay in sync with moderation.ModerationSortOrder
    // default
    this.sort_ = sort || Moderation.LOW_QUALITY_FIRST;

    $("#feedback-list").empty();
    $(".load-more").prop("disabled", false);
};

Moderation.Queue.prototype.bindEvents_ = function() {
    $(".tabrow").on("click", "li", this.fetchType_);

    $(".load-more").on("click", this.fetchData_);

    $("#feedback-list").on("mouseenter", ".author-nickname", function() {
        HoverCard.createHoverCardQtip($(this));
    });

    $(".feedback-sort-links").on("click", "a", this.fetchSort_);
};

Moderation.Queue.prototype.fetchSort_ = function(event) {
    var jel = $(event.target);

    // Change selection
    jel.addClass("selected").siblings().removeClass("selected");

    this.reset_(null, jel.data("value"));

    this.fetchData_();
};

Moderation.Queue.prototype.fetchType_ = function(event) {
    // Get the containing <li>
    var jel = $(event.target).parent();

    // Change selection
    jel.addClass("selected").siblings().removeClass("selected");

    this.reset_(jel.data("type"));

    this.fetchData_();
};

Moderation.Queue.prototype.onDataLoaded_ = function(data) {
    this.offset_ += data.length;
    if (data.length === 0) {
        $(".load-more").prop("disabled", true);
    }

    var isSortedByHeuristics = this.sort_ === Moderation.LOW_QUALITY_FIRST;

    // Create booleans from feedback type because of handlebars' logiclessness
    _.each(data, function(feedback) {
        var type = feedback.type;

        if (type === "question") {
            feedback.isQuestion = true;
        } else if (type === "answer") {
            feedback.isAnswer = true;
        } else if (type === "comment") {
            feedback.isComment = true;
        }

        // When sorted by heuristics, the feedback entities will have slightly
        // different mod controls. That is, they will have a "Not spam"
        // button (as opposed to a "Clear flags" button).
        feedback.isSortedByHeuristics = isSortedByHeuristics;
    });

    $("#feedback-list").append(Moderation.Queue.template_(data));
};

Moderation.Queue.prototype.fetchData_ = function() {
    $.ajax({
        method: "GET",
        url: "/api/v1/moderation/feedback",
        data: {
            casing: "camel",
            offset: this.offset_,
            type: this.type_,
            sort: this.sort_
        },
        success: this.onDataLoaded_
    });
};

Moderation.Queue.prototype.show = function() {
    this.bindEvents_();
    this.fetchData_();
};
