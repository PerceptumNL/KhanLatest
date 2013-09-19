"""Holds UserData, UniqueUsername, NicknameIndex, UnverifiedUser, StudentList.

UserData: database entity holding information about a single registered user
UniqueUsername: database entity of usernames that've been set on profile pages
NicknameIndex: database entity allowing search for users by their nicknames
UnverifiedUser: holds info on users in the midst of the signup process
StudentList: a list of users associated with a single coach.

A 'user' is an entity that logs into Khan Academy in some way (there
are also some 'fake' users that do not require logging in, like the
phantom user).
"""

import datetime
import logging
import os
import re

from google.appengine.api import datastore_errors, users
from google.appengine.ext import db

from exercises import accuracy_model
from api import jsonify   # TODO(csilvers): move out of api/?
import auth.models
from auth import age_util
from counters import user_counter
from discussion import discussion_models
from tincan import TinCan
import badges
import facebook_util
import gae_bingo.models
import gae_bingo.gae_bingo
import nicknames
import object_property
import phantom_users
import request_cache
import transaction_util
import user_util
import util
import uid


_PRE_PHANTOM_EMAIL = "http://nouserid.khanacademy.org/pre-phantom-user-2"
_USER_KEY_PREFIX = "_k"
ID_PREFIX = "http://id.khanacademy.org/"
# TODO(ankit): Ideally, this should be in google_util.py. But that
# causes a circular import problem. Fix that.
GOOGLE_ID_PREFIX = "http://googleid.khanacademy.org/"


# Demo user khanacademy.demo2@gmail.com is a coworker of
# khanacademy.demo@gmail.com khanacademy.demo@gmail.com is coach of a bunch of
# Khan staff and LASD staff, which is shared with users as a demo. Access to
# the demo is via /api/auth/token_to_session with oauth tokens for
# khanacademy.demo2@gmail.com supplied via secrets.py
_COACH_DEMO_COWORKER_EMAIL = "khanacademy.demo2@gmail.com"


