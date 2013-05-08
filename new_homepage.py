import request_handler
import user_util
class ViewHomePage(request_handler.RequestHandler):
  @user_util.open_access
  def get(self):
    template_values = {}
    self.render_jinja2_template('new_homepage.html', template_values)
#    layer_cache.enable()
