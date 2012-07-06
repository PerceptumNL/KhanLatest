"""A database entity that ties exercises and videos together.

Every exercise has a video that can help people with the exercise, and
some videos have exercises that practice the content of the video.
"""

from google.appengine.ext import db

import backup_model
import exercise_models
import video_models


class ExerciseVideo(backup_model.BackupModel):
    """Connect a video and an exercise that cover the same material."""

    # Should be db.ReferenceProperty(video_models.Video); here we leave
    # off the constraint to alleviate some circular import woes.
    video = db.ReferenceProperty(collection_name='video_exercisevideos_set')

    # Should be db.ReferenceProperty(exercise_models.Exercise); here we leave
    # off the constraint to alleviate some circular import woes.
    exercise = db.ReferenceProperty(collection_name='exercise_exercisevideos_set')

    # the order videos should appear for this exercise
    exercise_order = db.IntegerProperty()

    def key_for_video(self):
        return ExerciseVideo.video.get_value_for_datastore(self)

    @staticmethod
    def get_key_dict(query):
        exercise_video_key_dict = {}
        for exercise_video in query.fetch(10000):
            video_key = ExerciseVideo.video.get_value_for_datastore(
                    exercise_video)

            if video_key not in exercise_video_key_dict:
                exercise_video_key_dict[video_key] = {}

            exercise_video_key_dict[video_key][ExerciseVideo.exercise.get_value_for_datastore(exercise_video)] = exercise_video

        return exercise_video_key_dict

    # returns all ExerciseVideo objects whose Video has no topic
    @staticmethod
    def get_all_with_topicless_videos(version=None):
        videos = video_models.Video.get_all_live(version)
        video_keys = [v.key() for v in videos]
        evs = ExerciseVideo.all().fetch(100000)

        if version is None or version.default:
            return [ev for ev in evs
                    if ExerciseVideo.video.get_value_for_datastore(ev)
                    not in video_keys]

        # if there is a version check to see if there are any updates
        # to the exercise videos
        else:
            video_dict = dict((v.key(), v.readable_id) for v in videos)
            video_readable_dict = dict((v.readable_id, v) for v in videos)
            ev_key_dict = dict((ev.key(), ev) for ev in evs)

            # create ev_dict so we can access the ev in constant time
            # from the exercise_key and the video_readable_id
            ev_dict = {}

            for ev in evs:
                exercise_key = ExerciseVideo.exercise.get_value_for_datastore(ev)
                video_key = ExerciseVideo.video.get_value_for_datastore(ev)

                # if the video is not live get it (it will be a
                # topicless video) there shouldnt be too many of
                # these, hence not bothering to do things efficiently
                # in one get
                if video_key not in video_dict:
                    video = db.get(video_key)
                    video_readable_id = video.readable_id
                    video_readable_dict[video.readable_id] = video
                else:
                    video_readable_id = video_dict[video_key]
                    video = video_readable_dict[video_readable_id]

                # the following line is needed otherwise the list comprehension
                # by the return statement will fail on the un put EVs with:
                # Key' object has no attribute '_video' if
                # ExerciseVideo.video.get_value_for_datastore(ev) is used
                ev.video = video

                if exercise_key not in ev_dict:
                    ev_dict[exercise_key] = {}

                ev_dict[exercise_key][video_readable_id] = ev.key()

            # cycle through all the version changes to see if an
            # exercise has been updated
            # TODO(csilvers): get rid of circular imports here
            import topic_models
            changes = topic_models.VersionContentChange.get_updated_content_dict(version)
            new_evs = []

            for key, content in changes.iteritems():

                if (type(content) == exercise_models.Exercise):

                    # remove the existing Exercise_Videos if there are any
                    if key in ev_dict:
                        for video_readable_id, ev_key in ev_dict[key].iteritems():
                            del ev_key_dict[ev_key]

                    # add new related_videos
                    for i, video_readable_id in enumerate(content.related_videos
                        if hasattr(content, "related_videos") else []):

                        if video_readable_id not in video_readable_dict:
                            video = video.get_for_readable_id(
                                video_readable_id)
                            video_readable_dict[video_readable_id] = (
                                video.readable_id)
                        else:
                            video = video_readable_dict[video_readable_id]

                        new_ev = ExerciseVideo(
                            video=video,
                            exercise=content,
                            exercise_order=i
                            )
                        new_evs.append(new_ev)

            evs = [ev for ev in ev_key_dict.values()]
            evs += new_evs

            # ExerciseVideo.video.get_value_for_datastore(ev) is not needed
            # because we populated ev.video
            return [ev for ev in evs if ev.video.key() not in video_keys]

    @staticmethod
    def update_related_videos(exercise, related_video_readable_ids):
        ''' This function updates the exercise's related videos according to
        the order that they appear in the related_video_readable_ids list
        '''
        # Get the video keys
        video_keys = []
        for video_name in related_video_readable_ids:
            video = video_models.Video.get_for_readable_id(video_name)
            if video and not video.key() in video_keys:
                video_keys.append(str(video.key()))

        # Get the existing exercise videos
        query = ExerciseVideo.all()
        query.filter('exercise =', exercise.key())
        existing_exercise_videos = query.fetch(1000)

        existing_video_keys = []
        for exercise_video in existing_exercise_videos:
            existing_video_keys.append(exercise_video.video.key())
            
            if not exercise_video.video.key() in video_keys:
                # delete the exercise videos that are no longer there
                exercise_video.delete()

            elif exercise_video.exercise_order != video_keys.index(
                    exercise_video.video.key()):
                # update new position of videos that are still there and whose
                # position changed
                exercise_video.exercise_order = video_keys.index(
                    exercise_video.video.key())
                exercise_video.put()

        for i, video_key in enumerate(video_keys):
            if not video_key in existing_video_keys:
                # add the videos that don't exist
                exercise_video = ExerciseVideo()
                exercise_video.exercise = exercise
                exercise_video.video = db.Key(video_key)
                exercise_video.exercise_order = i
                exercise_video.put()
