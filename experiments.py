#!/usr/bin/env python

import gae_bingo.gae_bingo
from gae_bingo.models import ConversionTypes


class StrugglingExperiment(object):

    DEFAULT = 'old'

    # "Struggling" model experiment parameters.
    _ab_test_alternatives = {
        'old': 8,  # The original '>= 20 problems attempted' heuristic
        'accuracy_1.8': 1,  # Using an accuracy model with 1.8 as the parameter
        'accuracy_2.0': 1,  # Using an accuracy model with 2.0 as the parameter
    }
    _conversion_tests = [
        ('struggling_problems_done', ConversionTypes.Counting),
        ('struggling_problems_wrong', ConversionTypes.Counting),
        ('struggling_problems_correct', ConversionTypes.Counting),
        ('struggling_gained_proficiency_all', ConversionTypes.Counting),
        ('struggling_gained_proficiency_post_struggling',
         ConversionTypes.Counting),

        # the user closed the "Need help?" dialog that pops up
        ('struggling_message_dismissed', ConversionTypes.Counting),

        # the user clicked on the video in the "Need help?" dialog that pops up
        ('struggling_videos_clicked_post_struggling',
         ConversionTypes.Counting),

        # the user clicked on the pre-requisite exercise in the
        # "Need help?" dialog that pops up
        ('struggling_prereq_clicked_post_struggling',
         ConversionTypes.Counting),

        ('struggling_videos_landing', ConversionTypes.Counting),
        ('struggling_videos_finished', ConversionTypes.Counting),
        # the number of users that went into struggling at some point
        ('struggling_struggled_binary', ConversionTypes.Binary),
    ]
    _conversion_names, _conversion_types = [
        list(x) for x in zip(*_conversion_tests)]

    @staticmethod
    def get_alternative_for_user(user_data, current_user=False):
        """ Returns the experiment alternative for the specified user, or
        the current logged in user. If the user is the logged in user, will
        opt in for an experiment, as well. Will not affect experiments if
        not the current user.
        
        """
        
        # We're interested in analyzing the effects of different struggling
        # models on users. A more accurate model would imply that the user
        # can get help earlier on. This varies drastically for those with
        # and without coaches, so it is useful to separate the population out.
        if user_data.coaches:
            exp_name = 'Struggling model 2 (w/coach)'
        else:
            exp_name = 'Struggling model 2 (no coach)'

        # If it's not the current user, then it must be an admin or coach
        # viewing a dashboard. Don't affect the actual experiment as only the
        # actions of the user affect her participation in the experiment.
        if current_user:
            return gae_bingo.gae_bingo.ab_test(
                exp_name,
                StrugglingExperiment._ab_test_alternatives,
                StrugglingExperiment._conversion_names,
                StrugglingExperiment._conversion_types)

        return gae_bingo.gae_bingo.find_alternative_for_user(
            exp_name, user_data)


class CoreMetrics(object):
    """Useful metrics that we'll want to use in multiple A/B tests.

    You probably want to use these metrics in all of your tests.
    If there's something highly specific, add it to your own test.
    If you think your metric could be reusable, add it to here.

    It's worth noting that GAE/bingo will keep track of multiple experiments
    with the same conversion metrics, which is convenient.

    """

    core_metrics = {
        "accounts":  # More general account metrics
        [
            ('login_binary', ConversionTypes.Binary),
            ('login_count', ConversionTypes.Counting),

            # Binary only since users probably won't register more than once
            # (unless maybe something is broken)
            ('registration_binary', ConversionTypes.Binary),
        ],

        "exercises":  # Exercise-related metrics
        [
            ('new_proficiency_binary', ConversionTypes.Binary),
            ('new_proficiency_count', ConversionTypes.Counting),

            ('problem_attempt_binary', ConversionTypes.Binary),
            ('problem_attempt_count', ConversionTypes.Counting),

            ('problem_correct_binary', ConversionTypes.Binary),
            ('problem_correct_count', ConversionTypes.Counting),

            ('problem_incorrect_binary', ConversionTypes.Binary),
            ('problem_incorrect_count', ConversionTypes.Counting),
        ],

        "profile":  # Changes to the profile page
        [
            ('avatar_update_binary', ConversionTypes.Binary),
            ('avatar_update_count', ConversionTypes.Counting),

            ('edited_display_case_binary', ConversionTypes.Binary),
            ('edited_display_case_count', ConversionTypes.Counting),

            # Nickname updates won't be that common
            ('nickname_update_binary', ConversionTypes.Binary),

            ('profile_update_binary', ConversionTypes.Binary),
            ('profile_update_count', ConversionTypes.Counting),

            # Updates to public/private status likewise won't
            # be that common, probably
            ('public_update_binary', ConversionTypes.Binary),

        ],

        "retention":
        [
            # Measure return visits by registered (and logged-in) users
            ('logged_in_return_visit_binary', ConversionTypes.Binary),
            ('logged_in_return_visit_count', ConversionTypes.Counting),

            # Measure return visits by non-logged-in users
            ('phantom_return_visit_binary', ConversionTypes.Binary),
            ('phantom_return_visit_count', ConversionTypes.Counting),

            # Measure return visits by users who haven't done anything
            ('pre_phantom_return_visit_binary', ConversionTypes.Binary),
            ('pre_phantom_return_visit_count', ConversionTypes.Counting),

            # Measure all return visits
            ('return_visit_binary', ConversionTypes.Binary),
            ('return_visit_count', ConversionTypes.Counting),
        ],

        "videos":  # Video-related metrics
        [
            ('video_completed_binary', ConversionTypes.Binary),
            ('video_completed_count', ConversionTypes.Counting),

            ('video_started_binary', ConversionTypes.Binary),
            ('video_started_count', ConversionTypes.Counting),
        ],

    }

    # Lets us very easily run ab tests with default values,
    # and specify any additional metrics we want to test.
    @staticmethod
    def ab_test(
            canonical_name,
            alternative_params=None,
            conversion_name=[],
            conversion_type=ConversionTypes.Binary,
            family_name=None,
            core_categories=[]):
        '''Wrapper for GAE/bingo's A/B test that allows seamless inclusion
        of commonly used metrics.

        Arguments: canonical_name: the canonical name of the experiment,
                                   as in gae_bingo.ab_test
                   alternative_params: specify alternate options,
                                        as in gae_bingo
                   conversion_name: Add conversion(s) specific to your
                                    experiment that aren't in core_metrics
                   conversion_type: types for your addidtional metrics
                                    (can be a list)
                   family_name: just gets passed to gae_bingo.ab_test()
                   core_categories: Specify categories of metrics you want.
                                    (e.g., ["videos", "exercises"])
                                    "all" (or ["all"]) for all of them,
                                    [] for none

        '''
        core_conversions = []
        core_types = []

        if "all" in core_categories:
            # take all of the lists of metrics and concatenate them
            values = CoreMetrics.core_metrics.values()
            values = sum(values, [])  # flatten
            core_conversions, core_types = [list(x) for x in zip(*values)]
        else:
            for metric_category in core_categories:
                for conversion in CoreMetrics.core_metrics[metric_category]:
                    core_conversions.append(conversion[0])
                    core_types.append(conversion[1])

        conversion_names = (conversion_name
                                if type(conversion_name) == list
                                else [conversion_name])

        conversion_types = (conversion_type
                                if type(conversion_type) == list
                                else [conversion_type] * len(conversion_names))

        return gae_bingo.gae_bingo.ab_test(canonical_name,
                       alternative_params=alternative_params,
                       conversion_name=core_conversions + conversion_names,
                       conversion_type=core_types + conversion_types,
                       family_name=family_name)
