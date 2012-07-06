"""Database entity that holds pending requests to be someone's coach.

You can request to be someone's coach, this holds the pending request.
"""

from google.appengine.ext import db

import user_models


class CoachRequest(db.Model):
    coach_requesting = db.UserProperty()
    student_requested = db.UserProperty()

    # The string the requestor typed in to create this request. This can
    # correspond to an e-mail or username, and is static.
    student_identifier = db.StringProperty(indexed=False)

    @property
    def coach_requesting_data(self):
        if not hasattr(self, "coach_user_data"):
            self.coach_user_data = user_models.UserData.get_from_db_key_email(
                self.coach_requesting.email())
        return self.coach_user_data

    @property
    def student_requested_data(self):
        if not hasattr(self, "student_user_data"):
            self.student_user_data = \
                user_models.UserData.get_from_db_key_email(
                    self.student_requested.email())
        return self.student_user_data

    @property
    def student_requested_identifier(self):
        # If we have the actual string the Coach used to request the student
        # by, use that.
        # As of May 2012, we allowed coach requests to be done by public
        # usernames, and showing someone's e-mail when you typed in their
        # username seemed inappropriate. Prior to that, student_identifier
        # was not available, since requests were always done by email.
        if self.student_identifier:
            return self.student_identifier

        return self.student_requested_data.email

    @staticmethod
    def key_for(user_data_coach, user_data_student):
        return "%s_request_for_%s" % (user_data_coach.key_email,
                                      user_data_student.key_email)

    @staticmethod
    def get_for(user_data_coach, user_data_student):
        return CoachRequest.get_by_key_name(
            CoachRequest.key_for(user_data_coach, user_data_student))

    @staticmethod
    def get_or_insert_for(user_data_coach, user_data_student, identifier):
        return CoachRequest.get_or_insert(
                key_name=CoachRequest.key_for(user_data_coach,
                                              user_data_student),
                coach_requesting=user_data_coach.user,
                student_requested=user_data_student.user,
                student_identifier=identifier
                )

    @staticmethod
    def get_for_student(user_data_student):
        return CoachRequest.all().filter("student_requested = ",
                                         user_data_student.user)

    @staticmethod
    def get_for_coach(user_data_coach):
        return CoachRequest.all().filter("coach_requesting = ",
                                         user_data_coach.user)
