(function() {
    // from http://daringfireball.net/2010/07/improved_regex_for_matching_urls
    var regex = /\b((?:https?:\/\/|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}\/)(?:[^\s()<>&]+|&amp;|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’&]))/ig;

    var Autolink = {
        autolink: function(text) {
            return text.replace(regex, function(match, text) {
                var url = text;

                if (!(/^https?:\/\//).test(url)) {
                    url = "http://" + url;
                }

                return "<a href='" + url + "'>" + text + "</a>";
            });
        }
    };

    window.Autolink = Autolink;
})();
