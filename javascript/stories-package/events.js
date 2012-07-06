$(function() {

    $(".share-story-btn").click(function(e) {

        // Show story submission area
        $(".stories-submit")
            .slideToggle(function() {
                $(".stories-submit textarea").focus();
            })
            .find(".submit-story-btn")
                .html("Send us your story")
                .removeClass("disabled")
                .removeClass("success")
                .addClass("primary");

        e.preventDefault();
    });

    $(".share-story-btn-bottom").click(function(e) {

        $('html, body').animate({
            scrollTop: 0
        }, 250, function() {
            if (!$(".stories-submit").is(":visible")) {
                $(".share-story-btn").trigger("click");
            }
        });

        e.preventDefault();

    });

    $(".submit-story-btn").click(function(e) {

        // Submit story
        if ($("#story").val().length) {

            $(this)
                .addClass("disabled")
                .html("Sending&hellip;");

            $.post(
                "/stories/submit",
                {
                    "story": $("#story").val(),
                    "video": $("#video").val(),					
                    "name": $("#name").val(),
                    "email": $("#email").val(),
                    "share": $("#shareAllow").is(":checked") ? "1": "0"
                },
                function() {

                    $(".submit-story-btn")
                        .removeClass("primary")
                        .addClass("success")
                        .html("Success!");

                    // Close and clean up story submission area after delay
                    setTimeout(function() {
                        $(".stories-submit")
                            .slideUp()
                            .find("textarea")
                                .val("");
                    }, 3000);

                });

        }

        e.preventDefault();
    });

});
