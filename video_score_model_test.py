from google.appengine.ext import db

from testutil import gae_model
import video_models
import video_score_model


class VideoScoreTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(VideoScoreTest, self).setUp(db_consistency_probability=1)

    def tearDown(self):
        super(VideoScoreTest, self).tearDown()

    def make_video_score(self, score_dict, parent=None):
        if parent is None:
            new_score = video_score_model.VideoScores(score_map=score_dict)
        else:
            new_score = video_score_model.VideoScores(score_map=score_dict,
                                                      parent=parent)
        return new_score.put()

    def test_put(self):
        key = self.make_video_score({str(i): i for i in xrange(200)})
        self.assertEqual(1, video_score_model.VideoScores.all().count())
        self.assertEqual(200, len(db.get(key).score_map))

    def test_index_consistency(self):
        indices = video_score_model.VideoScoresIndex()
        vid_keys = []
        for i in xrange(300):
            new_video = video_models.Video()
            vid_keys.append(new_video)
        vid_keys = db.put(vid_keys)

        scores = {}
        for key in vid_keys:
            scores[str(key)] = {str(k): i for (k, i) in
                            zip(vid_keys, xrange(len(vid_keys))) if k != key}

        indices.put_matrix(scores)

        self.assertTrue(all(indices.get_key_from_index(
                indices.get_index_from_key(str(x))) == str(x)
            for x in vid_keys))

        # Save the dictionaries so we can test later consistency.
        saved_index_to_key = indices.index_to_key
        saved_key_to_index = indices.key_to_index

        (index_to_key, key_to_index, matrix) = indices.get_matrix()
        self.assertEqual(saved_index_to_key, index_to_key)
        self.assertEqual(saved_key_to_index, key_to_index)

        saved_keys = [index_to_key[x] for x in matrix]
        self.assertEqual(set(scores.keys()), set(saved_keys))
        
        # TODO(josh): check values of dictionaries
        # (I'm not doing this yet because the translation to indices
        # is a bit annoying)

    def test_deletion(self):
        vid_one = video_models.Video()
        vid_two = video_models.Video()
        db.put([vid_one, vid_two])

        self.make_video_score({str(vid_two.key()): 0.5},
                parent=vid_one)
        self.make_video_score({str(vid_one.key()): 0.4},
                parent=vid_two)

        self.assertEqual(2, video_score_model.VideoScores.all().count())

        indices = video_score_model.VideoScoresIndex()
        indices.put_matrix({str(vid_one.key()): {}})

        self.assertEqual(1, video_score_model.VideoScores.all().count())

