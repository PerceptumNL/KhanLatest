/**
 * A component to display a user hover card.

 Usage:
 <div class="video-footer">
    <span class="author-nickname" data-user-id="http://googleid.khanacademy.org/11111">Katniss</span>
    <span class="author-nickname" data-user-id="http://googleid.khanacademy.org/22222">Katniss>Haymitch</span>
    <span class="author-nickname" data-user-id="http://googleid.khanacademy.org/33333">Katniss>Thresh</span>
 </div>

 Note the required author-nickname class and data-user-id attribute.

 $(".video-footer").on("mouseenter", ".author-nickname", function() {
     HoverCard.createHoverCardQtip($(this));
 });

 */

var HoverCard = {
    cache_: {},

    createHoverCardQtip: function(jel) {
        var userId = jel.data("user-id"),
            hasQtip = jel.data("has-qtip");

        if (!userId || hasQtip) {
            return;
        }

        var cached = HoverCard.cache_[userId],
            html;

        if (cached != null) {
            // We've hovered over the user somewhere else on the page
            html = cached.html;

            // Add href to link
            var profileRoot = cached.model.get("profileRoot");
            if (profileRoot != null && jel.is("a")) {
                jel.attr("href", profileRoot + "discussion");
            }
        } else {
            // Create loading view
            var view = new HoverCardView();
            html = view.render().el.innerHTML;

            $.ajax({
                type: "GET",
                url: "/api/v1/user/profile",
                data: {
                    casing: "camel",
                    userId: userId
                  },
                dataType: "json",
                success: _.bind(HoverCard.onHoverCardDataLoaded_, this, jel)
            });
        }

        jel.data("has-qtip", true);

        // Create tooltip
        jel.qtip({
                content: {
                    text: html
                },
                style: {
                    classes: "custom-override"
                },
                hide: {
                    delay: 100,
                    fixed: true
                },
                position: {
                    my: "top left",
                    at: "bottom left"
                }
            });

        jel.qtip("show");
    },

    onHoverCardDataLoaded_: function(jel, data) {
        var userId = jel.data("user-id"),
            model = new ProfileModel(data),
            view = new HoverCardView({model: model}),
            html = view.render().el.innerHTML;

        // Cache html for this user
        HoverCard.cache_[userId] = {
            model: model,
            html: html
        };

        // Replace tooltip content
        jel.qtip("option", "content.text", html);

        // Add href to link
        var profileRoot = model.get("profileRoot");
        if (profileRoot != null && jel.is("a")) {
            jel.attr("href", profileRoot + "discussion");
        }
    }
}
