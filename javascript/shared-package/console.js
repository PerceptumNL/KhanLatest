var KAConsole = {
    oldMessages_: [],

    flushOldMessages_: function() {
        _.each(this.oldMessages_, function(a) {
            this.log.apply(this, a);
        }, this);
        this.oldMessages_ = [];
    },

    /**
     * Saves all messages to a buffer. Used when no window.console is present,
     * or when KAConsole is disabled.
     *
     * @this {KAConsole}
     */
    logToBuffer_: function() {
        this.oldMessages_.push(arguments);
    },

    /*
     * Used when KAConsole is enabled, but no window.console is present.
     * Saves all logs to the buffer but checks each time to see if a console
     * appears.
     *
     * @this {KAConsole}
     */
    logOrPreserve_: function() {
        if (window.console) {
            this.enable();
            this.log.apply(this, arguments);
        } else {
            this.logToBuffer_.apply(this, arguments);
        }
    },

    /*
     * Assumes a console is available, and passes arguments through. Does not
     * preserve line number of caller, so only used when console.log.bind is
     * not supported.
     */
    logCompatible_: function() {
        if (!window.console) return;
        // this should just be console.log.apply(console, arguments), but to be
        // compatible with IE8 we have to be a bit more indirect
        Function.prototype.apply.call(console.log, null, arguments);
    },

    /*
     * Enables display of log messages. Attempts to directly bind KAConsole.log
     * to console.log to preserve display of line numbers. If this is not
     * possible, falls back to a compatible method. If a console is not present
     * (IE 8 before dev tools are enabled), preserves logs until a console
     * appears.
     *
     * @this {KAConsole}
     */
    enable: function() {
        if (window.console) {
            if (console.log.bind) {
                // When possible, directly call the correctly bound console.log
                // function. This preserves line number display in the console.
                this.log = console.log.bind(console);
            } else {
                // We have a console, but don't support bind.
                this.log = this.logCompatible_;
            }
            this.flushOldMessages_();
        } else {
            // There is no console, so record everything until a console becomes
            // available.
            this.log = this.logOrPreserve_;
        }
    },

    disable: function() {
        this.log = this.logToBuffer_;
    },

    init: function(enable) {
        if (enable) {
            this.enable();
        } else {
            this.disable();
        }
    }
};

// todo(dmnd) if this init call can be placed elsewhere, console.js is competely
// decoupled. For now, leave it here.
KAConsole.init(window.KA_IS_DEV);
