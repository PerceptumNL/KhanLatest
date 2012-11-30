from __future__ import with_statement
from testutil import gae_model
from rssblog_model import RSSBlog
import datetime

class RSSBlogTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(RSSBlogTest, self).setUp(db_consistency_probability=1)

    def test_addentry(self):
        date = datetime.datetime.now()
        title = "test title"
        link = "blog.khanacademie.nl"
        entry = RSSBlog(date=date, title=title, link=link)
        entry.put()
        self.assertEqual(1, len(RSSBlog.all()[:1]))

    def test_remove_entry(self):
        pass

    def runTest(self):
        pass

if __name__ == '__main__':
    blogtest = RSSBlogTest()
    blogtest.setUp()
    blogtest.test_addentry()
