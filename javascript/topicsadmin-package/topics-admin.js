// Creates & handles events for the topic tree

var debugNodeIDs = false;

var TopicTreeEditor = {

    dynatree: null,
    topicTree: null,
    boundList: [],
    maxProgressLength: 0,
    currentVersion: null,
    versionEditTemplate: Templates.get("topicsadmin.edit-version"),
    searchView: null,

    currentEditor: null,
    itemCopyBuffer: null,

    createEditor: function(kind) {
        if (kind == "Topic") {
            return new TopicTreeEditor.TopicEditor();
        } else if (kind == "Video") {
            return new TopicTreeEditor.VideoEditor();
        } else if (kind == "Exercise") {
            return new TopicTreeEditor.ExerciseEditor();
        } else if (kind == "Url") {
            return new TopicTreeEditor.UrlEditor();
        }
        return null;
    },

    // Initialize the Dynatree view of the given TopicVersion's topic tree.
    init: function(version) {
        this.topicTree = version.getTopicTree();
        this.currentVersion = version;

        // Attach the dynatree widget to an existing <div id="tree"> element
        // and pass the tree options as an argument to the dynatree() function:
        $("#topic_tree").dynatree({
            imagePath: "/images/",

            onActivate: function(node) {
                KAConsole.log("Activated: ", node);

                if (TopicTreeEditor.currentEditor) {
                    TopicTreeEditor.currentEditor.hide();
                    TopicTreeEditor.currentEditor = null;
                }

                if (node.data.kind != "Topic" || node.data.id != "root") {
                    TopicTreeEditor.currentEditor = TopicTreeEditor.createEditor(node.data.kind);
                }

                if (TopicTreeEditor.currentEditor) {
                    TopicTreeEditor.currentEditor.init(node);
                    TopicTreeEditor.currentEditor.show();
                } else {
                    $("#details-view").html("");
                }
            },

            onCreate: function(node, span) {
                if (node.data.kind == "Topic") {
                    $(span).contextMenu({menu: "topic_context_menu"}, function(action, el, pos) {
                        TopicTreeEditor.topicTree.fetchByID(node.data.id, function() {
                            TopicTreeEditor.createEditor(node.data.kind)
                                .init(node)
                                .handleAction(action);
                        });
                    });
                }
                if (_.include(["Video", "Exercise", "Url"], node.data.kind)) {
                    if (node.parent.data.key == "ChangedContent") {
                        var menu_name = "content_change_context_menu"
                    } else {
                        var menu_name = "item_context_menu"
                    }
                    $(span).contextMenu({menu: menu_name}, function(action, el, pos) {
                        TopicTreeEditor.createEditor(node.data.kind)
                            .init(node)
                            .setParentModel(TopicTreeEditor.topicTree.get(node.parent.data.id))
                            .handleAction(action);
                    });
                }
            },

            onExpand: function(flag, node) {
                if (flag) {
                    node.activate();
                }
            },

            onLazyRead: function(node) {
                if (node.data.key == "UnrefContent") {
                    $.ajaxq("topics-admin", {
                        url: "/api/v1/topicversion/" + TopicTreeEditor.currentVersion.get("number") + "/unused_content",
                        success: function(json) {
                            node.removeChildren();

                            childNodes = [];
                            _.each(json, function(item) {
                                var childWrapper = new TopicChild(item);
                                childNodes.push(TopicTreeEditor.createChild(childWrapper));
                            });
                            node.addChild(childNodes);
                        },
                        error: TopicTreeEditor.handleError
                    });
                } else if (node.data.key == "ChangedContent") {
                    $.ajaxq("topics-admin", {
                        url: "/api/v1/topicversion/" + TopicTreeEditor.currentVersion.get("number") + "/changelist",
                        success: function(json) {
                            node.removeChildren();

                            childNodes = [];
                            _.each(json, function(item) {
                                var childWrapper = new TopicChild(item.content);

                                var oldValues = {};
                                _.each(item.content_changes, function(value, key) {
                                    if (_.isArray(item.content[key]) || _.isArray(value)) {
                                        if (item.content[key] && item.content[key].length > 0) {
                                            oldValues[key] = item.content[key];
                                        } else {
                                            oldValues[key] = ["(No old values)"];
                                        }
                                    } else {
                                        if (item.content[key]) {
                                            oldValues[key] = item.content[key];
                                        } else {
                                            oldValues[key] = "NULL";
                                        }
                                    }
                                });
                                childWrapper.model.oldValues = oldValues;
                                childWrapper.model.changeUser = item.last_edited_by;
                            
                                childNodes.push(TopicTreeEditor.createChild(childWrapper));
                            });
                            node.addChild(childNodes);
                        },
                        error: TopicTreeEditor.handleError
                    });
                } else {
                    TopicTreeEditor.topicTree.fetchByID(node.data.id, TopicTreeEditor.refreshTreeNode);
                }
            },

            dnd: {
                onDragStart: function(node) {
                    return TopicTreeEditor.currentVersion.get("edit");
                },

                onDragEnter: function(node, sourceNode) {
                    if (node.data.key == "UnrefContent" ||
                        node.parent.data.key == "UnrefContent" ||
                        node.data.key == "ChangedContent" ||
                        node.parent.data.key == "ChangedContent") {
                        return [];
                    }

                    if (node.data.kind != "Topic") {
                        return ["before", "after"];
                    }

                    return ["over", "before", "after"];
                },
                onDragLeave: function(node, sourceNode) {
                },
                onDragOver: function(node, sourceNode, hitMode) {
                },

                onDrop: function(node, sourceNode, hitMode, ui, draggable) {
                    var oldParent = sourceNode.parent;

                    sourceNode.move(node, hitMode);

                    var newParent = sourceNode.parent;

                    if (oldParent.data.key == "UnrefContent" ||
                        oldParent.data.key == "ChangedContent") {
                        TopicTreeEditor.addItemToTopic(sourceNode.data.kind, sourceNode.data.id, sourceNode.data.title, newParent, TopicTreeEditor.topicTree.get(newParent.data.id), _.indexOf(newParent.childList, sourceNode));
                    } else {
                        var data = {
                            kind: sourceNode.data.kind,
                            id: sourceNode.data.id,
                            new_parent_id: newParent.data.id,
                            new_parent_pos: _.indexOf(newParent.childList, sourceNode)
                        };
                        TopicTreeEditor.moveItem(oldParent.data.id, data);
                    }
                }
            },

            children: [
                {
                    title: "Loading...",
                    key: "Topic/root",
                    id: "root",
                    kind: "Topic",
                    isFolder: true,
                    isLazy: true,
                    icon: "topictree-icon-small.png"
                }, {
                    title: "Unreferenced Content",
                    key: "UnrefContent",
                    id: "",
                    kind: "",
                    isFolder: true,
                    isLazy: true,
                    icon: "topictree-icon-small.png"
                }, {
                    title: "Changed Content",
                    key: "ChangedContent",
                    id: "",
                    kind: "",
                    isFolder: true,
                    isLazy: true,
                    icon: "topictree-icon-small.png"
                }
            ]
        });
        TopicTreeEditor.dynatree = $("#topic_tree").dynatree("getTree");
        $("#topic_tree").bind("mousedown", function(e) { e.preventDefault(); });

        $("#details-view").html("");

        $("#topicversion-editor")
            .html(TopicTreeEditor.versionEditTemplate(_.extend({IS_DEV:window.KA_IS_DEV}, version.toJSON())))
            .delegate( "a.set-default", "click", TopicTreeEditor.setTreeDefault )
            .delegate( "a.show-versions", "click", TopicTreeEditor.showVersionList );

        $("#topicversion-editor").delegate("input[type=\"text\"]", "change", function() {
            if (TopicTreeEditor.currentVersion.get("edit")) {
                var field = $(this).attr("name");
                if (field) {
                    var value = $(this).val();

                    var attrs = {};
                    attrs[field] = value;

                    version.save(attrs);
                }
            }
        });

        $("#topictree-queue-progress-bar").progressbar({ value: 0, disable: true });
        $("#topictree-queue-progress-text").html("");

        if (!this.searchView) {
            this.searchView = new TopicTreeEditor.SearchView();
            $(this.searchView.el).appendTo(document.body);
        }

        var self = this;
        $(window).resize(function() { self.resize(); } );
        this.resize();

        // Get the data for the topic tree (may fire callbacks immediately)

        TopicTreeEditor.topicTree.bind("add", this.treeUpdate, TopicTreeEditor.topicTree);
        TopicTreeEditor.topicTree.bind("remove", this.treeUpdate, TopicTreeEditor.topicTree);
        TopicTreeEditor.topicTree.bind("clear", this.treeUpdate, TopicTreeEditor.topicTree);

        var root = TopicTreeEditor.topicTree.getRoot();
        root.bind("change", this.refreshTreeNode);
        if (root.__inited) {
            this.refreshTreeNode.call(null, root);
        }

        this.updateProgressBar();
    },

    updateProgressBar: function() {
        if (document.ajaxq && document.ajaxq.q["topics-admin"] &&
            document.ajaxq.q["topics-admin"].length > 0) {
            $("#topictree-queue-progress-bar").progressbar("enable");

            var remaining = document.ajaxq.q["topics-admin"].length;
            if (TopicTreeEditor.maxProgressLength < remaining) {
                TopicTreeEditor.maxProgressLength = remaining;
            }

            var progress_percentage = (1 - (remaining / TopicTreeEditor.maxProgressLength)) * 100;
            var progress = TopicTreeEditor.maxProgressLength - remaining + 1;

            $("#topictree-queue-progress-bar").progressbar("value", progress_percentage);
            $("#topictree-queue-progress-text").html("Updating (" + progress + " / " + TopicTreeEditor.maxProgressLength + ")");

        } else {
            if (TopicTreeEditor.maxProgressLength > 0) {
                $("#topictree-queue-progress-text").html("Done updating.");
                $("#topictree-queue-progress-bar").progressbar("value", 100);
                TopicTreeEditor.maxProgressLength = 0; // 1 second delay before we wipe the progress
            } else {
                $("#topictree-queue-progress-bar").progressbar({ value: 0, disable: true });
            }
        }

        setTimeout(TopicTreeEditor.updateProgressBar, 1000);
    },

    resize: function() {
        var containerHeight = $(window).height();
        var yTopPadding = $("#topic_tree").offset().top;
        var newHeight = containerHeight - (yTopPadding + 42);

        $("#topic_tree").height(newHeight);
        $("#details-view").height(newHeight);

        $(this.searchView.el).offset($("#topic_tree").offset());
    },

    createChild: function(child) {
        var iconTable = {
            Topic: "leaf-icon-small.png",
            Video: "video-camera-icon-full-small.png",
            Exercise: "exercise-icon-small.png",
            Url: "link-icon-small.png"
        };
        var data = {
            title: child.title,
            key:  child.kind + "/" + child.id,
            id: child.id,
            kind: child.kind,
            icon: iconTable[child.kind],
            oldValues: child.model ? child.model.oldValues : null
        };
        if (debugNodeIDs) {
            data.title += " [(" + child.id + ")]";
        }
        if (child.model && child.model.changeUser) {
            data.title += " (by " + child.model.changeUser + ")";
        }
        if (child.kind === "Topic") {
            data.isFolder = true;
            data.isLazy = true;
            if (child.hide) {
                data.addClass = "hidden-topic";
                data.title = child.title + " [Hidden]";
            }
        }
        data.original = child;
        return data;
    },

    refreshTreeNode: function(model) {
        node = TopicTreeEditor.dynatree.getNodeByKey(model.get("kind") + "/" + model.id);
        if (!node) {
            return;
        }

        var newData = model.toJSON();

        if (_.isEqual(newData, node.data.original)) {
            KAConsole.log("Model " + model.id + " has not changed. Not refreshing.");
            return;
        }

        KAConsole.log("Refreshing " + model.id);

        node.data = TopicTreeEditor.createChild(newData);
        node.render();

        // Update the parent so we don't unnecessarily refresh all the sibling nodes
        if (model.id != "root") {
            var parentOriginalChild = _.find(node.parent.data.original.children, function(child) {
                if (child.id == model.id)
                    return child;
                return null;
            });
            parentOriginalChild.title = model.get("title");
            parentOriginalChild.hide = model.get("hide");
        }

        node.removeChildren();
        if (model.get("children")) {
            childNodes = [];
            _.each(model.get("children"), function(child) {
                childNodes.push(TopicTreeEditor.createChild(child));
            });
            node.addChild(childNodes);
        }

        if (model.id == "root") {
            node.expand();
        }
    },

    handleChange: function(model, oldID) {
        var modelWrapper = new TopicChild(model);

        KAConsole.log("Model of type " + modelWrapper.kind + " changed ID: " + oldID + " -> " + model.id);

        TopicTreeEditor.topicTree.each(function(topic) {
            var found = false;
            var children = _.map(topic.get("children"), function(child) {
                if (child.kind == modelWrapper.kind && child.id == oldID) {
                    var new_child = {
                        id: model.id,
                        kind: modelWrapper.kind,
                        title: modelWrapper.title,
                        hide: child.hide
                    };

                    found = true;

                    return new_child;
                } else {
                    return child;
                }
            });
            if (found) {
                topic.set({children: children});
            }
        });
    },

    // Called with TopicTree as "this"
    treeUpdate: function() {
        this.each(function(childModel) {
            var found = false;
            _.each(TopicTreeEditor.boundList, function(childId) {
                if (childId == childModel.id) {
                    found = true;
                }
            });
            if (!found) {
                //KAConsole.log("Binding: " + childModel.id);
                childModel.bind("change", TopicTreeEditor.refreshTreeNode);
                TopicTreeEditor.boundList.push(childModel.id);
            }
        });
    },

    setTreeDefault: function() {
        var confirmationMessage = {
                buttons: [
                    { title: "Yes", action: TopicTreeEditor.doSetTreeDefault },
                    { title: "No", action: hideGenericMessageBox }
                ]};

        if (window.KA_IS_DEV) {
            // local edits are not as worrysome
            $.extend(confirmationMessage, {
                title: "Commit local topic tree?",
                message: "Clicking 'yes' here will only publish your changes locally. If you'd like to push your changes to the site, export this tree and import it on khanacademy.org.",
            });
        } else {
            // edits on appspot actually, you know, matter
            $.extend(confirmationMessage, {
                title: "Publish this Topic Tree?",
                message: "Marking this version of the topic tree default will publish all changes to the live version of the website. Are you sure?",
            });
        }
        popupGenericMessageBox(confirmationMessage);
    },

    doSetTreeDefault: function() {
        hideGenericMessageBox();
        popupGenericMessageBox({
            title: "Publishing topic tree",
            message: "Publishing topic tree. Please wait...",
            buttons: []
        });
        $.ajaxq("topics-admin", {
            url: "/api/v1/topicversion/edit/setdefault",
            success: function() {
                hideGenericMessageBox();
                popupGenericMessageBox({
                    title: "Topic tree publish begun",
                    message: "Topic tree publish is now in progress. This may take a few minutes...",
                    buttons: []
                });
                setTimeout(TopicTreeEditor.waitForTreeDefault, 15000);
            },
            error: TopicTreeEditor.handleError
        });
    },

    waitForTreeDefault: function() {
        $.ajax({
            url: "/api/v1/dev/task_message",
            success: function(message) {
                if (message != "Publish: finished successfully") {
                    hideGenericMessageBox();
                    popupGenericMessageBox({
                        title: "Topic tree publish begun",
                        message: "Topic tree publish is now in progress. This may take a few minutes...<br/>Current Status - " + message,
                        buttons: []
                    });
                    setTimeout(TopicTreeEditor.waitForTreeDefault, 15000);
                } else {
                    hideGenericMessageBox();
                    popupGenericMessageBox({
                        title: "Topic tree publish complete",
                        message: "Topic tree has been published to the live site. The page will now refresh.",
                        buttons: [
                            { title: "OK", action: function() { location.reload(true); } }
                        ]
                    });
                }
            },
            error: function() {
                setTimeout(TopicTreeEditor.waitForTreeDefault, 15000);
            }
        });
    },

    showVersionList: function() {
        TopicTreeEditor.versionListView = new TopicTreeEditor.VersionListView().show();
    },

    editVersion: function(versionNumber) {
        if (TopicTreeEditor.versionListView) {
            TopicTreeEditor.versionListView.hide();
        }

        version = getTopicVersionList().get(versionNumber);
        if (version) {
            version.getTopicTree().reset();
            TopicTreeEditor.init(version);
        }
    },

    handleError: function(xhr, queryObject) {
        popupGenericMessageBox({
            title: "Server error",
            message: "There has been a server error:<br /><span style=\"color: #900;\">" + (queryObject.responseText? queryObject.responseText : xhr.responseText) + "</span><br />The topic tree will now refresh.",
            buttons: [
                { title: "OK", action: function() { hideGenericMessageBox(); TopicTreeEditor.editVersion(TopicTreeEditor.currentVersion.get("number")); } }
            ]
        });
    },

    addItemToTopic: function(kind, id, title, parent_node, parent_model, parent_pos) {

        if (parent_pos < 0) {
            parent_pos = parent_model.get("children").length;
        }

        KAConsole.log("Adding " + kind + " " + id + " to Topic " + parent_model.get("title"));

        var newChild = {
            kind: kind,
            id: id,
            title: title
        };
        children = parent_model.get("children").slice(0);
        children.splice(parent_pos, 0, newChild);
        parent_model.set({ children: children });

        parent_node.reloadChildren();
        parent_node.getChildren()[parent_pos].activate();

        var data = {
            kind: kind,
            id: id,
            pos: parent_pos
        };
        $.ajaxq("topics-admin", {
            url: "/api/v1/topicversion/edit/topic/" + parent_model.id + "/addchild",
            type: "POST",
            data: data,
            success: function(json) {
                KAConsole.log("Added item successfully.");
            },
            error: TopicTreeEditor.handleError
        });
    },

    moveItem: function(oldParentID, moveData) {
        // Apply the change to the model data first
        var old_parent = TopicTreeEditor.topicTree.get(oldParentID)
        var child = old_parent.removeChild(moveData.kind, moveData.id);
        TopicTreeEditor.refreshTreeNode(old_parent)
        var new_parent = TopicTreeEditor.topicTree.fetchByID(moveData.new_parent_id, function(model) {
            model.addChild(child, moveData.new_parent_pos);

            var parent_node = TopicTreeEditor.dynatree.getNodeByKey("Topic/" + moveData.new_parent_id);
            parent_node.expand();
            parent_node.reloadChildren();
            parent_node.getChildren()[moveData.new_parent_pos].activate();

            $.ajaxq("topics-admin", {
                url: "/api/v1/topic/" + oldParentID + "/movechild",
                type: "POST",
                data: moveData,
                success: function() {
                },
                error: TopicTreeEditor.handleError
            });
        });
    },

    ungroupTopic: function(node, topic) {
        var children = topic.get("children");
        var new_parent = TopicTreeEditor.topicTree.fetchByID(node.parent.data.id, function(model) {
            var child_list = model.get("children").slice(0);
            var child_index = _.indexOf(child_list, _.find(child_list, function(child) { return child.id === topic.id; }));

            splice_args = [child_index, 1].concat(children);
            [].splice.apply(child_list, splice_args);

            model.set({"children": child_list});

            $.ajaxq("topics-admin", {
                url: "/api/v1/topic/" + topic.id + "/ungroup",
                type: "POST",
                success: function() {
                },
                error: TopicTreeEditor.handleError
            });
        });
    }
};

