import user_models
from coach_resources.coach_request_model import CoachRequest
from avatars import util_avatars
from badges import util_badges


def get_last_student_list(request_handler, student_lists, use_cookie=True):
    student_lists = student_lists.fetch(100)

    # default_list is the default list for this user
    if student_lists:
        default_list = str(student_lists[0].key())
    else:
        default_list = 'allstudents'

    # desired list is the list the user asked for (via cookie or querystring)
    desired_list = None

    if use_cookie:
        cookie_val = request_handler.get_cookie_value('studentlist_id')
        desired_list = cookie_val or desired_list

    # override cookie with explicitly set querystring
    desired_list = request_handler.request_string('list_id', desired_list)

    # now validate desired_list exists
    current_list = None
    list_id = 'allstudents'
    if desired_list != 'allstudents':
        for s in student_lists:
            if str(s.key()) == desired_list:
                current_list = s
                list_id = desired_list
                break

        if current_list is None:
            list_id = default_list

    if use_cookie:
        request_handler.set_cookie('studentlist_id', list_id, max_age=2629743)

    return list_id, current_list


def get_student(coach, request_handler):
    student = request_handler.request_student_user_data()
    if student is None:
        raise Exception("No student found")
    if not student.is_coached_by(coach):
        raise Exception("Not your student!")
    return student


def get_student_list(coach, list_key):
    student_list = user_models.StudentList.get(list_key)
    if student_list is None:
        raise Exception("No list found with list_key='%s'." % list_key)
    if coach.key() not in student_list.coaches:
        raise Exception("Not your list!")
    return student_list


# Return a list of students, either from the list or from the user data,
# dependent on the contents of a querystring parameter.
def get_students_data(user_data, list_key=None):
    student_list = None
    if list_key and list_key != 'allstudents':
        student_list = get_student_list(user_data, list_key)

    if student_list:
        return student_list.get_students_data()
    else:
        return user_data.get_students_data()


def get_coach_student_and_student_list(request_handler):
    coach = user_models.UserData.current()
    student_list = get_student_list(coach,
        request_handler.request_string("list_id"))
    student = get_student(coach, request_handler)
    return (coach, student, student_list)