class UserData(gae_bingo.models.GAEBingoIdentityModel,
               auth.models.CredentialedUser):
    # Canonical reference to the user entity. Avoid referencing this directly
    # as the fields of this property can change; only the ID is stable and
    # user_id can be used as a unique identifier instead.
    user = db.UserProperty()

    # Deprecated - this was used to represent the current e-mail address of the
    # user but is no longer relevant. Do not use - see user_id instead.
    current_user = db.UserProperty()

    # An opaque and uniquely identifying string for a user - this is stable
    # even if the user changes her e-mail.
    user_id = db.StringProperty()

    # A uniquely identifying string for a user. This is not stable and can
    # change if a user changes her e-mail. This is not actually always an
    # e-mail; for non-Google users, this can be a
    # URI like http://facebookid.khanacademy.org/1234
    user_email = db.StringProperty()

    # A human-readable name that will be user-configurable.
    # Do not read or modify this directly! Instead, use the nickname property
    # and update_nickname method
    user_nickname = db.StringProperty(indexed=False)

    # A globally unique user-specified username,
    # which will be used in URLS like khanacademy.org/profile/<username>
    username = db.StringProperty(default="")

    moderator = db.BooleanProperty(default=False)
    developer = db.BooleanProperty(default=False)
    coach_project = db.BooleanProperty(default=False)

    # Account creation date in UTC
    joined = db.DateTimeProperty(auto_now_add=True)

    # Last login date in UTC. Note that this was incorrectly set, and could
    # have stale values (though is always non-empty) for users who have never
    # logged in prior to the launch of our own password based
    # logins(2012-04-12)
    last_login = db.DateTimeProperty(indexed=False)

    # Whether or not user has been hellbanned from community participation
    # by a moderator
    discussion_banned = db.BooleanProperty(default=False)

    # Names of exercises in which the user is *explicitly* proficient
    proficient_exercises = object_property.StringListCompatTsvProperty()

    # Names of all exercises in which the user is proficient
    all_proficient_exercises = object_property.StringListCompatTsvProperty()

    suggested_exercises = object_property.StringListCompatTsvProperty()

    # All awarded badges
    badges = object_property.StringListCompatTsvProperty()

    need_to_reassess = db.BooleanProperty(indexed=False)
    points = db.IntegerProperty(default=0)
    total_seconds_watched = db.IntegerProperty(default=0)

    # A list of email values corresponding to the "user" property of the
    # coaches for the user. Note that it may not be the current, active email
    # Don't use directly - see add_coach, remove_coach to mutate this
    coaches = db.StringListProperty()

    # Capabilities for child accounts represented as a list of strings.
    # See user_models.Capabilities for interpretation of the contents.
    # This allows parent accounts the ability to restrict certain features.
    child_capabilities = object_property.TsvProperty()

    coworkers = db.StringListProperty()
    student_lists = db.ListProperty(db.Key)
    map_coords = db.StringProperty(indexed=False)
    videos_completed = db.IntegerProperty(default=-1)
    last_daily_summary = db.DateTimeProperty(indexed=False)
    last_badge_review = db.DateTimeProperty(indexed=False)
    last_activity = db.DateTimeProperty(indexed=False)
    start_consecutive_activity_date = db.DateTimeProperty(indexed=False)
    count_feedback_notification = db.IntegerProperty(default=-1,
                                                     indexed=False)

    question_sort_order = db.IntegerProperty(default=-1, indexed=False)
    uservideocss_version = db.IntegerProperty(default=0, indexed=False)
    has_current_goals = db.BooleanProperty(default=False, indexed=False)

    # A list of badge names that the user has chosen to display publicly
    # Note that this list is not contiguous - it may have "holes" in it
    # indicated by the reserved string "__empty__"
    public_badges = object_property.TsvProperty()

    # The name of the avatar the user has chosen. See avatar.util_avatar.py
    avatar_name = db.StringProperty(indexed=False)

    # The user's birthday was only relatively recently collected (Mar 2012)
    # so older UserData may not have this information.
    birthdate = db.DateProperty(indexed=False)

    # The user's gender is optional, and only collected as of Mar 2012,
    # so older UserData may not have this information.
    gender = db.StringProperty(indexed=False)

    # Whether or not the user has indicated she wishes to have a public
    # profile (and can be searched, etc)
    is_profile_public = db.BooleanProperty(default=False, indexed=False)

    # Whether or not the user has a notification of some sort waiting
    # TODO(kamens): unify has_notification w/ count_feedback_notification
    has_notification = db.BooleanProperty(default=False, indexed=False)

    _serialize_blacklist = [
            "credential_version",  # from auth.models.CredentialedUser
            "backup_timestamp",  # from backup_model.BackupModel
            "badges", "count_feedback_notification", "last_discussion_view",
            "last_daily_summary", "need_to_reassess", "videos_completed",
            "moderator", "question_sort_order",
            "last_login", "user", "current_user", "map_coords",
            "user_nickname", "user_email",
            "seconds_since_joined", "has_current_goals", "public_badges",
            "avatar_name", "username", "is_profile_public",
            "birthdate", "gender",
            "conversion_test_hard_exercises",
            "conversion_test_easy_exercises",
            "child_capabilities",
    ]

    conversion_test_hard_exercises = set([
        'order_of_operations', 'graphing_points', 'probability_1',
        'domain_of_a_function', 'division_4', 'ratio_word_problems',
        'writing_expressions_1', 'ordering_numbers', 'geometry_1',
        'converting_mixed_numbers_and_improper_fractions'])
    conversion_test_easy_exercises = set([
        'counting_1', 'significant_figures_1', 'subtraction_1'])


    @property
    def nickname(self):
        """Gets a human-friendly display name that the user can optionally set
        themselves. Will initially default to either the Facebook name or
        part of the user's e-mail.
        """

        # Note - we make a distinction between "None", which means the user has
        # never gotten or set their nickname, and the empty string, which means
        # the user has explicitly made an empty nickname
        if self.user_nickname is not None:
            return self.user_nickname

        return nicknames.get_default_nickname_for(self)

    def update_nickname(self, nickname=None):
        """Updates the user's nickname and relevant indices and persists
        to the datastore.
        """
        if nickname is None:
            nickname = nicknames.get_default_nickname_for(self)
        new_name = nickname or ""

        if new_name != self.user_nickname:
            if nickname and not nicknames.is_valid_nickname(nickname):
                # The user picked a name, and it seems offensive. Reject it.
                return False

            self.user_nickname = new_name

            def txn():
                NicknameIndex.update_indices(self)
                self.put()
            transaction_util.ensure_in_transaction(txn, xg_on=True)
            discussion_models.Feedback.update_author_nickname(self)
        return True

    @property
    def email(self):
        """Represents the user-visible email address for the user.

        Note that for some users, this field can be a URI and not an actual
        e-mail address, and for some users this may be empty (e.g. child
        accounts). Use has_sendable_email() to determine if it's a real email.

        Email values are guaranteed to be unique across users, so this can
        be used as a public identifier for a user.
        """
        return self.user_email

    @property
    def key_email(self):
        """key_email is an unchanging key that's used
        as a reference to this user in many old db entities.
        It will never change, and it does not represent the user's
        actual email. It is used as a key for db queries only. It
        should not be displayed to users -- for that, use the 'email'
        property.
        """
        return self.user.email()

    def has_sendable_email(self):
        """Whether or not this user's email property corresponds to
        an actual e-mail that we can send mail to.
        """

        if self.is_pre_phantom:
            return False

        value = self.email
        return (value and
                not facebook_util.is_facebook_user_id(value) and
                not phantom_users.phantom_util.is_phantom_id(value))

    @property
    def badge_counts(self):
        return badges.util_badges.get_badge_counts(self)

    def has_badge(self, badge_name, target_context_name=None,
                  ignore_target_context=False):
        """Returns True if this user has a given badge.

        Arguments:
            badge_name: The name of the badge to check
                (ex: "gettingstartedbadge")
            target_context_name: The exercise in which the badge was earned
                (ex: "Addition 1")
            ignore_target_context: Whether to ignore the target context.
                (ex: True if we are only interested in checking that this user
                has earned a "Net begonnen" badge, regardless of what
                exercise(s) it was in.)

        """
        if target_context_name:
            badge_name = badges.Badge.add_target_context_name(
                badge_name, target_context_name)

        badge_name_list = []
        if ignore_target_context:
            context_regex = r"(\[.+\])"
            badge_name_list = [re.sub(context_regex, "", b) for b
                                                            in self.badges]
        else:
            badge_name_list = self.badges

        return badge_name in badge_name_list

    @staticmethod
    def get_from_url_segment(segment):
        """Retrieve a user by a URL segment, as expected to be built from
        the user's UserData.profile_root value.

        Arguments:
            segment - A string for the segment to query the user by, typically
                 URI encoded (though this method will try to be flexible).
        """
        if segment.startswith(_USER_KEY_PREFIX):
            key = segment[len(_USER_KEY_PREFIX):]
            return db.get(key)
        else:
            return UserData.get_from_username(segment)

    @property
    def profile_root(self):
        """Returns the profile URL for the user.

        Unless it is a phantom user, the username is always used
        to indentify users in profile URLs.
        """
        if self.is_phantom:
            identifier = "nouser"
        elif self.username:
            identifier = self.username
        else:
            identifier = _USER_KEY_PREFIX + str(self.key())

        return "/profile/" + identifier + "/"

    # Return data about the user that we'd like to track in MixPanel
    @staticmethod
    def get_analytics_properties(user_data):
        properties_list = []

        if not user_data:
            properties_list.append(("User Type", "New"))
        elif user_data.is_phantom:
            properties_list.append(("User Type", "Phantom"))
        else:
            properties_list.append(("User Type", "Logged In"))

        if user_data:
            properties_list.extend([
                ("User Points", user_data.points),
                ("User Videos", user_data.get_videos_completed()),
                ("User Exercises", len(user_data.all_proficient_exercises)),
                ("User Badges", len(user_data.badges)),
                ("User Video Time", user_data.total_seconds_watched),
            ])

        return properties_list

    @staticmethod
    @request_cache.cache()
    def current(create_if_none=False):
        """Determine the current logged in user and return it.

        Arguments:
            create_if_none: Whether or not to create a new user if valid
                auth credentials are detected, but no existing user was found
                for those credentials.

        Returns:
            The user_models.UserData object corresponding to the logged in
            user, or phantom user. Returns None if no phantom or user
            was detected.
        """

        user_id = util.get_current_user_id_unsafe(bust_cache=True)
        if user_id is None:
            return None

        google_user = users.get_current_user()
        if google_user:
            email = google_user.email()
        else:
            email = user_id

        existing = UserData.get_from_request_info(user_id, email)
        if existing:
            return existing
        elif create_if_none:
            # Try to "upgrade" to a real email for FB users, if possible.
            if facebook_util.is_facebook_user_id(email):
                fb_email = facebook_util.get_fb_email_from_cookies()
                email = fb_email or user_id
            return UserData.insert_for(user_id, email)
        return None

    @staticmethod
    def get_from_request_info(user_id, email=None, oauth_map=None):
        """Retrieve a user given the specified information for the request.

        This should be used sparingly, typically by login code that can
        resolve the request information from authentication credentials
        or tokens in the request.

        Arguments:
            user_id:
                The user_id computed from the request credentials.
                This is typically the user_id of the returned user,
                if one matches. However, if no existing user matches
                this user_id, and an existing e-mail matches instead,
                the result user will have a different user_id.

            email:
                The e-mail address from the request credentials (may be a URI
                value for Facebook users).

            oauth_map:
                The OAuthMap corresponding to this request. If None is
                provided, this method will look at the cookies for the
                current request (if cookie auth is allowed).

        Returns:
            The existing UserData object matching the parameters, if any.
            None if no user was found.
        """

        if not user_id:
            return None

        # Always try to retrieve by user_id. Note that for _really_ old users,
        # we didn't have user_id values, and we used a "db_key_email". That
        # value never changes (it's an e-mail for most users, but is a URI
        # for facebook users).
        existing = (UserData.get_from_user_id(user_id) or
                    UserData.get_from_db_key_email(email))
        if existing:
            return existing

        # If no user exists by the user_id, it could be that the user logged
        # in as a different third party auth provider than what she
        # initially registered with (logging now with FB instead of Google).
        # Look for a matching e-mail address (this time the email value
        # tries to be a real email for FB users, not a URI).
        if facebook_util.is_facebook_user_id(user_id):
            if oauth_map:
                fb_email = facebook_util.get_fb_email_from_oauth_map(oauth_map)
            else:
                fb_email = facebook_util.get_fb_email_from_cookies()
            email = fb_email or user_id

        return UserData.get_from_user_input_email(email)

    @staticmethod
    def pre_phantom():
        return UserData.insert_for(_PRE_PHANTOM_EMAIL, _PRE_PHANTOM_EMAIL)

    @property
    def is_facebook_user(self):
        """Return whether or not this account was registered using Facebook.

        Note that it's possible that the user has logged in with Facebook,
        but had initially registered the account using a Google or KA login,
        in which case this will return False.
        """
        return facebook_util.is_facebook_user_id(self.user_id)

    @property
    def is_google_user(self):
        """Return whether or not this account was registered using Google.
        """
        return self.user_id.startswith(GOOGLE_ID_PREFIX)

    @property
    def is_phantom(self):
        return util.is_phantom_user(self.user_id)

    @property
    def is_demo(self):
        return (self.user_email and
                self.user_email.startswith(_COACH_DEMO_COWORKER_EMAIL))

    @property
    def is_pre_phantom(self):
        return _PRE_PHANTOM_EMAIL == self.user_email

    @property
    def is_moderator_or_developer(self):
        """Returns True if the user is either a moderator or developer."""
        return self.moderator or self.developer

    @property
    def seconds_since_joined(self):
        return util.seconds_since(self.joined)

    @staticmethod
    @request_cache.cache_with_key_fxn(
        lambda user_id: "UserData_user_id:%s" % user_id)
    def get_from_user_id(user_id):
        if not user_id:
            return None

        query = UserData.all()
        query.filter('user_id =', user_id)
        query.order('-points')  # Temporary workaround for issue 289

        return query.get()

    @staticmethod
    def get_from_user_input_email(email):
        if not email:
            return None

        query = UserData.all()
        query.filter('user_email =', email)
        query.order('-points')  # Temporary workaround for issue 289

        return query.get()

    @staticmethod
    def get_from_username(username):
        if not username:
            return None
        canonical_username = UniqueUsername.get_canonical(username)
        if not canonical_username:
            return None
        query = UserData.all()
        query.filter('username =', canonical_username.username)
        return query.get()

    @staticmethod
    def get_from_db_key_email(email):
        if not email:
            return None

        query = UserData.all()
        query.filter('user =', users.User(email))
        query.order('-points')  # Temporary workaround for issue 289

        return query.get()

    @staticmethod
    def get_from_user(user):
        return UserData.get_from_db_key_email(user.email())

    @staticmethod
    def get_from_username_or_email(username_or_email):
        if not username_or_email:
            return None

        return user_util.get_possibly_current_user(username_or_email)

    @classmethod
    def key_for(cls, user_id):
        return "user_id_key_%s" % user_id

    # TODO(benkomalo): this has become quite complicated and should only be
    # used as a low-level tool to instantiate users. Break this up into
    # distinct calls for the different cases with more a explicit API, as
    # some of these parameters don't even make sense together.
    @staticmethod
    def insert_for(user_id, email,
                   username=None, password=None, parent_user=None, **kwds):
        """Create a user with the specified values, if possible, or returns
        an existing user if the user_id has been used by an existing user.

        Arguments:
            user_id:
                The unique user_id of the user. Should be non-empty.
            email:
                The unique email address of the user. This corresponds
                to the "key_email" value of UserData, and will also be used
                for the "email" property, if non-empty. This can be empty
                for child accounts
            username:
                The unique username to set for this user, if any. Optional.
            password:
                The password to set for this user, if any. Optional.
            parent_user:
                Another UserData instance to set as the parent account of
                this account. Must be specified if this is a child account.

        Returns:
            None if user_id or email values are invalid, or the user couldn't
            be created for other reasons. Otherwise, returns the created,
            or existing user if this user_id is being re-used.
        """

        if not user_id:
            # Every account requires a user_id
            return None

        if not email and not parent_user:
            # Every account that isn't a child account requires an e-mail.
            return None

        if parent_user and (not username or not password):
            raise Exception("Child accounts require username and password")

        # Make default dummy values for the ones that don't matter
        prop_values = {
            'moderator': False,
            'proficient_exercises': [],
            'suggested_exercises': [],
            'need_to_reassess': True,
            'points': 0,
            'coaches': [],
        }

        # Allow clients to override
        prop_values.update(**kwds)

        # Forcefully override with important items.
        db_user_email = email or user_id
        user_email = email

        user = users.User(db_user_email)
        key_name = UserData.key_for(user_id)
        for pname, pvalue in {
            'key_name': key_name,
            'user': user,
            'current_user': user,
            'user_id': user_id,
            'user_email': user_email,
            }.iteritems():
            if pname in prop_values:
                logging.warning("UserData creation about to override"
                                " specified [%s] value" % pname)
            prop_values[pname] = pvalue

        if username or password:
            # Username or passwords are separate entities.
            # That means we have to do this in multiple steps - make a txn.
            def create_txn():
                user_data = UserData.get_by_key_name(key_name)
                if user_data is not None:
                    logging.warning("Tried to re-make a user for key=[%s]" %
                                    key_name)
                    return user_data

                user_data = UserData(**prop_values)
                # Both claim_username and set_password updates user_data
                # and will call put() for us.
                if username and not user_data.claim_username(username):
                    raise datastore_errors.Rollback(
                        "username [%s] already taken" % username)
                if password and user_data.set_password(password):
                    raise datastore_errors.Rollback(
                        "invalid password for user")

                if parent_user:
                    # Parent user was specified, create a bond.
                    if not ParentChildPair.make_bond(parent_user, user_data):
                        raise datastore_errors.Rollback(
                            "Unable to create child account")
                return user_data

            user_data = transaction_util.ensure_in_transaction(create_txn,
                                                               xg_on=True)

        else:
            # No username means we don't have to do manual transactions.
            # Note that get_or_insert is a transaction itself, and it can't
            # be nested in the above transaction.
            user_data = UserData.get_or_insert(**prop_values)
            user_data = db.get(user_data.key())   # force-commit for HRD data

        if user_data and not user_data.is_phantom:
            # Record that we now have one more registered user
            if (datetime.datetime.now() - user_data.joined).seconds < 60:
                # Extra safety check against user_data.joined in case some
                # subtle bug results in lots of calls to insert_for for
                # UserData objects with existing key_names.
                user_counter.add(1)

                gae_bingo.gae_bingo.bingo('registered_binary')  # Core metric

        return user_data

    def spawn_child(self, username, birthdate, password):
        """Create a child account with this account as the parent.

        Returns None if a child account could not be created or bonded to
        this account for any reason.
        """

        if age_util.get_age(birthdate) >= 13:
            raise Exception("Can't spawn child that's over 13!")

        user_id = uid.new_user_id()

        result = UserData.insert_for(user_id,
                                     email=None,
                                     username=username,
                                     password=password,
                                     birthdate=birthdate,
                                     parent_user=self,
                                     user_nickname=username)

        if result:
            # HACK(benkomalo): Flush the transaction for the parent/child pair
            # This corresponds to a line in ParentChildPair.make_bond, which,
            # when run inside the insert_for transaction, obviously doesn't do
            # us much good, so we have to do another get outside the txn.
            ParentChildPair.get_for_child(result)

        return result

    def consume_identity(self, new_user):
        """Take over another UserData's identity by updating this user's
        user_id, and other personal information with that of new_user's,
        assuming the new_user has never received any points.

        This is useful if this account is a phantom user with history
        and needs to be updated with a newly registered user's info, or some
        other similar situation.

        This method will fail if new_user has any points whatsoever,
        since we don't yet support migrating associated UserVideo
        and UserExercise objects.

        Returns whether or not the merge was successful.
        """

        if (new_user.points > 0):
            return False

        # Really important that we be mindful of people who have been added as
        # coaches - no good way to transfer that right now.
        if new_user.has_students():
            return False

        def txn():
            # IMPORTANT: historically, activity data like ProblemLog,
            # UserExercise, VideoLog, etc, uses a db.UserProperty corresponding
            # to the UserData.user property, we do *not* transfer that over.
            # That way, only identity is transfered, and history is maintained.
            # If any user-owned entities are using different foreign keys, like
            # any of the information below, they must be re-keyed accordingly.
            self.user_id = new_user.user_id
            self.current_user = new_user.current_user
            self.user_email = new_user.user_email
            self.user_nickname = new_user.user_nickname
            self.birthdate = new_user.birthdate
            self.gender = new_user.gender
            self.joined = new_user.joined
            if new_user.last_login:
                if self.last_login:
                    self.last_login = max(new_user.last_login, self.last_login)
                else:
                    self.last_login = new_user.last_login
            self.set_password_from_user(new_user)
            UniqueUsername.transfer(new_user, self)

            # TODO(benkomalo): update nickname and indices!

            if self.put():
                new_user.delete()
                return True
            return False

        result = transaction_util.ensure_in_transaction(txn, xg_on=True)
        if result:
            # Note that all of the updates to the above fields causes changes
            # to indices affected by each user. Since some of those are really
            # important (e.g. retrieving a user by user_id), it'd be dangerous
            # for a subsequent request to see stale indices. Force an apply()
            # of the HRD by doing a get()
            db.get(self.key())
            db.get(new_user.key())
        return result

    @staticmethod
    def get_visible_user(user, actor=None):
        """Retrieve user for actor, in the style of O-Town, all or nothing.

        TODO(marcia): Sort out UserData and UserProfile visibility turf war
        """
        if actor is None:
            actor = UserData.current() or UserData.pre_phantom()

        if user and user.is_visible_to(actor):
            # Allow access to user's profile
            return user

        return None

    def delete(self, clock=None):
        # Override delete(), so that we can log this severe event, and clean
        # up some statistics.
        logging.info("Deleting user data %s with points %s and badges [%s]" %
                     (str(self), self.points, self.badges))

        # Avoid calling JSONify which may touch badge models and queries to
        # do the JSONify if there are cache misses. That would be unwise in
        # a transaction since GAE doesn't like non-ancestor queries in txn's
        if not db.is_in_transaction():
            logging.info("Dumping user data for %s: %s" %
                         (self.user_id, jsonify.jsonify(self)))

        if not self.is_phantom:
            user_counter.add(-1)

        # TODO(benkomalo): handle cleanup of nickname indices!
        # TODO(benkomalo): handle cleanup of orphaned site info (exercises,
        #      Q&A data, video, stack data, etc)
        # TODO(benkomalo): handle cleanup of orphaned child users

        def do_deletion():
            if self.username:
                UniqueUsername.release(self.username, clock=clock)

            # Delegate to the normal implentation
            super(UserData, self).delete()

        return transaction_util.ensure_in_transaction(do_deletion, xg_on=True)

    def is_over_eighteen(self):
        """A conservative check that guarantees a user is at least 18.

        Note that even if someone is over 18, this can return False, since we
        may not have their birthdate. However, if this returns True,
        they're guaranteed to be over 18.
        """

        if self.birthdate:
            return age_util.get_age(self.birthdate) >= 18
        return False

    def is_eligible_parent(self):
        return (not self.is_phantom and
                # If we have a birthdate on record, require them to be >18.
                # Otherwise, our ToS should enforce that requirement.
                (not self.birthdate or self.is_over_eighteen()))

    def is_child_account(self):
        """Whether or not this account is intended for someone under 13.

        Child accounts have restricted functionality on the site, such as
        limited ability to interact with the community.
        """

        if self.birthdate:
            return age_util.get_age(self.birthdate) < 13

        # Users who are missing a birthdate in the system registered via
        # third party accounts (Google or Facebook), and their ToS requires
        # users to be 13 years old (with the exception of Google Apps for Edu,
        # though they have parental consent to be treated as full users)
        return False

    def get_parent_user(self):
        """Return the UserData for this user's parent, if any.

        A parent account is automatically a coach of this account, and
        manages this account (e.g. has access to change passwords).

        A given UserData instance can only have one parent.
        """
        bond = ParentChildPair.get_for_child(self)
        return bond and bond.resolve_parent()

    def get_child_users(self):
        """Return the child accounts for this user.

        This user may manage multiple child accounts. Note that th
        term "child" in this context denotes relationship only; it's possible
        that the child has grown up and no longer returns True for
        UserData.is_child_account() (though it's likely the case that
        a child account of a parent account is also a truly under 13).
        """
        return [bond.resolve_child()
                for bond in ParentChildPair.get_for_parent(self)]

    def is_maybe_edu_account(self):
        """A conservative check for Google Apps for Education users.

        Note that this method may return True for users in the gray area,
        even though they may not be GAFE users, since there is no official,
        sanctioned way by Google to check if a domain is a GAFE domain.
        """

        if self.developer:
            return False

        if self.is_facebook_user:
            return False

        if not self.has_sendable_email():
            return False

        domain_index = self.email.rfind('@')
        email_domain = self.email[domain_index + 1:]

        white_listed_domains = set(["gmail.com",
                                    "googlemail.com",  # Gmail in germany
                                    "khanacademy.org",
                                    "hotmail.com",
                                    "aol.com",
                                    "yahoo.com",
                                    "comcast.net",
                                    "live.com",
                                    "sbcglobal.net",
                                    "msn.com",
                                    "ymail.com",
                                    "hotmail.co.uk",
                                    "verizon.net",
                                    "att.net",
                                    "me.com",
                                    "rocketmail.com",
                                   ])

        return email_domain not in white_listed_domains

    def get_or_insert_exercise(self, exercise, allow_insert=True):
        # TODO(csilvers): get rid of the circular import here
        import exercise_models

        if not exercise:
            return None

        exid = exercise.name
        userExercise = exercise_models.UserExercise.get_by_key_name(
            exid, parent=self)

        if not userExercise:
            # There are some old entities lying around that don't have
            # keys.  We have to check for them here, but once we have
            # reparented and rekeyed legacy entities, this entire
            # function can just be a call to .get_or_insert()
            query = exercise_models.UserExercise.all(keys_only=True)
            query.filter('user =', self.user)
            query.filter('exercise =', exid)
            query.order('-total_done')  # Temporary workaround for issue 289

            # In order to guarantee consistency in the HR datastore, we need to
            # query via db.get for these old, parent-less entities.
            key_user_exercise = query.get()
            if key_user_exercise:
                userExercise = exercise_models.UserExercise.get(
                    str(key_user_exercise))

            TinCan.create_question(self, "launched", exercise)

        if allow_insert and not userExercise:
            userExercise = exercise_models.UserExercise.get_or_insert(
                key_name=exid,
                parent=self,
                user=self.user,
                exercise=exid,
                exercise_model=exercise,
                streak=0,
                _progress=0.0,
                longest_streak=0,
                first_done=datetime.datetime.now(),
                last_done=None,
                total_done=0,
                _accuracy_model=accuracy_model.AccuracyModel(),
                )

        return userExercise

    def reassess_from_graph(self, user_exercise_graph):
        all_proficient = user_exercise_graph.proficient_exercise_names()
        suggested_exercises = user_exercise_graph.suggested_exercise_names()

        is_changed = (all_proficient != self.all_proficient_exercises or
                      suggested_exercises != self.suggested_exercises)

        self.all_proficient_exercises = all_proficient
        self.suggested_exercises = suggested_exercises
        self.need_to_reassess = False

        return is_changed

    def reassess_if_necessary(self, user_exercise_graph=None):
        if not self.need_to_reassess or self.all_proficient_exercises is None:
            return False

        if user_exercise_graph is None:
            # TODO(csilvers): get rid of the circular import here
            import exercise_models
            user_exercise_graph = exercise_models.UserExerciseGraph.get(self)

        return self.reassess_from_graph(user_exercise_graph)

    def is_proficient_at(self, exid, exgraph=None):
        self.reassess_if_necessary(exgraph)
        return (exid in self.all_proficient_exercises)

    def is_explicitly_proficient_at(self, exid):
        return (exid in self.proficient_exercises)

    def is_suggested(self, exid):
        self.reassess_if_necessary()
        return (exid in self.suggested_exercises)

    def get_coaches_data(self):
        """Return list of coaches UserData for this user."""
        coaches = []
        for key_email in self.coaches:
            user_data_coach = UserData.get_from_db_key_email(key_email)
            if user_data_coach:
                coaches.append(user_data_coach)
            else:
                logging.warning("No coach with info [db_key_email=%s] "
                                "exists for user %s" % (key_email, self))
        return coaches

    def can_modify_coaches(self):
        if not self.is_child_account():
            return True
        return Capabilities.can_modify_coaches(self.child_capabilities)

    def set_can_modify_coaches(self, allow=True):
        if not self.is_child_account():
            # Normal accounts can always do this, so it's a noop.
            return

        self.child_capabilities = Capabilities.set_can_modify_coaches(
                self.child_capabilities,
                allow=allow)
        self.put()

    def remove_coach(self, key_email):
        if not self.can_modify_coaches():
            raise CapabilityError("Can't remove coaches")
        parent_user = self.get_parent_user()
        if parent_user and key_email.lower() == parent_user.key_email.lower():
            # Note that parents are perma-coaches and can't be removed.
            return
        self.coaches.remove(key_email)
        self.put()

    def add_coach(self, coach_data, force=False):
        """Adds a coach to the list of coaches for this user.

        Arguments:
            coach_data:
                The UserData instance of the coach to add.
            force:
                Whether or not this should bypass any capabilities check, and
                the client knows the coach bond should be forced. Use
                sparingly.
        """
        if not force and not self.can_modify_coaches():
            raise CapabilityError("Can't add coaches")

        if (coach_data.key_email in self.coaches or
                coach_data.key_email.lower() in self.coaches):
            return

        self.coaches.append(coach_data.key_email)
        self.put()

    def update_coaches(self, coach_key_emails):
        """Wholly replace the set of coaches with the given list of coaches.

        Note that parent users (see get_parent_user) are automatically coaches
        and cannot be removed, so the final coach set may differ slightly
        after this call to maintain that invariant.

        Arguments:
            coach_key_emails: A list of key_email values of the coaches to add.
        """
        if not self.can_modify_coaches():
            raise CapabilityError("Can't modify coaches")

        self.coaches = list(set(coach_key_emails))

        # Ensure that parents are still coaches.
        parent_user = self.get_parent_user()
        if parent_user:
            self.add_coach(parent_user, force=True)

        self.put()

    def get_students_data(self):
        """Return the full list of student UserData for this user."""
        coach_email = self.key_email
        query = UserData.all().filter('coaches =', coach_email)
        students_data = query.fetch(1000)

        # Attempt to be slightly case insensitive
        if coach_email.lower() != coach_email:
            students_set = set([s.key().id_or_name() for s in students_data])
            query = UserData.all().filter('coaches =', coach_email.lower())
            for student_data in query:
                if student_data.key().id_or_name() not in students_set:
                    students_data.append(student_data)

        return students_data

    def get_coworkers_data(self):
        return filter(
            lambda user_data: user_data is not None,
            map(lambda coworker_email:
                    UserData.get_from_db_key_email(coworker_email),
                self.coworkers))

    def has_students(self):
        coach_email = self.key_email

        # Coach keys use the "db_key_email" property.
        count = UserData.all().filter('coaches =', coach_email).count()
        if count > 0:
            return True

        # Attempt to be slightly case insensitive
        if coach_email.lower() != coach_email:
            count = UserData.all().filter('coaches =',
                                          coach_email.lower()).count()

        if count > 0:
            return True

        return len(self.get_child_users()) > 0

    def remove_student_lists(self, removed_coach_emails):
        """Remove student lists associated with removed coaches."""
        if len(removed_coach_emails):
            # Get the removed coaches' keys
            removed_coach_keys = frozenset([
                    UserData.get_from_username_or_email(coach_email).key()
                    for coach_email in removed_coach_emails])

            # Get the StudentLists from our list of StudentList keys
            student_lists = StudentList.get(self.student_lists)

            # Theoretically, a StudentList allows for multiple coaches, but in
            # practice there is exactly one coach per StudentList.  If/when we
            # support multiple coaches per list, we would need to change how
            # this works... How *does* it work? Well, let me tell you.

            # Set our student_lists to all the keys of StudentLists
            # whose coaches do not include any removed coaches.
            self.student_lists = [l.key() for l in student_lists
                    if (len(frozenset(l.coaches) & removed_coach_keys) == 0)]

    def is_coached_by(self, user_data_coach):
        if (user_data_coach.key_email in self.coaches or
                user_data_coach.key_email.lower() in self.coaches):
            return True
        parent_user = self.get_parent_user()
        if parent_user:
            return parent_user.user_id == user_data_coach.user_id
        return False

    def is_coworker_of(self, user_data_coworker):
        return user_data_coworker.key_email in self.coworkers

    def is_coached_by_coworker_of_coach(self, user_data_coach):
        for coworker_email in user_data_coach.coworkers:
            if coworker_email in self.coaches:
                return True
        return False

    def is_visible_to(self, user_data):
        """Returns whether or not this user's information is *fully* visible
        to the specified user
        """
        return (self.key() == user_data.key() or
                self.is_coached_by(user_data) or
                self.is_coached_by_coworker_of_coach(user_data) or
                user_data.developer)

    def are_students_visible_to(self, user_data):
        return (self.is_coworker_of(user_data) or
                user_data.developer)

    def record_activity(self, dt_activity):

        # Make sure last_activity and start_consecutive_activity_date have
        # values
        self.last_activity = self.last_activity or dt_activity
        self.start_consecutive_activity_date = (
            self.start_consecutive_activity_date or dt_activity)

        if dt_activity > self.last_activity:

            # If it has been over 40 hours since we last saw this user, restart
            # the consecutive activity streak.
            #
            # We allow for a lenient 40 hours in order to offer kinder timezone
            # interpretation.
            #
            # 36 hours wasn't quite enough. A user with activity at 8am on
            # Monday and 8:15pm on Tuesday would not have consecutive days of
            # activity.
            #
            # See http://meta.stackoverflow.com/questions/55483/proposed-consecutive-days-badge-tracking-change
            if util.hours_between(self.last_activity, dt_activity) >= 40:
                self.start_consecutive_activity_date = dt_activity

            self.last_activity = dt_activity

    def current_consecutive_activity_days(self):
        if not self.last_activity or not self.start_consecutive_activity_date:
            return 0

        dt_now = datetime.datetime.now()

        # If it has been over 40 hours since last activity, bail.
        if util.hours_between(self.last_activity, dt_now) >= 40:
            return 0

        return (self.last_activity - self.start_consecutive_activity_date).days

    def add_points(self, points):
        if self.points is None:
            self.points = 0

        if not hasattr(self, "_original_points"):
            self._original_points = self.points

        # Check if we crossed an interval of 2500 points
        if self.points % 2500 > (self.points + points) % 2500:
            phantom_users.util_notify.update(
                self, user_exercise=None, threshold=True)
        self.points += points

    def original_points(self):
        return getattr(self, "_original_points", 0)

    def get_videos_completed(self):
        if self.videos_completed < 0:
            # TODO(csilvers): get rid of the circular import here
            import video_models
            self.videos_completed = (
                video_models.UserVideo.count_completed_for_user_data(self))
            self.put()
        return self.videos_completed

    def mark_feedback_notification_count_as_stale(self):
        """Mark that the feedback notification count must be recalculated."""
        self.count_feedback_notification = -1
        self.put()

    def feedback_notification_count(self):
        """Return the number of questions with unread answers.

        May calculate (and cache) a stale count if called shortly after any
        change to the FeedbackNotification index.
        """
        if self.count_feedback_notification == -1:
            # Recalculate feedback notification count

            # Get all unread answers
            answers = discussion_models.FeedbackNotification.get_feedback_for(
                    self)

            # Group the unread answers by question
            questions = set(answer.question_key() for answer in answers
                            if answer.question().is_type(
                                discussion_models.FeedbackType.Question))

            self.count_feedback_notification = len(questions)
            self.put()

        return self.count_feedback_notification

    def save_goal(self, goal):
        """Save a goal, atomically updating the user_data.has_current_goal when
        necessary.
        """

        if self.has_current_goals:  # no transaction necessary
            goal.put()
            return

        # otherwise this is the first goal the user has created, so be sure we
        # update user_data.has_current_goals too
        def save_goal():
            self.has_current_goals = True
            db.put([self, goal])
        db.run_in_transaction(save_goal)

    def claim_username(self, name, clock=None):
        """Claims a username for the current user, and assigns it to her
        atomically. Returns True on success.

        Note: If you call this method inside another transaction,
            remember to flush the changes outside it using
            db.get([self.key()]).
        """
        def claim_and_set():
            claim_success = UniqueUsername._claim_internal(
                name, claimer_id=self.user_id, clock=clock)
            if claim_success:
                if self.username:
                    UniqueUsername.release(self.username, clock)
                self.username = name
                self.put()
            return claim_success

        result = transaction_util.ensure_in_transaction(
            claim_and_set, xg_on=True)
        if result:
            # Success! Ensure we flush the apply() phase of the modifications
            # so that subsequent queries get consistent results. This makes
            # claiming usernames slightly slower, but safer since rapid
            # claiming or rapid claim/read won't result in weirdness.
            db.get([self.key()])
        return result

    def has_password(self):
        return self.credential_version is not None

    def has_public_profile(self):
        return (self.is_profile_public and
                bool(self.username) and
                not self.is_child_account())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return "<UserData [%s] [%s] [%s]>" % (self.user_id,
                                              self.email,
                                              self.username or "<no username>")

    @classmethod
    def from_json(cls, json, user=None):
        """This method exists for testing convenience only. It's called only
        by code that runs in exclusively in development mode. Do not rely on
        this method in production code. If you need to break this code to
        implement some new feature, feel free!
        """
        user_id = json['user_id']
        email = json['email']
        user = user or users.User(email)

        user_data = cls(
            key_name=cls.key_for(user_id),
            user=user,
            current_user=user,
            user_id=user_id,
            user_email=email,
            moderator=False,
            joined=util.parse_iso8601(json['joined']),
            last_activity=util.parse_iso8601(json['last_activity']),
            last_badge_review=util.parse_iso8601(json['last_badge_review']),
            start_consecutive_activity_date=util.parse_iso8601(
                    json['start_consecutive_activity_date']),
            need_to_reassess=True,
            points=int(json['points']),
            nickname=json['nickname'],
            coaches=['test@example.com'],
            total_seconds_watched=int(json['total_seconds_watched']),
            all_proficient_exercises=json['all_proficient_exercises'],
            proficient_exercises=json['proficient_exercises'],
            suggested_exercises=json['suggested_exercises'],
        )
        return user_data


