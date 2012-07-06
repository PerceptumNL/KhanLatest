import request_handler
import user_util
import library


class GenerateLibraryContent(request_handler.RequestHandler):

    @user_util.open_access
    def post(self):
        # We support posts so we can fire task queues at this handler
        self.get(from_task_queue=True)

    @user_util.open_access
    def get(self, from_task_queue=False):
        library.library_content_html(ajax=True, version_number=None,
            bust_cache=True)
        library.library_content_html(ajax=False, version_number=None,
            bust_cache=True)

        if not from_task_queue:
            self.redirect("/")
