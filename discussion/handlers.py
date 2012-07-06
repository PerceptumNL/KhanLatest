from google.appengine.ext import db

from badges import discussion_badges
import discussion_models
import notification
import rate_limiter
import request_handler
import user_models
import user_util


class ExpandQuestion(request_handler.RequestHandler):
    @user_util.open_access
    def post(self):
        qa_expand_key = self.request.get("qa_expand_key")
        notification.clear_notification_for_question(qa_expand_key)


class FlagEntity(request_handler.RequestHandler):
    # You have to at least be logged in to flag
    @user_util.login_required_and(phantom_user_allowed=False)
    def post(self):
        user_data = user_models.UserData.current()

        limiter = rate_limiter.FlagRateLimiter(user_data)
        if not limiter.increment():
            self.render_json({"error": limiter.denied_desc()})
            return

        key = self.request_string("entity_key", default="")
        flag = self.request_string("flag", default="")
        if key and discussion_models.FeedbackFlag.is_valid(flag):
            entity = db.get(key)

            # Entities that have already been deemed ok by moderators can not
            # be flagged again
            if (entity and not entity.definitely_not_spam and
                entity.add_flag_by(flag, user_data)):
                entity.put()

                if not discussion_badges.FirstFlagBadge().is_already_owned_by(
                        user_data):
                    discussion_badges.FirstFlagBadge().award_to(user_data)
                    user_data.put()


class ModPanel(request_handler.RequestHandler):
    @user_util.moderator_required
    def get(self):
        template_values = {
            'selected_id': 'panel',
        }
        self.render_jinja2_template('discussion/mod/mod.html',
                                    template_values)


class ModeratorList(request_handler.RequestHandler):
    # Must be an admin to change moderators
    @user_util.admin_required
    def get(self):
        mods = user_models.UserData.gql('WHERE moderator = :1', True)
        template_values = {
            'mods': mods,
            'selected_id': 'moderatorlist',
        }
        self.render_jinja2_template('discussion/mod/moderatorlist.html',
                                    template_values)

    @user_util.admin_required
    def post(self):
        user_data = self.request_user_data('user')

        if user_data:
            user_data.moderator = self.request_bool('mod')

            if user_data.moderator:
                if not discussion_badges.ModeratorBadge().is_already_owned_by(
                        user_data):
                    discussion_badges.ModeratorBadge().award_to(user_data)

            db.put(user_data)

        self.redirect('/discussion/mod/moderatorlist')


class FlaggedFeedback(request_handler.RequestHandler):
    @user_util.moderator_required
    def get(self):
        template_values = {
                'selected_id': 'flaggedfeedback',
            }

        self.render_jinja2_template('discussion/mod/flaggedfeedback.html',
                                    template_values)


class BannedList(request_handler.RequestHandler):
    @user_util.moderator_required
    def get(self):
        banned_user_data_list = user_models.UserData.gql(
                'WHERE discussion_banned = :1', True)
        template_values = {
            'banned_user_data_list': banned_user_data_list,
            'selected_id': 'bannedlist',
        }
        self.render_jinja2_template('discussion/mod/bannedlist.html',
                                    template_values)

    @user_util.moderator_required
    def post(self):
        user_data = self.request_user_data('user')

        if user_data:
            user_data.discussion_banned = self.request_bool('banned')
            db.put(user_data)

            if user_data.discussion_banned:
                # Delete all old posts by hellbanned user
                query = discussion_models.Feedback.all()
                query.ancestor(user_data)
                for feedback in query:
                    if not feedback.deleted:
                        feedback.deleted = True
                        feedback.put()

        self.redirect('/discussion/mod/bannedlist')
