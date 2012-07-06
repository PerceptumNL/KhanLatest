/**
 * Tracking of return visits for logged-in, phantom, and pre-phantom users.
 */

$(function() {
    if (!window.KA) {
        return;
    }

    var returnVisitTime = 60 * 60 * 3;  // 3 hours to be return visit
    var keepCookieFor = 365 * 2;  // Keep the cookie for at most 2 years
    var frequency = 60 * 30;  // Only update at most once/30 min

    var curID = KA.getUserID();

    var encCurID = encodeURIComponent(curID);

    // cookie value: last visit time (ms since local epoch)
    var lastVisit = +readCookie("return_visits_" + encCurID);

    var curTime = KA.currentServerTime();

    if (lastVisit) {
        if (lastVisit + returnVisitTime < curTime) {
            var userType = "";
            if (!curID) {
                userType = "pre_phantom";
            } else if (KA.getUserProfile().isPhantom()) {
                userType = "phantom";
            } else {
                userType = "logged_in";
            }

            _.delay(gae_bingo.bingo,
                    30000,  // Wait 30s to let more important stuff finish
                   ["return_visit_binary",  // Core metric
                    "return_visit_count",  // Core metric
                     userType + "_return_visit_binary",  // Core metric
                     userType + "_return_visit_count"  // Core metric
                   ]);
        }
    } else {
        lastVisit = 0;  // Reset cookie (it's corrupt or not there yet)
    }

    if (lastVisit + frequency < curTime) {  // Don't update cookie too often
        createCookie("return_visits_" + encCurID, curTime, keepCookieFor);
    }
});
