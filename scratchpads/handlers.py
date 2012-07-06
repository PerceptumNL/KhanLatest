from api import jsonify
from api.auth import xsrf
import base64
from custom_exceptions import PageNotFoundException, ClosedBetaException
import profiles.util_profile
import gandalf.bridge
import request_handler
import scratchpads.models as scratchpad_models
import user_models
import user_util


class ScratchpadHandler(request_handler.RequestHandler):
    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def new(self):
        if not gandalf.bridge.gandalf("scratchpads"):
            self.error(404)
            raise ClosedBetaException

        env_js = {
            "user": user_models.UserData.current()
        }

        self.render_jinja2_template('scratchpads/code.html', {
            "pagetitle": "New Scratchpad",
            "selected_nav_link": "explore",
            "selected_id": "new-scratchpad",
            "env_js": jsonify.jsonify(env_js)
        })

    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def show(self, slug, scratchpad_id):
        # Only the scratchpad_id is used to retrieve the Scratchpad - the slug
        # is ignored
        scratchpad = scratchpad_models.Scratchpad.get_by_id(int(scratchpad_id))

        if not scratchpad or scratchpad.deleted:
            self.error(404)
            raise PageNotFoundException

        user = (user_models.UserData.current() or
                user_models.UserData.pre_phantom())
        creator = user_models.UserData.get_from_user_id(scratchpad.user_id)
        creator_profile = profiles.util_profile.UserProfile.from_user(
            creator, actor=user)

        env_js = {
            "user": user,
            "scratchpad": scratchpad
        }

        selected_id = ""

        if scratchpad.category in ("official", "tutorial"):
            selected_id = "show-explorations"

        elif user and creator and user.user_id == creator.user_id:
            selected_id = "my-explorations"

        self.render_jinja2_template('scratchpads/code.html', {
            "pagetitle": scratchpad.title,
            "selected_nav_link": "explore",
            "selected_id": selected_id,
            "creator_profile": creator_profile,
            "scratchpad": scratchpad,
            "show_scratchpad_review_system": (user and user.developer and
                creator and creator.developer),
            "env_js": jsonify.jsonify(env_js)
        })

    @user_util.open_access
    def image(self, slug, scratchpad_id):
        # We want to avoid embedding huge data:image/png URIs into HTML bodies
        # because it makes the files massive. Instead, we convert them to be
        # binary pngs on demand

        # Only the scratchpad_id is used to retrieve the Scratchpad - the slug
        # is ignored
        scratchpad = scratchpad_models.Scratchpad.get_by_id(int(scratchpad_id))

        if scratchpad is None:
            self.error(404)
            raise PageNotFoundException

        image_url = scratchpad.revision.image_url

        if image_url.startswith("data:"):
            base64_image_data = image_url[len("data:image/png;base64,"):]

            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(base64.b64decode(base64_image_data))
        else:
            self.redirect(image_url)

    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def index_official(self):
        if not gandalf.bridge.gandalf("scratchpads"):
            self.error(404)
            raise ClosedBetaException

        self.render_jinja2_template("scratchpads/explorations.html", {
            "selected_nav_link": "explore",
            "selected_id": "show-explorations",
            "pagetitle": "Explorations",
            "env_js": jsonify.jsonify({
                "officialScratchpads": list(scratchpad_models.Scratchpad
                    .get_all_official()
                    .run(batch_size=1000)),
                "tutorialScratchpads": list(scratchpad_models.Scratchpad
                    .get_all_tutorials()
                    .run(batch_size=1000)),
            })
        })

    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def index_tutorials(self):
        if not gandalf.bridge.gandalf("scratchpads"):
            self.error(404)
            raise ClosedBetaException

        self.render_jinja2_template("scratchpads/tutorials.html", {
            "selected_nav_link": "explore",
            "selected_id": "show-tutorials",
            "pagetitle": "Tutorials",
            "env_js": jsonify.jsonify({
                "tutorialScratchpads": list(scratchpad_models.Scratchpad
                    .get_all_tutorials()
                    .run(batch_size=1000))
            })
        })


class SoundcloudCallbackRequestHandler(request_handler.RequestHandler):

    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def get(self):
        self.render_jinja2_template('scratchpads/callback.html', {})

