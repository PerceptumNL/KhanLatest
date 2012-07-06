function createCookie(name, value, days, domain) {
    var expires;
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toGMTString();
    } else {
        expires = "";
    }
    if (domain) {
        domain = "; domain=" + domain;
    } else {
        domain = "";
    }
    document.cookie = name + "=" + value + expires + domain + "; path=/";
}

function readCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(";");
    for (var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == " ") c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

function eraseCookie(name, domain) {
    createCookie(name, "", -1, domain);
}

function areCookiesEnabled() {
    createCookie("detectCookiesEnabled", "KhanAcademy", 1);
    if (readCookie("detectCookiesEnabled") == null)
        return false;
    eraseCookie("detectCookiesEnabled");
    return true;
}