// Utility function for comparing arrays of strings only (type coercion/null/undefined values are not relevant)
function stringArraysEqual(ar1, ar2) {
    return !(ar1 < ar2 || ar1 > ar2);
}

// Details view common code

(function(editor) {
    editor.NodeEditor = function(node) {
        this.node = null;
        this.model = null;
        this.parentModel = null;
        this.modelKind = null;
        this.template = null;
        this.visible = false;
        this.el = null;
    };

    editor.NodeEditor.prototype.init = function(node) {
        this.node = node;
        _.bindAll(this, "modelLoaded", "handleChange", "render", "deleteTag");
        return this;
    };

    editor.NodeEditor.prototype.setParentModel = function(parentModel) {
        this.parentModel = parentModel;
        return this;
    };

    editor.NodeEditor.prototype.show = function() {
        if (!this.visible) {
            this.visible = true;
            this.render();

            if (this.model) {
                this.model.bind("change", this.render);
            }
        }
    };

    editor.NodeEditor.prototype.hide = function() {
        if (this.model) {
            this.model.unbind("change", this.render);
        }
        this.visible = false;
    };

    editor.NodeEditor.prototype.modelLoaded = function(model) {
        this.modelKind = model.get('kind');
        this.model = model;
        this.parentModel = editor.topicTree.get(this.node.parent.data.id);
        this.template = Templates.get("topicsadmin.edit-" + model.get('kind').toLowerCase());

        if (this.visible) {
            this.render();
            this.model.bind("change", this.render);
        }

        return this;
    };

    editor.NodeEditor.prototype.render = function() {
        var self = this;

        if (this.model) {
            js = this.model.toJSON();
            oldValues = this.node.data.oldValues || {};

            html = this.template({version: editor.currentVersion.toJSON(), model: js, oldValues: oldValues});

            this.el = $("#details-view")
                .html(html)
                .find("input, textarea")
                    .change(this.handleChange)
                    .end()
                .find("a.item-action")
                    .click(function() { self.handleAction($(this).attr("data-id")); })
                    .end()
                .find(".character-count")
                    .each(function() {
                        var counter = this;
                        var suffix = $(counter).html();
                        var params = $(counter).attr("data-id").split(" ");
                        var maxLength = -1;
                        if (params.length > 1) {
                            maxLength = params[1];
                        }

                        var keyUpFn = function() {
                            var cnt = $(this).val().length;
                            $(counter).html(cnt + suffix);
                            $(counter).toggleClass("character-count-over", (cnt > maxLength));
                        };

                        $("#details-view").find(params[0])
                            .bind("keyup", keyUpFn)
                            .each(keyUpFn);
                    })
                    .end();
        } else {
            this.el = $("#details-view")
                .html("<div style=\"left: 350px; position: relative; width: 10px;\"><div class=\"dialog-progress-bar\"></div></div>")
                .find(".dialog-progress-bar")
                    .progressbar({ enable: true, value: 100 })
                    .end();
        }
    };

    editor.NodeEditor.prototype.handleChange = function() {
        var self = this;
        unsavedChanges = this.hasUnsavedChanges();
        $("input[type=\"text\"]", this.el)
            .add("input[type=\"radio\"]:checked", this.el)
            .add("input[type=\"checkbox\"]", this.el)
            .add("textarea", this.el)
            .each(function() {
                var field = $(this).attr("name");
                if (field) {
                    var value = ( this.type == "checkbox" ) ?  $( this ).is( ":checked" ) : $( this ).val();
                    if (String(self.model.get(field)) != String(value)) {
                        unsavedChanges = true;
                    }
                }
            });
        if (unsavedChanges) {
            $(".save-button", this.el).removeClass("disabled").addClass("green");
        } else {
            $(".save-button", this.el).addClass("disabled").removeClass("green");
        }
    };

    editor.NodeEditor.prototype.hasUnsavedChanges = function() {
        return this.tags && !stringArraysEqual(this.tags, this.model.get("tags"));
    };

    editor.NodeEditor.prototype.serializeChanges = function(attrs) {
        if (this.tags && !stringArraysEqual(this.tags, this.model.get("tags"))) {
            attrs.tags = this.tags;
        }
    };
    
    editor.NodeEditor.prototype.updateTags = function() {
        var self = this;
        var elements = [];
        _.each( this.tags, function( tag ) {
            elements.push(
                $("<div>" + tag + " <a href=\"javascript:\">(remove)</a></div>")
                    .delegate( "a", "click", function() { self.deleteTag(tag); } )
            );
        });
        $(".tags-list", this.el).children().remove();
        _.each( elements, function( element ) { element.appendTo(".tags-list", this.el); } );
    };

    editor.NodeEditor.prototype.deleteTag = function(tag) {
        var idx = _.indexOf(this.tags, tag);
        if (idx >= 0) {
            this.tags.splice(idx, 1);
            this.updateTags();
            this.handleChange();
        }
    };

    editor.NodeEditor.prototype.handleAction = function(action) {
        var self = this;

        if (action == "save") {
            var attrs = {};
            $("input[type=\"text\"]", this.el)
                .add("input[type=\"radio\"]:checked", this.el)
                .add("input[type=\"checkbox\"]", this.el)
                .add("textarea")
                .each(function() {
                    var field = $(this).attr("name");
                    if (field) {
                        var value = ( this.type == "checkbox" ) ?  $( this ).is( ":checked" ) : $( this ).val();
                        if (String(self.model.get(field)) != String(value)) {
                            attrs[field] = value;
                        }
                    }
                });
            this.serializeChanges(attrs);

            if (attrs != {}) {
                Throbber.show($(".save-button", this.el), true);

                // We do special things on save because of the potential ID change
                var oldID = this.model.id;
                this.model.save(attrs, {
                    url: self.model.url(), // URL with the old slug value
                    success: function() {
                        editor.handleChange(self.model, oldID);
                        Throbber.hide();
                    },
                    error: TopicTreeEditor.handleError
                });
            }
        } else if (action == "add-tag") {
            var tag = escape($(".add-tag", this.el).val());
            var idx = _.indexOf(this.tags, tag);
            if (tag && idx < 0) {
                this.tags.push(tag);
                this.updateTags();
                this.handleChange();
            }

            $(".add-tag", this.el).val("");
        }
    };

})(TopicTreeEditor);

