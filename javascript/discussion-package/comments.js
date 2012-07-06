/**
 * Handle loading and adding comments on the video page.
 */
var Comments = {
    page: 0,

    init: function() {
        $("a.comment_add").click(Comments.add);
        $("a.comment_show").click(Comments.show);
        $("a.comment_cancel").click(Comments.cancel);
        $("input.comment_submit").click(Comments.submit);
        $("form.comments").submit(function() { return false; });
        $(".comment_text").change(Comments.updateRemaining).keyup(Comments.updateRemaining);

        Comments.loadPage(0, true);
        Comments.enable();
    },

    initPages: function() {
        $("a.comments_page").click(function() { Comments.loadPage($(this).attr("page")); return false; });
        $("span.ellipsisExpand").click(Comments.expand);
    },

    expand: function() {
        var parent = $(this).parents("div.comment");
        if (!parent.length) return;

        $(this).css("display", "none");
        $("span.hiddenExpand", parent).removeClass("hiddenExpand");
    },

    loadPage: function(page, fInitialLoad) {

        try { page = parseInt(page); }
        catch (e) { return; }

        if (page < 0) return;

        $.get("/discussion/pagecomments",
                {
                    video_key: $("#video_key").val(),
                    topic_key: $("#topic_key").val(),
                    page: page
                },
                function(data) { Comments.finishLoadPage(data, fInitialLoad); });

        if (!fInitialLoad) Throbber.show($(".comments_page_controls span"));
    },

    finishLoadPage: function(data, fInitialLoad) {
        $(".comments_container").html(data.html);
        Comments.page = data.page;
        Comments.initPages();
        if (!fInitialLoad) Throbber.hide();

        if (!fInitialLoad) {
            document.location = "#comments";
        }
    },

    add: function() {
        $("a.comment_add").css("display", "none");

        setTimeout(function() {
            $("div.comment_form").slideDown("fast", function() {
                $(".comment_text").focus();
            });
        }, 0);

        Comments.updateRemaining();
        return false;
    },

    cancel: function() {
        $("a.comment_add").css("display", "");
        $("div.comment_form").slideUp("fast");
        $(".comment_text").val("");
        return false;
    },

    show: function() {
        $("div.comments_hidden").slideDown("fast");
        $(".comments_show_more").css("display", "none");
        return false;
    },

    submit: function() {
        if (!$.trim($(".comment_text").val()).length) return;

        var fCommentsHidden = $("div.comments_hidden").length && !$("div.comments_hidden").is(":visible");
        var data_suffix = "&comments_hidden=" + (fCommentsHidden ? "1" : "0");
        $.post("/discussion/addcomment",
                $("form.comments").serialize() + data_suffix,
                Comments.finishSubmit);

        Comments.disable();
        Throbber.show($(".comment_cancel"));
    },

    finishSubmit: function(data) {
        Comments.finishLoadPage(data);
        $(".comment_text").val("");
        Comments.updateRemaining();
        Comments.enable();
        Comments.cancel();
    },

    disable: function() {
        $(".comment_text, .comment_submit").attr("disabled", "disabled");
        $(".comment_submit").addClass("buttonDisabled");
    },

    enable: function() {
        $(".comment_text, .comment_submit").removeAttr("disabled");
        $(".comment_submit").removeClass("buttonDisabled");
    },

    updateRemaining: function() {
        Discussion.updateRemaining(300, ".comment_text",
                                        ".comment_add_controls .chars_remaining",
                                        ".comment_add_controls .chars_remaining_count");
    }
};
