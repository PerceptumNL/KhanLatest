import request_handler
import logging
import user_util
from rssblog_model import RSSBlog


class UpdateBlogEntries(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        """update get the blog entries add the new ones """
        logging.info("importing feed from edit version")
        RSSBlog.fetch_feed()
