from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import WSGIApplication

import request_handler
import user_util


class RedirectGTV(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.redirect("/gtv/")


application = WSGIApplication([
    ('/gtv', RedirectGTV),
])


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
