var ScratchpadUI = {
    // player holds the SoundManager object
    player: null,

    // track holds the track data from SoundCloud
    track: null,

    // key used to persist new scratchpads in localStorage
    localStorageKey: "cs-scratchpad-new",

    scratchpad: new Scratchpad({
        title: "New Scratchpad",
        category: null,
        difficulty: null,
        revision: new ScratchpadRevision({
            code: ""
        })
    })

    // TODO(jlfwong): Move init and all of the helper functions in here as well
};

(function() {

var DEBUG = false;

/*
 * Initialize SoundCloud and SoundManager for audio playback
 *
 * TODO(jlfwong): Move this somewhere else
 */

soundManager.url = "/soundmanager/";
soundManager.debugMode = false;

// Disable this callback function in SoundCloud, it throws errors (not sure why)
Recorder.realStop = Recorder.stop;
Recorder.stop = function() {};

// Make sure SoundCloud writes to localStorage to save repeated login attempts
SC.storage = function() {
    return window.localStorage;
};

SC.initialize({
    client_id: window.KA_IS_DEV ?
        "82ff867e7207d75bc8bbd3d281d74bf4" :
        "3f0c48a9e159d0610cae89b55f39751e",
    redirect_uri: window.location.href
        .replace(/explore\/.*$/, "explore/soundcloud-callback")
});

ScratchpadUI.init = function() {
    /*
     * Initialize the editor and canvas drawing area
     */

    var editor = new Editor("editor");
    Canvas.init();

    $("#editor")
        .data("editor", editor)
        .hotNumber();

    editor.editor.setFontSize("14px");
    editor.editor.setHighlightSelectedWord(false);

    editor.editor.renderer.setShowGutter(false);
    editor.editor.renderer.setShowPrintMargin(false);

    /*
     * Initialize content.
     */

     // Set up color button handling
     $(".toolbar a.color").each(function() {
         $(this).addClass("ui-button").children().css("background", this.id);
     });

    // Set up toolbar buttons
    $(document).buttonize();

    // Set up the playback progress bar
    $("#progress").slider({
        range: "min",
        value: 0,
        min: 0,
        max: 100
    });

    // Remove some extraneous classes from container boxes
    $("#editor-box, #output-box")
        .removeClass("ui-tabs-panel ui-corner-bottom");

    // Add a scratch class to make styling easier
    $(".content").addClass("scratch");

    /*
     * Bind events.
     */

    // Make sure that disabled buttons can't still be used
    $(document).delegate(".simple-button.disabled", "click", function(e) {
        e.stopImmediatePropagation();
        return false;
    });

    // Handle color button clicks during recording
    $(document).delegate(".toolbar a.color", "buttonClick", function() {
        Canvas.setColor(this.id);
        focusEditor();
    });

    // Handle the play button
    $(document).delegate("#play", "click", function() {
        if (Record.playing) {
            Record.pausePlayback();
        } else {
            Record.play();
        }
    });

    // Handle the clear button click during recording
    $(document).delegate("#clear", "buttonClick", function() {
        Canvas.clear();
        Canvas.endDraw();
        focusEditor();
    });

    // Handle the clear button
    $(document).delegate("#record", "click", function() {
        // If we're already recording, stop
        if (Record.recording) {
            Record.stopRecord();

        } else {
            var saveCode = $("#editor").editorText();

            // You must have some code in the editor before you start recording
            // otherwise the student will be starting with a blank editor, which
            // is confusing
            if (!saveCode) {
                var dialog = $("<div></div>")
                    .dialog({ modal: true });

                dialog.html("<strong>There is no code in the editor!</strong>" +
                    "<p>The student won't see anything when they first see the scratchpad, you should enter some code.</p>");

            } else {
                // Start recording the presenter's audio
                connectAudio(function() {
                    SC.record({
                        start: function() {
                            // Save the initial code state
                            ScratchpadUI.scratchpad.get("revision")
                                .set("code", $("#editor").editorText());

                            // Reset the cursor to the start
                            setCursor({ row: 0, column: 0 });

                            // Focus on the editor
                            focusEditor();

                            // Start recording
                            Record.record();
                        }
                    });
                });
            }
        }

        focusEditor();
    });

    $(document).delegate("#delete-scratchpad-button", "click", function() {
        var $dialog = $("<div/>")
            .text(
                "Are you sure you want to delete this Scratchpad? " +
                "This can't be undone."
            )
            .dialog({
                closeOnEscape: false,
                modal: true,
                title: "Delete this Scratchpad?",
                buttons: [
                    {
                        text: "Cancel",
                        click: function() {
                            $(this).dialog("close");
                        }
                    },
                    {
                        text: "Delete",
                        click: function() {
                            $dialog.dialog("option", {
                                title: "Deleting...",
                                buttons: {}
                            }).text(
                                "Deleting scratchpad. You'll be redirected " +
                                "when it's done."
                            );

                            ScratchpadUI.scratchpad.destroy({
                                success: function() {
                                    window.location.href = "/explore";
                                },
                                error: function() {
                                    $dialog.dialog("option", {
                                        title: "Deletion Failed.",
                                        buttons: [{
                                            text: "Okay"
                                        }]
                                    }).html(
                                        "Something went wrong and we " +
                                        "couldn't delete the scratchpad. " +
                                        "Please try again!"
                                    );
                                }
                            });
                        }
                    }
                ]
            })
            .parent()
                .addClass("ui-dialog-no-close-button")
            .end();
    });

    $(document).delegate("#dev-settings-button", "click", function() {
        $("#dev-controls-modal").dialog({
            title: "Developer-only Settings",
            buttons: {
                "Done!": function() {
                    $(this).dialog("close");
                }
            }
        });
    });

    // Handle the restart button
    $(document).delegate("#restart-code", "click", function() {
        Output.restart();
        Record.log({ restart: true });
    });

    // Handle the save and fork buttons
    $(document).delegate("#save-button, #fork-button", "click", function() {
        $("#save-button, #fork-button").addClass("disabled");

        var scratchpad = ScratchpadUI.scratchpad;
        var revision = scratchpad.get("revision");

        var fork = $(this).is("#fork-button");

        // Show a dialog to let the user know that saving is happening
        // TODO(jeresig): Show some kind of progress indicator
        var dialog = $("<div/>")
            .dialog({
                closeOnEscape: false,
                modal: true
            })
            .parent()
                .addClass("ui-dialog-no-close-button")
            .end();

        if (fork) {
            var changeTitlePrompt = $("<div/>")
                .append($("<input/>", {val: scratchpad.get("title")}))
                .appendTo(dialog);

            dialog.dialog("option", {
                title: "Save As...",
                buttons: {
                    "Save" : function() {
                        var newTitle = changeTitlePrompt
                            .children("input").val();

                        if (!newTitle) {
                            return;
                        }

                        scratchpad.set("title", newTitle);
                        changeTitlePrompt.remove();
                        validate();
                    },

                    "Cancel" : function() {
                        dialog.dialog("close");
                    }
                },
                close: function() {
                    $("#save-button, #fork-button")
                        .removeClass("disabled");
                }
            });

            changeTitlePrompt.children("input").focus().select();
        } else {
            validate();
        }

        function validate() {
            // If a recording was done was use the initial, cached, code
            // otherwise we use the current code in the editor
            var saveCode = Record.recorded ? revision.get("code") :
                $("#editor").editorText();

            // If no code is provided, show an error message
            if (!saveCode) {
                showError("<strong>Whoops!</strong><p>You aren't saving any code, you should enter some code to save!</p>");
                return;
            }

            // If the user is a developer and is saving a tutorial or official exploration,
            // warn them that their scratchpad won't be listed on the main page.
            var user = ENV.user;
            var category = $("#scratchpad-category [name=category]:checked").val();
            var difficulty = $("#scratchpad-difficulty-select").val();
            if (user && user.developer &&
                    (category === "tutorial" || category === "official") &&
                    difficulty === "-1") {
                dialog.html("You are about to save an official scratchpad without a difficulty! " +
                    "Your scratchpad will not be listed on the main exploration page.");

                dialog.dialog("option", {
                    title: "Warning!!",
                    buttons: {
                        "Cancel" : function() {
                            dialog.dialog("close");
                        },
                        "Don't care. Save Anyways!!" : function() {
                            checkForRecording();
                        }
                    },
                    close: function() {
                        $("#save-button, #fork-button")
                            .removeClass("disabled");
                    }
                });
                return;
            }

            checkForRecording();
        }

        function checkForRecording() {
            dialog.dialog("option", {
                title: "Saving...",
                buttons: {}
            });

            // If no recording was made, just save the results
            if (!Record.recorded) {
                save();
                return;
            }

            // If we're already authorized by SoundCloud, just upload
            if (SC.accessToken()) {
                uploadAudio();

            // Otherwise get authorization and then upload
            } else {
                dialog.html("Authorizing with SoundCloud...");
                SC.connect(uploadAudio);
            }
        }

        // Upload the audio recording to SoundCloud
        function uploadAudio() {
            dialog.html("Uploading recording to SoundCloud...");

            SC.recordUpload(
                {
                    track: {
                        // Genre and tags picked rather arbitrarily
                        genre: "Khan Academy Code",
                        tags: "KhanAcademyCode",
                        sharing: "public",
                        track_type: "spoken",
                        description: "",
                        title: scratchpad.get("title"),
                        license: "cc-by-nc-sa"
                    }
                },
                function(response, error) {
                    if (response) {
                        // When we get a response back from the server
                        // add the SoundCloud ID to the exercise and save
                        revision.set("audio_id", response.id);
                        save();

                    // Show error message if something bad happened
                    } else {
                        showError("Error saving recording to SoundCloud. Please try again!");
                    }
                }
           );
        }

        // Save the data and recording to the server
        function save() {
            dialog.html("Saving Scratchpad...");

            // We cache this result before we save to determine if it's a new
            // scratchpad being saved or a pre-existing one.
            var isNewScratchpad = scratchpad.isNew();

            // Save the final results to the server
            saveScratchpadRevision({
                fork: fork,
                success: function(savedScratchpad) {
                    // If a new scratchpad was just saved, clear the
                    // localStorage cache
                    if (isNewScratchpad) {
                        window.localStorage.removeItem(
                            ScratchpadUI.localStorageKey);
                    }

                    // Redirect the user to the newly saved scratchpad.
                    dialog.html("Saved! Loading scratchpad...");
                    window.location.href = savedScratchpad.showUrl();
                },
                error: function() {
                    showError("Error saving scratchpad to the server. Please try again!");
                }
            });
        }

        // Display an error message and re-enable the save button
        function showError(msg) {
            dialog.html(msg);
            dialog.dialog("option", {
                buttons: {
                    "Okay" : function() {
                        dialog.dialog("close");
                    }
                }
            });
            $("#save-button, #fork-button").removeClass("disabled");
        }
    });

    // Watch for when the user is leaving the page.
    // Used for temporarily saving a user's code when they're making a new
    // scratchpad.
    $(window).bind("beforeunload", function() {
        var scratchpad = ScratchpadUI.scratchpad;

        // Only save if we're on a new scratchpad
        if (!scratchpad.isNew()) {
            return;
        }

        // Extract current editor text
        scratchpad.get("revision").set("code", $("#editor").editorText());

        // Extract cursor position from the editor
        var cursor = {};

        // Don't save if we're debugging
        if (!window.DEBUG) {
            // Save the cached results to localStorage for later retrieval
            window.localStorage[ScratchpadUI.localStorageKey] = JSON.stringify({
                cursor: $("#editor").getCursor(),
                scratchpad: ScratchpadUI.scratchpad
            });

        }
    });

    /*
     * Bind events to Record (for recording and playback)
     * and to Canvas (for recording and playback)
     */

    $(Record).bind({
        // Playback of a recording has begun
        playStarted: function(e, resume) {
            // We're starting over so reset the editor and
            // canvas to its initial state
            if (!resume) {
                // Reset the editor
                $("#editor").editorText(
                    ScratchpadUI.scratchpad.get("revision").get("code"));

                setCursor({ row: 0, column: 0 });
                focusEditor();

                // Clear and hide the drawing area
                Canvas.clear(true);
                Canvas.endDraw();
            }

            // During playback disable the restart button
            $("#restart-code").addClass("disabled");

            // Turn on playback-related styling
            $("html").addClass("playing");

            // Show an invisible overlay that blocks interactions with the
            // editor and canvas areas (preventing the user from being able to
            // disturb playback)
            $("#canvas-editor .disable-overlay").show();

            // Activate the play button
            $("#play").addClass("ui-state-active")
                .find(".ui-icon")
                    .removeClass("ui-icon-play").addClass("ui-icon-pause");
        },

        // Playback of a recording has been paused
        playPaused: function() {
            // Turn off playback-related styling
            $("html").removeClass("playing");

            // Disable the blocking overlay
            $("#canvas-editor .disable-overlay").hide();

            // Allow the user to restart the code again
            $("#restart-code").removeClass("disabled");

            // Deactivate the play button
            $("#play").removeClass("ui-state-active")
                .find(".ui-icon")
                    .addClass("ui-icon-play").removeClass("ui-icon-pause");
        },

        // Recording has begun
        recordStarted: function() {
            $("#draw-widgets").show();

            // Reset the canvas to its initial state
            Canvas.clear(true);
            Canvas.endDraw();

            // Disable the save button
            $("#save-button, #fork-button").addClass("disabled");

            // Activate the recording button
            $("#record").addClass("toggled");
        },

        // Recording has ended
        recordEnded: function() {
            // Stop the SoundCloud recording
            Recorder.realStop();

            // Re-enable the save button
            $("#save-button, #fork-button").removeClass("disabled");

            // Disable the record button
            $("#record").removeClass("toggled").addClass("disabled");

            // Show an invisible overlay that blocks interactions with the
            // editor and canvas areas (preventing the user from being able to
            // disturb the recording)
            $("#canvas-editor .disable-overlay").show();

            // Turn on playback-related styling (hides hot numbers, for example)
            $("html").addClass("playing");

            // Prevent the editor from being changed
            $("#editor").data("editor").editor.setReadOnly(true);

            $("#draw-widgets").hide();

            // Reset the canvas to its initial state
            Canvas.clear(true);
            Canvas.endDraw();
        }
    });

    $(Canvas).bind({
        // Drawing has started
        drawStarted: function() {
            // Activate the canvas
            $("#canvas").addClass("canvas");

            // Activate the drawing button
            $("#draw").addClass("ui-state-active");
        },

        // Drawing has ended
        drawEnded: function() {
            // Hide the canvas
            $("#canvas").removeClass("canvas");

            // Deactivate the drawing button
            $("#draw").removeClass("ui-state-active");
        },

        // A color has been chosen
        colorSet: function(e, color) {
            // Deactivate all the color buttons
            $("a.color").removeClass("ui-state-active");

            // If a new color has actually been chosen
            if (color != null) {
                // Select that color and activate the button
                $("#" + color).addClass("ui-state-active");
            }
        }
    });

    // When a restart occurs during playback, restart the output
    Record.handlers.restart = function() {
        var $restart = $("#restart-code");

        if (!$restart.hasClass("hilite")) {
            $restart.addClass("hilite green");
            setTimeout(function() {
                $restart.removeClass("hilite green");
            }, 300);
        }

        Output.restart();
    };

    if (ENV.scratchpad) {
        // Display a saved Scratchpad
        var scratchpad = ScratchpadUI.scratchpad;

        // We pipe the boostrapped data through the Scratchpad's parse so that
        // it acts exactly as if it had been fetched from the server
        scratchpad.set(scratchpad.parse(ENV.scratchpad));

        // Load the recording playback commands as well, if applicable
        Record.commands = scratchpad.get("revision").get("recording");
    }

    // Start the scratchpad display
    startScratch();
};

/*
 * Load a Scratchpad into the site and make it editable
 */
var startScratch = function() {
    // If an audio track is provided, load the track data
    // and load the audio player as well
    var user = ENV.user;
    var scratchpad = ScratchpadUI.scratchpad;
    var cursor = { row: 0, col: 0 };

    if (scratchpad.isNew()) {
        // Load saved data from localStorage
        var results = JSON.parse(
            window.localStorage[ScratchpadUI.localStorageKey] || null);
        if (results) {
            scratchpad.set(scratchpad.parse(results.scratchpad));
            cursor = results.cursor;
        }
    }

    // This has to be after the load from localStorage, because the reference to
    // revision might go stale otherwise
    var revision = scratchpad.get("revision");

    if (revision.get("audio_id")) {
        connectAudio(function(data) {
            ScratchpadUI.track = data;
            audioInit();
        });
    }

    // Hook in the execution enviroment
    Output.init();

    // Load the text into the editor and set the cursor
    $("#editor").editorText(revision.get("code") || "");

    // Focus on the editor
    focusEditor();

    // Restore the cursor position
    $("#editor").setCursor(cursor);

    // Hide the overlay
    $("#page-overlay").hide();

    // TODO(jeresig): hotNumber initializes in the wrong position
    // this should be changed to wait until rendering of Ace is complete
    setTimeout(function() {
        $("#editor").hotNumber(true);
    }, 100);

    // Start with a dummy scratchpad title
    if (!scratchpad.get("title")) {
        scratchpad.set("title", "New Scratchpad");
    }

    // If the user is a developer...
    if (user && user.developer) {
        // Provide the ability to make a scratchpad an official tutorial or
        // a promoted one
        $("#scratchpad-category [name=category]")
            // Select the correct category
            .prop("checked", function() {
                return this.value === (scratchpad.get("category") || "");
            });

        // And allow the difficulty to be marked
        var $difficultySelect = $("#scratchpad-difficulty-select");

        // Make the default option "Difficulty" act as both the label and
        // designate a difficulty of -1 if selected
        $("<option/>")
            .val(-1)
            .text("Difficulty")
            .prop("selected", scratchpad.get("difficulty") === -1)
            .appendTo($difficultySelect);

        var difficulties = _.keys(Scratchpad.difficultyMapping).sort();
        _.each(difficulties, function(difficulty) {
            var text = Scratchpad.difficultyMapping[difficulty];
            $("<option/>")
                .val(difficulty)
                .text(text)
                // Set the currently set difficulty as selected
                .prop("selected", parseInt(difficulty, 10) ===
                    scratchpad.get("difficulty"))
                .appendTo($difficultySelect);
        });

        // Fill the youtube_id input with the current value, if any
        $("#scratchpad-youtube-id").val(scratchpad.get("youtube_id"));
    }

    // The current scratchpad can be forked as long as it isn't new
    // Exception: Tutorials cannot be forked
    if (!scratchpad.isNew() && scratchpad.get("category") !== "tutorial") {
        $("#fork-button").show();
    }

    // The current scratchpad can be saved if any of the following are true:
    //  1. It's a new scratchpad
    //  2. It's a tutorial or official scratchpad and the user is a developer
    //  3. It's a pre-existing scratchpad created by the current user
    //
    // TODO(jlfwong): Switch this to use the published flag
    // See: http://phabricator.khanacademy.org/T44
    var category = scratchpad.get("category");
    if (scratchpad.isNew() ||
       (user && user.user_id === scratchpad.get("user_id")) ||
       (user && user.developer &&
           (category === "tutorial" || category === "official"))) {
        $("#save-button").show();
    }

    var saveButtonVisible = $("#save-button").is(":visible");
    var forkButtonVisible = $("#fork-button").is(":visible");

    // Highlight the fork button if it's the only save option available
    if (forkButtonVisible && !saveButtonVisible) {
        $("#fork-button").addClass("green");
    }

    // Set up the hovercard for the author box, if there is one
    $(".author-nickname").on("mouseenter", function() {
        HoverCard.createHoverCardQtip($(this));
    });

    $(".timeago").timeago();

    // The primary container of the header
    var $titleBox = $(".title-box")
        // If a click occurs, start editing
        .click(function() {
            // If there is no way to save the changes, don't permit the
            // user to change the title.
            if (!forkButtonVisible && !saveButtonVisible) {
                return;
            }

            $input
                .val(scratchpad.get("title"))
                .show().focus().select();
            $titleBox.hide();
        })

        // Set the title
        .find("#scratchpad-title")
            .text(scratchpad.get("title"))
        .end();

    // Don't show the edit title button if the user can't update the
    // current title (since it would probably confuse them anyway)
    if (!saveButtonVisible) {
        $("#edit-title").hide();
        $titleBox.css("cursor", "auto");
    }

    // Create an input for changing the title of a scratchpad
    var $input = $("<input>")
        .addClass("title")
        .hide()
        .insertAfter($titleBox)

        // Watch for when focus is lost on the input
        // Save the results at that time
        .blur(function() {
            // Set the scratchpad title in the model
            if ($input.val().length > 0) {
                scratchpad.set("title", $input.val());
            }

            // If this is not a new scratchpad, show the header again
            if (!scratchpad.isNew()) {
                $titleBox
                    .show()
                    .find("#scratchpad-title")
                        .text(scratchpad.get("title"));

                $input.hide();
            }
        })

        // Or watch for when 'Enter' is hit
        .keypress(function(e) {
            // Enter hit
            if (e.which === 13) {
                $input.trigger("blur");
                e.preventDefault();
             }
         });

    // If we're dealing with a new scratchpad then the title is always editable
    if (scratchpad.isNew()) {
        $titleBox.click();
    }
};

/*
 * Save Scratchpad to the server.
 * Handles creating a new scratchpad, saving a new revision of an existing
 * scratchpad, and forking an existing scratchpad.
 */
var saveScratchpadRevision = function(options) {
    // XXX(jlfwong): There will be weird behaviour here if the user logs out
    // and _then_ saves, because it'll attempt to update, but then it'll fail
    // (403 Forbidden) when it hits the server.

    // These properties are always set, regardless of whether we're creating or
    // updating
    var scratchpad = ScratchpadUI.scratchpad;
    var revision = scratchpad.get("revision");

    var currentCode = $("#editor").editorText();

    // Save the recording if a recording was just made OR
    // if no changes to the code were made (making the recording still valid)
    // TODO(jeresig): Warn the user, if the code has changed and a recording exists,
    //                that the recording will be lost.
    var saveRecording = Record.recorded || revision.get("code") === currentCode;

    revision.set({
        code: saveRecording ? revision.get("code") : currentCode,
        audio_id: saveRecording ? revision.get("audio_id") || 0 : 0,
        recording: saveRecording ? Record.commands : [],
        image_url: $("#output-canvas")[0].toDataURL("image/png")
    });

    var user = ENV.user;

    // If the user is a developer then extract and set the selected category and
    // difficulty
    if (user && user.developer) {
        var $checked = $("#scratchpad-category [name=category]:checked");
        scratchpad.set("category", $checked.val() || null);

        scratchpad.set("difficulty",
            parseInt($("#scratchpad-difficulty-select").val(), 10));
        scratchpad.set("youtube_id", $("#scratchpad-youtube-id").val());
    }

    if (options.fork) {
        scratchpad = scratchpad.fork();
    }

    scratchpad.save({}, {
        success: options.success,
        error: options.error
    });
};

/*
 * Initialize audio playback capabilities
 */

// Note: It would be really cool to make use of track.waveform_url on the progress bar
var audioInit = function() {
    var wasPlaying;

    // An empty track means that the server is still processing the audio
    if (ScratchpadUI.track.duration === 0) {
        $("#playbar")
            .show()
            .html("<span class='loading-msg'>Audio is processing, reload page in a minute." +
                "<span class='loading'></span></span>");
        return;
    }

    // Update the time left in playback of the track
    var updateTimeLeft = function(time) {
        $("#timeleft").text("-" +
            formatTime((ScratchpadUI.track.duration / 1000) - time));
    };

    // Start the play head at 0
    Record.time = 0;
    updateTimeLeft(0);

    // Add an empty command to force the Record playback to keep playing
    // until the audio track finishes playing
    if (Record.commands) {
        Record.commands.push({ time: ScratchpadUI.track.duration });
    }

    // Show the playback bar and a loading indicator
    $("#playbar")
        .show()
        .append("<span class='loading-msg'>Loading audio... " +
            "<span class='loading'></span></span>");

    var scratchpad = ScratchpadUI.scratchpad;
    var revision = scratchpad.get("revision");

    // Start loading the audio from SoundCloud
    ScratchpadUI.player = SC.stream(revision.get("audio_id").toString(), {
        // Load the audio automatically
        autoLoad: true,

        // While the audio is playing update the position on the progress bar
        // and update the time indicator
        whileplaying: function() {
            updateTimeLeft(ScratchpadUI.player.position);
            $("#progress").slider("option", "value",
                ScratchpadUI.player.position / 1000);
        },

        // Hook audio playback into Record command playback
        onplay: Record.play,
        onresume: Record.play,
        onpause: Record.pausePlayback,

        // When audio playback is complete, notify everyone listening
        // that playback is officially done
        onfinish: function() {
            $(Record).trigger("playPaused");
            $(Record).trigger("playStopped");
            $(Record).trigger("playEnded");
        }
    });

    // Wait to start playback until we at least have some
    // bytes from the server (otherwise the player breaks)
    var checkStreaming = setInterval(function() {
        // We've loaded enough to start playing
        if (ScratchpadUI.player.bytesLoaded > 0) {
            // Show the playback bar and hide the loading message
            $("#playbar .loading-msg").hide();
            $("#playbar .playarea").show();
            clearInterval(checkStreaming);
        }
    }, 16);

    // Bind events to the progress playback bar
    $("#progress").slider({
        // When a user has started dragging the slider
        start: function() {
            // Pause playback and remember if we were playing or were paused
            wasPlaying = Record.playing;
            Record.pausePlayback();
        },

        // While the user is dragging the slider
        slide: function(e, ui) {
            // Seek the player and update the time indicator
            updateTimeLeft(ui.value);
            seekTo(ui.value * 1000, true);
        },

        // When change is complete
        change: function(e, ui) {
            // Update the time indicator
            updateTimeLeft(ui.value);
        },

        // When the sliding has stopped
        stop: function(e, ui) {
            // If we were playing when we started sliding, resume playing
            if (wasPlaying) {
                Record.play();
            }
        }
    });

    // Set the duration of the progress bar based upon the track duration
    $("#progress").slider("option", "max", ScratchpadUI.track.duration / 1000);

    // Force the recording to sync to the current time of the audio playback
    Record.currentTime = function() {
        return ScratchpadUI.player.position;
    };

    // Bind events to the Record object, to track when playback events occur
    $(Record).bind({
        // When play has started
        playStarted: function() {
            // If the audio player is paused, resume playing
            if (ScratchpadUI.player.paused) {
                ScratchpadUI.player.resume();

            // Otherwise we can assume that we need to start playing from the top
            } else if (ScratchpadUI.player.playState === 0) {
                ScratchpadUI.player.play();
            }
        },

        // Pause when recording playback pauses
        playPaused: function() {
            ScratchpadUI.player.pause();
        },

        // Stop when recording playback stops (and jump back to position 0)
        playStopped: function() {
            seekTo(0);
        }
    });
};

// Utility method for formatting time in minutes/seconds
var formatTime = function(seconds) {
    var min = Math.floor(seconds / 60),
        sec = Math.round(seconds % 60);

    if (min < 0 || sec < 0) {
        min = 0;
        sec = 0;
    }

    return min + ":" + (sec < 10 ? "0" : "") + sec;
};

// Seek the player to a particular time
var seekTo = function(time, noUpdate) {
    // Optionally don't update the slider position
    // (since this triggers an event on the #progress element)
    if (!noUpdate) {
        $("#progress").slider("option", "value", time / 1000);
    }

    // Move the recording and player positions
    Record.seekTo(time);
    ScratchpadUI.player.setPosition(time);
};

// Set up the audio playback
var connectAudio = function(callback) {
    // Wait until SoundManager is loaded
    SC.whenStreamingReady(function() {
        // Wait until SoundManager thinks it's ready
        soundManager.onready(function() {
            // If we have an audio_id to access
            var scratchpad = ScratchpadUI.scratchpad;
            var revision = scratchpad.get("revision");
            var audio_id = revision.get("audio_id");

            if (audio_id) {
                // Load that track from SoundCloud
                SC.get("/tracks/" + audio_id, callback);

            // Otherwise we're ready to (probably) start recording
            } else {
                callback();
            }
        });
    });
};

window.ScratchpadGroupedListView = Backbone.View.extend({
    render: function() {
        var scratchpadGroups = this.collection
            .chain()
            // Sort using the provided key function, or just use the
            // scratchpads' natural sort order if none is provided.
            .sortBy(this.options.sortBy || _.identity)
            .reject(function(s) { return s.get("difficulty") === -1; })
            .groupBy(function(s) { return s.get("difficulty") })
            .map(function(scratchpads, difficulty) {
                // Convert each scratchpad into a plain object containing the
                // properties needed by the handlebars template.
                //
                // Because handlebars cannot do dynamic lookup without adding
                // custom helpers, we need to pass down the objects as the
                // string we want displayed.
                return {
                    difficulty: difficulty,
                    difficultyText: Scratchpad.difficultyMapping[difficulty] ||
                        "no difficulty marked",
                    scratchpads: scratchpads.map(function(s) {
                        return {
                            imageUrl: s.showUrl() + "/image.png",
                            showUrl: s.showUrl(),
                            title: s.get("title")
                        };
                    })
                };
            })
            .value();

        this.$el.html(this.template({
            scratchpadGroups: scratchpadGroups
        }));
    }
});

window.ScratchpadTutorialSidebarView = ScratchpadGroupedListView.extend({
    template: Templates.get("scratchpads.tutorial-sidebar")
});

window.ScratchpadExplorationView = ScratchpadGroupedListView.extend({
    template: Templates.get("scratchpads.explorations")
});

})();
