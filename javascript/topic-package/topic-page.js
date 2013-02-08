(function() {
    // The video data for the subtopics of this topic
    var videosByTopic = {};

    // The currently selected subtopic in the content pane
    var selectedTopic = null;

    // The topic information for the current page's topic
    var rootPageTopic = null;

    // View for the root topic in the content pane
    var rootTopicView = null;

    // All the video information sorted by YouTube ID
    var videosDict = {};

    // Maximum content height
    var maxContentHeight = 0;

    window.TopicPage = {
        init: function(topicID) {
            // TODO(tom): figure out how to invalidate this if we need to change
            // the schema of a topic.
            $.ajax({
                url: "/api/v1/topic/" + topicID + "/topic-page",
                dataType: "json",
                success: function(rootTopic) {
                    rootPath = "/" + rootTopic.extended_slug + "/";
                    TopicPage.finishInit(rootPath, rootTopic);
                }
            });

            // Try to retain maximum content pane height
            TopicPage.growContent();

            $(window).resize(function() {
                TopicPage.growContent();
            });
        },
        finishInit: function(rootPath, rootTopic) {
            var self = this;

            rootPageTopic = rootTopic;

            // TODO(tomyedwab): Temporary, should move this to a shared lib 
            Handlebars.registerPartial("youtube-player", Templates.get("shared.youtube-player"));

            videosDict[rootTopic.marquee_video.youtube_id] = rootTopic.marquee_video;
            _.each(rootTopic.subtopics, function(topic) {
                videosByTopic[topic.id] = topic;
                videosDict[topic.thumbnail_link.youtube_id] = topic.thumbnail_link;
            });

            $(".topic-page-content").on("click", ".topic-page-content a.subtopic-link", function() {
                selectedID = $(this).attr("data-id");
                self.router.navigate(selectedID, true);
                return false;
            });
            $(".topic-page-content").on("click", ".topic-page-content a.subtopic-link-and-scroll", function() {
                selectedID = $(this).attr("data-id");
                self.router.navigate(selectedID, true);
                $("body").animate( {scrollTop:0}, 200, "easeInOutCubic");
                return false;
            });

            $(".topic-page-content").on("click", "a.modal-video", function(ev) {
                var videoDesc = videosDict[$(this).attr("data-youtube-id")];
                if (videoDesc) {
                    var video = {
                        youtubeId: videoDesc.youtube_id,
                        relative_url: videoDesc.href,
                        title: videoDesc.title,
                        description: videoDesc.teaser_html
                    };
                    ModalVideo.show(video);
                    ev.preventDefault();
                    return false;
                }
                return true;
            });

            this.router = new this.SubTopicRouter();
            this.router.bind("all", Analytics.handleRouterNavigation);
            Backbone.history.start({pushState: true, root: rootPath});
        },
        growContent: function() {
            //TODO delete this empty function
        },
        SubTopicRouter: Backbone.Router.extend({
            routes: {
                "*subtopicID": "showSubtopic"
            },

            showSubtopic: function(subtopicID) {
                var selectedTopicID = '';
                if (subtopicID.charAt(0) === '/') {
                    subtopicID = subtopicID.substr(1);
                }

                KAConsole.log("Switching to subtopic: " + subtopicID);
                if (subtopicID === "") {
                    selectedTopic = null;
                } else {
                    selectedTopic = videosByTopic[subtopicID] || null;
                }

                var analyticsParams;

                if (selectedTopic) {
                    selectedTopic.view = selectedTopic.view || new TopicPage.ContentTopicView({ model: selectedTopic, viewCount: 0 });
                    selectedTopic.view.show();
                    selectedTopicID = selectedTopic.id;

                    analyticsParams = {
                        "Topic Title": selectedTopic.title,
                        "Topic Type": "Subtopic",
                        "Topic View Count": selectedTopic.view.options.viewCount
                    };
                } else {
                    if (rootPageTopic.child_videos) {
                        rootTopicView = rootTopicView || new TopicPage.ContentTopicView({ model: rootPageTopic.child_videos, viewCount: 0 });
                        analyticsParams = {
                            "Topic Title": rootPageTopic.title,
                            "Topic Type": "Content topic"
                        };
                    } else {
                        rootTopicView = rootTopicView || new TopicPage.RootTopicView({ model: rootPageTopic, viewCount: 0 });
                        analyticsParams = {
                            "Topic Title": rootPageTopic.title,
                            "Topic Type": "Supertopic"
                        };
                    }
                    rootTopicView.show();
                    analyticsParams["Topic View Count"] = rootTopicView.options.viewCount;
                }

                Analytics.trackSingleEvent("Topic Page View", analyticsParams);

                $(".topic-page-content .nav-pane")
                    .find("li.selected")
                        .removeClass("selected")
                        .end()
                    .find("li[data-id=\"" + selectedTopicID + "\"]")
                        .addClass("selected");

                // Try to retain maximum content pane height
                TopicPage.growContent();
            }
        }),

        ContentTopicView: Backbone.View.extend({
            template: Templates.get("topic.content-topic-videos"),
            initialize: function() {
                this.render();
            },

            render: function() {
                var prerendered = $(".prerendered[data-id=\"" + this.model.id + "\"]");
                if (prerendered.length) {
                    this.setElement(prerendered.get(0));
                } else {
                    // Split topic children into two equal lists
                    var listLength = Math.floor((this.model.children.length+1)/2);
                    var childrenCol1 = this.model.children.slice(0, listLength);
                    var childrenCol2 = this.model.children.slice(listLength);

                    $.each(childrenCol1, function(idx, video) {
                        if (idx < 3) {
                            video.number = idx+1;
                        }
                    });

                    $(this.el).html(this.template({
                        topic: this.model,
                        childrenCol1: childrenCol1,
                        childrenCol2: childrenCol2
                    }));
                }
                VideoControls.initThumbnailHover($(this.el));
            },

            show: function() {
                $(".topic-page-content .content-pane")
                    .children()
                        .detach()
                        .end()
                    .append(this.el);

                this.options.viewCount++;
            }
        }),

        RootTopicView: Backbone.View.extend({
            template: Templates.get("topic.root-topic-view"),
            initialize: function() {
                this.render();
            },

            render: function() {
                var prerendered = $(".prerendered[data-id=\"" + this.model.topic.id + "\"]");
                if (prerendered.length) {
                    this.setElement(prerendered.get(0));
                } else {
                    // Split subtopics into two equal lists
                    var listLength = Math.floor((this.model.subtopics.length+1)/2);
                    var childrenCol1 = this.model.subtopics.slice(0, listLength);
                    var childrenCol2 = this.model.subtopics.slice(listLength);

                    subtopicAddInfo = function(idx, subtopic) {
                        if (idx > 0) {
                            subtopic.notFirst = true;
                        }
                        if (idx < 3) {
                            subtopic.number = idx+1;
                        }
                        subtopic.description_truncate_length = (subtopic.title.length > 28) ? 38 : 68;
                    };
                    $.each(childrenCol1, subtopicAddInfo);
                    $.each(childrenCol2, subtopicAddInfo);
                    $(this.el).html(this.template({topic_info: this.model, subtopicsA : childrenCol1, subtopicsB: childrenCol2 }));
                }
                VideoControls.initThumbnailHover($(this.el));
            },

            show: function() {
                $(".topic-page-content .content-pane")
                    .children()
                        .detach()
                        .end()
                    .append(this.el);

                this.options.viewCount++;
            }
        })
    };
})();
