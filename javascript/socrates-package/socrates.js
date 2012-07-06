Socrates = {};

// this should work with a QuestionView
Socrates.ControlPanel = Backbone.View.extend({
    el: ".interactive-video-controls",

    controls: [],

    events: {
        "click button#label": "addLabel",
        "click button#inputtext": "addInputText"
    },

    addLabel: function() {
        this.addView(new Socrates.Label());
    },

    addInputText: function() {
        this.addView(new Socrates.InputText());
    },

    addView: function(view) {
        this.controls.push(view);

        // place in document before rendering, as jquery.ui checks if element is
        // positioned, and positioning is done in external CSS.
        this.$controlEl.append(view.el);
        view.render();
    },

    serializeHtml: function() {
        _.each(this.controls, function(c) {
            c.moveable(false);
        });
        return this.$controlEl.html();
    }
}, {
    onReady: function() {
        window.ControlPanel = new Socrates.ControlPanel();
    }
});

// Editing actions needed:
// 1. Lock / unlock moving (console)
// 2. Delete (console)
// 3. Edit text (dblclick)

Socrates.Label = Backbone.View.extend({
    tagName: "div",
    className: "label",

    events: {
        "dblclick": "promptForContents"
    },

    render: function() {
        this.$el.text("Default label contents");
        this.moveable(true);
        return this;
    },

    isMoveable: false,
    moveable: function(val) {
        if (val === this.isMoveable) return this;
        if (val == null) {
            val = !this.isMoveable;
        }
        this.isMoveable = val;

        if (this.isMoveable) {
            this.$el
                .addClass("moveable")
                .resizable()
                .draggable();
        } else {
            this.$el
                .removeClass("moveable")
                .resizable("destroy")
                .draggable("destroy");
        }

        return this;
    },

    promptForContents: function(evt) {
        var contents = prompt("Enter label contents", this.$el.text());
        this.$el.text(contents);
        if (this.isMoveable) {
            // need to toggle as .text() destroys the corner thing
            this.moveable(false);
            this.moveable(true);
        }
    },

    serializedForm: function() {

    }
});

Socrates.InputText = Backbone.View.extend({
    className: "inputtext",
    template: Templates.get("socrates.inputtext"),

    events: {
        "dblclick": "promptForContents"
    },

    render: function() {
        var contents = this.template({
            placeholder: "?"
        });
        this.$el.html(contents);
        this.moveable(true);
        return this;
    },

    isMoveable: false,
    moveable: function(val) {
        if (val === this.isMoveable) return this;
        if (val == null) {
            val = !this.isMoveable;
        }
        this.isMoveable = val;

        if (this.isMoveable) {
            this.$el
                .addClass("moveable")
                .resizable()
                .draggable();
        } else {
            this.$el
                .removeClass("moveable")
                .resizable("destroy")
                .draggable("destroy");
        }

        return this;
    },

    promptForContents: function(evt) {
        var $input = this.$("input");
        var contents = prompt("Enter placeholder contents",
            $input.attr("placeholder"));
        $input.attr("placeholder", contents);
    },

    serializedForm: function() {
        this.$("input").prop("disabled", false);
    }
});

Socrates.Bookmark = Backbone.Model.extend({
    defaults: {
        complete: false
    },

    seconds: function() {
        return Socrates.Question.timeToSeconds(this.get("time"));
    },

    slug: function() {
        return _.str.slugify(this.get("title"));
    },

    toJSON: function() {
        var json = Backbone.Model.prototype.toJSON.call(this);
        json.slug = this.slug();
        return json;
    }
}, {
    timeToSeconds: function(time) {
        if (time == null || time.length === 0) {
            throw "Invalid argument";
        }
        // convert a string like "4m21s" into just the number of seconds
        result = 0;
        var i = 0;
        while (time[i]) {
            var start = i;
            while (time[i] && /[\d\.,]/.test(time[i])) i++;
            var n = parseFloat(time.slice(start, i));
            var unit = time[i] || "s"; // assume seconds if reached end
            if (unit == "m") {
                result += n * 60;
            } else if (unit == "s") {
                result += n;
            } else {
                throw "Unimplemented unit, only ISO8601 durations with mins and secs";
            }
            i++;
        }
        return result;
    }
});

