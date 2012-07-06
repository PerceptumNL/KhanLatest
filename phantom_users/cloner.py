import request_handler
import user_util


class Clone(request_handler.RequestHandler):
    """This is a hack of a handler that shows a page for a fixed number of
    seconds to pretend we're migrating data from a phantom user to a real
    user.
    
    Note - in reality, it is not actually doing any migrations and just pausing
    long enough for App Engine HRD indices to catch up from the identity
    consumption process that should have already been kicked off in PostLogin
    prior to the user hitting this endpoint.

    If we ever need to do "real migration" of any entities, it should be done
    here, probably.
    """

    @user_util.open_access
    def get(self):
        title = "Please wait while we copy your data to your new account."
        message_html = ("We're in the process of copying over all of the "
                        "progress you've made. You may access your account "
                        "once the transfer is complete.")
        sub_message_html = ("This process can take a long time, thank you for "
                            "your patience.")
        cont = self.request_continue_url()
        self.render_jinja2_template('phantom_users/transfer.html', {
            'title': title,
            'message_html': message_html,
            'sub_message_html': sub_message_html,
            'dest_url': cont,
        })
