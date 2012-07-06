from google.appengine.api import taskqueue

import request_handler
import user_models
import user_util
import util_badges
import models_badges


class ViewBadge(request_handler.RequestHandler):

    @user_util.open_access
    def get(self, badge_slug=None):

        user_data = (user_models.UserData.current()
                        or user_models.UserData.pre_phantom())
        template_values = util_badges.get_grouped_user_badges(user_data)

        # if regexp matches a badge-slug, try to fetch badge
        # and add to page context if possible
        if badge_slug:
            # TODO what should happen if badge_slug is a hidden badge?

            all_the_slugs = util_badges.all_badges_slug_dict()
            if badge_slug in all_the_slugs:
                template_values['badge'] = all_the_slugs[badge_slug]

            # if no badge retrieved, redirect to default badge view
            else:
                self.redirect("/badges")
                return None

        self.render_jinja2_template('viewbadges.html', template_values)


# /admin/badgestatistics is called periodically by a cron job
class BadgeStatistics(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        # Admin-only restriction is handled by /admin/* URL pattern
        # so this can be called by a cron job.
        taskqueue.add(url='/admin/badgestatistics',
                        queue_name='badge-statistics-queue',
                        params={'start': '1'})
        self.response.out.write("Badge statistics task started.")

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def post(self):
        if not self.request_bool("start", default=False):
            return

        for badge in util_badges.all_badges():

            badge_stat = models_badges.BadgeStat.get_or_insert_for(badge.name)

            if badge_stat and badge_stat.needs_update():
                badge_stat.update()
                badge_stat.put()


# /admin/startnewbadgemapreduce is called periodically by a cron job
class StartNewBadgeMapReduce(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        # Admin-only restriction is handled by /admin/* URL pattern
        # so this can be called by a cron job.
        mapreduce_id = util_badges.start_new_badge_mapreduce()
        self.response.out.write("OK: " + str(mapreduce_id))
