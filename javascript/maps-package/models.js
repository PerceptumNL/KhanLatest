
// TODO: would be nice if this were part of a larger KnowledgeMap context
// instead of needing the KnowledgeMap naming prefix.

/**
 * All models that may be represented on the knowledge map
 */
var KnowledgeMapModels = {};

/**
 * All models rendered as nodes on the knowledge map extend Node
 */
KnowledgeMapModels.Node = Backbone.Model.extend({

    /**
     * Set all required properties for rendering map node
     */
    setNodeAttrs: function(name, displayName, x, y, iconUrl, isSuggested, nodeType) {

        var className = "nodeLabel";
        if (this.customClass) {
            className += " " + this.customClass;
        }
        if (this.get("invalidForGoal")) {
            className += " goalNodeInvalid";
        }

        this.set({
            name: name,
            x: x,
            y: y,
            display_name: displayName,
            lowercaseName: displayName.toLowerCase(),
            iconUrl: iconUrl,
            isSuggested: isSuggested,
            className: className,
            url: this.url(),
            preferredZoom: this.preferredZoom,
            nodeType: nodeType
        });

    },

    isClickableAtZoom: function(zoom) {
        return true;
    }

});

/**
 * Model of topic node on the knowledge map. Note that
 * this has properties unique to a knowledge map node that
 * may differ from a standard Topic model.
 */
KnowledgeMapModels.Topic = KnowledgeMapModels.Node.extend({

    // Custom class added to each node
    customClass: "topic",

    // Preferred map zoom when automatically panning to this node
    preferredZoom: 6,

    initialize: function(attributes) {

        // Translate topic properties to standard node properties
        this.setNodeAttrs(
            this.get("id"),
            this.get("standalone_title"),
            this.get("x"),
            this.get("y"),
            this.get("icon_url"),
            this.get("suggested"),
            "topic"
        );

        return KnowledgeMapModels.Node.prototype.initialize.call(this, attributes);

    },

    viewType: function() {
        return KnowledgeMapViews.TopicRow;
    },

    url: function() {
        return "/topicexercise/" + this.get("id");
    }

});

/**
 * Model of an exercise node on the knowledge map. Note that
 * this has properties unique to a knowledge map node that
 * may differ from a standard Exercise model.
 */
KnowledgeMapModels.Exercise = KnowledgeMapModels.Node.extend({

    // Custom class added to each node
    customClass: "exercise",

    // Preferred map zoom when automatically panning to this node
    preferredZoom: 8,

    initialize: function(attributes) {

        // Translate exercise properties to standard node properties
        this.setNodeAttrs(
            this.get("name"),
            this.get("display_name"),
            this.get("v_position"), // v_position is actually x
            this.get("h_position"), // h_position is actually y
            null, // iconUrl
            this.get("states").suggested && !this.get("states").reviewing,
            "exercise"
        );

        return KnowledgeMapModels.Node.prototype.initialize.call(this, attributes);
    },

    viewType: function() {
        return KnowledgeMapViews.ExerciseRow;
    },

    url: function() {
        if (this.get("admin")) {
            return "/editexercise?name=" + this.get("name");
        } else {
            return "/exercise/" + this.get("name");
        }
    },

    isClickableAtZoom: function(zoom) {
        // Exercises aren't clickable at or below zoom level 7
        return zoom > 7;
    }

});

/**
 * Polyline represents a collection of line points for drawing paths on the map
 */
KnowledgeMapModels.Polyline = Backbone.Model.extend({

    initialize: function(attributes) {

        // Convert line path to appropriate lat/lng coord path
        this.set({
            latLngPath: _.map(this.get("path"), function(pt) {
                return KnowledgeMapGlobals.xyToLatLng(pt.x, pt.y);
            })
        });

        return Backbone.Model.prototype.initialize.call(this, attributes);
    }

});
