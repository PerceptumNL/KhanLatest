from google.appengine.ext import db
import feedparser
import datetime


"""
    Collects feeds from external Blog
    Should be run in a cron entry
"""

class RSSBlog(db.Model):
    link = db.StringProperty(indexed=True)
    title = db.StringProperty(indexed=False)
    created_on = db.DateTimeProperty(auto_now_add=True)
    pub_date = db.DateTimeProperty(auto_now_add=True, indexed=True)

    @property
    def id(self):
        return self.key().id()

    @staticmethod
    def get(count=5, offset=0):
        query = RSSBlog.all()[offset:offset + count]
        return query

    @staticmethod
    def get_latest_date():
        query = RSSBlog.all()
        last = query.order('-pub_date').get()
        if last is None:
            return datetime.date(1984, 1, 1)
        return last.pub_date

    @staticmethod
    def insert_for(pub_date=None, title=None, link=None):
        entry = RSSBlog()
        entry.pub_date = pub_date
        entry.title = title
        entry.link = link
        entry.put()
        return entry

    @staticmethod
    def fetch_feed():
        import pytz
        from operator import attrgetter
        from dateutil.parser import parse
        latest_date = RSSBlog.get_latest_date()

        python_wiki_rss_url = "http://blog.khanacademie.nl/feeds/posts/default?alt=rss"
        feed = feedparser.parse(python_wiki_rss_url)
        count = 0
        entries = feed["items"]
        for entry in sorted(entries, key=attrgetter('date'), reverse=False):
            pub_date = parse(entry['date']).astimezone(pytz.utc)
            if int(pub_date.strftime("%s")) > (int(latest_date.strftime("%s"))):
                count += 1
                RSSBlog.insert_for(pub_date, entry['title'], entry['link'])
        return count
