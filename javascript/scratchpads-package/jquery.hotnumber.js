(function() {
    var oldValue, range, firstNum, scrubber, colorPicker, curPicker, handle, ignore = false;

    $.fn.hotNumber = function(reload) {
        var editor = this.data("editor").editor,
            selection = editor.session.selection;

        if (reload) {
            checkNumber.call(editor);

        } else {
            selection.on("changeCursor", $.proxy(checkNumber, editor));
            selection.on("changeSelection", $.proxy(checkNumber, editor));

            editor.renderer.scrollBar.addEventListener("scroll", function() {
                if (curPicker) {
                    updatePos(editor);
                }
            });

            attachPicker(editor);
            attachScrubber(editor);
        }

        Record.handlers.hot = function(e) {
            update(editor, e.hot);
            updatePos(editor);
        };

        return this;
    };

    function attachScrubber(editor) {
        if (!scrubber) {
            scrubber = $("<div class='hotnumber'><div class='scrubber'></div><div class='arrow'></div>")
                .appendTo("body")
                .find(".scrubber")
                    .append(
                        $("<div class='scrubber-handle'/>")
                            .text("◄ ◆ ►")
                            .draggable({
                                drag: function() {
                                    scrubber.addClass("dragging");

                                    var thisOffset = $(this).offset();
                                    var parentOffset = $(this).parent().offset();
                                    var dx = thisOffset.left - parentOffset.left;
                                    var dy = parentOffset.top - thisOffset.top;
                                    var powerOfTen = Math.round(dy / 50.0);
                                    if (powerOfTen < -5) powerOfTen = -5;
                                    if (powerOfTen > 5) powerOfTen = 5;

                                    if (handle) {
                                        handle(Math.round(dx / 2.0) * Math.pow(10, powerOfTen));
                                    }
                                },
                                stop: function() {
                                    scrubber.removeClass("dragging");

                                    $(this).css({
                                        left: 0,
                                        top: 0
                                    });
                                    checkNumber.call(editor);
                                }
                            })
                    )
                    .end()
                .hide();
        }
    }

    function attachPicker(editor) {
        if (!colorPicker) {
            colorPicker = $("<div class='hotnumber picker'><div id='hotpicker' class='picker'></div><div class='arrow'></div>")
                .appendTo("body")
                .find(".picker").ColorPicker({
                    flat: true,
                    onChange: function(hsb, hex, rgb) {
                        if (handle) {
                            handle(rgb);
                        }
                    }
                }).end()
                .bind("mouseleave", function() {
                    var pos = editor.selection.getCursor(),
                        coords = editor.renderer.textToScreenCoordinates(pos.row,
                            editor.session.getDocument().getLine(pos.row).length);

                    $(this).css({ top: $(window).scrollTop() + coords.pageY, left: coords.pageX });
                })
                .hide();
        }
    }

    function checkNumber() {
        if (ignore) {
            return;
        }

        range = null;

        var editor = this,
            pos = editor.selection.getCursor(),
            line = editor.session.getDocument().getLine(pos.row),
            prefix = line.slice(0, pos.column),
            oldPicker = curPicker, newPicker;

        if (/\b(?:background|fill|stroke)\(\s*([\s\d,]*)\s*$/.test(prefix)) {
            var before = pos.column - RegExp.$1.length;

            if (/^\s*([\s\d,]*?)\s*(\)|$)/.test(line.slice(before))) {
                var Range = require("ace/range").Range;

                oldValue = RegExp.$1;
                range = new Range(pos.row, before, pos.row, before + oldValue.length);

                // Insert a); if one doesn't exist
                // Makes it easier to quickly insert a color
                // TODO: Maybe we should do this for more methods?
                if (RegExp.$2.length === 0) {
                    ignore = true;

                    Record.pauseLog();

                    editor.session.getDocument().insertInLine({ row: pos.row, column: line.length },
                        (oldValue ? "" : (oldValue = "255, 0, 0")) + ");");
                    editor.selection.setSelectionRange(range);
                    editor.selection.clearSelection();

                    Record.resumeLog();

                    ignore = false;
                }

                handle = function(value) {
                    updateColorSlider(editor, value);
                };

                newPicker = colorPicker;
            }

        } else {
            var before = pos.column - (/([\d.-]+)$/.test(prefix) ? RegExp.$1.length : 0);

            if (/^([\d.-]+)/.test(line.slice(before)) && !isNaN(parseFloat(RegExp.$1))) {
                var Range = require("ace/range").Range;

                oldValue = RegExp.$1;
                firstNum = parseFloat(oldValue);
                range = new Range(pos.row, before, pos.row, before + oldValue.length);

                handle = function(value) {
                    updateNumberScrubber(editor, value);
                };

                newPicker = scrubber;
            }
        }

        if (oldPicker && oldPicker !== newPicker) {
            oldPicker.hide();
        }

        if (newPicker) {
            curPicker = newPicker;
            updatePos(editor);
        } else {
            curPicker = null;
        }
    }

    function updatePos(editor) {
        var pos = editor.selection.getCursor(),
            offset = editor.renderer.scroller.getBoundingClientRect(),
            coords = editor.renderer.textToScreenCoordinates(pos.row,
                curPicker === colorPicker ? editor.session.getDocument().getLine(pos.row).length : pos.column),
            relativePos = coords.pageY - offset.top;

        curPicker
            .css({ top: $(window).scrollTop() + coords.pageY, left: coords.pageX })
            .toggle(!(relativePos < 0 || relativePos >= offset.height));

        if (curPicker === colorPicker) {
            var colors = oldValue.replace(/\s/, "").split(",");

            colorPicker.find(".picker").ColorPickerSetColor(colors.length === 3 ?
                { r: parseFloat(colors[0]), g: parseFloat(colors[1]), b: parseFloat(colors[2]) } :
                colors.length === 1 && !colors[0] ?
                    { r: 255, g: 0, b: 0 } :
                    { r: parseFloat(colors[0]), g: parseFloat(colors[0]), b: parseFloat(colors[0]) });
        }
    }

    function updateColorSlider(editor, rgb) {
        if (!range) {
            return;
        }

        // Replace the old color with the new one
        update(editor, rgb.r + ", " + rgb.g + ", " + rgb.b);
    }

    function updateNumberScrubber(editor, newNum) {
        if (!range) {
            return;
        }

        newNum = firstNum + newNum;

        var newNumString = newNum.toString();
        var fixed = newNum.toFixed(5);

        // Using a really small interval (1e-5), we start hitting float
        // precision issues during addition/subtraction, so cap the number of
        // digits after the decimal
        if (fixed.length < newNumString.length) {
            newNumString = fixed;
        }
        // Replace the old number with the new one
        update(editor, newNumString);
    }

    function update(editor, newValue) {
        ignore = true;

        Record.pauseLog();

        // Insert the new number
        range.end.column = range.start.column + oldValue.length;
        editor.session.replace(range, newValue);

        // Select and focus the updated number
        range.end.column = range.start.column + newValue.length;
        editor.selection.setSelectionRange(range);
        editor.focus();

        Record.resumeLog();

        Record.log({ hot: newValue });

        ignore = false;
        oldValue = newValue;
    }
})();