class UniqueUsername(db.Model):
    """Stores usernames that users have set from their profile page."""
    # The username value selected by the user.
    username = db.StringProperty()

    # A date indicating when the username was released.
    # This is useful to block off usernames, particularly after they were just
    # released, so they can be put in a holding period.
    # This will be set to an "infinitely" far-futures date while the username
    # is in use
    release_date = db.DateTimeProperty()

    # The user_id value of the UserData that claimed this username.
    # NOTE - may be None for some old UniqueUsername objects, or if it was
    # just blocked off for development.
    claimer_id = db.StringProperty()

    @staticmethod
    def build_key_name(username):
        """Builds a unique, canonical version of a username."""
        if username is None:
            logging.error("Trying to build a key_name for a null username!")
            return ""
        return username.replace('.', '').lower()

    # Usernames must be at least 3 characters long (excluding periods), must
    # start with a letter
    VALID_KEY_NAME_RE = re.compile('^[a-z][a-z0-9]{2,}$')

    @staticmethod
    def is_username_too_short(username, key_name=None):
        if key_name is None:
            key_name = UniqueUsername.build_key_name(username)
        return len(key_name) < 3

    @staticmethod
    def is_valid_username(username, key_name=None):
        """Determines if a candidate for a username is valid
        according to the limitations we enforce on usernames.

        Usernames must be at least 3 characters long (excluding dots), start
        with a letter and be alphanumeric (ascii only).
        """
        if username.startswith('.'):
            return False
        if key_name is None:
            key_name = UniqueUsername.build_key_name(username)
        return UniqueUsername.VALID_KEY_NAME_RE.match(key_name) is not None

    @staticmethod
    def is_available_username(username, key_name=None, clock=None):
        if key_name is None:
            key_name = UniqueUsername.build_key_name(username)
        entity = UniqueUsername.get_by_key_name(key_name)
        if clock is None:
            clock = datetime.datetime
        return entity is None or not entity._is_in_holding(clock.utcnow())

    @staticmethod
    def matches(username1, username2):
        """Determine if two username strings match to one canonical name.

        If either string is not a valid username, will return False.
        """
        if not username1 or not username2:
            return False
        key1 = UniqueUsername.build_key_name(username1)
        key2 = UniqueUsername.build_key_name(username2)
        if (not UniqueUsername.is_valid_username(username1, key1) or
                not UniqueUsername.is_valid_username(username2, key2)):
            return False
        return key1 == key2

    def _is_in_holding(self, utcnow):
        return (self.release_date + UniqueUsername.HOLDING_PERIOD_DELTA >=
                utcnow)

    INFINITELY_FAR_FUTURE = datetime.datetime(9999, 1, 1, 0, 0, 0)

    # Released usernames are held for 120 days
    HOLDING_PERIOD_DELTA = datetime.timedelta(120)

    @staticmethod
    def _claim_internal(desired_name, claimer_id=None, clock=None):
        key_name = UniqueUsername.build_key_name(desired_name)
        if not UniqueUsername.is_valid_username(desired_name, key_name):
            return False

        is_available = UniqueUsername.is_available_username(
                desired_name, key_name, clock)
        if is_available:
            entity = UniqueUsername(key_name=key_name)
            entity.username = desired_name
            entity.release_date = UniqueUsername.INFINITELY_FAR_FUTURE
            entity.claimer_id = claimer_id
            entity.put()
        return is_available

    @staticmethod
    def claim(desired_name, claimer_id=None, clock=None):
        """Claim an unclaimed username.

        Return True on success, False if you are a slow turtle or invalid.
        See is_valid_username for limitations of a username.
        """

        key_name = UniqueUsername.build_key_name(desired_name)
        if not UniqueUsername.is_valid_username(desired_name, key_name):
            return False

        return db.run_in_transaction(UniqueUsername._claim_internal,
                                     desired_name,
                                     claimer_id,
                                     clock)

    @staticmethod
    def release(username, clock=None):
        if clock is None:
            clock = datetime.datetime

        if username is None:
            logging.error("Trying to release a null username!")
            return

        entity = UniqueUsername.get_canonical(username)
        if entity is None:
            logging.warn("Releasing username %s that doesn't exist" % username)
            return
        entity.release_date = clock.utcnow()
        entity.put()

    @staticmethod
    def transfer(from_user, to_user):
        """Transfers a username from one user to another, assuming the to_user
        does not already have a username.

        Returns whether or not a transfer occurred.
        """
        def txn():
            if not from_user.username or to_user.username:
                return False
            entity = UniqueUsername.get_canonical(from_user.username)
            entity.claimer_id = to_user.user_id
            to_user.username = from_user.username
            from_user.username = None
            db.put([from_user, to_user, entity])
            return True
        return transaction_util.ensure_in_transaction(txn, xg_on=True)

    @staticmethod
    def get_canonical(username):
        """Returns the entity with the canonical format of the user name, as
        it was originally claimed by the user, given a string that may include
        more or less period characters in it.

        e.g. "joe.smith" may actually translate to "joesmith"
        """
        key_name = UniqueUsername.build_key_name(username)
        return UniqueUsername.get_by_key_name(key_name)


