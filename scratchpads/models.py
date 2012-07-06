#!/usr/bin/env python

from object_property import UnvalidatedObjectProperty
from google.appengine.ext import db
import templatefilters
import transaction_util


class ScratchpadRevision(db.Model):
    """Contains a specific revision of the code, audio and recording for a
    Scratchpad.

    Should not be created directly - use Scratchpad.create_revision instead.

    Should never be updated - updates to the code for a Scratchpad should be
    done by creating a new ScratchpadRevision.
    """

    # The full text for the user's code
    code = db.TextProperty(indexed=False, required=True,
        default='')

    # The datetime when the revision was created
    created = db.DateTimeProperty(auto_now_add=True)

    # The ID of the audio track
    audio_id = db.IntegerProperty()

    # Recording data (simulated mouse/keyboard events)
    recording = UnvalidatedObjectProperty(indexed=False)

    # URL for screenshot of the canvas
    # Will either be a data:image/png URL or a URL to something on EC2
    image_url = db.TextProperty(indexed=False, required=True,
        default='http://placekitten.com/g/200/200')

    _serialize_blacklist = [
        'image_url',
    ]

    @property
    def id(self):
        return self.key().id()

    @property
    def scratchpad_id(self):
        return self.parent_key().id()


def dict_keys_to_strings(d):
    """Convert the keys of the provided dict to be strings.

    This is especially useful for converting request.json's keys to be regular
    strings instead of unicode strings so that they can be unpacked as **kwargs
    to functions.
    """
    return dict((str(k), v) for (k, v) in d.iteritems())


