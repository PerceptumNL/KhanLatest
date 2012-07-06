import user_util
import request_handler


class MapLayoutEditor(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        self.render_jinja2_template('knowledgemap/kmap_editor.html', {})