class UserProfile(object):
    """Profile information about a user.

    This is a transient object and derived from the information in UserData,
    and formatted/tailored for use as an object about a user's public profile.
    """

    def __init__(self):
        self.username = None
        self.profile_root = "/profile"
        self.email = ""
        self.is_phantom = True

        # Indicates whether or not the profile has been marked public. Not
        # necessarily indicative of what fields are currently filled in this
        # current instance, as different projections may differ on actor
        # privileges
        self.is_public = False

        # Whether or not the app is able to collect data about the user.
        # Note users under 13 without parental consent cannot give private
        # data.
        self.is_data_collectible = False

        # Whether or not the data about the user's activity on the site is
        # available to the viewer of this profile. This includes goals,
        # video and exercise data.
        self.is_activity_accessible = False

        # TODO(benkomalo): extract these one-off variables out into
        # something nicer that encapsulates relationship with the actor
        self.is_coaching_logged_in_user = False
        self.is_requesting_to_coach_logged_in_user = False
        self.is_parent_of_logged_in_user = False

        self.is_moderator = False

        self.nickname = ""
        self.date_joined = ""
        self.points = 0
        self.count_videos_completed = 0
        self.count_exercises_proficient = 0
        self.public_badges = []

        default_avatar = util_avatars.avatar_for_name()
        self.avatar_name = default_avatar.name
        self.avatar_src = default_avatar.image_src

    @staticmethod
    def from_user(user, actor):
        """Retrieve profile information about a user for the specified actor.

        This will do the appropriate ACL checks and return the greatest amount
        of profile data that the actor has access to, or None if no access
        is allowed.

        user - user_models.UserData object to retrieve information from
        actor - user_models.UserData object corresponding to who is requesting
                the data
        identifier - Optional. The identifier used by the actor to identify the
        user. It can be the user's username, email or userId.
        """

        if user is None:
            return None

        is_self = user.user_id == actor.user_id
        user_is_visible_to_actor = user.is_visible_to(actor)
        actor_is_visible_to_user = actor.is_visible_to(user)

        if is_self or user_is_visible_to_actor:
            # Avoid a DB hit in the common case where you're viewing your
            # own profile.
            if not is_self:
                # TODO(benkomalo): think of a way to avoid this DB hit. If
                # we ever go to a case where coaches pull up entire lists of
                # student profiles, this will cause a db hit for each one.
                is_parent_of_logged_in_user = \
                        user_models.ParentChildPair.is_pair(
                                parent_user_data=user,
                                child_user_data=actor)
            else:
                is_parent_of_logged_in_user = False

            # Full data about the user
            return UserProfile._from_user_internal(
                    user,
                    full_projection=True,
                    is_coaching_logged_in_user=actor_is_visible_to_user,
                    is_parent_of_logged_in_user=is_parent_of_logged_in_user,
                    is_self=is_self)
        elif user.has_public_profile():
            # Return only public data
            return UserProfile._from_user_internal(
                    user,
                    full_projection=False,
                    is_coaching_logged_in_user=actor_is_visible_to_user)
        else:
            return UserProfile._for_private_user(user)

    @staticmethod
    def _for_private_user(user):
        # TODO(ankit): Incorporate into _from_user_internal to reduce # of
        # places that need to be updated with any new properties
        profile = UserProfile()
        profile.username = user.username
        profile.nickname = user.nickname or ""
        profile.is_public = False
        profile.profile_root = user.profile_root
        profile.user_key = str(user.key())
        return profile

    @staticmethod
    def _from_user_internal(user,
                            full_projection=False,
                            is_coaching_logged_in_user=False,
                            is_parent_of_logged_in_user=False,
                            is_self=False):

        profile = UserProfile()

        # A stranger's public discussion data is fetched by user_key if she
        # does not have a username.
        # TODO(marcia): Backfill usernames so we can remove user_key
        profile.user_key = str(user.key())
        profile.username = user.username
        profile.nickname = user.nickname or user.username or ""
        profile.date_joined = user.joined
        avatar = util_avatars.avatar_for_name(user.avatar_name)
        profile.avatar_name = avatar.name
        profile.avatar_src = avatar.image_src
        profile.public_badges = util_badges.get_public_user_badges(user)
        profile.points = user.points
        profile.count_videos_completed = user.get_videos_completed()
        profile.count_exercises_proficient = len(user.all_proficient_exercises)

        profile.is_self = is_self
        profile.is_coaching_logged_in_user = is_coaching_logged_in_user
        profile.is_parent_of_logged_in_user = is_parent_of_logged_in_user
        profile.is_phantom = user.is_phantom

        profile.is_moderator = user.is_moderator_or_developer

        profile.is_public = user.has_public_profile()

        if profile.is_public or full_projection:
            profile.profile_root = user.profile_root

        if full_projection:
            profile.email = user.email
            profile.is_data_collectible = (not user.is_child_account() and
                                           not user.is_maybe_edu_account())
            profile.is_activity_accessible = True

        return profile

    @staticmethod
    def get_coach_and_requester_profiles_for_student(student_user_data):
        coach_profiles = []

        for coach_user_data in student_user_data.get_coaches_data():
            profile = UserProfile._from_coach(coach_user_data,
                                              student_user_data)
            coach_profiles.append(profile)

        requests = CoachRequest.get_for_student(student_user_data)
        for request in requests:
            coach_user_data = request.coach_requesting_data
            profile = UserProfile._from_coach(coach_user_data,
                                              student_user_data)
            coach_profiles.append(profile)

        return coach_profiles

    @staticmethod
    def _from_coach(coach, actor):
        """Retrieve profile information about a coach for the specified actor.

        At minimum, this will return a UserProfile with the following data:
        -- email
        -- is_coaching_logged_in_user
        -- is_requesting_to_coach_logged_in_user

        If the coach has a public profile or if she is coached by the actor,
        more information will be retrieved as allowed.

        coach - user_models.UserData object to retrieve information from
        actor - user_models.UserData object corresponding to who is requesting
                the data

        TODO(marcia): Move away from using email to manage coaches, since
        this breaks our notions of public/private profiles.

        """

        profile = UserProfile.from_user(coach, actor) or UserProfile()

        profile.email = coach.email

        is_coach = actor.is_coached_by(coach)
        profile.is_coaching_logged_in_user = is_coach
        profile.is_requesting_to_coach_logged_in_user = not is_coach
        profile.is_parent_of_logged_in_user = \
                user_models.ParentChildPair.is_pair(
                        parent_user_data=coach,
                        child_user_data=actor)

        return profile
