#!/user/bin/env python

from user_models import UserData
from testutil import gae_model
import coaches_utils
import coaches
import logging


class CoachesUtilsTest(gae_model.GAEModelTestCase):

    def setUp(self):
        super(CoachesUtilsTest, self).setUp(db_consistency_probability=1)

    def make_user(self, email):
        return UserData.insert_for(email, email)

    def make_user_json(self, user, is_coaching):
        return {
            'email': user.key_email,
            'isCoachingLoggedInUser': is_coaching,
        }

    def test_add_multiple_coaches(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')
        edward = self.make_user('edward@gmail.com')

        coaches_json = [self.make_user_json(coach, True) for coach in
                [jacob, edward]]
        coaches.update_coaches(bella, coaches_json)
        self.assertEqual(2, len(bella.coaches))
        coaches_list = coaches_utils.get_coaches_students_count()
        self.assertEqual(1, coaches_list[0]['number_of_students'])

    #def test_add_a_coach(self):
    #    student = self.make_user('student@gmail.com')
    #    coach = self.make_user('coach@gmail.com')