// todo(dmnd): need to make this less confusing
Socrates.Question = Socrates.Bookmark.extend({
    baseSlug: Socrates.Bookmark.prototype.slug,

    slug: function() {
        return this.baseSlug() + "/q";
    },

    imageUrl: function() {
        return this.get("youtubeId") + "-" + this.get("time");
    },

    templateName: function() {
        return this.get("youtubeId") + "." + this.baseSlug();
    }
});

Socrates.QuestionCollection = Backbone.Collection.extend({
    model: Socrates.Question
});

Socrates.QuestionView = Backbone.View.extend({
    className: "question",

    events: {
        "submit form": "submit",
        "click .submit-area a.skip": "skip",
        "click .close": "skip",
        "click .submit-area a.see-answer": "seeAnswerClicked"
    },

    timeDisplayed: 0,
    startTime: null,

    initialize: function() {
        _.extend(this, this.options);
        this.version = 1;
        this.loaded = false;
        this.template = Templates.get(this.model.templateName());

        this.render();
    },

    render: function() {
        this.$el.html(this.template({
            title: this.model.get("title"),
            explainUrl: this.model.get("nested")
        }));

        // add in a backdrop if necessary
        var $screenshot = this.$(".layer.backdrop.videoframe");
        if ($screenshot.length > 0) {
            $screenshot.append($("<img>", {src: this.imageUrl()}));
        }

        // linkify the explain button
        var parent = this.model.get("nested");
        if (parent) {
            this.$(".simple-button.explain").attr("href", "#" + parent);
        }
        this.loaded = true;

        return this;
    },

    qtip: function() {
        var qtipq = this.$(".qtip-question");
        if (qtipq.length > 0) {
            var $controls = this.$('.controls');
            $controls.qtip({
                content: {
                    text: qtipq,
                    title: this.model.get('title')
                },
                position: $.extend({
                    container: $controls,
                    at: [0, 0]
                }, this.model.get('qtip-position')),
                style: {
                    classes: "ui-tooltip ui-tooltip-rounded ui-tooltip-shadow"
                },
                show: {
                    event: false,
                    ready: true
                },
                hide: false
            });
        }
    },

    hide: function() {
        this.finishRecordingTime();
        this.$el.removeClass("visible");
        return this;
    },

    finishRecordingTime: function() {
        if (this.startTime) {
            this.timeDisplayed += (+new Date() - this.startTime);
            this.startTime = null;
        } else {
            this.timeDisplayed = 0;
        }
        return this.timeDisplayed;
    },

    show: function() {
        this.startTime = +new Date();
        this.$el.addClass("visible");
        this.qtip();
        return this;
    },

    imageUrl: function() {
        return "/images/videoframes/" + this.model.imageUrl() + ".jpeg";
    },

    isCorrect: function(data) {
        var correctAnswer = this.model.get("correctData");

        // if no answer is specified, any answer is correct
        if (correctAnswer == null) {
            return true;
        }

        // otherwise make sure they got it right.
        // todo: look at how khan-exercise does their fancy number handling
        return _.isEqual(data, correctAnswer);
    },

    getData: function() {
        data = {};

        // process all matrix-inputs
        var $matrixInputs = this.$("table.matrix-input");
        data = _.extend(data, this.matrixInputToAnswer($matrixInputs));

        // process all checkbox-grids
        var $checkboxGrids = this.$("table.checkbox-grid");
        data = _.extend(data, this.checkBoxGridToAnswer($checkboxGrids));

        // process the result of the inputs
        var $inputs = this.$("input").
            not($matrixInputs.find("input")).
            not($checkboxGrids.find("input"));

        data = _.extend(data, this.freeInputsToAnswer($inputs));
        return data;
    },

    matrixInputToAnswer: function($matrixInputs) {
        var data = {};
        _.each($matrixInputs, function(table) {
            var matrix = _.map($(table).find("tr"), function(tr) {
                return _.map($(tr).find("input"), function(input) {
                    return parseFloat($(input).val());
                });
            });

            var name = $(table).attr("name") || "answer";
            data[name] = matrix;
        });
        return data;
    },

    checkBoxGridToAnswer: function($checkboxGrids) {
        var data = {};
        _.each($checkboxGrids, function(grid) {
            var headers = _.map($(grid).find("thead th"), function(td) {
                return $(td).attr("name");
            });
            headers = _.rest(headers, 1);
            var answer = {};
            _.each($(grid).find("tbody tr"), function(tr) {
                var row = {};
                _.each($(tr).find("input"), function(input, i) {
                    row[headers[i]] = $(input).prop("checked");
                });
                answer[$(tr).attr("name")] = row;
            });

            var name = $(grid).attr("name") || "answer";
            data[name] = answer;
        });
        return data;
    },

    freeInputsToAnswer: function($inputs) {
        var data = {};
        $inputs.each(function(i, el) {
            var $el = $(el);
            var key = $el.attr("name");

            var val;
            if ($el.attr("type") === "checkbox") {
                val = $el.prop("checked");
            } else if ($el.attr("type") === "radio") {
                if ($el.prop("checked")) {
                    val = $el.val();
                } else {
                    // ignore if it's an unchecked radio button
                    return true; // continue
                }
            } else {
                val = $el.val();
            }

            var isArray = false;
            if (data[key] != null) {
                if (!_.isArray(data[key])) {
                    data[key] = [data[key]];
                }
                isArray = true;
            }

            if (isArray) {
                data[key].push(val);
            } else {
                data[key] = val;
            }
        });
        return data;
    },

    seeAnswerClicked: function() {
        this.$(".submit-area .submit").prop("disabled", true);
        this.showMem();
        this.loadAnswer();
    },

    loadAnswer: function() {
        var data = $.extend(true, {}, this.model.get("correctData"));

        // process all matrix-inputs
        var $matrixInputs = this.$("table.matrix-input");
        data = this.answerToMatrixInputs($matrixInputs, data);

        // process all checkbox-grids
        var $checkboxGrids = this.$("table.checkbox-grid");
        data = this.answerToCheckboxGrids($checkboxGrids, data);

        // process the result of the inputs
        var $inputs = this.$("input").
            not($matrixInputs.find("input")).
            not($checkboxGrids.find("input"));

        data = this.answerToFreeInputs($inputs, data);

        // by now data should be empty
        if (!_.isEmpty(data)) {
            console.log("failed to load answer correctly");
        }
    },

    answerToMatrixInputs: function($matrixInputs, data) {
        _.each($matrixInputs, function(table) {
            var name = $(table).attr("name") || "answer";
            var matrix = data[name];

            _.each($(table).find("tr"), function(tr, i) {
                return _.each($(tr).find("input"), function(input, j) {
                    $(input).val(matrix[i][j]);
                });
            });

            delete data[name];
        });
        return data;
    },

    answerToCheckboxGrids: function($checkboxGrids, data) {
        _.each($checkboxGrids, function(grid) {
            var name = $(grid).attr("name") || "answer";
            var answer = data[name];

            var headers = _.map($(grid).find("thead th"), function(td) {
                return $(td).attr("name");
            });
            headers = _.rest(headers, 1);
            _.each($(grid).find("tbody tr"), function(tr) {
                var rowName = $(tr).attr("name");
                _.each($(tr).find("input"), function(input, i) {
                    $(input).prop("checked", answer[rowName][headers[i]]);
                });
            });
        });
        return data;
    },

    answerToFreeInputs: function($inputs, data) {
        $inputs.each(function(i, el) {
            var $el = $(el);
            var key = $el.attr("name");

            var val = data[key];
            var isArray = _.isArray(data[key]);
            if (isArray) {
                val = data[key].pop();
            }
            // delete the item unless it's a nonempty array
            if (!(isArray && !_.isEmpty(data[key]))) {
                delete data[key];
            }

            if ($el.attr("type") === "checkbox") {
                $el.prop("checked", val);
            } if ($el.attr("type") === "radio") {
                if ($el.val() === val) {
                    $el.prop("checked", true);
                }
                else {
                    // put the item back since we can't use it
                    data[key] = val;
                    return true; // continue
                }
            } else {
                $el.val(val);
            }
        });

        return data;
    },

    getResponse: function() {
        // get response data
        var data = this.getData();

        // find how long it took to answer, then reset the countera
        var timeDisplayed = this.finishRecordingTime();
        this.timeDisplayed = 0;

        return {
            time: this.model.get("time"),
            youtubeId: this.model.get("youtubeId"),
            id: this.model.get("id"),
            version: this.version,
            correct: this.isCorrect(data),
            data: data,
            timeDisplayed: timeDisplayed
        };
    },

    validateResponse: function(response) {
        requiredProps = ["id", "version", "correct", "data", "youtubeId",
            "time"];
        var hasAllProps = _.all(requiredProps, function(prop) {
            return response[prop] != null;
        });
        if (!hasAllProps) {
            console.log(response);
            throw "Invalid response from question";
        }
        return true;
    },

    alreadyFiredAnswered: false,
    fireAnswered: function() {
        if (!this.alreadyFiredAnswered) {
            this.alreadyFiredAnswered = true;

            // notify router that the question was answered correctly
            this.trigger("answered");
        }
    },

    submit: function(evt) {
        evt.preventDefault();
        var $form = $(evt.currentTarget);
        var $button = $form.find(".submit");

        // when question has been answered correctly, the submit button
        // says continue.
        if ($button.text() === "Continue") {
            this.fireAnswered();
            return;
        }

        // otherwise, get the answer
        var response = this.getResponse();
        this.validateResponse(response);

        // log it on the server side
        this.log("submit", response);

        // tell the user if they got it right or wrong
        if (response.correct) {
            this.model.set({"complete": true});

            this.$(".submit-area .alert-error").hide();
            this.$(".submit-area .alert-success").show();

            if ($button) {
                $button.html("Continue");
            }

            if (this.hasMem()) {
                this.showMem();
            } else {
                // otherwise resume the video in 3s
                _.delay(_.bind(this.fireAnswered, this), 3000);
            }
        } else {
            this.$(".submit-area .alert-success").hide();
            this.$(".submit-area .alert-error").show();
        }
    },

    hasMem: function() {
        return this.$(".mem").length > 0;
    },

    showMem: function() {
        this.$(".mem").slideDown(350, 'easeInOutCubic');
    },

    skip: function() {
        var response = this.getResponse();
        this.validateResponse(response);
        this.log("skip", response);
        this.trigger("skipped");
    },

    log: function(kind, response) {
        console.log("POSTing response", kind, response);
    }
});