// Details view & editing functions for topics

(function(editor) {
    editor.TopicEditor = function() {
        this.existingItemView = null;
        this.newExerciseView = null;
        this.newVideoView = null;
        this.newUrlView = null;
        this.importView = null;
        this.exportView = null;
        this.contextNode = null;
        this.contextModel = null;
        this.itemCopyBuffer = null;
    };

    editor.TopicEditor.prototype = new TopicTreeEditor.NodeEditor();

    editor.TopicEditor.prototype.init = function(node) {
        editor.NodeEditor.prototype.init.call(this, node);

        editor.topicTree.fetchByID(this.node.data.id, this.modelLoaded);
        return this;
    };

    editor.TopicEditor.prototype.render = function() {
        editor.NodeEditor.prototype.render.call(this);

        if (this.model) {
            this.tags = this.model.get("tags").slice(0);
            this.updateTags();
        }

        if (!TopicTreeEditor.currentVersion.get("edit")) {
            $("input", this.el).attr("disabled", "disabled");
        }

    };

    editor.TopicEditor.prototype.handleAction = function(action) {
        var self = this;

        if (!TopicTreeEditor.currentVersion.get("edit"))
            return;

        if (action == "add_new_topic") {
            var topic = new Topic();
            KAConsole.log("Creating new topic...");
            topic.save({}, {
                success: function() {
                    KAConsole.log("Created new topic:", topic.id);
                    var data = {
                        kind: "Topic",
                        id: topic.id,
                        pos: self.model.get("children").length
                    };
                    $.ajaxq("topics-admin", {
                        url: "/api/v1/topicversion/edit/topic/" + self.model.id + "/addchild",
                        type: "POST",
                        data: data,
                        success: function(json) {
                            KAConsole.log("Added topic successfully.");
                            self.model.set(json);

                            self.node.expand();
                            self.node.reloadChildren()
                            self.node.getChildren()[data.pos].activate();
                        },
                        error: TopicTreeEditor.handleError
                    });
                }
            });

        } else if (action == "add_new_video") {
            this.newVideoView = this.newVideoView || new TopicTreeEditor.CreateVideoView();
            this.newVideoView.show(this.node, this.model);

        } else if (action == "add_existing_video") {
            this.existingItemView = this.existingItemView || new TopicTreeEditor.AddExistingItemView();
            this.existingItemView.show("video", editor.addItemToTopic, this.node, this.model);

        } else if (action == "add_new_exercise") {
            this.newExerciseView = this.newExerciseView || new TopicTreeEditor.CreateExerciseView();
            this.newExerciseView.show(this.node, this.model);

        } else if (action == "add_existing_exercise") {
            this.existingItemView = this.existingItemView || new TopicTreeEditor.AddExistingItemView();
            this.existingItemView.show("exercise", editor.addItemToTopic, this.node, this.model);

        } else if (action == "add_new_url") {
            this.newUrlView = this.newUrlView || new TopicTreeEditor.CreateUrlView();
            this.newUrlView.show(this.node, this.model);

        } else if (action == "export_topic") {
            this.exportView = this.exportView || new TopicTreeEditor.ImportExportView({ import: false });
            this.exportView.show(this.model.id);

        } else if (action == "import_topic") {
            this.importView = this.importView || new TopicTreeEditor.ImportExportView({ import: true });
            this.importView.show(this.model.id);

        } else if (action == "ungroup_topic") {
            var self = this;
            popupGenericMessageBox({
                title: "Confirm ungroup topic",
                message: "Ungrouping this topic will delete it and move all its children to the parent topic. Are you sure?",
                buttons: [
                    { title: "Yes", action: function() { TopicTreeEditor.ungroupTopic(self.node, self.model); hideGenericMessageBox(); } },
                    { title: "No", action: hideGenericMessageBox }
                ]
            });

        } else if (action == "paste_item") {

            if (!editor.itemCopyBuffer) {
                return;
            }

            if (editor.itemCopyBuffer.type == "copy") {
                editor.addItemToTopic(editor.itemCopyBuffer.kind, editor.itemCopyBuffer.id, editor.itemCopyBuffer.title, this.node, this.model, -1);

            } else if (editor.itemCopyBuffer.type == "cut") {
                var moveData = {
                    kind: editor.itemCopyBuffer.kind,
                    id: editor.itemCopyBuffer.id,
                    new_parent_id: self.model.id,
                    new_parent_pos: self.model.get("children").length
                };
                TopicTreeEditor.moveItem(editor.itemCopyBuffer.originalParent, moveData);
            }

        } else if (action == "delete_topic") {
            var deleteData = {
                kind: "Topic",
                id: self.model.id
            };
            $.ajaxq("topics-admin", {
                url: "/api/v1/topic/" + self.parentModel.id + "/deletechild",
                type: "POST",
                data: deleteData,
                success: function(json) {
                    self.parentModel.removeChild("Topic", self.model.id);
                    TopicTreeEditor.refreshTreeNode(self.parentModel)
                },
                error: TopicTreeEditor.handleError
            });
        } else {
            editor.NodeEditor.prototype.handleAction.call(this, action);
        }
    };

})(TopicTreeEditor);

