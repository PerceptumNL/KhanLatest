from google.appengine.ext import db

import object_property


class VideoScores(db.Model):
    """Each VideoScores entity is a child of a Video.

    score_map is a jsonified dict from str(video_key) -> score,
    where score is the co-occurrence score for the video indicated by video_key
    and the video this entity is the child of.
    """

    score_map = object_property.JsonProperty()

    @property
    def video(self):
        """Return the parent video associated with this VideoScores entity"""
        return self.parent()

    @property
    def video_key(self):
        """Return the key of this VideoScores' parent video."""
        return self.parent_key()

    def get_index_dict(self, key_to_index):
        """Return an index->score version of score_map.

        key_to_index: dict from str(video_key)->index showing how to translate
        """
        index_dict = {}
        for key in self.score_map:
            index_dict[key_to_index[key]] = self.score_map[key]

        return index_dict


class VideoScoresIndex():
    """Transforms VideoScores entities to a single matrix that uses indices.

    This class allows us to more feasibly keep the whole matrix in memory so
    we can compute recommendations for each user.
    """

    def __init__(self,
                 index_to_key={},
                 key_to_index={},
                 translation_cache_dirty=True,
                 matrix_cache={},
                 matrix_cache_dirty=True):
        """Initialize the caches with default values and statuses"""
        # Caches for translating indices <-> (string) video keys
        self.index_to_key = index_to_key
        self.key_to_index = key_to_index
        self.translation_cache_dirty = translation_cache_dirty

        # Cache to keep whole matrix of {index -> {index -> score}}
        self.matrix_cache = matrix_cache
        self.matrix_cache_dirty = matrix_cache_dirty

    def generate_dicts(self):
        """Populates the key_to_index and index_to_key dicts.

        Only does work if the translation caches are dirty or empty.
        Thus, it's critical that any transaction that updates a VideoScores
        entity set translation_cache_dirty = True.
        """
        if (self.translation_cache_dirty or
                not(self.index_to_key and self.key_to_index)):
            # Make sure the values are actually all cleared so we don't get any
            # inconsistent conversions after deleting VideoScores entities
            self.index_to_key = {}
            self.key_to_index = {}

            index = 0
            for video_score in VideoScores.all():
                # We just generate an arbitrary indexing scheme to take up
                # a reasonably small amount of space
                key = str(video_score.video_key)
                self.index_to_key[index] = key
                self.key_to_index[key] = index
                index += 1
            self.translation_cache_dirty = False

    def get_key_from_index(self, index):
        """Given an index, get the associated video key"""
        self.generate_dicts()
        return self.index_to_key[index]

    def get_index_from_key(self, key):
        """Given a video key, return the associated index"""
        self.generate_dicts()
        return self.key_to_index[key]

    def get_index_from_vid_score(self, vid_score):
        """Given a VideoScores entity, return the associated index"""
        return self.get_index_from_key(str(vid_score.video_key))

    def put_matrix(self, new_matrix):
        """Update/add/delete VideoScores entities as indicated by new_matrix

        new_matrix: dict {str(video_key) -> {str(video_key) -> score}}

        When this function finishes running, there will be |new_matrix|
        VideoScores entities in the database.
        For VideoScores entities e, e.score_map == new_matrix[e.video_key]
        """

        # Just delete all of the videos -- this isn't all that common of an
        # operation so the performance hit is fine
        db.delete(VideoScores.all())

        to_put = []
        for key in new_matrix:
            vid_score = VideoScores(parent=db.Key(encoded=key))
            vid_score.score_map = new_matrix[key]
            to_put.append(vid_score)

        db.put(to_put)  # Put as a batch for better efficiency
        self.translation_cache_dirty = True
        self.matrix_cache_dirty = True

    def get_matrix(self):
        """Generate a {video_index -> {video_index -> score}} matrix,
        and return a tuple of (index_to_key, key_to_index, matrix)
        """
        self.generate_dicts()

        if not self.matrix_cache_dirty:
            return (self.index_to_key, self.key_to_index, self.matrix_cache)

        index_matrix = {}
        for vid_score in VideoScores.all():
            index_matrix[self.get_index_from_vid_score(vid_score)] = (
                    vid_score.get_index_dict(self.key_to_index))

        self.matrix_cache = index_matrix
        self.matrix_cache_dirty = False
        return (self.index_to_key, self.key_to_index, index_matrix)
