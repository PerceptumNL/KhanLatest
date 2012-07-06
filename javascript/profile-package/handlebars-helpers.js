Handlebars.registerHelper("encodeURIComponent", function(str) {
    return encodeURIComponent(str);
});

Handlebars.registerHelper("commafy", function(numPoints) {
    // From KhanUtil.commafy in math-format.js
    return numPoints.toString().replace(/(\d)(?=(\d{3})+$)/g, "$1,");
});

/**
 * Convert number of seconds to a time phrase for recent activity video entries.
 * Stolen from templatefilters.py
 */
Handlebars.registerHelper("secondsToTime", function(seconds) {
    // TODO: bring out KhanUtil's plural function
    // or somehow clean up the > 1 ? "s" : "" mess
    var years = Math.floor(seconds / (86400 * 365));
    seconds -= years * (86400 * 365);

    var days = Math.floor(seconds / 86400);
    seconds -= days * 86400;

    var months = Math.floor(days / 30.5);
    var weeks = Math.floor(days / 7);

    var hours = Math.floor(seconds / 3600);
    seconds -= hours * 3600;

    minutes = Math.floor(seconds / 60);
    seconds -= minutes * 60;

    if (years) {
        return years + " year" + (years > 1 ? "s" : "");
    } else if (months) {
        return months + " month" + (months > 1 ? "s" : "");
    } else if (weeks) {
        return weeks + " week" + (weeks > 1 ? "s" : "");
    } else if (days) {
        var result = days + " day" + (days > 1 ? "s" : "");
        if (hours) {
            result += " " + hours + " hour" + (hours > 1 ? "s" : "");
        }
        return result;
    } else if (hours) {
        var result = hours + " hour" + (hours > 1 ? "s" : "");
        if (minutes) {
            result += minutes + " minute" + (minutes > 1 ? "s" : "");
        }
    } else if (!minutes && seconds) {
        return seconds + " second" + (seconds > 1 ? "s" : "");
    } else {
        return minutes + " minute" + (minutes > 1 ? "s" : "");
    }
});