Socrates.MasterView = Backbone.View.extend({
    initialize: function(options) {
        this.views = options.views;
    },

    render: function() {
        this.$el.append(_.pluck(this.views, "el"));
    }
});

Socrates.Nav = Backbone.View.extend({
    template: Templates.get("socrates.socrates-nav"),

    initialize: function() {
        this.model.bind("change", this.render, this);

        // only show the event bar when the mouse is hovering over the video
        var that = this;
        this.options.$hoverContainerEl.hoverIntent(
            function() {
                that.$(".timebar").fadeIn(300, 'easeInOutCubic');
            },
            function() {
                that.$(".timebar").fadeOut(300, 'easeInOutCubic');
            }
        );
    },

    questionsJson: function() {
        return this.model.
            filter(function(i) {return i.constructor == Socrates.Question;}).
            map(function(question) {
                var pc = question.seconds() / this.options.videoDuration * 100;
                return {
                    title: question.get("title"),
                    time: question.get("time"),
                    slug: question.slug(),
                    percentage: pc,
                    complete: question.get("complete") ? "complete" : ""
                };
            }, this);
    },

    render: function() {
        this.$el.html(this.template({
            questions: this.questionsJson()
        }));
        return this;
    }
});

var recursiveTrigger = function recursiveTrigger(triggerFn) {
    var t = window.VideoStats.getSecondsWatched();

    triggerFn(t);

    // schedule another call when the duration is probably ticking over to
    // the next tenth of a second
    t = window.VideoStats.getSecondsWatched();
    var delay = (Poppler.nextPeriod(t, 0.1) - t) * 1000;
    _.delay(recursiveTrigger, delay, triggerFn);
};