// Details view common code for videos/exercises

(function(editor) {
    editor.ItemEditor = function() {
    };

    editor.ItemEditor.prototype = new TopicTreeEditor.NodeEditor();

    editor.ItemEditor.prototype.handleAction = function(action) {
        var self = this;

        if (!TopicTreeEditor.currentVersion.get("edit")) {
            editor.NodeEditor.prototype.handleAction.call(this, action);
            return;
        }

        if (action == "copy_item") {
            editor.itemCopyBuffer = {
                type: "copy",
                kind: this.node.data.kind,
                id: this.node.data.id,
                title: this.node.data.title,
                originalParent: this.parentModel.id
            };

        } else if (action == "cut_item") {
            editor.itemCopyBuffer = {
                type: "cut",
                kind: this.node.data.kind,
                id: this.node.data.id,
                title: this.node.data.title,
                originalParent: this.parentModel.id,
                originalPosition: _.indexOf(this.node.parent.childList, this.node)
            };

        } else if (action == "paste_after_item") {

            var new_position = _.indexOf(this.node.parent.childList, this.node) + 1;

            if (!editor.itemCopyBuffer) {
                return;
            }

            if (editor.itemCopyBuffer.type == "copy") {
                if (this.parentModel.id == editor.itemCopyBuffer.originalParent) {
                    return;
                }

                editor.addItemToTopic(editor.itemCopyBuffer.kind, editor.itemCopyBuffer.id, editor.itemCopyBuffer.title, this.node.parent, this.parentModel, new_position);

            } else if (editor.itemCopyBuffer.type == "cut") {
                if (this.parentModel.id == editor.itemCopyBuffer.originalParent &&
                    new_position > editor.itemCopyBuffer.originalPosition) {
                    new_position--;
                }

                var moveData = {
                    kind: editor.itemCopyBuffer.kind,
                    id: editor.itemCopyBuffer.id,
                    new_parent_id: this.parentModel.id,
                    new_parent_pos: new_position
                };
                editor.moveItem(editor.itemCopyBuffer.originalParent, moveData);
            }

        } else if (action == "remove_item") {
            var deleteData = {
                kind: this.node.data.kind,
                id: this.node.data.id
            };
            $.ajaxq("topics-admin", {
                url: "/api/v1/topic/" + this.parentModel.id + "/deletechild",
                type: "POST",
                data: deleteData,
                success: function(json) {
                    self.parentModel.removeChild(self.node.data.kind, self.node.data.id);
                    TopicTreeEditor.refreshTreeNode(self.parentModel)
                },
                error: TopicTreeEditor.handleError
            });
        } else if (action == "undo_changes") {
            var deleteData = {
                kind: this.node.data.kind,
                id: this.node.data.id
            };               
            $.ajaxq("topics-admin", {
                url: "/api/v1/topicversion/edit/deletechange",
                type: "POST",
                data: deleteData,
                success: function(json) {
                    self.node.parent.removeChild(self.node);
                },
                error: TopicTreeEditor.handleError
            });
        } else {
            editor.NodeEditor.prototype.handleAction.call(this, action);
        }
    };

})(TopicTreeEditor);

