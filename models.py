"""Obsolete wrapper for various data models.

Each of the models in this file have moved somewhere else.  This file
is provided for backwards compatibility with code that has
'import models' and expects to get all the models at once.

This is also important for backwards compatibility with
de-pickling items that contain object instances from the old models
definition. That de-pickling process would expect the class
definitions to be in this 'models' module.

Use the following grep command to find imports you need to use in
the new file:
(@Nolint) $ cat <filename> | fgrep -o -w -e datetime -e logging -e json -e json -e math -e urllib -e pickle -e random -e itertools -e users -e memcache -e Rollback -e deferred -e taskqueue -e TransactionFailedError -e jsonify -e db -e object_property -e util -e user_util -e consts -e points -e Searchable -e App -e layer_cache -e request_cache -e discussion_models -e all_topics_list -e nicknames -e user_counter -e is_facebook_user_id -e FACEBOOK_ID_PREFIX -e AccuracyModel -e InvFnExponentialNormalizer -e clamp -e synchronized_with_memcache -e base64 -e os -e ImageCache -e age_util -e CredentialedUser -e slugify -e bingo -e GAEBingoIdentityModel -e StrugglingExperiment -e re -e library_content_html -e autocomplete -e templatetags -e MapLayout -e thumbnail_link_dict -e thumbnail_link_dict -e search -e exercise_save_data -e zlib -e traceback -e StringIO -e shared_jinja -e ClassDailyActivitySummary -e util_badges -e last_action_cache -e topic_exercise_badges -e util_notify -e GoalList -e exercise_sha1 | sort -u


To find out classes that are defined in this file that may be moving
outside (and thus will also need to be imported) use:
(@Nolint) $ cat <filename> | fgrep -o -w -e BackupModel -e Setting -e Exercise -e UserExercise -e CoachRequest -e StudentList -e UserVideoCss -e UniqueUsername -e NicknameIndex -e UnverifiedUser -e UserData -e TopicVersion -e VersionContentChange -e Topic -e Url -e Video -e UserTopic -e UserVideo -e VideoLog -e DailyActivityLog -e LogSummaryTypes -e LogSummaryShardConfig -e LogSummary -e ProblemLog -e ExerciseVideo -e UserExerciseCache -e UserExerciseGraph -e PromoRecord -e VideoSubtitles -e VideoSubtitlesFetchReport -e ParentSignup | sort -u

The remaining circular dependencies
   exercise_models: exercise_video_models

   video_models: exercise_video_models

   exercise_video_model: video_models, exercise_models
"""

# For backwards-compatibility with folks who do 'import models'.
from backup_model import *
from coach_resources.coach_request_model import *
from exercise_video_model import *
from exercise_models import *
from parent_signup_model import *
from promo_record_model import *
from setting_model import *
from summary_log_models import *
from topic_models import *
from url_model import *
from user_models import *
from video_models import *
