from profiles import recent_activity
import points
import exercise_models
import video_models
import exercise_video_model
import badges.topic_exercise_badges


class SuggestedActivity(object):
    """ Suggested exercises and videos for a student.
    """

    @staticmethod
    def get_for(user_data, recent_activities=[]):
        """ Retrieves a list of suggested "activites" bucketed by type.

            user_data - the student to retrieve suggestions for
            recent_activities - a list of recent activities so that suggestions
                can be based on them.
        """
        user_exercise_graph = exercise_models.UserExerciseGraph.get(user_data)
        return {
            "exercises": SuggestedActivity.get_exercises_for(
                    user_data, user_exercise_graph),
            "videos": SuggestedActivity.get_videos_for(
                    user_data, recent_activities, user_exercise_graph),
        }

    @staticmethod
    def get_videos_for(user_data, recent_activities=None,
        user_exercise_graph=None):
        if recent_activities is None:
            recent_activities = recent_activity.recent_activity_list(user_data)

        if user_exercise_graph is None:
            user_exercise_graph = exercise_models.UserExerciseGraph.get(
                user_data)

        recent_completed_ids = set([v.youtube_id for v in filter(
                lambda entry:
                        (entry.__class__ == recent_activity.RecentVideoActivity
                         and entry.is_video_completed),
                recent_activities)])

        # Note that we can't just look for entries with
        # is_video_completed false since the user may have completed
        # it in a later entry after a break.
        recent_incomplete_videos = filter(
                lambda entry:
                        (entry.__class__ == recent_activity.RecentVideoActivity
                        and entry.youtube_id not in recent_completed_ids
                        and entry.seconds_watched > 60),
                recent_activities)

        max_activities = 2
        suggestions = [SuggestedActivity.from_video_activity(va)
                       for va in recent_incomplete_videos[:max_activities]]

        if len(suggestions) < max_activities:
            exercise_graph_dicts = user_exercise_graph.suggested_graph_dicts()

            completed = set([
                video_models.UserVideo.video.get_value_for_datastore(uv)
                for uv
                in video_models.UserVideo.get_completed_user_videos(user_data)
            ])
            # TODO(benkomalo): this results in way too many DB hits -
            # have to figure out a better way to do this.

            # Suggest based on upcoming exercises
            for exercise_dict in exercise_graph_dicts:
                exercise = exercise_models.Exercise.get_by_name(
                        exercise_dict['name'])
                for exercise_video in exercise.related_videos_query():
                    if (exercise_video_model.ExerciseVideo.video
                            .get_value_for_datastore(exercise_video)
                            in completed):
                        continue
                    video = SuggestedActivity.from_video(exercise_video.video)
                    if video is not None:
                        suggestions.append(video)
                    if len(suggestions) >= max_activities:
                        return suggestions

        return suggestions

    @staticmethod
    def get_exercises_for(user_data, user_exercise_graph):
        exercise_graph_dicts = user_exercise_graph.suggested_graph_dicts()

        # Favor the exercises you're closest to finishing
        # TODO: if we stick w/ this and want it everywhere,
        # move this sorting lower in the suggested_graph_dicts chain.
        exercise_graph_dicts = sorted(exercise_graph_dicts,
                                      key=lambda d: d["progress"],
                                      reverse=True)

        max_activities = 3
        return [SuggestedActivity.from_exercise(d)
                for d in exercise_graph_dicts[:max_activities]]

    @staticmethod
    def from_exercise(exercise_graph_dict):
        """ Build a SuggestedActivity dict
            from a UserExerciseGraph exercise graph dict.
        """
        activity = SuggestedActivity()
        activity.name = exercise_graph_dict["display_name"]
        exercise_name = exercise_graph_dict["name"]
        activity.url = exercise_models.Exercise.get_relative_url(
                exercise_name)
        activity.progress = exercise_graph_dict["progress"]
        first_topic = exercise_models.Exercise.get_by_name(
                        exercise_name).first_topic()
        activity.topic = first_topic.title
        activity.topic_icon = (badges.topic_exercise_badges.TopicExerciseBadge
                                .get_by_exercise(exercise_name)
                                .icon_src)
        return activity

    @staticmethod
    def from_video_activity(recent_video_activity):
        """Build a SuggestedActivity dict from a RecentVideoActivity object."""
        activity = SuggestedActivity()
        activity.name = recent_video_activity.video_title
        activity.last_second_watched = \
                recent_video_activity.last_second_watched
        activity.progress = points.video_progress_from_points(
                recent_video_activity.points_earned)

        # TODO(benkomalo): append a seektime so that the video starts at the
        # last position (minus some rewind constant or something...)
        activity.url = recent_video_activity.relative_url
        return activity

    @staticmethod
    def from_video(video):
        """Build a SuggestedActivity dict from a video_models.Video object."""
        # TODO(benkomalo): remove this check when there are sanity checks at
        # higher levels. Right now we have to guard against orphaned vids.
        if len(video.topic_string_keys or []) == 0:
            return None
        activity = SuggestedActivity()
        activity.name = video.title
        activity.url = video.relative_url
        activity.progress = 0
        activity.last_second_watched = 0
        return activity
