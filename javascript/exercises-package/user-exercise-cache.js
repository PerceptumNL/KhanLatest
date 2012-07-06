/**
 * UserExerciseCache is responsible for holding onto
 * and updating all userExercise objects, and it
 * passes them on to khan-exercises when khan-exercises
 * needs 'em.
 *
 * TODO(david)(or anybody): Write unit tests for this thing!
 */
(function() {

// Adapted from a comment on http://mathiasbynens.be/notes/localstorage-pattern
function testSessionStorage() {
    var enabled, uid = +(new Date);
    try {
        sessionStorage[uid] = uid;
        enabled = (sessionStorage[uid] == uid);
        sessionStorage.removeItem(uid);
        return enabled;
    } catch (e) {
        return false;
    }
}

Exercises.UserExerciseCache = {

    sessionStorageEnabled: null,

    // Private cache of userExercise objects for
    // each exercise we encounter
    _userExerciseCache: {},

    init: function(userExercises) {

        var self = this;

        this.sessionStorageEnabled = testSessionStorage();

        // Cache initial userExercise objects sent down on page load
        _.each(userExercises, this.cacheLocally, this);

        $(Khan)
            .one("newProblem", function() {
                // Delay the potential one-time warning until after khan-exercises
                // is all set up
                if (!self.sessionStorageEnabled) {
                    self.warnSessionStorageDisabled();
                }
            })
            .bind("updateUserExercise", function(ev, userExercise) {
                // Any time khan-exercises tells us it has new
                // updateUserExercise data, update cache if it's more recent
                self.cacheLocally(userExercise);
            })
            .bind("attemptError", function(ev, userExercise) {
                // Something went wrong w/ the /attempt API request.
                // Clear the cache so we get a fresh userExercise on reload.
                self.clearCache(userExercise);
            })
            .bind("problemDone", function() {

                // Whenever a problem is completed, we may be waiting for
                // a while for the /attempt callback to finish and send us the
                // server's updated userExercise data. So we cheat a bit and
                // bump up the just-finished userExercises's totalDone count
                // here in case we run into it again before the ajax call
                // returns.
                // TODO(david): Make this file not have to know about the main
                //     Exercises object by passing exerciseName with the event
                //     firing.
                var currentExercise = Exercises.currentCard.get("exerciseName"),
                    userExercise = self.get(currentExercise);

                if (userExercise) {
                    userExercise.totalDone += 1;
                    self.cacheLocally(userExercise);
                }

            });

    },

    warnSessionStorageDisabled: function() {
        $(Exercises).trigger("warning", {
            text: "You must enable DOM storage in your browser; see <a href='https://sites.google.com/a/khanacademy.org/forge/for-developers/how-to-enable-dom-storage'>here</a> for instructions.",
            showClose: false
        });
    },

    get: function(exerciseName) {
        return this._userExerciseCache[exerciseName];
    },

    /**
     * Gets the cache key for storing a userExercise.
     * @param {UserExercise} userExercise The object to get the cache key from.
     * @return {string} The cache key for the associated userExercise object.
     */
    cacheKey: function(userExercise) {
        return "userexercise:" + userExercise.user + ":" +
            userExercise.exercise;
    },

    cacheLocally: function(userExercise) {

        if (!userExercise) {
            return;
        }

        var cachedUserExercise = this.get(userExercise.exercise);

        // If we don't have a cached version yet, check session storage
        if (!cachedUserExercise && this.sessionStorageEnabled) {

            var data = window.sessionStorage[this.cacheKey(userExercise)];
            if (data) {
                // Found data in session storage, use as currently cached val.
                cachedUserExercise = JSON.parse(data);
                this._userExerciseCache[userExercise.exercise] = cachedUserExercise;
            }

        }

        // Update cache, if new data is more recent
        if (!cachedUserExercise || (userExercise.totalDone >= cachedUserExercise.totalDone)) {

            this._userExerciseCache[userExercise.exercise] = userExercise;

            // Persist to session storage so we get nice back button behavior
            if (this.sessionStorageEnabled) {
                window.sessionStorage[this.cacheKey(userExercise)] =
                    JSON.stringify(userExercise);
            }

            $(Exercises).trigger("newUserExerciseData", {exerciseName: userExercise.exercise});
        }

    },

    clearCache: function(userExercise) {

        if (!userExercise) {
            return;
        }

        // Before we reload after an error, clear out sessionStorage.
        // If there' a discrepancy between server and sessionStorage such that
        // problem numbers are out of order or anything else, we want
        // to restart with whatever the server sends back on reload.
        delete this._userExerciseCache[userExercise.exercise];

        if (this.sessionStorageEnabled) {
            delete window.sessionStorage[this.cacheKey(userExercise)];
        }

    }

};

})();
