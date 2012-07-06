import request_handler
import user_util
import os


class RobotsTxt(request_handler.RequestHandler):
    """Dynamic robots.txt that hides staging apps from search engines"""
    @user_util.open_access
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write("User-agent: *\n")

        visible_domains = [
            'www.khanacademy.org',
            'smarthistory.khanacademy.org',
        ]

        if os.environ['SERVER_NAME'] in visible_domains:
            self.response.write("Disallow:")
        else:
            self.response.write("Disallow: *")