class NicknameIndex(db.Model):
    """Index entries to be able to search users by their nicknames.

    Each user may have multiple index entries, all pointing to the same user.
    These entries are expected to be direct children of UserData entities.

    These are created for fast user searches.
    """

    # The index string that queries can be matched again. Must be built out
    # using nicknames.build_index_strings
    index_value = db.StringProperty()

    @staticmethod
    def update_indices(user):
        """ Updates the indices for a user given her current nickname. """
        nickname = user.nickname
        index_strings = nicknames.build_index_strings(nickname)

        db.delete(NicknameIndex.entries_for_user(user))
        entries = [NicknameIndex(parent=user, index_value=s)
                   for s in index_strings]
        db.put(entries)

    @staticmethod
    def entries_for_user(user):
        """Retrieves all index entries for a given user. """
        q = NicknameIndex.all()
        q.ancestor(user)
        return q.fetch(10000)

    @staticmethod
    def users_for_search(raw_query):
        """Given a raw query string, retrieve a list of the users that match
        that query by returning a list of their entity's key values.

        The values are guaranteed to be unique.

        TODO: there is no ranking among the result set, yet
        TODO: extend API so that the query can have an optional single token
              that can be prefixed matched, for autocomplete purposes
        """

        q = NicknameIndex.all()
        q.filter("index_value =", nicknames.build_search_query(raw_query))
        return list(set([entry.parent_key() for entry in q]))


