window.ScratchpadRevision = Backbone.Model.extend({
    parse: function(resp, xhr) {
        // resp.created comes down from the server as an RFC date string (see
        // api/jsonify.py). We want it as a native JS Date object.
        resp.created = new Date(resp.created);
        return resp;
    }
});

window.Scratchpad = Backbone.Model.extend({
    urlRoot: "/api/labs/scratchpads",

    showUrl: function() {
        return "/explore/" + this.get("slug") + "/" + this.get("id");
    },

    // This is called whenever data is pulled down via fetch or save.
    //
    // We want to add a revision key with another backbone model (since backbone
    // doesn't support nested .set and .get out of the box
    parse: function(resp, xhr) {
        resp.revision = new ScratchpadRevision(resp.revision, {parse: true});
        return resp;
    },

    // Returns a copy of the Scratchpad with origin_scratchpad_id and
    // origin_revision_id set, and with the id stripped out
    fork: function() {
        // Clone the scratchpad and revision, but strip out the ids, and
        // all developer-only attributes

        var forkedScratchpad = this.clone()
            .unset("id")
            .unset("category")
            .unset("difficulty")
            .unset("youtube_id")
            .set({
                revision: this.get("revision").clone().unset("id"),
                origin_scratchpad_id: this.get("id"),
                origin_revision_id: this.get("revision").get("id")
            });

        return forkedScratchpad;
    },

    save: function(attributes, options) {
        // TODO(jlfwong): Fix these issues on the serverside instead
        // (this is gross)

        // These properties are not assignable properties of Scratchpads, so we
        // want to strip them out before saving
        this
            .unset("kind")
            .unset("slug")
            .get("revision")
                .unset("created")
                .unset("kind")
                .unset("scratchpad_id");

        if (!this.isNew()) {
            // These properties are immutable once set, so we
            // want to strip them out before trying to do an update
            this
                .unset("origin_revision_id")
                .unset("origin_scratchpad_id")
                .unset("user_id")
                .get("revision")
                    .unset("id");
        }

        return Scratchpad.__super__.save.call(this, attributes, options);
    }
}, {
    // Static Properties

    difficultyMapping: {
        "10": "Getting Started",
        "20": "Easy",
        "30": "Intermediate",
        "40": "Expert"
    }
});

window.ScratchpadList = Backbone.Collection.extend({
    model: Scratchpad,
    fetchForUser: function(options) {
        return this.fetch($.extend({
            url: "/api/labs/user/scratchpads"
        }, options));
    }
});

window.ScratchpadListView = Backbone.View.extend({
    template: Templates.get("shared.scratchpad-list"),

    render: function() {
        var scratchpads = this.collection
            .chain()
            // Sort using the provided key function, or just use the
            // scratchpads' natural sort order if none is provided.
            .sortBy(this.options.sortBy || _.identity)
            .map(function(scratchpad) {
                var difficulty = scratchpad.get("difficulty");
                var category = scratchpad.get("category");

                return {
                    // TODO(jlfwong): Switch this to use the published flag
                    // See: http://phabricator.khanacademy.org/T44
                    displayDifficulty: (difficulty !== -1 &&
                        (category === "tutorial" || category === "official")),
                    difficulty: difficulty,
                    difficultyText: Scratchpad.difficultyMapping[difficulty],
                    imageUrl: scratchpad.showUrl() + "/image.png",
                    showUrl: scratchpad.showUrl(),
                    title: scratchpad.get("title")
                };
            })
            .value();

        this.$el.html(this.template({
            scratchpads: scratchpads
        }));
    }
});

