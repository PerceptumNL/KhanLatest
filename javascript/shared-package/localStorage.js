/**
 * LocalStore is a *super* simple abstraction around localStorage for easy
 * get/set/delete. We may end up wanting something more powerful like
 * BankersBox, but for now this is much lighter weight.
 *
 * If you ever need to completely wipe LocalStore for *all* users when,
 * say, changing the format of data being cached, just bump up the "version"
 * property below.
 */
var LocalStore = {

    // Bump up "version" any time you want to completely wipe LocalStore results.
    // This lets us expire values on all users' LocalStores when deploying
    // a new version, if necessary.
    version: 4,

    keyPrefix: "ka",

    cacheKey: function(key) {
        if (!key) {
            throw "Attempting to use LocalStore without a key";
        }

        return [this.keyPrefix, this.version, key].join(":");
    },

    /**
     * Get whatever data was associated with key. Returns null if no data is
     * associated with the key, regardless of key's value (null, undefined, "monkey").
     */
    get: function(key) {
        var data = window.localStorage[LocalStore.cacheKey(key)];

        if (data) {
            return JSON.parse(data);
        }

        return null;
    },

    /**
     * Store data associated with key in localStorage
     */
    set: function(key, data) {

        var stringified = JSON.stringify(data),
            cacheKey = LocalStore.cacheKey(key);

        try {
            window.localStorage[cacheKey] = stringified;
        } catch (e) {
            // If we had trouble storing in localStorage, we may've run over
            // the browser's 5MB limit. This should be rare, but when hit, clear
            // everything out.
            LocalStore.clearAll();
        }
    },

    /**
     * Delete whatever data was associated with key
     */
    del: function(key) {
        delete window.localStorage[this.cacheKey(key)];
    },

    /**
     * Delete all cached objects from localStorage
     */
    clearAll: function() {
        var i = 0;
        while (i < localStorage.length) {
            var key = localStorage.key(i);
            if (key.indexOf(LocalStore.keyPrefix + ":") === 0) {
                delete localStorage[key];
            } else {
                i++;
            }
        }
    }

};
