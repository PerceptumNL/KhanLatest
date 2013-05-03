import request_handler
class ViewNewPage(request_handler.RequestHandler):
    def get(self):
        some_value = 100
        template_values = {'some_value': some_value}
        self.render_jinja2_template('new_page.html', template_values)
