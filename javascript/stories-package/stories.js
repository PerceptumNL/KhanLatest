
var Stories = Stories || {};

Stories.router = null;
Stories.views = {};
Stories.cShown = 0;
Stories.cRendered = 0;

Stories.render = function(storyData) {

    var row = null;
    var lastStory = null;
    var storiesPerRow = 3;

    $.each(storyData.content, function(ix, story) {

        if (ix % storiesPerRow == 0) {
            row = $("<div class='row'></div>");
            $(storyData.target).append(row);
        }

        if (lastStory && !story.empty) {
            lastStory.next_story = story;
            story.prev_story = lastStory;
        }

        var view = new Stories.SmallView({ model: story });
        row.append($(view.render(ix).el));

        Stories.views[story.name] = view;
        lastStory = story;

    });

    Stories.router = new Stories.StoryRouter();
    Backbone.history.start({
        pushState: true,
        root: "/stories/"
    });

};

Stories.SmallView = Backbone.View.extend({

    template: Templates.get("stories.story"),

    render: function(ix) {
        var model = this.model;

        $(this.el)
            .html(this.template(this.model))
            .addClass("span-one-third")
            .addClass("story-container")
            .find(".story")
                .addClass(this.model.envelope || this.randomEnvelope())
                .not(".disabled")
                    .addClass(this.randomRotation())
                    .click(function() { Stories.navigateTo(model); });

        Stories.cRendered++;

        return this;
    },

    randomRotation: function() {
        return this.randomChoice(["rotate-6", "rotate-neg-6"]);
    },

    randomEnvelope: function() {

        if (Stories.cRendered == 0) {
            // Evil dictator override!
            // I happen to think the first envelope is really pretty and it
            // should start off the series.
            return "envelope-1";
        }
        else if (Stories.cRendered == 1) {
            // Same as above
            return "envelope-2";
        }

        return this.randomChoice(["envelope-1", "envelope-2", "envelope-3", "envelope-4"]);
    },

    randomChoice: function(choices) {
        // Consistent style for this particular story
        Math.seedrandom(this.model.name);

        var index = Math.floor(Math.random() * choices.length);
        return choices[index];
    },

    showFull: function() {

        $(".content-teaser-show, .content-teaser-hide")
            .removeClass("content-teaser-show")
            .removeClass("content-teaser-hide");

        var model = this.model;
        var jelStory = $(this.el).find(".story");

        setTimeout(function() {

            $(jelStory).addClass("content-teaser-show");

            setTimeout(function() {

                $(jelStory).addClass("content-teaser-hide");
                var jelOld = $("#modal-story");

                var view = new Stories.FullView({ model: model });

                // If modal was previously visible, remove 'fade' class
                // so transition swaps immediately
                var classToRemove = Stories.cShown > 0 ? "fade" : "";

                $(view.render().el)
                    .find("#modal-story")
                        .removeClass(Stories.cShown > 0 ? "fade" : "")
                        .appendTo(document.body)
                        .bind("show", function() { Stories.cShown++; })
                        .bind("hidden", function() {

                            $(this).remove();

                            $(jelStory)
                                .removeClass("content-teaser-show")
                                .removeClass("content-teaser-hide");

                            // If no other modal dialog is on its way
                            // to becoming visible, push history
                            Stories.cShown--;
                            if (!Stories.cShown) {
                                Stories.navigateTo(null);
                            }
                        })
                        .modal({
                            keyboard: true,
                            backdrop: true,
                            show: true
                        })
                        .find(".modal-body")
                            .scroll(function() {

                                if (!this.fixedScrollRender) {

                                    // Chrome has an issue with not scrolling
                                    // content even though the scrollbars are
                                    // moving. Force a single re-render of the
                                    // modal dialog on first scroll.
                                    //
                                    // Feel free to enlighten me on the proper
                                    // fix for this bug...
                                    var jel = $(this).parents(".modal");
                                    $(jel).height($(jel).height() + 1);
                                    $(jel).height($(jel).height() - 1);

                                    this.fixedScrollRender = true;
                                }

                            });

                // Hide any existing modal dialog
                jelOld.removeClass("fade").modal("hide");

            }, 400);

        }
        , 1);

    }

});

Stories.FullView = Backbone.View.extend({

    template: Templates.get("stories.story-full"),

    render: function() {
        var model = this.model;

        $(this.el)
            .html(this.template(this.model))
            .find(".prev-btn")
                .not(".disabled")
                    .click(function() { Stories.navigateTo(model.prev_story); })
                    .end()
                .end()
            .find(".next-btn")
                .not(".disabled")
                    .click(function() { Stories.navigateTo(model.next_story); });
        return this;
    }

});

Stories.navigateTo = function(model) {
    if (model) {
        Stories.router.navigate(model.name, true);
    }
    else {
        Stories.router.navigate("");
    }
};

Stories.StoryRouter = Backbone.Router.extend({

    routes: {
        "": "showNone",
        ":story": "showStory"
    },

    showNone: function() {
        // If #modal-story is still in the DOM,
        // we got here via history navigation and
        // need to remove it.
        $("#modal-story").modal("hide");
    },

    showStory: function(name) {
        var view = Stories.views[name];
        if (view) {
            view.showFull();
        }
    }

});
