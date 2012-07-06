self.onmessage = function(event) {
    var data = event.data,
        grabAll = data.context,
        code = "with(arguments[0]){\n" +
            data.code +
            "\nif (typeof draw !== 'undefined' && draw){draw();}}",
        runtimeCost = 0,
        drawMethods = ["background", "bezier", "curve", "ellipse", "line", "quad", "rect", "triangle", "vertex", "text"],
        willDraw = {},
        drawCount = function(name) {
           runtimeCost += willDraw[name] ? 1 : 0.1;
        };

    for (var i = 0; i < drawMethods.length; i++) {
        willDraw[drawMethods[i]] = true;
    }

    // TODO: Export a list of function calls back to the main window
    for (var prop in grabAll) (function(prop) {
        grabAll[prop] = (grabAll[prop] === "__STUBBED_FUNCTION__" ?
            function() { drawCount(prop); } :
            grabAll[prop]);
    })(prop);

    // Execute the code and the drawing function, at least once
    // TODO: Run other functions that execute on event (mousePressed, etc.)
    (new Function(code)).call({}, data.context);

    // Cap the maximum number of function calls
    // Score 1 for the popular function calls that draw to the screen
    // Score 0.1 for every other function calls
    // Max determined rather arbitrarily, higher than this seems too complex for most simple programs
    if (runtimeCost > 16000) {
        self.postMessage({
            type: "error",
            message: "The program is taking too long to run. " +
                "Perhaps you could try and make it a bit simpler?"
        });

    } else {
        self.postMessage({ type: "end" });
    }
};
