
var Discussion = {

    init: function() {
        VideoControls.initJumpLinks();
    },

    // TODO(marcia): Note that keyhandling.js exists and may be applicable.
    updateRemaining: function(max, textSelector, charsSelector,
                              charCountSelector, parent) {
        setTimeout(function() {
            var c = 0;
            try {
                c = max - parseInt($(textSelector, parent).val().length, 10);
            } catch (e) {
                return;
            }

            if (c <= 0)
                $(charsSelector, parent).addClass("chars_remaining_none");
            else
                $(charsSelector, parent).removeClass("chars_remaining_none");

            // Disable submit buttons within form so user can't submit and lose
            // clipped content.
            var jForm = $(textSelector, parent).parents("form");
            if (jForm.length)
            {
                if (c < 0) {
                    $("input[type=button]", jForm)
                        .addClass("buttonDisabled")
                        .attr("disabled", "disabled");
                } else {
                    $("input[type=button]", jForm)
                      .removeClass("buttonDisabled")
                      .removeAttr("disabled");
                }
            }

            $(charCountSelector, parent).html(c);
        }, 1);
    }
};

var Voting = {

    init: function() {
        $(".vote_for").live("click", Voting.voteEntity);
    },

    voteEntity: function(e) {
        // Handle a click event on a voting arrow.

        if (QA.showNeedsLoginNote(this, "to vote.")) return false;

        var jel = $(this);

        // +1 for upvote, -1 for downvote
        var voteType = jel.data("voteType");
        if (!voteType) return false;

        // GAE db key of model to vote on
        var key = jel.attr("data-key");
        if (!key) return false;

        // false when making a new vote; true when clearing an existing one
        var fAbstain = jel.is(".voted");

        var jelParent = jel.parents(".comment, .answer, .question").first();
        var jelVotes = jelParent.find(".sum_votes");

        $.post("/discussion/voteentity", {
            entity_key: key,
            vote_type: fAbstain ? 0 : voteType
        }, function(data) {
            Voting.finishVoteEntity(data, jel, jelParent, jelVotes);
        });

        var votes = Voting.clearVote(jel, jelParent, jelVotes);
        votes += (fAbstain ? 0 : voteType);

        Voting.setVoteCount(jelParent, jelVotes, votes);
        jelVotes.addClass("sum_votes_changed");
        if (!fAbstain) jel.addClass("voted");

        return false;
    },

    setVoteCount: function(jelParent, jelVotes, votes) {
        // Show the passed-in vote count next to a comment or question, adding
        // the appropriate "votes," suffix for comments (as opposed to
        // questions and answers, where only the number is shown to the left)

        if (jelParent.is(".comment")) {
            jelVotes.html(votes + " vote" + (votes == 1 ? "" : "s") + ", ");
        } else {
            jelVotes.html(votes);
        }
    },

    clearVote: function(jel, jelParent, jelVotes) {
        // Clear the clicked-ness of the arrows inside a vote and update the
        // count to reflect the new non-clicked-ness of the arrow (e.g., if it
        // said 17 with a highlighted (.voted) arrow then running clearVote
        // would show the effect of removing that upvote -- that is, make it
        // show 16 with neither arrow highlighted.
        //
        // Returns the new number of votes displayed.

        var votes = parseInt(jelVotes.text(), 10);
        jelParent.find("a.vote_for.voted").each(function() {
            var el = $(this);
            el.removeClass("voted");
            votes -= el.data("voteType");
        });

        jelVotes.removeClass("sum_votes_changed");
        Voting.setVoteCount(jelParent, jelVotes, votes);
        return votes;
    },

    finishVoteEntity: function(data, jel, jelParent, jelVotes) {
        // Show an error if the server returned one; possible error causes
        // are not being logged in and voting on your own posts

        if (data && data.error) {
            Voting.clearVote(jel, jelParent, jelVotes);
            QA.showInfoNote(jel.get(0), data.error);
        }
    }

};

// Now that we enable YouTube's JS api so we can control the player w/
// "{minute}:{second}"-style links, we are vulnerable to a bug in IE's flash
// player's removeCallback implementation.  This wouldn't harm most users b/c
// it only manifests itself during page unload, but for anybody with IE's "show
// all errors" enabled, it becomes an annoying source of "Javascript error
// occurred" popups on unload.  So we manually fix up the removeCallback
// function to be a little more forgiving. See:
// http://www.fusioncharts.com/forum/Topic12189-6-1.aspx#bm12281
// http://swfupload.org/forum/generaldiscussion/809
// http://www.longtailvideo.com/support/forums/jw-player/bug-reports/10374/javascript-error-with-embed
$(window).unload(
function() {
    (function($) {
        $(function() {
            if (typeof __flash__removeCallback != "undefined") {
                __flash__removeCallback = function(instance, name) {
                    if (instance != null && name != null)
                        instance[name] = null;
                };
            }
        });
    })(jQuery);
});
