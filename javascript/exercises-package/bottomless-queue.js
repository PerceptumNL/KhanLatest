/**
 * BottomlessQueue returns a never-ending sequence of
 * Card objects once primed with
 * some initial cards.
 *
 * It'll talk to our API to try to find the best next
 * cards in the queue when possible.
 *
 * TODO(david)(or anybody): Write unit tests for this thing!
 */
Exercises.BottomlessQueue = {

    topic: null,

    // # of exercises we keep around as "recycled"
    // in case we need to re-use them if ajax requests
    // have failed to refill our queue.
    recycleQueueLength: 5,

    // # of exercises in queue below which we will
    // send off an ajax request for a refill
    queueRefillSize: 2,

    // # of exercises in upcoming queue for which we
    // trigger upcomingExercise events to give
    // listeners a chance to preload resources
    preloadUpcoming: 2,

    // true if this queue can talk to the server to refill itself with new
    // exercises, otherwise it'll keep recycling its original exercises.
    refillEnabled: true,

    // true if there's a refill request currently pending
    refilling: false,

    currentQueue: [],
    recycleQueue: [],

    // current item that was most recently popped off the queue
    current: null,

    init: function(topic, cards, refillEnabled) {

        this.topic = topic;
        this.refillEnabled = (refillEnabled !== false);  // default is true

        // Fill up our queue with initial cards sent on first pageload
        _.each(cards, this.enqueue, this);

    },

    enqueue: function(card) {

        if (!(card instanceof Exercises.Card)) {
            card = new Exercises.Card(card);
        }

        // Push onto current queue
        this.currentQueue.push({
            card: card,
            // true if we've triggered an upcomingExercise event for this queue entry
            upcomingTriggered: false
        });

        // Possibly new upcoming exercises
        this.triggerUpcoming();

    },

    /**
     * Make sure an upcomingExercise event has been triggered for the
     * first this.preloadUpcoming events in currentQueue.
     */
    triggerUpcoming: function() {

        _.each(this.currentQueue, function(item, ix) {

            if (!item.upcomingTriggered && ix < this.preloadUpcoming) {

                var userExercise = item.card.getUserExercise();
                if (!userExercise) {
                    return;
                }

                // Tell khan-exercises to preload this upcoming exercise if it hasn't
                // already
                $(Exercises).trigger("upcomingExercise", {
                    exerciseId: userExercise.exercise,
                    exerciseName: userExercise.exerciseModel.displayName,
                    exerciseFile: userExercise.exerciseModel.fileName
                });

                item.upcomingTriggered = true;

            }

        }, this);

    },

    /**
     * Returns the next available card that we have. If we don't have any cards
     * left in our queue (possibly because the refill AJAX request haven't
     * returned yet), return a recycled old card that has already been presented
     * to the user.
     * @return {Card} The next card.
     */
    next: function() {

        // If the queue is empty, use the recycle queue
        // to fill up w/ old problems while we wait for
        // an ajax request for more exercises to complete.
        if (!this.currentQueue.length) {
            this.currentQueue = this.recycleQueue;
            this.recycleQueue = [];
        }

        // We don't ever expect to find an empty queue at
        // this point. If we do, we've got a problem.
        if (!this.currentQueue.length) {
            throw "No exercises are in the queue";
        }

        // Pull off the next card
        this.current = _.head(this.currentQueue);

        // Remove it from current queue...
        this.currentQueue = _.rest(this.currentQueue);

        // ...but put a cloned version on the end of our recycle queue. This
        // way, we can safely reuse recycled cards without worrying about stale
        // properties like leavesEarned.
        var cloned = {};
        _.each(this.current, function(value, key) {
            cloned[key] = (value && value.clone && value.clone()) || value;
        });

        this.recycleQueue.push(cloned);

        // ...and then chop the recycle queue down so it
        // doesn't just constantly grow.
        this.recycleQueue = _.last(this.recycleQueue, Math.min(5, this.recycleQueue.length));

        // Refill if we're running low
        if (this.currentQueue.length < this.queueRefillSize) {
            this.refill();
        }

        // Possibly new upcoming exercises
        this.triggerUpcoming();

        return this.current.card;

    },

    refill: function() {

        if (!this.refillEnabled) {
            // We don't refill in reviewMode or practiceMode, all stack
            // data was sent down originally
            return;
        }

        if (this.refilling) {
            // Only one refill request at a time
            return;
        }

        $.ajax({
            url: "/api/v1/user/topic/" + encodeURIComponent(this.topic.get("id")) + "/cards/next",
            type: "GET",
            dataType: "json",
            data: {
                // Return a list of upcoming exercises so the server can decide
                // whether or not to re-suggest them.
                queued: _.pluck(this.currentQueue, "exercise"),
                casing: "camel"
            },
            complete: function() {
                Exercises.BottomlessQueue.refilling = false;
            },
            success: function(data) {

                // Enqueue the next few cards to show the user
                _.each(data.cards, function(cardData) {
                    Exercises.BottomlessQueue.enqueue(cardData);
                });

                // Cache any associated userExercises for the cards we got
                _.each(data.userExercises,
                    Exercises.UserExerciseCache.cacheLocally,
                    Exercises.UserExerciseCache);

            }
        });

        this.refilling = true;

    }

};
