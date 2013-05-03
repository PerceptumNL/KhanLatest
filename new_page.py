import request_handler
import user_utils
class ViewNewPage(request_handler.RequestHandler):
    @user_utils.open_access
    def get(self):
        some_value = 100
        template_values = {'some_value': some_value}
        self.render_jinja2_template('new_page.html', template_values)
