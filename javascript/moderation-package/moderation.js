/**
 * Handle flagging and moderating feedback on the video page and in the
 * moderator-only flagged feedback queue.
 */
var Moderation = {
    // Actions that a moderator can take on feedback entities.
    // Must be kept in sync with the server's representation in moderation.py
    ModAction: {
        "CLEAR_FLAGS": "clearflags",
        "CHANGE_TYPE": "changetype",
        "UNDELETE": "undelete"
    },

    // Keep in sync with constants in ModerationSortOrder in moderation.py
    LOW_QUALITY_FIRST: 1,
    LOWEST_VOTES_FIRST: 2,

    init: function() {
        $(".mod_tools .mod_edit").live("click", Moderation.editEntity);
        $(".mod_tools .mod_delete").live("click", Moderation.deleteEntity);
        $(".mod_tools .mod_change").live("click",
            Moderation.changeEntityType);
        $(".mod_tools .mod_clear_flags").live("click", Moderation.clearFlags);
        $(".mod_tools .mod_undelete").live("click", Moderation.undelete);
        $(".flag_show").live("click", Moderation.showFlagTools);
        $(".flag_tools .flag_as").live("click", Moderation.flagEntity);
    },

    showFlagTools: function() {
        if (QA.showNeedsLoginNote(this, "to flag this item.")) return false;

        var parent = $(this).parents(".flag_tools");
        if (!parent.length) {
            return false;
        }

        $(".flag_tools_show", parent).css("display", "none");
        $(".flag_tools_hidden", parent).css("display", "");

        return false;
    },

    flagEntity: function() {
        var flag = $(this).data("flag");
        if (!flag) {
            return;
        }

        // TODO(drew): add this to the API's perform_mod_action()
        return Moderation.actionWithoutConfirmation(this,
                "/discussion/flagentity",
                {flag: flag},
                "Gerapporteerd!");
    },

    deleteEntity: function() {
        var jel = $(this),
            key = jel.data("key"),
            mod_queue = jel.closest(".mod_tools").hasClass("mod_queue"),
            isAuthor = jel.parent().data("isAuthor"),
            isModerator = KA.getUserProfile().get("isModerator");

        if (!key) {
            return;
        }

        var isSortedByHeuristics = Boolean(jel.data("heuristics"));

        var url = "/api/v1/feedback/" + key + "?casing=camel";

        var deleteByAuthor = (isAuthor &&
                    confirm("Weet je zeker dat je dit wil verwijderen?")),
            deleteByModerator = (!isAuthor && isModerator),
            shouldDelete = deleteByAuthor || deleteByModerator;

        if (shouldDelete) {
            $.ajax({
                type: "DELETE",
                url: url,
                dataType: "json",
                success: function(data) {
                    if (deleteByModerator) {
                        // TODO(drew): Update video.comment or video.answer
                        // template to ensure the class "deleted" is added to
                        // div.question

                        data["message"] = "Verwijderd!";

                        var template;
                        if (mod_queue) {
                            template = Templates.get(
                                "moderation.mod-controls");

                            // Mantain data so that the buttons are labeled
                            // accordingly
                            data["isSortedByHeuristics"] = Boolean(
                                jel.data("heuristics"));
                        } else {
                            template = (Templates.
                                get("discussion.mod-controls"));
                        }
                        jel.closest(".mod_tools").replaceWith(template(data));

                        Moderation.finishedAction(jel);
                    } else {
                        var container;
                        if (QA.isInsideExistingQA(jel)) {
                            container = QA.getQAParent(jel);
                        } else {
                            container = jel.closest(".comment");
                        }

                        container.animate({
                            height: 0,
                            opacity: 0
                        },"slow", function() {
                            container.remove();
                        });
                    }
                }
            });
        }

        return false;
    },

    editEntity: function() {
        QA.edit(this);
        return false;
    },

    changeEntityType: function() {
        var jel = $(this),
            key = jel.data("key"),
            targetType = jel.data("targetType"),
            data = {
                type: targetType
            };

        if (!key || !targetType) {
            return;
        }

        $.ajax({
            type: "PUT",
            url: "/api/v1/feedback/" + key + "/" +
                    Moderation.ModAction.CHANGE_TYPE + "?casing=camel",
            contentType: "application/json",
            data: JSON.stringify(data),
            dataType: "json",
            success: _.bind(Moderation.finishedAction, Moderation, jel,
                    "Veranderd!")
        });

    },

    clearFlags: function() {
       Moderation.restore.call(this, false);
    },

    undelete: function() {
        Moderation.restore.call(this, true);
    },

    /**
     * PUT call that removes flags, undeletes the entity, and sets
     * definitely_not_spam to false.
     *
     * If onlyUndelete is set to true, the entity is undeleted but the flags
     * are kept, definitely_not_spam does not change. This is useful for
     * undoing a moderator 'delete' action
     */
    restore: function(onlyUndelete) {
        var jel = $(this),
            key = jel.data("key"),
            mod_queue = jel.closest(".mod_tools").hasClass("mod_queue");
            url = "/api/v1/feedback/" + key + "/" +
                    (onlyUndelete ? Moderation.ModAction.UNDELETE :
                                    Moderation.ModAction.CLEAR_FLAGS) +
                    "?casing=camel";

        if (!key) {
            return;
        }

        $.ajax({
            type: "PUT",
            url: url,
            dataType: "json",
            success: function(data) {
                var template;
                if (mod_queue) {
                    template = Templates.get("moderation.mod-controls");

                    // Mantain data so that the buttons are labeled
                    // accordingly
                    data["isSortedByHeuristics"] = !!jel.data("heuristics");
                } else {
                    template = Templates.get("discussion.mod-controls");
                }

                if (onlyUndelete) {
                    data["message"] = "Ongedaan gemaakt!";
                } else {
                    data["message"] = "Rapportages en ongedaan makingen verwijderd";
                }

                jel.closest(".mod_tools").replaceWith(template(data));

                Moderation.finishedAction(jel);
            }
        });
    },

    actionWithoutConfirmation: function(el, sUrl, data, sCompleted) {
        var key = $(el).data("key");
        if (!key) {
            return false;
        }

        data = data || {};
        data["entity_key"] = key;

        $.post(sUrl, data);
        Moderation.finishedAction(el, sCompleted);

        return false;
    },

    /**
     * Remove moderator controls and replace with the message provided as a
     * second parameter.
     * TODO(marcia): Revisit this behavior in the flagged feedback view, since
     * it feels a little bit awkward.
     */
    finishedAction: function(el, sMsg) {
        if (sMsg != null) {
            // Show message beside moderation controls
            var jelMessage = $(el).siblings(".message");
            if (!jelMessage.length) {
                // Replace flag controls with message, so we must
                // find ancestor
                jelMessage = $(el).parents(".message");
            }

            jelMessage.text(sMsg);
        }
        Throbber.hide();
    }
};
