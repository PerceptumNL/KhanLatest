import request_handler
import user_util
from video_models import Video


class AboutRequestHandler(request_handler.RequestHandler):
    def render_jinja2_template(self, template_name, template_values):
        template_values["selected_nav_link"] = "about"
        request_handler.RequestHandler.render_jinja2_template(
            self, template_name, template_values)

class ViewAbout(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/about_the_site.html', {
            "selected_id": "the-site",
            "approx_vid_count": Video.approx_count(),
        })

class ViewStart(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/gettingstarted.html',
                                    {"selected_id": "the-team"})


class ViewContact(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/contact.html', {
            "selected_id": "discovery-lab"})


class ViewFAQ(AboutRequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('about/faq.html', {
            "selected_id": "faq",
            "approx_vid_count": Video.approx_count()
        })