// Details view for exercises

(function(editor) {
    editor.ExerciseEditor = function() {
        this.existingItemView = null;
        this.covers = null;
        this.prereqs = null;
        this.videos = null;
    };

    editor.ExerciseEditor.prototype = new TopicTreeEditor.ItemEditor();

    editor.ExerciseEditor.prototype.init = function(node) {
        editor.ItemEditor.prototype.init.call(this, node);
        _.bindAll(this, "addCover", "deleteCover", "addPrereq", "deletePrereq", "addVideo", "deleteVideo");

        getExerciseList().fetchByID(node.data.id, this.modelLoaded);

        return this;
    };

    editor.ExerciseEditor.prototype.render = function() {
        editor.ItemEditor.prototype.render.call(this);

        if (this.model) {
            this.tags = this.model.get("tags").slice(0);
            this.updateTags();

            this.prereqs = this.model.get("prerequisites").slice(0);
            this.updatePrereqs();

            this.covers = this.model.get("covers").slice(0);
            this.updateCovers();

            this.videos = (this.model.get("related_video_readable_ids") || []).slice(0);
            this.updateVideos();
        }
    };

    editor.ExerciseEditor.prototype.hasUnsavedChanges = function()  {
        var ret = editor.ItemEditor.prototype.hasUnsavedChanges.call(this);
        return ret || !(
            stringArraysEqual(this.prereqs, this.model.get("prerequisites")) &&
            stringArraysEqual(this.covers, this.model.get("covers")) &&
            stringArraysEqual(this.videos, this.model.get("related_video_readable_ids"))
        );
    };

    editor.ExerciseEditor.prototype.serializeChanges = function(attrs) {
        editor.ItemEditor.prototype.serializeChanges.call(this, attrs);

        if (this.prereqs && !stringArraysEqual(this.prereqs, this.model.get("prerequisites"))) {
            attrs.prerequisites = this.prereqs;
        }

        if (this.covers && !stringArraysEqual(this.covers, this.model.get("covers"))) {
            attrs.covers = this.covers;
        }

        if (this.videos && !stringArraysEqual(this.videos, this.model.get("related_video_readable_ids"))) {
            attrs.related_video_readable_ids = this.videos;
        }
    };

    editor.ExerciseEditor.prototype.updateCovers = function() {
        var self = this;
        var elements = [];
        _.each(this.covers, function(cover) {
            elements.push(
                $("<div>" + cover + " <a href=\"javascript:\">(remove)</a></div>")
                    .delegate("a", "click", function() { self.deleteCover(cover); })
            );
        });
        $(".exercise-covers-list", this.el).children().remove();
        _.each(elements, function(element) { element.appendTo(".exercise-covers-list", this.el); });
    };
    editor.ExerciseEditor.prototype.addCover = function(kind, id, title) {
        if (id) {
            this.covers.push(id);
            this.updateCovers();
            this.handleChange();
        }
    };
    editor.ExerciseEditor.prototype.deleteCover = function(cover) {
        var idx = _.indexOf(this.covers, cover);
        if (idx >= 0) {
            this.covers.splice(idx, 1);
            this.updateCovers();
            this.handleChange();
        }
    };

    editor.ExerciseEditor.prototype.updatePrereqs = function() {
        var self = this;
        var elements = [];
        _.each(this.prereqs, function(prereq) {
            elements.push(
                $("<div>" + prereq + " <a href=\"javascript:\">(remove)</a></div>")
                    .delegate("a", "click", function() { self.deletePrereq(prereq); })
            );
        });
        $(".exercise-prereqs-list", this.el).children().remove();
        _.each(elements, function(element) { element.appendTo(".exercise-prereqs-list", this.el); });
    };
    editor.ExerciseEditor.prototype.addPrereq = function(kind, id, title) {
        if (id) {
            this.prereqs.push(id);
            this.updatePrereqs();
            this.handleChange();
        }
    };
    editor.ExerciseEditor.prototype.deletePrereq = function(prereq) {
        var idx = _.indexOf(this.prereqs, prereq);
        if (idx >= 0) {
            this.prereqs.splice(idx, 1);
            this.updatePrereqs();
            this.handleChange();
        }
    };

    editor.ExerciseEditor.prototype.updateVideos = function() {
        var self = this;
        var elements = [];
        _.each(this.videos, function(video) {
            elements.push(
                $("<div id='related-video-" + video + "'>" + video + " <a href=\"javascript:\">(remove)</a></div>")
                    .delegate("a", "click", function() { self.deleteVideo(video); })
            );
        });
        $(".exercise-videos-list", this.el).children().remove();
        _.each(elements, function(element) { element.appendTo(".exercise-videos-list", this.el); });
        $(".exercise-videos-list", this.el).sortable({
            update: $.proxy(function(event, ui) {
                this.videos = $(".exercise-videos-list", this.el)
                    .sortable("toArray").map(function(id){
                        return id.substring(14);
                    })
            }, this)   
        })
    };
    editor.ExerciseEditor.prototype.addVideo = function(kind, id, title) {
        if (id) {
            this.videos.push(id);
            this.updateVideos();
            this.handleChange();
        }
    };
    editor.ExerciseEditor.prototype.deleteVideo = function(video) {
        var idx = _.indexOf(this.videos, video);
        if (idx >= 0) {
            this.videos.splice(idx, 1);
            this.updateVideos();
            this.handleChange();
        }
    };

    editor.ExerciseEditor.prototype.handleAction = function(action) {
        if (action == "add-prereq") {
            this.existingItemView = this.existingItemView || new TopicTreeEditor.AddExistingItemView();
            this.existingItemView.show("exercise", this.addPrereq);

        } else if (action == "add-cover") {
            this.existingItemView = this.existingItemView || new TopicTreeEditor.AddExistingItemView();
            this.existingItemView.show("exercise", this.addCover);

        } else if (action == "add-video") {
            this.existingItemView = this.existingItemView || new TopicTreeEditor.AddExistingItemView();
            this.existingItemView.show("video", this.addVideo);

        } else {
            editor.ItemEditor.prototype.handleAction.call(this, action);
        }
    };

})(TopicTreeEditor);


