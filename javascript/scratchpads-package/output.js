// Load in SJS-compiled dependencies
require("sjs:apollo-sys").require("/javascript/scratchpads-package/text-apollo");

(function() {

var curProblem;

window.Output = {
    icons: {
        pass: "check",
        fail: "none",
        error: "alert",
        info: "info"
    },

    init: function(id) {
        this.id = id;
        this.$elem = $("#" + id);
        this.$editor = $("#editor");
        this.editor = this.$editor.data("editor").editor;

        this.tests = [];
        this.testAnswers = [];

        this.errors = [];
        this.asserts = [];
        this.inTask = null;

        this.toExec = true;
        this.context = {};

        if (curProblem && !curProblem.taskOpen) {
            curProblem.taskOpen = [];
        }

        // Default to using CanvasOutput
        var type = CanvasOutput;

        // Prime the test queue
        if (curProblem && curProblem.validate) {
            Output.exec(curProblem.validate, Output.testContext);

            if (Output.tests.length) {
                for (var i = 0; i < Output.tests.length; i++) {
                    var test = Output.tests[i];

                    if (test.type !== "default") {
                        type = test.type;
                    }
                }
            }
        }

        Output.setOutput(type);

        this.bind();
    },

    bind: function() {
        if (Output.bound) {
            return;
        }

        Output.editor.on("change", function() {
            Output.toExec = Output.getUserCode();
        });

        setInterval(function() {
            if (Output.toExec != null) {
                Output.runCode(Output.toExec === true ?
                    Output.getUserCode() :
                    Output.toExec);

                Output.toExec = null;
            }
        }, 100);

        this.bound = true;
    },

    setOutput: function(output) {
        if (Output.output) {
            Output.output.kill();
        }

        Output.output = output.init();
    },

    registerOutput: function(output) {
        if (!Output.outputs) {
            Output.outputs = [];
        }

        Output.outputs.push(output);

        $.extend(Output.testContext, output.testContext);
    },

    // Returns an object that holds all the exposed properties
    // from the current execution environment. The properties will
    // correspond to boolean values: true if it cannot be overriden
    // by the user, false if it can be. See: JSHintGlobalString
    exposedProps: function() {
        return Output.output ? Output.output.props : {};
    },

    // Build a string of variables names to feed into JSHINT
    // This lets JSHint know which variables are globally exposed and
    // which can be overridden, more details: http://www.jshint.com/about/
    // propName: true (is a global property, but can be overridden)
    // propName: false (is a global property, may not be overridden)
    JSHintGlobalString: function() {
        var propList = [],
            externalProps = Output.exposedProps();

        for (var prop in externalProps) {
            propList.push(prop + ":" + externalProps[prop]);
        }

        return propList.join(",");
    },

    runCode: function(userCode) {
        var doRunTests = !!JSHINT(
                "/*jshint undef:true, noempty:true, plusplus:true, " +
                "noarg:true, latedef:true, eqeqeq:true, curly:true */" +
                "/*global " + Output.JSHintGlobalString() + "*/\n" + userCode),
            hintData = JSHINT.data(),
            externalProps = Output.exposedProps();

        Output.globals = {};

        if (hintData && hintData.globals) {
            for (var i = 0, l = hintData.globals.length; i < l; i++) {
                var global = hintData.globals[i];

                if (global in TextOutput.props) {
                    if (Output.output !== TextOutput) {
                        Output.setOutput(TextOutput.init());
                    }
                }

                // Do this so that declared variables are gobbled up
                // into the global context object
                if (!externalProps[global] && !(global in Output.context)) {
                    Output.context[global] = undefined;
                }

                Output.globals[global] = true;
            }
        }

        Output.errors = [];

        var runDone = function() {
            Output.toggleErrors();
        };

        if (doRunTests) {
            // Run the tests
            Output.test(userCode);

            // Then run the user's code
            if (Output.output && Output.output.runCode) {
                Output.output.runCode(userCode, Output.context, runDone);
                return;

            } else {
                Output.exec(userCode, Output.context);
            }

        } else {
            for (var i = 0; i < JSHINT.errors.length; i++) {
                var error = JSHINT.errors[i];

                if (error && error.line && error.character &&
                        error.reason &&
                        !/unable to continue/i.test(error.reason)) {

                    Output.errors.push({
                        row: error.line - 2,
                        column: error.character - 1,
                        text: clean(error.reason),
                        type: "error",
                        lint: error
                    });
                }
            }
        }

        runDone();
    },

    toggleErrors: function() {
        var session = Output.editor.getSession(),
            hasErrors = !!Output.errors.length;

        session.clearAnnotations();

        $("#show-errors").toggleClass("ui-state-disabled", !hasErrors);
        $("#output .error-overlay").toggle(hasErrors);

        Output.toggle(!hasErrors);

        if (hasErrors) {
            Output.errors = Output.errors.sort(function(a, b) {
                return a.row - b.row;
            });

            session.setAnnotations(Output.errors);

            if (Output.errorDelay) {
                clearTimeout(Output.errorDelay);
            }

            Output.errorDelay = setTimeout(function() {
                if (Output.errors.length > 0) {
                    $("#output").showTip("Error", Output.errors, function() {
                        $(".tipbar.error .text")
                            .append(" (<a href=''>View Error</a>)");
                    });
                }
            }, 1500);

        } else {
            $("#output").hideTip("Error");
        }
    },

    test: function(userCode) {
        if (Output.testAnswers.length) {
            return;
        }

        var insert = $("#results .desc").empty();

        Output.testing = true;
        Output.asserts = [];

        for (var i = 0; i < Output.tests.length; i++) {
            var fieldset = $("<fieldset><legend>" + Output.tests[i].name +
                " (<a href=''>View Output</a>)</legend><ul></ul></fieldset>")
                .appendTo(insert);

            var testOutput = Output.runTest(userCode, Output.tests[i], i);

            fieldset.data("output", testOutput || false);
        }

        Output.testing = false;

        var total = Output.asserts.length,
            pass = 0;

        for (var i = 0; i < Output.asserts.length; i++) {
            if (Output.asserts[i]) {
                pass += 1;
            }
        }

        if (total > 0) {
            if (pass === total) {
                // TODO(jeresig): Handle case where problem is done
            }

            $("#results")
                .toggleClass("multiple", tests.length > 1)
                .toggleClass("error", pass < total)
                .show();

        } else {
            // TODO(jeresig): Handle case where problem is done
        }
    },

    runTest: function(userCode, test, i) {
        Output.clear();

        if (Output.output && Output.output.preTest) {
            Output.output.preTest();
        }

        if (typeof test.type === "object") {
            if (test.type.runTest) {
                test.type.runTest(userCode, test, i);
            }

        } else if (curProblem && curProblem.validate) {
            // We need to maintain the closure so we have to re-initialize
            // the tests and then run the current one. Definitely not ideal.
            Output.exec(userCode +
                "\n(function(){ Output.tests = [];\n" +
                curProblem.validate + "\n})(); Output.tests[" + i + "].fn();",
                Output.context, Output.testContext);
        }

        if (Output.output && Output.output.postTest) {
            return Output.output.postTest();
        }
    },

    toggle: function(toggle) {
        if (Output.output && Output.output.toggle) {
            Output.output.toggle(toggle);
        }
    },

    start: function() {
        if (Output.output && Output.output.start) {
            Output.output.start();
        }
    },

    stop: function() {
        if (Output.output && Output.output.stop) {
            Output.output.stop();
        }
    },

    restart: function() {
        if (Output.output && Output.output.restart) {
            Output.output.restart();
        }
    },

    clear: function() {
        if (Output.output && Output.output.clear) {
            Output.output.clear();
        }
    },

    handleError: function(e) {
        // Temporarily hide the errors generated by using a prompt()
        // See: #50
        if (!/Unexpected end of input/.test(e.message)) {
            Output.errors.push({
                row: 0,
                column: 0,
                text: clean(e.message),
                type: "error"
            });

            Output.testContext.assert(false, "Error: " + e.message,
                "A critical problem occurred in your program " +
                "making it unable to run.");

            Output.toggleErrors();
        }
    },

    exec: function(code) {
        try {
            if (Output.output && Output.output.compile) {
                code = Output.output.compile(code);
            }

            var contexts = Array.prototype.slice.call(arguments, 1);

            for (var i = 0; i < contexts.length; i++) {
                if (contexts[i]) {
                    code = "with(arguments[" + i + "]){\n" + code + "\n}";
                }
            }

            (new Function(code)).apply(Output.context, contexts);

        } catch (e) {
            Output.handleError(e);
        }
    },

    testContext: {
        test: function(name, fn, type) {
            if (!fn) {
                fn = name;
                name = "Test Case";
            }

            Output.tests.push({
                name: name,

                type: type || "default",

                fn: function() {
                    try {
                        return fn.apply(this, arguments);

                    } catch (e) {
                        Output.handleError(e);
                    }
                }
            });
        },

        testAnswer: function(name, val) {
            Output.testAnswers.push({ answer: val, text: "<form>" + name +
                "<br/><input type='text'/>" +
                "<input type='submit' value='Check Answer' class='ui-button'/></form>" });
        },

        task: function(msg, tip) {
            Output.testContext.log(msg, "pass", tip);

            var pos = $("#results li.task").length,
                task = $("#results li").last()
                    .addClass("task")
                    .append("<ul></ul>");

            if (Output.inTask !== null) {
                task.parents("ul").last().append(task);
            }

            if (curProblem && curProblem.taskOpen[pos]) {
                task.find("ul").show();
            }

            Output.inTask = true;
        },

        log: function(msg, type, expected) {
            type = type || "info";

            Output.updateTask(type);

            $("<li class='" + type + "'>" +
                "<span class='check'><span class='ui-icon ui-icon-" +
                Output.icons[type] + "'></span></span> " +
                "<a href='' class='msg'>" + clean(msg) + "</a></li>")
                .data("expected", expected || false)
                .appendTo($("#results ul").last());
        },

        assert: function(pass, msg, expected) {
            pass = !!pass;

            Output.testContext.log(msg, pass ? "pass" : "fail", expected);
            Output.asserts.push(pass);

            return pass;
        },

        isEqual: function(a, b, msg) {
            var pass = a === b;

            Output.testContext.log(msg, pass ? "pass" : "fail", [a, b]);
            Output.asserts.push(pass);

            return pass;
        }
    },

    updateTask: function(type) {
        if (Output.inTask === true && type !== "pass") {
            $("#results li.task").last()
                .removeClass("pass")
                .addClass(type || "")
                .find(".ui-icon")
                    .removeClass("ui-icon-" + Output.icons.pass)
                    .addClass("ui-icon-" + Output.icons[type]);

            Output.inTask = false;
        }
    },

    getUserCode: function() {
        return $("#editor").editorText();
    },

    stringify: function(obj) {
        try {
            return typeof obj === "function" ?
                obj.toString() :
                JSON.stringify(obj);
        } catch (e) {
            console.error(e, obj);
            return "null";
        }
    }
};

// TODO(jeresig): Handle saved output from a test run

window.TextOutput = {
    props: {
        input: false,
        inputNumber: false,
        print: false
    },

    init: function() {
        this.id = this.id || "output-text";
        this.$elem = $("#" + this.id);
        this.$elem.show();

        this.oni = window.__oni_rt;

        // For managing real-time inputs
        if (curProblem && !curProblem.inputs) {
            curProblem.inputs = [];
        }

        // Need to execute the test code in apollo itself
        this.doCompile = true;

        this.focusLine = null;
        this.inputNum = 0;
        this.curLine = -1;
        this.toInput = null;

        Output.context = jQuery.extend({}, TextOutput.context);

        this.bind();

        return this;
    },

    bind: function() {
        if (this.bound) {
            return;
        }

        var self = this,
            root = this.$elem;

        this.$elem.delegate("input", "keydown keyup change", function() {
            var last = $(this).data("last"),
                val = $(this).val() || null;

            if (last != val) {
                var pos = root.find("input").index(this);

                if (!TextOutput.restarting) {
                    if (curProblem) {
                        curProblem.inputs[pos] = val;
                    }

                    TextOutput.focusLine =
                        root.children().index(this.parentNode);
                }

                $(this).data("last", val);
            }
        });

        setInterval(function() {
            if (TextOutput.focusLine != null) {
                TextOutput.runCode(Output.getUserCode());
                TextOutput.focusLine = null;
            }
        }, 13);

        this.bound = true;
    },

    runCode: function(code, context, callback) {
        TextOutput.clear();
        Output.exec(code, context);

        if (callback) {
            callback();
        }
    },

    context: {
        print: function(msg) {
            TextOutput.resumeTest();

            if (TextOutput.focusLine != null &&
                    TextOutput.focusLine + 1 > ++TextOutput.curLine) {
                return;
            }

            TextOutput.addLine(clean(msg));

            TextOutput.resumeTest("waitTestPrint", msg);
        }
    },

    showInput: function(msg) {
        if (TextOutput.focusLine != null &&
                TextOutput.focusLine + 1 > ++TextOutput.curLine) {
            return;
        }

        var div = TextOutput.addLine(clean(msg) +
                " <input type='text' class='text'/>"),
            input = div.find("input")
                .val(TextOutput.toInput != null ? TextOutput.toInput : "");

        if (!Output.testing) {
            TextOutput.$elem.scrollTop(TextOutput.$elem[0].scrollHeight);
        }

        if (TextOutput.inputNum - 1 === TextOutput.focusInput) {
            input.focus();
        }
    },

    addLine: function(line) {
        var $line = $("<div>" + line + "</div>")
            .appendTo(this.$elem);

        // output.scrollTop(output[0].scrollHeight);

        return $line;
    },

    resumeTest: function(name, msg) {
        name = name || "waitTest";

        if (TextOutput[name]) {
            var doResume = TextOutput[name];
            delete TextOutput[name];
            doResume(msg);

            return true;
        }
    },

    preTest: function() {
        TextOutput.$elem = $("#" + this.id + "-test");
    },

    postTest: function() {
        var oldElem = TextOutput.$elem[0];

        TextOutput.$elem = $("#" + this.id);

        return oldElem;
    },

    runTest: function(userCode, test, i) {
        // TODO(jeresig): Have all tests run after user's code has been defined
        // Will need to force input/print statements to block during testMode

        Output.clear();

        // Load up the IO tests
        Output.exec("waitfor() { TextOutput.waitTest = resume; } " +
            "Output.tests[" + i + "].fn();", Output.testContext);

        // Need to execute the test code in apollo itself
        // Need to be compiled after they've been referenced
        if (TextOutput.doCompile && curProblem && curProblem.validate) {
            Output.tests = [];
            Output.exec(curProblem.validate, Output.testContext);
            TextOutput.doCompile = false;
        }

        // Then run the user's code
        Output.exec(userCode, Output.context);

        // Make sure the remaining IO tests are printed out so that the
        // user knows what's expected of them
        var checkIO;

        do {
            checkIO = false;

            TextOutput.resumeTest();

            checkIO = TextOutput.resumeTest("waitTestInput", false) || checkIO;
            checkIO = TextOutput.resumeTest("waitTestPrint", false) || checkIO;
        } while (checkIO);
    },

    testContext: {
        testIO: function(name, fn) {
            Output.testContext.test(name, fn, TextOutput);
        }
    },

    clear: function() {
        if (!Output.testing && TextOutput.focusLine != null) {
            TextOutput.$elem.children().slice(
                TextOutput.focusLine + 1).remove();

        } else {
            TextOutput.$elem.empty();
        }

        TextOutput.inputNum = 0;
        TextOutput.curLine = -1;
    },

    compile: function(code) {
        return TextOutput.oni.c1.compile(code);
    },

    kill: function() {
        TextOutput.$elem.empty();
        TextOutput.$elem.hide();
    },

    restart: function() {
        if (curProblem) {
            curProblem.inputs = [];
        }

        TextOutput.focusLine = null;
        TextOutput.inputNum = 0;
        TextOutput.curLine = -1;

        TextOutput.restarting = true;
        Output.runCode(Output.getUserCode());
        TextOutput.restarting = false;
    }
};

Output.registerOutput(TextOutput);

var CanvasOutput = {
    // Canvas mouse events to track
    // Tracking: mousemove, mouseover, mouseout, mousedown, and mouseup
    trackedMouseEvents: ["move", "over", "out", "down", "up"],

    init: function(id) {
        this.id = id || "output-canvas";
        this.$elem = $("#" + this.id);
        this.$elem.show();

        var offset = this.$elem.offset();

        // Go through all of the mouse events to track
        jQuery.each(CanvasOutput.trackedMouseEvents, function(i, name) {
            var eventType = "mouse" + name;

            // Track that event on the Canvas element
            CanvasOutput.$elem.bind(eventType, function(e) {
                // Only log if recording is occurring
                if (Record.recording) {
                    var action = {};

                    // Track the x/y coordinates of the event
                    // Set to a property with the mouse event name
                    action[name] = {
                        x: e.pageX - offset.left,
                        y: e.pageY - offset.top
                    };

                    // Log the command
                    Record.log(action);
                }
            });

            // Handle the command during playback
            Record.handlers[name] = function(e) {
                // Get the command data
                var action = e[name];

                // Build the clientX and clientY values
                var pageX = action.x + offset.left;
                var pageY = action.y + offset.top;
                var clientX = pageX - $(window).scrollLeft();
                var clientY = pageY - $(window).scrollTop();

                // Construct the simulated mouse event
                var evt = document.createEvent("MouseEvents");

                // See: https://developer.mozilla.org/en/DOM/
                //          event.initMouseEvent
                evt.initMouseEvent(eventType, true, true, window, 0,
                    0, 0, clientX, clientY,
                    false, false, false, false,
                    0, document.documentElement);

                // And execute it upon the canvas element
                CanvasOutput.$elem[0].dispatchEvent(evt);
            };
        });

        CanvasOutput.lastGrab = null;

        CanvasOutput.build(this.id);

        // If a list of exposed properties hasn't been generated before
        if (!CanvasOutput.props) {
            // CanvasOutput.props holds the names of the properties which
            // are to be exposed by Processing.js to the user.
            var externalProps = CanvasOutput.props = {},

                // CanvasOutput.safeCalls holds the names of the properties
                // which are functions which appear to not have any
                // side effects when called.
                safeCalls = CanvasOutput.safeCalls = {};

            // Make sure that only certain properties can be manipulated
            for (var processingProp in Output.context) {
                // Processing.js has some "private" methods (beginning with __)
                // these shouldn't be exposed to the user.
                if (processingProp.indexOf("__") < 0) {
                    var value = Output.context[processingProp],
                        isFunction = (typeof value === "function");

                    // If the property is a function or begins with an uppercase
                    // character (as is the case for constants in Processing.js)
                    // then the user should not be allowed to override the
                    // property (restricted by JSHINT).
                    externalProps[processingProp] =
                        !(/^[A-Z]/.test(processingProp) || isFunction);

                    // Find the functions which could be safe to call
                    // (in that they have no side effects when called)
                    if (isFunction) {
                        // Serializing Output.context.PVector
                        // throws a TypeError for unknown reasons
                        try {
                            // Serialize the function into a string
                            var strValue = String(value);

                            // Determine if a function has any side effects
                            // (a "side effect" being something that changes
                            //  state in the Processing.js environment)
                            //  - If it's a native method then it doesn't have
                            //    any Processing side effects.
                            //  - Otherwise it's a Processing method so we need
                            //    to make sure it:
                            //      (1) returns a value,
                            //      (2) that it doesn't call any other
                            //          Processing functions, and
                            //      (3) doesn't instantiate any Processing
                            //          objects.
                            //    If all three of these are the case assume then
                            //    assume that there are no side effects.
                            if (/native code/.test(strValue) ||
                                /return /.test(strValue) &&
                                !/p\./.test(strValue) &&
                                !/new P/.test(strValue)) {
                                    safeCalls[processingProp] = true;
                            }
                        } catch (e) {}
                    }
                }
            }

            // The one exception to the rule above is the draw function
            // (which is defined on init but CAN be overridden).
            externalProps.draw = true;
        }

        return this;
    },

    build: function(canvas) {
        CanvasOutput.canvas = Output.context =
            new Processing(canvas, function(instance) {
                instance.draw = CanvasOutput.DUMMY;
            });

        CanvasOutput.canvas.size(400, 400);
        CanvasOutput.canvas.frameRate(30);
        CanvasOutput.clear();
    },

    DUMMY: function() {},

    preTest: function() {
        CanvasOutput.oldContext = Output.context;

        CanvasOutput.testCanvas = document.createElement("canvas");
        CanvasOutput.build(CanvasOutput.testCanvas);
    },

    postTest: function() {
        CanvasOutput.canvas = Output.context = CanvasOutput.oldContext;

        return CanvasOutput.testCanvas;
    },

    runTest: function(userCode, test, i) {
        // TODO(jeresig): Add in Canvas testing
        // Create a temporary canvas and a new processing instance
        // temporarily overwrite Output.context
        // Save the canvas for later and return that as the output
        // CanvasOutput.runCode(userCode);
    },

    runCode: function(userCode, globalContext, callback) {
        if (window.Worker) {
            var context = {};

            for (var global in Output.globals) {
                var value = Output.context[global];

                context[global] = (typeof value === "function" ?
                    "__STUBBED_FUNCTION__" :
                    value);
            }

            Output.worker.exec(userCode, context, function() {
                CanvasOutput.injectCode(userCode, callback);
            });

        } else {
            CanvasOutput.injectCode(userCode, callback);
        }
    },

    /*
     * Injects code into the live Processing.js execution.
     *
     * The first time the code is injected, or if no draw loop exists, all of
     * the code is just executed normally using Output.exec().
     *
     * For all subsequent injections the following workflow takes place:
     *   - The code is executed but with all functions that have side effects
     *     replaced with empty function placeholders.
     *     - During this execution a context is set (wrapping the code with a
     *       with(){...}) that intentionally gobbles up all globally-exposed
     *       variables that the user has defined. For example, this code:
     *       var x = 10, y = 20; will result in a grabAll object of:
     *       {"x":10,"y":20}. Only user defined variables are captured.
     *     - Additionally all calls to side effect-inducing functions are logged
     *       for later to the fnCalls array (this includes a log of the function
     *       name and its arguments).
     *   - When the injection occurs a number of pieces need to be inserted into
     *     the live code.
     *     - First, all side effect-inducing function calls are re-run. For
     *       example a call to background(0, 0, 0); will result in the code
     *       background(0, 0, 0); being run again.
     *     - Second any new, or changed, variables will be re-inserted. Given
     *       the x/y example from above, let's say the user changes y to 30,
     *       thus the following code will be executed: var y = 30;
     *     - Third, any variables that existed on the last run of the code but
     *       no longer exist will be deleted. For example, if the ", y = 20" was
     *       removed from the above example the following would be executed:
     *       "delete y;" If the draw function was deleted then the output will
     *       need to be cleared/reset as well.
     *     - Finally, if any draw state was reset to the default from the last
     *       inject to now (for example there use to be a 'background(0, 0, 0);'
     *       but now there is none) then we'll need to reset that draw state to
     *       the default.
     *   - All of these pieces of injected code are collected together and are
     *     executed in the context of the live Processing.js environment.
     */
    injectCode: function(userCode, callback) {
        // Holds all the global variables extracted from the user's code
        var grabAll = {},

            // Holds all the function calls that came from function calls that
            // have side effects
            fnCalls = [],

            // The properties exposed by the Processing.js object
            externalProps = CanvasOutput.props,

            // The code string to inject into the live execution
            inject = "";

        // Go through all the globally-defined variables (this is determined by
        // a prior run-through using JSHINT) and ensure that they're all defined
        // on a single context. Also make sure that any function calls that have
        // side effects are instead replaced with placeholders that collect a
        // list of all functions called and their arguments.
        // TODO(jeresig): See if we can move this off into the worker thread to
        //                save an execution.
        for (var global in Output.globals) (function(global) {
            var value = Output.context[global];

            // Expose all the global values, if they already exist although even
            // if they are undefined, the result will still get sucked into
            // grabAll) Replace functions that have side effects with
            // placeholders (for later execution)
            grabAll[global] = ((typeof value === "function" &&
                    !CanvasOutput.safeCalls[global]) ?
                function() { fnCalls.push([global, arguments]); } :
                value);
        })(global);

        // Run the code with the grabAll context. The code is run with no side
        // effects and instead all function calls and globally-defined variable
        // values are extracted
        Output.exec(userCode, grabAll);

        // Look for new top-level function calls to inject
        for (var i = 0; i < fnCalls.length; i++) {
            // Reconstruction the function call
            var args = Array.prototype.slice.call(fnCalls[i][1]);
            inject += fnCalls[i][0] + "(" +
                Output.stringify(args).slice(1, -1) + ");\n";
        }

        // We also look for newly-changed global variables to inject
        for (var prop in grabAll) {
            // Turn the result of the extracted value into
            // a nicely-formatted string
            grabAll[prop] = Output.stringify(grabAll[prop]);

            // Check to see that we've done an inject before and that the
            // property wasn't one  that shouldn't have been overridden, and
            // that either the property wasn't in the last extraction or that
            // the value of the property has changed.
            if (CanvasOutput.lastGrab && externalProps[prop] !== false &&
                    (!(prop in CanvasOutput.lastGrab) ||
                    grabAll[prop] != CanvasOutput.lastGrab[prop])) {
                // The code to inject the newly-defined (or changed) variable
                inject += "var " + prop + " = " + grabAll[prop] + ";\n";
            }
        }

        // Make sure that deleted variables are removed.
        // Go through all the previously-defined properties and check to see
        // if they've been removed.
        for (var oldProp in CanvasOutput.lastGrab) {
            // If the property doesn't exist in this grab extraction and
            // the property isn't a Processing.js-defined property
            // (e.g. don't delete 'background') but allow the 'draw' function to
            // be deleted (as it's user-defined)
            if (!(oldProp in grabAll) &&
                    (!(oldProp in CanvasOutput.props) || oldProp === "draw")) {
                // Create the code to delete the variable
                inject += "delete Output.context." + oldProp + ";\n";

                // If the draw function was deleted we also
                // need to clear the display
                if (oldProp === "draw") {
                    CanvasOutput.clear();
                }
            }
        }

        // Make sure the matrix is always reset
        Output.context.resetMatrix();

        // Make sure the various draw styles are also reset
        // if they were just removed
        if (CanvasOutput.lastGrab) {
            // Reset the background to its default if one wasn't specified
            if (!grabAll.background && CanvasOutput.lastGrab.background) {
                CanvasOutput.resetBackground();
            }

            // Reset the stroke to its default if one wasn't specified
            if (!grabAll.stroke && CanvasOutput.lastGrab.stroke) {
                CanvasOutput.resetStroke();
            }

            // Reset the strokeWeight to its default if one wasn't specified
            if (!grabAll.strokeWeight && CanvasOutput.lastGrab.strokeWeight) {
                CanvasOutput.resetStrokeWeight();
            }

            // Reset the fill to its default if one wasn't specified
            if (!grabAll.fill && CanvasOutput.lastGrab.fill) {
                CanvasOutput.resetFill();
            }
        }

        // Re-run the entire program if we don't need to inject the changes
        // (Injection only needs to occur if a draw loop exists and if a prior
        // run took place)
        if (Output.context.draw === CanvasOutput.DUMMY ||
                !CanvasOutput.lastGrab) {
            // Clear the output if no injection is occurring
            CanvasOutput.clear();

            // Run the code as normal
            Output.exec(userCode, Output.context);

        // Otherwise if there is code to inject
        } else if (inject) {
            // Execute the injected code
            Output.exec(inject, Output.context);
        }

        // Need to make sure that the draw function is never deleted
        // (Otherwise Processing.js starts to freak out)
        if (!Output.context.draw) {
            Output.context.draw = CanvasOutput.DUMMY;
        }

        // Save the extracted variables for later comparison
        CanvasOutput.lastGrab = grabAll;

        if (callback) {
            callback();
        }
    },

    restart: function() {
        CanvasOutput.lastGrab = null;
        CanvasOutput.runCode(Output.getUserCode());
    },

    testContext: {
        testCanvas: function(name, fn) {
            Output.testContext.test(name, fn, CanvasOutput);
        }
    },

    toggle: function(doToggle) {
        if (doToggle) {
            CanvasOutput.start();

        } else {
            CanvasOutput.stop();
        }
    },

    stop: function() {
        CanvasOutput.canvas.noLoop();
    },

    start: function() {
        CanvasOutput.canvas.loop();
    },

    clear: function() {
        CanvasOutput.resetStrokeWeight();
        CanvasOutput.resetStroke();
        CanvasOutput.resetBackground();
        CanvasOutput.resetFill();
    },

    resetStroke: function() {
        if (Output.dark) {
            CanvasOutput.canvas.stroke(255, 255, 255);
        } else {
            CanvasOutput.canvas.stroke(0, 0, 0);
        }
    },

    resetStrokeWeight: function() {
        CanvasOutput.canvas.strokeWeight(1);
    },

    resetBackground: function() {
        if (Output.dark) {
            CanvasOutput.canvas.background(15, 15, 15);
        } else {
            CanvasOutput.canvas.background(255);
        }
    },

    resetFill: function() {
        if (Output.dark) {
            CanvasOutput.canvas.fill(15, 15, 15);
        } else {
            CanvasOutput.canvas.fill(255, 255, 255);
        }
    },

    kill: function() {
        CanvasOutput.canvas.exit();
        CanvasOutput.$elem.hide();
    }
};

Output.registerOutput(CanvasOutput);

var clean = function(str) {
    return String(str).replace(/</g, "&lt;");
};

Output.worker = {
    firstRun: true,

    exec: function(userCode, context, callback) {
        Output.worker.stop();

        var worker = Output.worker.worker = new window.Worker("/javascript/scratchpads-package/worker.js");

        worker.onmessage = function(event) {
            if (event.data.type === "end") {
                Output.worker.stop();
                callback(userCode);

            } else if (event.data.type === "error") {
                Output.handleError(event.data);
            }
        };

        worker.onerror = Output.handleError;

        // For the first run of the code increase the delay considerably.
        // Browsers tend to be processing a number of different things on load
        // which slows down overall execution time, thus increase the delay for load.
        var timeoutDelay = Output.worker.firstRun ? 5000 : 500;

        // If the thread doesn't finish executing quickly, kill it and
        // don't execute the code
        Output.worker.timeout = window.setTimeout(function() {
            Output.handleError({
                message: "The program is taking too long to run. Perhaps you have a mistake in your code?"
            });
        }, timeoutDelay);

        worker.postMessage({
            code: userCode,
            context: context
        });

        Output.worker.firstRun = false;
    },

    /*
     * Calling this will stop execution of any currently running worker
     * Will return true if a worker was running, false if one was not.
     */
    stop: function() {
        if (Output.worker.timeout) {
            window.clearTimeout(Output.worker.timeout);
            Output.worker.timeout = null;
        }

        if (Output.worker.worker) {
            Output.worker.worker.terminate();
            Output.worker.worker = null;
            return true;
        }

        return false;
    }
};

})();