Socrates.QuestionRouter = Backbone.Router.extend({
    routes: {
        ":segment": "reactToNewFragment",
        ":segment/:qid": "reactToNewFragment"
    },

    initialize: function(options) {
        _.defaults(options, this.constructor.defaults);

        this.beep = new Audio("");
        var mimeTypes = {
            "ogg": "audio/ogg",
            "mp3": "audio/mpeg",
            "wav": "audio/x-wav"
        };
        var ext;
        var match = _.find(mimeTypes, function(i, k) {
            if (this.beep.canPlayType(mimeTypes[k]) !== "") {
                ext = k;
                return true;
            }
            return false;
        }, this);
        if (match) {
            this.beep.src = options.beepUrl + "." + ext;
            this.beep.volume = options.beepVolume;
        } else {
            this.beep = null;
        }

        this.videoControls = options.videoControls;

        // listen to player state changes
        $(this.videoControls).on("playerStateChange",
            _.bind(this.playerStateChange, this));

        this.bookmarks = options.bookmarks;

        this.questions = this.bookmarks.filter(function(b) {
            return b.constructor.prototype === Socrates.Question.prototype;
        });

        // wrap each question in a view
        this.questionViews = this.questions.map(function(question) {
            return new Socrates.QuestionView({model: question});
        });

        // subscribe to submit and skip
        _.each(this.questionViews, function(view) {
            view.bind("skipped", this.skipped, this);
            view.bind("answered", this.submitted, this);
        }, this);

        // hookup question display to video timelime
        this.poppler = new Poppler();
        _.each(this.questions, function(q) {
            this.poppler.add(q.seconds(), _.bind(this.videoTriggeredQuestion, this, q), q.slug());
        }, this);

        // trigger poppler every tenth of a second
        recursiveTrigger(_.bind(this.poppler.trigger, this.poppler));
    },

    playerStateChange: function(evt, state) {
        if (state === VideoPlayerState.PLAYING) {
            if (this.ignoreNextPlay) {
                this.ignoreNextPlay = false;
            } else {
                var t = VideoStats.getSecondsWatched();
                this.poppler.seek(t);
            }
        } else if (state === VideoPlayerState.PAUSED) {
            // sometimes the video buffers then pauses. When this happens, allow
            // the next play event to cause a seek
            this.ignoreNextPlay = false;
        } else if (state === VideoPlayerState.BUFFERING) {
            // buffering is usually followed by a play event. We only care about
            // play events caused by the user scrubbing, so ignore it
            this.ignoreNextPlay = true;
        }
    },

    // recieved a question or view, find the corresponding view
    questionToView: function(view) {
        if (view.constructor.prototype == Socrates.Question.prototype) {
            view = _.find(this.questionViews, function(v) { return v.model == view; });
        }
        return view;
    },

    reactToNewFragment: function(segment, qid) {
        if (qid) {
            segment = segment + "/" + qid;
        }

        // blank fragment for current state of video
        if (segment === "") {
            this.leaveCurrentState();
        }

        // top level question
        // slug for navigating to a particular question
        var question = this.bookmarks.find(function(b) {
            return b.slug() === segment;
        });
        if (question) {
            if (question.constructor.prototype === Socrates.Question.prototype) {
                this.linkTriggeredQuestion(question);
                return;
            } else {
                // was a bookmark
                var seconds = question.seconds();
                this.fragmentTriggeredSeek(seconds);
                return;
            }
        }

        // seek to time, e.g. 4m32s
        try {
            var seconds = Socrates.Question.timeToSeconds(slug);
            this.fragmentTriggeredSeek(seconds);
            return;
        } catch (e) {
            // ignore
        }

        // invalid fragment, replace it with nothing

        // todo(dmnd) replace playing with something that makes more sense
        this.navigate("playing", {replace: true, trigger: true});
    },

    // called when video was playing and caused a question to trigger
    videoTriggeredQuestion: function(question) {
        // if questions are disabled, ignore
        if (!$(".socrates-enable").prop("checked")) return;

        // pause the video
        this.videoControls.pause();
        if (this.beep != null) {
            this.beep.play();
        }

        // update the fragment in the URL
        this.navigate(question.slug());

        this.enterState(question);
        return true; // block poppler
    },

    // called when question has been triggered manually via clicking a link
    linkTriggeredQuestion: function(question) {
        this.videoControls.invokeWhenReady(_.bind(function() {
            // notify poppler
            this.poppler.blocked = true;

            this.poppler.seekToId(question.slug());
            this.poppler.eventIndex++; // make poppler only listen to events after the current one

            // put video in correct position
            this.videoControls.pause();
            var state = this.videoControls.player.getPlayerState();
            if (state === VideoPlayerState.PAUSED) {
                // only seek to the correct spot if we are actually paused
                this.videoControls.player.seekTo(question.seconds(), true);
            }

            this.enterState(question);
        }, this));
    },

    fragmentTriggeredSeek: function(seconds) {
        this.leaveCurrentState();
        this.videoControls.invokeWhenReady(_.bind(function() {
            this.poppler.blocked = true;
            this.poppler.seek(seconds);
            this.videoControls.player.seekTo(seconds, true);
            var state = this.videoControls.player.getPlayerState();
            if (state === VideoPlayerState.PAUSED) {
                this.videoControls.play();
            }
            this.poppler.blocked = false;
        }, this));
    },

    enterState: function(view) {
        this.leaveCurrentState();

        var nextView = this.questionToView(view);
        if (nextView) {
            this.currentView = nextView;
            this.currentView.show();
        } else {
            console.log("no view, wtf");
        }

        return this;
    },

    leaveCurrentState: function() {
        if (this.currentView) {
            if (this.currentView.hide)
                this.currentView.hide();
            this.currentView = null;
        }
        return this;
    },

    skipped: function() {
        var seconds = this.currentView.model.seconds();
        this.currentView.hide();

        this.navigate("playing");
        this.poppler.resumeEvents();

        if (this.poppler.blocked) {
            // another blocking event was present. Do nothing.
        } else {
            // no more events left, play video

            // prevent seek() from being called
            this.ignoreNextPlay = true;

            var state = this.videoControls.player.getPlayerState();
            if (state == VideoPlayerState.PAUSED) {
                this.videoControls.play();
            }
            else {
                this.videoControls.player.seekTo(seconds);
            }
        }
    },

    submitted: function() {
        this.skipped();
    }
}, {
    defaults: {
        beepUrl: "/sounds/72126__kizilsungur__sweetalertsound2",
        beepVolume: 0.3
    }
});