class UnverifiedUser(db.Model):
    """Preliminary signup data for new users.

    Includes an e-mail address that needs to be verified.
    """

    email = db.StringProperty()
    birthdate = db.DateProperty(indexed=False)

    # If at the time of signup, the user was in the middle of performing some
    # action, try to preserve that so they can resume as soon as they're done
    continue_url = db.StringProperty(indexed=False)

    # used as a token sent in an e-mail verification link.
    randstring = db.StringProperty(indexed=True)
    coach_project = db.BooleanProperty(default=False)

    @staticmethod
    def get_or_insert_for_value(email, birthdate, continue_url):
        return UnverifiedUser.get_or_insert(
                key_name=email,
                email=email,
                birthdate=birthdate,
                continue_url=continue_url,
                randstring=os.urandom(20).encode("hex"))

    @staticmethod
    def get_for_value(email):
        # Email is also used as the db key
        return UnverifiedUser.get_by_key_name(email)

    @staticmethod
    def get_for_token(token):
        return UnverifiedUser.all().filter("randstring =", token).get()


# TODO(csilvers): move this away from user_models (into some
# coach-related models file?) once we can remove the circular
# dependency between StudentList and UserData.
class StudentList(db.Model):
    """A list of students associated with a single coach."""
    name = db.StringProperty()
    coaches = db.ListProperty(db.Key)

    def delete(self, *args, **kwargs):
        self.remove_all_students()
        db.Model.delete(self, *args, **kwargs)

    def remove_all_students(self):
        students = self.get_students_data()
        for s in students:
            s.student_lists.remove(self.key())
        db.put(students)

    @property
    def students(self):
        return UserData.all().filter("student_lists = ", self.key())

    # these methods have the same interface as the methods on UserData
    def get_students_data(self):
        return [s for s in self.students]

    @staticmethod
    def get_for_coach(key):
        query = StudentList.all()
        query.filter("coaches = ", key)
        return query