class Scratchpad(db.Model):
    """Scratchpad for code - has one or more associated ScratchpadRevisions """

    # The creator of the scratchpad
    # This holds UserData.current().user_id
    # It could be None if the scratchpad was created by an anonymous user
    user_id = db.StringProperty()

    # The title of the scratchpad
    title = db.StringProperty(required=True, default='')

    # Reference to revision this scratchpad is based on
    # Will be None if this Scratchpad was made from a blank slate
    origin_revision = db.ReferenceProperty(ScratchpadRevision)

    # Reference to the scratchpad whose revision this scratchpad is based on
    # This seems redundant, but it's necessary to make the query to find
    # the origin_revision by id, due to how get_by_id works
    origin_scratchpad = db.SelfReferenceProperty()

    category = db.CategoryProperty(choices=['tutorial', 'official'])

    # Roughly indicates how difficult the concepts used in the Scratchpad are.
    # Only set for developer created Scratchpads. A difficulty of -1 indicates
    # that no difficulty was specified, and all non-developer created
    # Scratchpads will have a difficulty of -1
    #
    # TODO(jlfwong): Figure out if I can add indexed=False here safely
    difficulty = db.IntegerProperty(default=-1)

    # Youtube string id (e.g. LWNLE4sklfI) of a video associated with the
    # Scratchpad. This field is optional and and is developer only.
    youtube_id = db.StringProperty()

    # When Scratchpads are deleted, they are simply marked as deleted, not
    # actually removed from the datastore. This allows for easy retrieval in
    # case of accidental deletion
    deleted = db.BooleanProperty(default=False)

    _serialize_blacklist = [
        'deleted',
        'origin_revision',
        'origin_scratchpad',
    ]

    # These fields are only modifiable by developers.
    _developer_only_fields = [
        'category',
        'difficulty',
        'youtube_id',
    ]

    @classmethod
    def filtered_all(cls):
        # We want to include a default filter on all attempts to get a list of
        # Scratchpads to filter out all Scratchpads marked as deleted.
        return (cls
            .all()
            .filter('deleted', False))

    @property
    def id(self):
        return self.key().id()

    @property
    def origin_revision_id(self):
        if self.origin_revision:
            return self.origin_revision.key().id()
        else:
            return None

    @property
    def origin_scratchpad_id(self):
        if self.origin_scratchpad:
            return self.origin_scratchpad.key().id()
        else:
            return None

    @property
    def slug(self):
        return templatefilters.slugify(self.title)

    @property
    def revision(self):
        # TODO(jlfwong): Add an argument to retrieve an arbitrary revision.
        return ScratchpadRevision.all().ancestor(self).order('-created').get()

    @staticmethod
    def create(title=None,
               category=None,
               difficulty=None,
               youtube_id=None,
               user_id=None,
               origin_scratchpad_id=None,
               origin_revision_id=None,
               revision=None,
               **kwargs):
        """Create a new Scratchpad and ScratchpadRevision and save them to DB

        If either the Scratchpad or the ScratchpadRevision is invalid, the
        database will be unchanged.

        Arguments:
            origin_scratchpad_id:
                The id of the Scratchpad this Scratchpad is based off of.
                Used to set the origin_revision property of the Scratchpad
                being created.

            origin_revision_id:
                The revision of the origin Scratchpad that this Scratchpad is
                based on. Used to set the origin_scratchpad property of the
                Scratchpad being created.

            revision:
                Dict of ScratchpadRevision properties passed verbatim to
                Scratchpad.create_revision to create the initial revision of
                the Scratchpad.

            *:
                All other explicit (i.e. not **kwargs) arguments are passed
                verbatim to the Scratchpad constructor.

            kwargs:
                Should be empty. If set, a db.BadKeyError will be thrown since
                someone passed in a field we weren't expecting.

        Note: While all keys have defaults of None, some, like revision, are
              actually required. This is done to to make any incomplete data
              throw a db.BadValueError instead of a TypeError.
        """
        if kwargs:
            raise db.BadKeyError("Unexpected property " + kwargs.keys()[0])

        scratchpad = Scratchpad(title=title,
                                category=category,
                                difficulty=difficulty,
                                youtube_id=youtube_id,
                                user_id=user_id)

        if origin_revision_id and origin_scratchpad_id:
            origin_scratchpad = Scratchpad.get_by_id(origin_scratchpad_id)

            if origin_scratchpad is None:
                raise db.BadValueError("No scratchpad with id %d" % (
                    origin_scratchpad_id))

            origin_revision = origin_scratchpad.get_revision_by_id(
                origin_revision_id)

            if origin_revision is None:
                raise db.BadValueError(
                    "No revision with id %d for scratchpad %d" % (
                        origin_scratchpad_id, origin_revision_id))

            scratchpad.origin_scratchpad = origin_scratchpad
            scratchpad.origin_revision = origin_revision
        elif origin_revision_id or origin_scratchpad_id:
            raise db.BadValueError(
                "Specified one of origin_scratchpad_id/origin_revision_id"
                " but not the other")

        if revision is None:
            raise db.BadValueError("Property revision is required")

        def save_scratchpad_and_revision():
            scratchpad.put()
            # Convert the dict keys to strings in case they're unicode encoded
            # (This happens if revision came from JSON)
            scratchpad.create_revision(**dict_keys_to_strings(revision))

        transaction_util.ensure_in_transaction(save_scratchpad_and_revision)

        return scratchpad

    def update(self,
               title=None,
               category=None,
               difficulty=None,
               youtube_id=None,
               revision=None,
               **kwargs):
        """Update the Scratchpad and create a new ScratchpadRevision.

        If the either the Scratchpad or the ScratchpadRevision is invalid, the
        database will be unchanged.

        Arguments:
            revision:
                Dict of ScratchpadRevision properties passed verbatim to
                Scratchpad.create_revision.

            *:
                All other explicit (i.e. not **kwargs) arguments are assigned
                verbatim as properties to the Scratchpad, even if they hold
                a value of None. This is true if either None is explicitly
                passed in, or the default value of None is used.

            kwargs:
                Should be empty. If set, a db.BadKeyError will be thrown since
                someone passed in a field we weren't expecting.

        Note: While all keys have defaults of None, some, like revision, are
              actually required. This is done to to make any incomplete data
              throw a db.BadValueError instead of a TypeError.
        """

        if kwargs:
            raise db.BadKeyError("Unexpected property " + kwargs.keys()[0])

        if revision is None:
            raise db.BadValueError("Property revision is required")

        self.title = title
        self.category = category
        self.difficulty = difficulty
        self.youtube_id = youtube_id

        def save_scratchpad_and_revision():
            self.put()
            # Convert the dict keys to strings in case they're unicode encoded
            # (This happens if revision came from JSON)
            self.create_revision(**dict_keys_to_strings(revision))

        transaction_util.ensure_in_transaction(save_scratchpad_and_revision)

        return self

    def create_revision(self,
                        code=None,
                        audio_id=None,
                        recording=None,
                        image_url=None,
                        **kwargs):
        """Create a ScratchpadRevision with this Scratchpad as the parent.

        Arguments:
            *:
                All explicit (i.e. not **kwargs) arguments are passed verbatim
                to the constructor of ScratchpadRevision.

            kwargs:
                Should be empty. If set, a db.BadKeyError will be thrown since
                someone passed in a field we weren't expecting.
        """
        if kwargs:
            raise db.BadKeyError("Unexpected property " + kwargs.keys()[0])

        revision = ScratchpadRevision(
            parent=self,
            code=code,
            audio_id=audio_id,
            image_url=image_url,
            recording=recording
        )
        revision.put()

        return revision

    def get_revision_by_id(self, revision_id):
        return ScratchpadRevision.get_by_id(revision_id, parent=self)

    @classmethod
    def get_for_user_data(cls, user_data):
        """Get a db.Query instance for all of the scratchpads created by the
        user specified by user_data.
        """
        return (cls
            .filtered_all()
            .filter('user_id = ', user_data.user_id))

    @classmethod
    def get_all_official(cls):
        """Get a db.Query instance for all the scratchpads marked as official.
        """
        return (cls
            .filtered_all()
            .filter('category', 'official'))

    @classmethod
    def get_all_tutorials(cls):
        """Get a db.Query instance for all the scratchpads marked as tutorials.
        """
        return (cls
            .filtered_all()
            .filter('category', 'tutorial'))