Socrates.Skippable = (function() {
    var Skippable = function(options) {
        _.extend(this, options);
    };

    Skippable.prototype.seconds = function() {
        return _.map(this.span, Socrates.Question.timeToSeconds);
    };

    Skippable.prototype.trigger = function() {
        var pos = this.seconds()[1];
        this.videoControls.player.seekTo(pos, true);
    };

    return Skippable;
})();

Socrates.init = function(youtubeId) {
    // Create data
    window.Bookmarks = new Backbone.Collection(Socrates.Data[youtubeId].Events);


    // Create router which will manage transitions between questions
    window.Router = new Socrates.QuestionRouter({
        bookmarks: window.Bookmarks,
        videoControls: window.VideoControls
    });

    // For now, don't call Video.init() Just render the page then let our router
    // take over.
    // todo(dmnd) Integrate socrates & ajax video player routers. May need to
    // use hashChange from here: https://github.com/documentcloud/backbone/issues/803
    Video.videoLibrary = {};
    Video.pushStateDisabled = true;
    Video.rendered = true; // Stops video.js from assuming templates are pre-rendered
    Video.navigateToVideo(window.location.pathname);
    Backbone.history.start({
        pushState: false,
        root: window.location.pathname
    });


    // Render views
    VideoControls.invokeWhenReady(function() {
        var duration = VideoControls.player.getDuration();
        window.nav = new Socrates.Nav({
            el: ".socrates-nav",
            model: Bookmarks,
            videoDuration: duration,
            $hoverContainerEl: $(".youtube-video")
        });
        nav.render();

        $(".socrates-enable").
            prop("checked", true).
            parents('li').eq(0).show();
    });

    window.masterView = new Socrates.MasterView({
        el: ".video-overlay",
        views: Router.questionViews
    });
    masterView.render();
};

Socrates.initSkips = function(youtubeId) {
    window.skippable = _.map(Socrates.Data[youtubeId].Skips, function(item) {
        return new Socrates.Skippable(_.extend(item, {videoControls: window.VideoControls}));
    });
    _.each(skippable, function(item) {
        poppler.add(item.seconds()[0], _.bind(item.trigger, item));
    });
};

// This will be populated by video-specific javascript.
Socrates.Data = {};

Handlebars.registerPartial("submit-area", Templates.get("socrates.submit-area"));

// todo(dmnd) only run this in edit mode
$(Socrates.ControlPanel.onReady);