class ParentChildPair(db.Model):
    """A tie between two UserData's indicating a parent-child relationship.

    Parent accounts wholly manage child accounts and are automatically
    coaches of that child account.

    A parent may have multiple children, but child accounts cannot have more
    than one parent.
    """

    # Note - the "parent entity" is the child UserData.
    parent_user_id = db.StringProperty()

    @staticmethod
    def get_for_parent(parent_user_data):
        return ParentChildPair.all().filter("parent_user_id =",
                                            parent_user_data.user_id)

    @staticmethod
    def get_for_child(child_user_data):
        return ParentChildPair.all().ancestor(child_user_data).get()

    @staticmethod
    def is_pair(parent_user_data, child_user_data):
        if not parent_user_data or not child_user_data:
            return None
        return (ParentChildPair.all().
                ancestor(child_user_data).
                filter("parent_user_id =", parent_user_data.user_id).
                count() == 1)

    def resolve_parent(self):
        """Retrieves the UserData of the parent in this pair."""
        parent_user = UserData.get_from_user_id(self.parent_user_id)
        if not parent_user:
            logging.error("Couldn't resolve parent in ParentChildPair")
        return parent_user

    def resolve_child(self):
        """Retrieves the UserData of the child in this pair."""

        # Remember that the parent db.Model entity is the child!
        child_user = self.parent()
        if not child_user:
            logging.error("Couldn't resolve child in ParentChildPair")
        return child_user

    @staticmethod
    def make_bond(parent_user, child_user):
        def txn():
            if ParentChildPair.get_for_child(child_user) is not None:
                logging.error("User %s already has a parent" % child_user)
                return False

            if not child_user.is_child_account():
                logging.error("Can't set parent for non-child [%s]" %
                              child_user)
                return False

            bond = ParentChildPair(parent=child_user,
                                   parent_user_id=parent_user.user_id)

            # The parent automatically becomes the coach.
            child_user.add_coach(parent_user, force=True)
            return bond.put()

        key = transaction_util.ensure_in_transaction(txn)
        if key:
            # Flush the transaction.
            db.get(key)
        return bool(key)