// Details view for videos

(function(editor) {
    editor.VideoEditor = function() {
    };

    editor.VideoEditor.prototype = new TopicTreeEditor.ItemEditor();

    editor.VideoEditor.prototype.init = function(node) {
        editor.ItemEditor.prototype.init.call(this, node);

        getVideoList().fetchByID(node.data.id, this.modelLoaded);

        return this;
    };

})(TopicTreeEditor);

// Details view for external links

(function(editor) {
    editor.UrlEditor = function() {
    };

    editor.UrlEditor.prototype = new TopicTreeEditor.ItemEditor();

    editor.UrlEditor.prototype.init = function(node) {
        editor.ItemEditor.prototype.init.call(this, node);

        getUrlList().fetchByID(node.data.id, this.modelLoaded);

        return this;
    };

    editor.UrlEditor.prototype.render = function() {
        editor.ItemEditor.prototype.render.call(this);

        if (this.model) {
            this.tags = this.model.get("tags").slice(0);
            this.updateTags();
        }
    };

})(TopicTreeEditor);

// Add existing video/exercise dialog box

TopicTreeEditor.AddExistingItemView = Backbone.View.extend({
    template: Templates.get("topicsadmin.add-existing-item"),
    loaded: false,
    type: "",
    results: {},
    callback: null,
    contextNode: null,
    contextModel: null,

    initialize: function() {
        _.bindAll(this, "showResults");
        this.render();
    },

    events: {
        "click .do-search": "doSearch",
        "click .show-recent": "showRecent",
        "click .ok-button": "selectItem"
    },

    render: function() {
        var el = $(this.template({type: this.type})).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function(type, callback, node, model) {
        $(this.el).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        if (type != this.type) {
            this.loaded = false;
        }
        this.type = type;
        this.callback = callback;
        this.contextNode = node;
        this.contextModel = model;

        $(this.el).find(".title").html("Choose " + type + ":");

        if (!this.loaded) {
            this.showRecent();
        }
    },

    showResults: function(json) {
        var elements = [];
        var self = this;
        this.results = {};
        _.each(json, function(item) {
            if (self.type == "video") {
                elements.push($('<option value="' + item.id + '">' + item.title + '</option>'));
                self.results[item.id] = item.title;
            } else {
                elements.push($('<option value="' + item.name + '">' + item.display_name + '</option>'));
                self.results[item.name] = item.display_name;
            }
        });

        var resultsElement = $("select.search-results", this.el);
        resultsElement.html("");
        _.each(elements, function(element) { element.appendTo(resultsElement.get(0)); });
    },

    showRecent: function() {
        var self = this;

        if (this.type == "video") {
            $(this.el).find(".search-description").html("Most recent videos:");
        } else {
            $(this.el).find(".search-description").html("Most recent exercises:");
        }
        self.showResults([{
            readable_id: "_",
            name: "_",
            title: "Loading...",
            display_name: "Loading..."
        }]);

        var url;
        if (this.type == "video") {
            url = "/api/v1/videos/recent";
        } else {
            url = "/api/v1/exercises/recent";
        }
        $.ajax({
            url: url,

            success: function(json) {
                self.loaded = true;
                self.showResults(json);
            }
        });
    },

    doSearch: function() {
        var searchText = $(this.el).find("input[name=\"item-search\"]").val();
        var self = this;

        if (this.type == "video") {
            $(this.el).find(".search-description").html("Videos matching \"" + searchText + "\":");
        } else {
            $(this.el).find(".search-description").html("Exercises matching \"" + searchText + "\":");
        }
        self.showResults([{
            readable_id: "",
            name: "",
            title: "Loading...",
            display_name: "Loading..."
        }]);

        $.ajax({
            url: "/api/v1/autocomplete?q=" + encodeURIComponent(searchText),

            success: function(json) {
                self.loaded = true;
                if (self.type == "video") {
                    self.showResults(json.videos);
                } else {
                    self.showResults(json.exercises);
                }
            }
        });
    },

    selectItem: function() {
        var itemID = $(this.el).find("select.search-results option:selected").val();
        if (!itemID || itemID === "_") {
            return;
        }

        this.hide();

        var kind;
        if (this.type == "video") {
            kind = "Video";
        } else {
            kind = "Exercise";
        }

        this.callback(kind, itemID, this.results[itemID], this.contextNode, this.contextModel, -1);
    },

    hide: function() {
        return $(this.el).modal("hide");
    }
});

// Add a new exercise dialog box

TopicTreeEditor.CreateExerciseView = Backbone.View.extend({
    template: Templates.get("topicsadmin.create-exercise"),
    contextNode: null,
    contextModel: null,

    initialize: function() {
        this.render();
    },

    events: {
        "click .ok-button": "createExercise"
    },

    render: function() {
        var el = $( this.template( {type: this.type} ) ).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function(node, model) {
        $(this.el).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        this.contextNode = node;
        this.contextModel = model;
    },

    createExercise: function() {
        var self = this;
        var name = $(this.el).find("input[name=\"name\"]").val();
        var exercise = new Exercise({ name: name });

        exercise.save({}, {
            success: function() {
                TopicTreeEditor.addItemToTopic("Exercise", name, exercise.get("display_name"), self.contextNode, self.contextModel, -1);
            }
        });
        this.hide();
    },

    hide: function() {
        return $(this.el).modal("hide");
    }
});

// Add a new video dialog box

TopicTreeEditor.CreateVideoView = Backbone.View.extend({
    template: Templates.get( "topicsadmin.create-video" ),
    previewTemplate: Templates.get( "topicsadmin.create-video-preview" ),
    contextNode: null,
    contextModel: null,

    youtubeID: null,
    readableID: null,
    title: null,

    initialize: function() {
        _.bindAll(this, "doVideoSearch", "queueVideoSearch");
        this.render();
    },

    events: {
        "click .ok-button": "createVideo",
        "change input[name=\"youtube_id\"]": "doVideoSearch",
        "keydown input[name=\"youtube_id\"]": "queueVideoSearch"
    },

    render: function() {
        var el = $(this.template({type: this.type})).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function(node, model) {
        this.contextNode = node;
        this.contextModel = model;

        $(this.el).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        this.youtubeID = null;
        $(this.el).find("input[name=\"youtube_id\"]").val("");
        $(this.el).find(".create-video-preview").html("Enter a YouTube ID to look up a video.");
        $(self.el).find(".ok-button").addClass("disabled").removeClass("green");
    },

    createVideo: function() {
        var self = this;

        if (this.readableID) {
            TopicTreeEditor.addItemToTopic("Video", this.readableID, this.title, this.contextNode, this.contextModel, -1);
        } else {
            if (!this.youtubeID) {
                return;
            }

            var video = new Video({ youtube_id: this.youtubeID });
            video.save({}, {
                success: function(model) {
                    TopicTreeEditor.addItemToTopic("Video", model.get("readable_id"), model.get("title"), self.contextNode, self.contextModel, -1);
                }
            });
        }
        this.hide();
    },

    doVideoSearch: function() {
        var youtubeID = $(this.el).find("input[name=\"youtube_id\"]").val();
        var self = this;
        $.ajax({
            url: "/api/v1/videos/" + youtubeID + "/youtubeinfo",
            success: function(json) {
                self.youtubeID = youtubeID;
                if (json.existing) {
                    self.readableID = json.readable_id;
                    self.title = json.title;
                } else {
                    self.readableID = null;
                }
                $(self.el).find(".create-video-preview").html(self.previewTemplate(json));
                $(self.el).find(".ok-button").removeClass("disabled").addClass("green");
            },
            error: function(json) {
                self.youtubeID = null;
                self.readableID = null;
                $(self.el).find(".create-video-preview").html("Video not found.");
                $(self.el).find(".ok-button").addClass("disabled").removeClass("green");
            }
        });
    },

    queueVideoSearch: function() {
        this.queueVideoSearchFn = this.queueVideoSearchFn || _.debounce(this.doVideoSearch, 1000);
        this.queueVideoSearchFn();
    },

    hide: function() {
        return $(this.el).modal("hide");
    }
});

// Add a new url dialog box

TopicTreeEditor.CreateUrlView = Backbone.View.extend({
    template: Templates.get( "topicsadmin.create-url" ),
    contextNode: null,
    contextModel: null,

    initialize: function() {
        this.render();
    },

    events: {
        "click .ok-button": "createUrl"
    },

    render: function() {
        var el = $(this.template({type: this.type})).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function(node, model) {
        this.contextNode = node;
        this.contextModel = model;

        $(this.el).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        $(this.el).find("input[name=\"url\"]").val("");
    },

    createUrl: function() {
        var self = this;
        var url = $(this.el).find("input[name=\"url\"]").val();
        var title = $(this.el).find("input[name=\"title\"]").val();
        var urlObject = new ExternalURL({ url: url, title: title });

        urlObject.save({}, {
            success: function(model) {
                TopicTreeEditor.addItemToTopic("Url", model.id, model.get("title"), self.contextNode, self.contextModel, -1);
            }
        });
        this.hide();
    },

    hide: function() {
        return $(this.el).modal("hide");
    }
});

// View versions list

TopicTreeEditor.VersionListView = Backbone.View.extend({
    template: Templates.get( "topicsadmin.list-versions" ),
    templateItem: Templates.get( "topicsadmin.list-versions-item" ),

    initialize: function() {
        this.render();
    },

    render: function() {
        var el = $(this.template({})).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function( type ) {
        $( this.el ).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        var self = this;
        getTopicVersionList().fetch({
            success: function() {
                var elements = [];
                _.each( getTopicVersionList().models, function( model ) {
                    elements.push(
                        $( self.templateItem( model.toJSON() ) )
                            .find( "a.edit-version" )
                                .click( function() { TopicTreeEditor.editVersion( model.get( "number" ) ); } )
                                .end()
                    );
                });
                _.each( elements, function( element ) { element.appendTo( $( ".version-list", self.el ).get( 0 ) ); } );
            }
        });
        return this;
    },

    hide: function() {
        return $(this.el).modal("hide");
    }
});

// Search popup

TopicTreeEditor.SearchView = Backbone.View.extend({
    template: Templates.get( "topicsadmin.search-topics" ),
    visible: false,
    matchingPaths: null,
    currentIndex: 0,

    events: {
        "click .search-button": "toggle",
        "change input": "doSearch",
        "click .prev-button": "goToPrev",
        "click .next-button": "goToNext"
    },

    initialize: function() {
        this.render();
    },

    render: function() {
        var el = $(this.template({})).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    toggle: function() {
        this.visible = !this.visible;
        if (this.visible) {
            this.show();
        } else {
            this.hide();
        }
    },

    show: function() {
        $(".search-button", this.el).attr("src", "/images/circled_cross.png");
        $(".search-panel", this.el).slideDown(100);
    },

    hide: function() {
        $(".search-button", this.el).attr("src", "/images/jquery-mobile/icon-search-black.png");
        $(".search-panel", this.el).slideUp(100);
    },

    doSearch: function() {
        this.clearResults();

        el = $("input", this.el);
        query = el.val();
        if (query !== "") {
            var self = this;
            Throbber.show(el);
            $.ajax({
                url: "/api/v1/topicversion/" + TopicTreeEditor.currentVersion.get("number") + "/search/" + query,
                success: function(json) {
                    Throbber.hide();

                    var nodes = { };
                    _.each(json.nodes, function(node) {
                        nodes[node.kind] = nodes[node.kind] || [];
                        nodes[node.kind].push(node);
                    });
                    TopicTreeEditor.topicTree.addInited(nodes.Topic);
                    getExerciseList().addInited(nodes.Exercise);
                    getVideoList().addInited(nodes.Video);
                    getUrlList().addInited(nodes.URL);

                    self.matchingPaths = json.paths;
                    if (self.matchingPaths.length > 0) {
                        self.currentIndex = 0;
                        self.goToResult(0);
                    }
                }
            });
        }
    },

    clearResults: function() {
        this.matchingPaths = [];
        $(".prev-button", this.el).attr("src", "/images/vote-up-gray.png");
        $(".next-button", this.el).attr("src", "/images/vote-down-gray.png");
    },

    goToResult: function(index) {
        var path = this.matchingPaths[index];
        var node = TopicTreeEditor.dynatree.getNodeByKey("Topic/root");
        var last_key = path[path.length-1] + "/" + path[path.length-2];

        _.each(path, function(key) {
            if (node) {
                var nextNode = null;

                node.expand(true);

                KAConsole.log("Opening " + key + "...");

                _.each(node.childList, function(childNode) {
                    if (childNode.data.key == last_key) {
                        childNode.activate();
                    } else if (childNode.data.key == ("Topic/"+key)) {
                        childNode.expand(true);
                        nextNode = childNode;
                    } else {
                        childNode.expand(false);
                    }
                });

                node = nextNode;
            }
        });

        this.currentIndex = index;
        $(".prev-button", this.el).attr("src", (this.currentIndex === 0) ? "/images/vote-up-gray.png" : "/images/vote-up.png");
        $(".next-button", this.el).attr("src", (this.currentIndex < this.matchingPaths.length - 1) ? "/images/vote-down.png" : "/images/vote-down-gray.png");
    },

    goToPrev: function() {
        if (this.currentIndex > 0) {
            this.goToResult(this.currentIndex - 1);
        }
    },
    goToNext: function() {
        if (this.currentIndex < this.matchingPaths.length - 1) {
            this.goToResult(this.currentIndex + 1);
        }
    }
});

// Import / export

TopicTreeEditor.ImportExportView = Backbone.View.extend({
    template: Templates.get("topicsadmin.import-export"),

    events: {
        "click .ok-button": "close"
    },

    initialize: function() {
        this.render();
    },

    render: function() {
        var el = $(this.template({ import: this.options.import })).appendTo(document.body).get(0);
        this.setElement(el);
        this.delegateEvents();
        return this;
    },

    show: function(topicID) {
        var self = this;

        $(this.el).modal({
            keyboard: true,
            backdrop: true,
            show: true
        });

        this.topicID = topicID;

        if (!this.options.import) {
            $(this.el).find(".topic-data").html("Exporting topic data. Please wait.");
            $.ajax({
                url: "/api/v1/dev/topicversion/" + TopicTreeEditor.currentVersion.get("number") + "/topic/" + topicID + "/topictree",
                dataType: "html",
                success: function(text) {
                    $(self.el).find(".topic-data").html(text);
                }
            });
        }
        return this;
    },

    hide: function() {
        return $(this.el).modal("hide");
    },

    close: function() {
        var self = this;
        if (this.options.import) {
            this.hide();
            hideGenericMessageBox();
            popupGenericMessageBox({
                title: "Importing topic...",
                message: "Importing topic. Please wait...",
                buttons: []
            });
            $.ajax({
                url: "/api/v1/dev/topicversion/" + TopicTreeEditor.currentVersion.get("number") + "/topic/" + self.topicID + "/topictree",
                type: "PUT",
                contentType: "application/json",
                data:  $(self.el).find(".topic-data").val(),
                success: function() {
                    hideGenericMessageBox();
                }
            });
        } else {
            this.hide();
        }
    }
});
