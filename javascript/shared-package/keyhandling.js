/**
 * Generic utilities related to keyboard handling and input event listneing.
 */


// Namespace
var Keys = {};


/**
 * Conservatively determines if a key event is a text modifying key event.
 * Reads values "as-is" from the "keyCode" property, and does little to
 * resolve cross-browser differences among the values. Leans towards
 * "yes - it is a modifying event" if unknown.
 */
Keys.isTextModifyingKeyEvent_ = function(e) {
    if ((e.altKey && !e.ctrlKey) || e.metaKey ||
            // Function keys don't generate text
            e.keyCode >= 112 && e.keyCode <= 123) {
        return false;
    }

    switch (e.keyCode) {
        case $.ui.keyCode.ALT:
        case $.ui.keyCode.CAPS_LOCK:
        case $.ui.keyCode.COMMAND:
        case $.ui.keyCode.COMMAND_LEFT:
        case $.ui.keyCode.COMMAND_RIGHT:
        case $.ui.keyCode.CONTROL:
        case $.ui.keyCode.DOWN:
        case $.ui.keyCode.END:
        case $.ui.keyCode.ENTER:
        case $.ui.keyCode.ESCAPE:
        case $.ui.keyCode.HOME:
        case $.ui.keyCode.INSERT:
        case $.ui.keyCode.LEFT:
        case $.ui.keyCode.MENU:
        case $.ui.keyCode.PAGE_DOWN:
        case $.ui.keyCode.PAGE_UP:
        case $.ui.keyCode.RIGHT:
        case $.ui.keyCode.SHIFT:
        case $.ui.keyCode.UP:
        case $.ui.keyCode.WINDOWS:
            return false;
        default:
            return true;
    }
};


/**
 * A space-separated list of event names appropriate for indication for
 * when a text-change event occured.
 *
 * This is "input" in browsers that support it, but approximated by
 * similar events in IE, with some loss in accuracy. (e.g. it doesn't
 * handle holding down a button and having a repeated character fire
 * repeated events)
 */
Keys.textChangeEvents = $.browser.msie ? "keyup paste cut drop" : "input";


/**
 * Wrap an event handler intended for Keys.textChangeEvents. This will
 * pre-process and filter out any events not corresponding to a proper
 * text change event on an input.
 */
Keys.wrapTextChangeHandler = function(handler, context) {
    return function(e) {
        // When the "input" event is simulated, we have to supress benign
        // key presses.
        if (!Keys.isTextModifyingKeyEvent_(e)) {
            return;
        }
        return handler.call(context || this, e);
    };
};
