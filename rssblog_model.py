from google.appengine.ext import db
import feedparser
from datetime import datetime
from operator import attrgetter
import logging


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
            return datetime(1984, 1, 1)
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

        python_wiki_rss_url = "http://blog.khanacademie.nl/feeds/posts/default?alt=rss"
        feed = feedparser.parse(python_wiki_rss_url)
        entries = feed["items"]

        #Wed, 19 Sep 2012 08:50:00 +0000
        #Convert published date string to date object.
        for entry in entries:
            entry['published'] = datetime.strptime(entry.published[:-6], "%a, %d %b %Y %H:%M:%S")

        count = 0
        latest_date = RSSBlog.get_latest_date()
        for entry in sorted(entries, key=attrgetter('published'), reverse=False):
            pub_date = entry['published']
            if pub_date > latest_date:
                count += 1
                logging.info("New blog entry: " + str(entry['title'] + " [published] " + pub_date))
                RSSBlog.insert_for(pub_date, entry['title'], entry['description'], entry['link'])

        return count