class UserNotificationGroup(db.Model):
    """A single entity per-user representing all queued user notifications."""

    user_id = db.StringProperty(indexed=False)

    # .notifications is a dictionary of notification type keys mapped to lists
    # of notification objects. See notifications.py for examples of the
    # objects.
    #
    # Example:
    # {
    #  "badges": [<instance of notifications.BadgeNotification>, <another...>],
    #  "phantoms": [<instance of notifications.BadgeNotification>],
    #  "monkeys": []
    # }
    notifications = object_property.ObjectProperty()

    @property
    def has_notification(self):
        """Return true if this group contains at least one notification."""
        if not self.notifications:
            return False

        for key in self.notifications:
            if self.notifications[key]:
                return True

        return False

    @staticmethod
    def key_for_user_data(user_data):
        """Return identifying key for an entity tied to specified user_data."""
        return "UserNotificationGroup:%s" % user_data.user_id

    @staticmethod
    def get_for_user_data(user_data):
        """Return the UserNotificationGroup associated with user_data.
        
        This will return an empty UserNotificationGroup if none exists yet."""
        key_name = UserNotificationGroup.key_for_user_data(user_data)

        group = UserNotificationGroup.get_by_key_name(key_name)

        # If no UserNotificationGroup exists yet, return an empty one.
        if not group:
            group = UserNotificationGroup(
                    key_name=key_name, user_id=user_data.user_id)

        return group


