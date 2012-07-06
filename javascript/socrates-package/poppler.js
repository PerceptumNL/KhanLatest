// Poppler is an event triggering library for streams.

var Poppler = (function() {
    function Poppler() {
        this.events = [];
        this.duration = -1;
        this.eventIndex = 0;
        this.indicesById = {};
        this.began = false;
        _.bindAll(this);
    }

    Poppler.timeFn = function(e) { return e.time; };

    Poppler.nextPeriod = function(n, period) {
        return Math.round(Math.floor(n / period + 1)) * period;
    };

    Poppler.prototype.add = function(time, fn, id) {
        fn.time = time;
        fn.id = id;
        var i = _.sortedIndex(this.events, fn, Poppler.timeFn);

        // if there are existing elements with the same time, insert afterwards
        while (this.events[i] && this.events[i].time == time) i++;

        this.events.splice(i, 0, fn);
    };

    Poppler.prototype.begin = function() {
        this.began = true;

        // make an index of id -> index to seek by id
        this.indicesById = _.reduce(this.events, function(o, ev, i) {
            o[ev.id] = i;
            return o;
        }, {});
    };

    Poppler.prototype.trigger = function trigger(time) {
        if (!this.began) this.begin();
        if (this.blocked) return;

        var delta = time - this.duration;

        // ignore duplicate triggers
        var epsilon = 0.001;
        if (Math.abs(delta) < epsilon) return;

        // ignore any huge jumps
        var maxJumpSize = 1;
        if (Math.abs(delta) > maxJumpSize) return;

        // get a new duration
        this.duration = time;
        this.triggerEvents();
    };

    Poppler.prototype.triggerEvents = function() {
        while (this.events[this.eventIndex] && this.events[this.eventIndex].time <= this.duration) {
            var blocking = this.events[this.eventIndex]();
            this.eventIndex++;
            if (blocking) {
                this.blocked = true;
                break;
            }
        }
    };

    Poppler.prototype.resumeEvents = function() {
        this.blocked = false;
        this.triggerEvents();
    };

    Poppler.prototype.seek = function(time) {
        if (!this.began) this.begin();

        this.duration = time;
        this.eventIndex = _.sortedIndex(this.events, {time: this.duration}, Poppler.timeFn);
    };

    Poppler.prototype.seekToId = function(id) {
        if (!this.began) this.begin();

        var i = this.indicesById[id];
        if (i == null) {
            throw new Exception("No event found with id" + id);
        }
        var e = this.events[i];

        this.duration = e.time;
        this.eventIndex = i;
    };

    return Poppler;
})();
