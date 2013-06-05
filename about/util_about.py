import request_handler
import user_util
from video_models import Video


class AboutRequestHandler(request_handler.RequestHandler):
    def render_jinja2_template(self, template_name, template_values):
        if not hasattr(template_values, "selected_nav_link"):
            template_values["selected_nav_link"] = "about"
        request_handler.RequestHandler.render_jinja2_template(
            self, template_name, template_values)

class ViewAbout(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/about_the_site.html', {
            # "selected_id": "the-site",
            # "approx_vid_count": Video.approx_count(),
        })

class ViewStart(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/gettingstarted.html', {
            "selected_id": "gettingstarted",
            "selected_nav_link": "gettingstarted"
        })

class ViewContact(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/contact.html', {
            "selected_id": "discovery-lab",
            "selected_nav_link": "",
        })

class ViewFAQ(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/faq.html', {
            "selected_id": "faq",
            "selected_nav_link": "faq",
            "approx_vid_count": Video.approx_count()
        })
