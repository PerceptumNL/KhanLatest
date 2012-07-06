import request_handler
import user_util
import user_models
import notifications


class ToggleNotify(request_handler.RequestHandler):
    """Allows the user to close the notification bar (by deleting the memcache)
    until a new notification occurs.
    """
    @user_util.open_access
    def post(self):
        user_data = user_models.UserData.current()
        if user_data:
            notifications.PhantomNotification.clear(user_data)
