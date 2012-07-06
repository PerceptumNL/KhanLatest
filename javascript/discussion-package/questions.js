/**
 * Handle loading, asking, and answering questions on the video page.
 */
var QA = {
    registered_: false,

    init: function() {
        var page = $("#qa_page").val() || 0,
            expandKey = $("#qa_expand_key").val();
        QA.loadPage(page, expandKey, true);

        if (this.registered_) {
            return;
        }

        this.registered_ = true;

        $(".question_cancel, .answer_cancel").live("click", QA.cancel);
        $(".comment_not_question").live("click", QA.commentNotQuestion);
        $(".questions_container .question_container")
            .live("mouseover", QA.hover)
            .live("mouseout", QA.unhover)
            .live("click", QA.expand);
        $(".close_note").live("click", QA.closeNote);

        $(".video-footer").on("mouseenter", ".author-nickname", function() {
            HoverCard.createHoverCardQtip($(this));
        });

        QA.template_ = Templates.get("discussion.questions-area");

        Handlebars.registerPartial("thread",
                Templates.get("discussion.thread"));

        Handlebars.registerPartial("question",
                Templates.get("discussion.question"));

        Handlebars.registerPartial("answer",
                Templates.get("discussion.answer"));

        Handlebars.registerPartial("question-guide",
                Templates.get("discussion.question-guide"));

        Handlebars.registerPartial("page-controls",
                Templates.get("discussion.page-controls"));

        Handlebars.registerPartial("vote-controls",
                Templates.get("discussion.vote-controls"));

        Handlebars.registerPartial("flag-controls",
                Templates.get("discussion.flag-controls"));

        Handlebars.registerPartial("mod-controls",
                Templates.get("discussion.mod-controls"));

        Handlebars.registerPartial("author-controls",
                Templates.get("discussion.author-controls"));

        Handlebars.registerPartial("visit-profile-promo",
                Templates.get("discussion.visit-profile-promo"));

        Handlebars.registerHelper("formatContent", QA.formatContent_);

        $(".video-footer")
            .on("focus", ".question_text", QA.focusQuestion)
            .on("change, keyup", ".question_text", QA.updateRemainingQuestion)
            .on("click", ".add_yours", QA.expandAndFocus)
            .on("focus", ".answer_text", QA.focusAnswer)
            .on("click", "input.question_submit", QA.onQuestionSubmit_)
            .on("click", "input.answer_submit", QA.onAnswerSubmit_)
            .on("click", ".questions_page",
                function() {
                    QA.loadPage($(this).data("page"));
                    return false;
                });
    },

    /*
     * Identifier corresponding to the promo where we suggest that a user visit
     * her profile's discussion summary after submitting a question or answer.
     */
    promoName_: "visit_profile_after_post",
    shouldShowPromo_: false,

    checkPromo_: function() {
        Promos.hasUserSeen(QA.promoName_, function(hasSeen) {
            this.shouldShowPromo_ = !hasSeen;
        }, QA);
    },

    /*
     * Extend the provided template context to show the promo and mark the
     * promo as seen by the user.
     */
    handleShowingPromo_: function(context, askedQuestion) {
        if (QA.shouldShowPromo_) {
            _.extend(context, {
                showProfilePromo: true,
                profileRoot: KA.getUserProfile().get("profileRoot"),
                verb: askedQuestion ? "asking" : "answering"
            });

            Promos.markAsSeen(QA.promoName_);
        }
    },

    /**
     * Handle submitting a question to the server, either to add a new question
     * or to update an existing question.
     */
    onQuestionSubmit_: function() {
        var readableId = $("#readable_id").val(),
            url = "/api/v1/videos/" + readableId + "/questions",
            type = "POST";

        var jelParent = $(this).parents(".question_container"),
            questionKey = jelParent.data("key"),
            jelText = jelParent.find(".question_text"),
            text = $.trim(jelText.val()),
            data = JSON.stringify({
                text: text
            });

        if (text === "" || text === jelText.attr("placeholder")) {
            return;
        }

        if (questionKey) {
            // Update existing question
            url += "/" + questionKey;
            type = "PUT";
        }

        // Tell server that we expect a camelCase response
        url += "?casing=camel";

        $.ajax({
            type: type,
            url: url,
            contentType: "application/json",
            data: data,
            dataType: "json",
            success: QA.onQuestionSubmitSuccess_
        });

        // Show throbber and disable button
        var jelByThrobber = $(this).siblings(".question_cancel");
        Throbber.show(jelByThrobber);
        QA.disable();
    },

    /**
     * Render added or updated question in browser.
     *
     * TODO(marcia): It would be nice to render the question optimistically,
     * instead of waiting for the response.
     */
    onQuestionSubmitSuccess_: function(data) {
        $(".question_form textarea").val("");
        QA.hideStickyNote();
        Throbber.hide();
        QA.enable();

        // TODO(marcia): This is very a silly state storing situation.
        // I am going to FIXIT SOON.
        data["tempVideoKey"] = $("#video_key").val();

        var key = data["key"],
            jelExisting = $("#" + key),
            template,
            jel;

        if (jelExisting.length === 0) {
            // Add new question to page
            template = Templates.get("discussion.thread");

            // TODO(marcia): After the video qa html revamp, show the promo
            // for question edits as well. Not worth the intermediate work now.
            QA.handleShowingPromo_(data, true);

            jel = $(template(data));
            jelToInsertBefore = $(".questions_page_controls");
            if (jelToInsertBefore.length === 0) {
                jelToInsertBefore = $(".question_form").parent();
            }

            // Stopgap animation so that it looks like there is space for the
            // new question, then it fades in. Lots of room for improvement.
            jel.find(".timeago")
                    .timeago()
                .end()
                .css("opacity", 0)
                .insertBefore(jelToInsertBefore)
                .animate({
                    opacity: 1
                });
        } else {
            // Replace question, leaving alone the answers
            template = Templates.get("discussion.question");
            jel = $(template(data));

            QA.cancel_(jelExisting);  // Hide form
            jelExisting.find(".question").replaceWith(jel);
        }
    },

    /**
     * Handle submitting an answer to the server, either to add a new answer or
     * to update an existing answer.
     */
    onAnswerSubmit_: function() {
        var questionKey = $(this).parents(".question_container").data("key"),
            jelAnswer = $(this).parents(".answer_container"),
            answerKey = jelAnswer.data("key"),
            jelText = jelAnswer.find(".answer_text"),
            text = $.trim(jelText.val()),
            data = JSON.stringify({
                text: text
            });

        if (text === "" || text === jelText.attr("placeholder")) {
            return;
        }

        var url = "/api/v1/questions/" + questionKey + "/answers",
            type = "POST";

        if (answerKey) {
            // Update existing answer
            url += "/" + answerKey;
            type = "PUT";
        }

        // Tell server that we expect a camelCase response
        url += "?casing=camel";

        $.ajax({
            type: type,
            url: url,
            contentType: "application/json",
            data: data,
            dataType: "json",
            success: _.bind(QA.onAnswerSubmitSuccess_, QA, jelText)
        });

        // Show throbber and disable button
        var jelByThrobber = $(this).siblings(".answer_cancel");
        Throbber.show(jelByThrobber);
        QA.disable();
    },

    /**
     * Render added or updated answer in browser.
     */
    onAnswerSubmitSuccess_: function(jelText, data) {
        jelText.val("");
        Throbber.hide();
        QA.enable();

        QA.handleShowingPromo_(data, false);

        var answerTemplate = Templates.get("discussion.answer"),
            html = answerTemplate(data),
            jel = $(html).find(".timeago").timeago().end(),
            key = data["key"],
            questionKey = data["questionKey"],
            jelToReplace = $("#" + key);

        if (jelToReplace.length === 0) {
            // Add new answer to page
            $("#" + questionKey + " .answers_container").append(jel);
        } else {
            // Replace extant answer with updated one
            jelToReplace.replaceWith(jel);
        }
    },

    replaceTimestamps_: function(timestamp, minutes, seconds) {
        var numSeconds = 60 * parseInt(minutes, 10) + parseInt(seconds, 10);
        return "<span class='youTube' seconds='" + numSeconds + "'>" +
                timestamp + "</span>";
    },

    formatContent_: function(content) {
        // Escape user generated content
        content = Handlebars.Utils.escapeExpression(content);

        var timestampRegex = /\b(\d+):([0-5]\d)\b/g;
        content = content.replace(timestampRegex, QA.replaceTimestamps_);

        var newlineRegex = /[\n]/g;
        content = content.replace(newlineRegex, "<br>");

        content = Autolink.autolink(content);

        // Use SafeString because we already escaped the user generated
        // content and then added our own safe html
        return new Handlebars.SafeString(content);
    },

    onQuestionsLoaded_: function(data) {
        if (!data) {
            return;
        }

        var expandKey = $("#qa_expand_key").val();

        _.each(data.questions, function(question) {
            question.expanded = (expandKey === question.key);
            question.restrictPosting = data.restrictPosting;
            question.tempVideoKey = data.tempVideoKey;

            if (data.showModControls) {
                question.showModControls = data.showModControls;
                _.each(question.answers, function(answer) {
                    answer.showModControls = data.showModControls;
                });
            }
        });

        // TODO(marcia): Figure out why pages are one-based
        // and name these variables less awkwardly
        data.hasPreviousPage = (data.currentPage_1Based !== 1);
        data.hasNextPage = (data.currentPage_1Based !== data.pagesTotal);

        $(".questions_container")
            .html(QA.template_(data))
            .find(".timeago")
                .timeago();

        // Scroll to expanded question if specified
        if (expandKey) {
            var jelQuestion = $("#" + expandKey);

            if (jelQuestion.length !== 0) {
                $("html, body").animate({
                    scrollTop: jelQuestion.offset().top
                });
            }

            if (data.countNotifications) {
                $("#top-header .notification-bubble")
                    .text(data.countNotifications);
            } else {
                $("#top-header .user-notification").hide();
            }
        }

        QA.finishLoadPage();
    },

    loadPage: function(page, expandKey, fInitialLoad) {
        var readableId = $("#readable_id").val(),
            url = "/api/v1/videos/" + readableId + "/questions",
            data = {
                casing: "camel",
                sort: $("#sort").val(),
                page: page
            };

        if (expandKey) {
            data["qa_expand_key"] = expandKey;
        }

        $.ajax({
            type: "GET",
            url: url,
            data: data,
            dataType: "json",
            success: _.bind(QA.onQuestionsLoaded_, this)
        });

        if (!fInitialLoad) {
            Throbber.hide();
            Throbber.show($(".questions_page_controls span"));
        }
    },

    finishLoadPage: function(data) {
        if (data && data.html) {
            $(".questions_container").html(data.html);
        }
        Throbber.hide();
        $(".answer_text").placeholder();
        $(".question_text").placeholder();
    },

    // TODO(marcia): Determine whether we still need this.
    // TODO(drew): Add support for comments in this and the functions below.
    getQAParent: function(el) {
        var parentAnswer = $(el).parents("div.answer_container");
        if (parentAnswer.length) {
            return parentAnswer;
        }
        return QA.getQuestionParent(el);
    },

    getQuestionParent: function(el) {
        return $(el).parents("div.question_container");
    },

    isInsideExistingQA: function(el) {
        var parent = QA.getQAParent(el);
        if (!parent.length) {
            return false;
        }
        return $(".sig", parent).length > 0;
    },

    updateRemainingQuestion: function() {
        Discussion.updateRemaining(500, ".question_text",
                                        ".question_add_controls .chars_remaining",
                                        ".question_add_controls .chars_remaining_count");
    },

    disable: function() {
        $(".question_text, .answer_text").attr("disabled", "disabled");
        $(".question_submit, .answer_submit").addClass("buttonDisabled").attr("disabled", "disabled");
    },

    enable: function() {
        $(".question_text, .answer_text").removeAttr("disabled");
        $(".question_submit, .answer_submit").removeClass("buttonDisabled").removeAttr("disabled");
    },

    showNeedsLoginNote: function(el, sMsg) {
        return this.showNote($(".login_note"), el, sMsg,
            function() { $(".login_link").focus(); });
    },

    showInfoNote: function(el, sMsg) {
        return this.showNote($(".info_note"), el, sMsg);
    },

    closeNote: function() {
        $(".note").hide();
        return false;
    },

    showNote: function(jNote, el, sMsg, fxnCallback) {
        if (jNote.length && el) {
            $(".note_desc", jNote).text(sMsg);

            var jTarget = $(el);
            var offset = jTarget.offset();
            var offsetContainer = $("#video-page").offset();

            jNote.css("visibility", "hidden").css("display", "");
            var top = offset.top - offsetContainer.top + (jTarget.height() / 2) - (jNote.height() / 2);
            var left = offset.left - offsetContainer.left + (jTarget.width() / 2) - (jNote.width() / 2);
            jNote.css("top", top).css("left", left).css("visibility", "visible").css("display", "");

            if (fxnCallback) {
                setTimeout(fxnCallback, 50);
            }

            return true;
        }
        return false;
    },

    focusQuestion: function() {
        if (QA.showNeedsLoginNote(this, "to ask your question.")) {
            return false;
        }

        var jelContainer = $(this).parents(".question_container"),
            key = jelContainer.data("key");

        jelContainer.find(".question_controls_container").slideDown("fast");

        // Show "ask a great question" sticky note if adding a new question
        // (and not editing an existing question).
        if (key === undefined) {
            QA.showStickyNote();

            // Scroll to keep the question box on screen.
            var jelVideoQuestions = $(".video_questions");

            // Because we just opened up the sticky note and controls, the
            // values for the document height aren't being recalculated, so we
            // manually figure out the amount of scroll to display the question
            // area nicely.
            $("html, body").animate({
                scrollTop: jelVideoQuestions.offset().top +
                           jelVideoQuestions.height() +
                           $(".sticky_note_content").outerHeight() +
                           $(".question_controls_container").outerHeight() +
                           $(".push").outerHeight() -
                           $(window).height()
            }, "fast");
        }

        QA.checkPromo_();
    },

    edit: function(el) {
        var parent = QA.getQAParent(el);

        if (!parent.length) {
            return;
        }

        var type = $(parent).is(".answer_container") ? "answer" : "question";

        var jEntity = $("." + type, parent);
        var jControls = $("." + type + "_controls_container", parent);
        var jSignature = $("." + type + "_sig", parent);

        if (!jEntity.length || !jControls.length || !jSignature.length) {
            return;
        }

        jEntity.addClass(type + "_placeholder").removeClass(type);
        jSignature.css("display", "none");
        jControls.slideDown();

        // Build up a textarea with plaintext content
        var jTextarea = $("<textarea name='" + type + "_text' class='" + type + "_text'></textarea>");

        // Replace BRs with newlines.  Must use {newline} placeholder instead of \n b/c IE
        // doesn't preserve newline content when asking for .text() content below.
        var reBR = /<br>/gi;
        var reBRReverse = /{newline}/g;
        var jSpan = $("span", jEntity).first();
        var htmlEntity = $.browser.msie ? jSpan.html().replace(reBR, "{newline}") : jSpan.html();

        var jContent = $("<div>").html(htmlEntity);

        // Remove any artificially inserted ellipsis
        $(".ellipsisExpand", jContent).remove();

        // Fill, insert, then focus textarea
        var textEntity = $.browser.msie ? jContent.text().replace(reBRReverse, "\n") : jContent.text();
        jTextarea.val($.trim(textEntity));
        jSpan.css("display", "none").after(jTextarea);

        setTimeout(function() { jTextarea.focus(); }, 1);
    },

    /* Helper function that closes question/answer tools. */
    cancel_: function(parent) {
        if (!parent || !parent.length) {
            return;
        }

        var type = $(parent).is(".answer_container") ? "answer" : "question";

        $("." + type + "_text", parent).val("").placeholder();

        if (type == "question") {
            QA.hideStickyNote();
        }

        $("." + type + "_controls_container", parent).slideUp("fast");

        if (parent.data("key") !== undefined) {
            $("textarea", parent).first().remove();
            $("span", parent).first().css("display", "");
            $("." + type + "_placeholder", parent).addClass(type).removeClass(type + "_placeholder");
            $("." + type + "_sig", parent).slideDown("fast");
        }
    },

    cancel: function() {
        QA.cancel_(QA.getQAParent(this));
        return false;
    },

    /* The user started to ask a question but then clicked the link
     * to make a comment instead.
     */
    commentNotQuestion: function() {
        // Scroll to the comments section.
        var jelComments = $(".video_comments");

        if (jelComments.length !== 0) {
            $("html, body").animate({
                scrollTop: jelComments.offset().top
            });
        }

        // Display the top comments and activate the "add comment"
        // typein field. Triggering this after the scroll
        // reduces some jumpy behavior in Chrome.
        Comments.add();

        // Close up the "ask a question" sticky note.
        QA.cancel_(QA.getQAParent($(".question_cancel")));

        return false;
    },

    focusAnswer: function() {
        if (QA.showNeedsLoginNote(this, "to answer this question.")) {
            return false;
        }

        var parent = QA.getQAParent(this);
        if (!parent.length) {
            return;
        }

        $(".answer_controls_container", parent).slideDown("fast");

        QA.checkPromo_();
    },

    hover: function(e) {
        if ($(this).is(".question_container_expanded")) {
            return;
        }

        // If the user hovered over the voting tools, return.
        if ($(e.target).parents(".vote_tools").length > 0) {
            return;
        }

        $(this).addClass("question_container_hover");
    },

    unhover: function() {
        if ($(this).is(".question_container_expanded")) {
            return;
        }

        $(this).removeClass("question_container_hover");
    },

    showStickyNote: function() {
        $(".sticky_note").slideDown("fast");
    },

    hideStickyNote: function() {
        $(".sticky_note").slideUp("fast");
    },

    expandAndFocus: function(e) {
        var parent = QA.getQAParent(this);
        if (!parent.length) {
            return;
        }

        QA.expand.apply(parent[0], [e, function() { $(".answer_text",
            parent).focus(); }]);
        return false;
    },

    expand: function(e, fxnCallback) {
        if ($(this).is(".question_container_expanded")) {
            return;
        }

        var jel = $(e.target);

        // If the user clicked on the voting tools, don't expand.
        if (jel.parents(".vote_tools").length > 0) {
            return;
        }

        // If user clicks on a link during the expand...
        if (jel.is("a:link")) {
            // If it's a link inside a question's text or the "17 answers" link
            // to the right of the text
            if (jel.is(".question_container .question a, " +
                       ".question_container .question_answer_count a")) {
                // Don't follow the link
                e.preventDefault();
            } else {
                // Follow the link and don't expand the question
                return;
            }
        }

        $(".question_answer_count", this).css("display", "none");
        $(".answers_and_form_container", this).slideDown("fast", fxnCallback);

        QA.unhover.apply(this);

        $(this).addClass("question_container_expanded");

        var userProfile = KA.getUserProfile();
        if (userProfile && !userProfile.isPhantom()) {
            // Fire and forget that the user expanded this question,
            // which will clear notifications associated with the question.
            var key = $(".question", this).attr("data-question_key");
            $.post("/discussion/expandquestion", { qa_expand_key: key });
        }
    }
};