# TODO(benkomalo): possibly merge this with privileges.py
class Capabilities(object):
    """Utilities for interpreting raw capability lists.

    This allows us to introduce new restrictions/capabilities for child
    accounts that can be toggled by the managing parent account without
    having to introduce new properties on UserData. The whole set can
    be represented in a more compact TsvProperty and this class interprets
    the contents.
    """

    # The ability for a user to add or remove coaches. Entry in the list
    # implies the capability is granted.
    MODIFY_COACHES = "modifycoaches"

    @staticmethod
    def _list_includes(raw_list, capability):
        if not raw_list:
            return False
        return capability in raw_list

    @staticmethod
    def _set_capability_in_list(raw_list_existing, capability, allow=True):
        if allow:
            return list(set(raw_list_existing + [capability]))
        else:
            result = set(raw_list_existing)
            if capability in result:
                result.remove(capability)
            return list(result)

    @staticmethod
    def can_modify_coaches(raw_list):
        return Capabilities._list_includes(raw_list,
                                           Capabilities.MODIFY_COACHES)

    @staticmethod
    def set_can_modify_coaches(raw_list_existing, allow=True):
        return Capabilities._set_capability_in_list(
            raw_list_existing, Capabilities.MODIFY_COACHES, allow)


class CapabilityError(Exception):
    """An error when someone attempts to mutate a model without proper
    capabilities."""
    pass
