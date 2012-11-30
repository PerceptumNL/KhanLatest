from google.appengine.ext import db
import feedparser
from datetime import tzinfo, timedelta, datetime, date


"""
    Collects feeds from external Blog
    Should be run in a cron entry
"""


class RSSBlog(db.Model):
    link = db.StringProperty(indexed=True)
    title = db.StringProperty(indexed=False)
    description = db.TextProperty()
    created_on = db.DateTimeProperty(auto_now_add=True)
    pub_date = db.DateTimeProperty(auto_now_add=True, indexed=True)

    @property
    def id(self):
        return self.key().id()

    @staticmethod
    def get(offset=0, count=5):
        query = RSSBlog.all()
        #bb=query.order('-pub_date')
        #for b in bb:
        #    print(b)
        #    b.delete()
        return query.order('-pub_date')[offset:offset + count]

    @staticmethod
    def get_latest_date():
        query = RSSBlog.all()
        last = query.order('-pub_date').get()
        if last is None:
            return date(1984, 1, 1)
        return last.pub_date

    @staticmethod
    def insert_for(pub_date=None, title=None, description=None, link=None):
        entry = RSSBlog()
        entry.pub_date = pub_date
        entry.title = title
        entry.description = description
        entry.link = link
        entry.put()
        return entry

    @staticmethod
    def fetch_feed():
        ZERO = timedelta(0)

        class UTC(tzinfo):
            """UTC"""

            def utcoffset(self, dt):
                return ZERO

            def tzname(self, dt):
                return "UTC"

            def dst(self, dt):
                return ZERO

        from operator import attrgetter
        from dateutil.parser import parse
        latest_date = RSSBlog.get_latest_date()

        python_wiki_rss_url = "http://blog.khanacademie.nl/feeds/posts/default?alt=rss"
        feed = feedparser.parse(python_wiki_rss_url)
        count = 0
        entries = feed["items"]
        for entry in sorted(entries, key=attrgetter('date'), reverse=False):
            pub_date = parse(entry['date']).astimezone(UTC())
            if int(pub_date.strftime("%s")) > (int(latest_date.strftime("%s"))):
                count += 1
                RSSBlog.insert_for(pub_date, entry['title'], entry['description'], entry['link'])
        return count
