import badges
import shared_jinja
import util_badges


def badge_counts(user_data):

    counts_dict = {}
    # TODO: awkward turtle, decide what happens with phantom users
    link_to_profile = "/profile"
    if user_data:
        counts_dict = util_badges.get_badge_counts(user_data)
        link_to_profile = user_data.profile_root + "achievements"
    else:
        counts_dict = badges.BadgeCategory.empty_count_dict()

    sum_counts = 0
    for key in counts_dict:
        sum_counts += counts_dict[key]

    template_context = {
            "link_to_profile": link_to_profile,
            "sum": sum_counts,
            "bronze": counts_dict[badges.BadgeCategory.BRONZE],
            "silver": counts_dict[badges.BadgeCategory.SILVER],
            "gold": counts_dict[badges.BadgeCategory.GOLD],
            "platinum": counts_dict[badges.BadgeCategory.PLATINUM],
            "diamond": counts_dict[badges.BadgeCategory.DIAMOND],
            "master": counts_dict[badges.BadgeCategory.MASTER],
    }

    return shared_jinja.get().render_template("badges/badge_counts.html",
                                              **template_context)


def badge_block(badge, user_badge=None, show_frequency=False,
                user_data_student=None):

    if user_badge:
        badge.is_owned = True

    if badge.is_hidden():
        return ""  # Don't render anything for this hidden badge

    frequency = None
    if show_frequency:
        frequency = badge.frequency()

    can_become_goal = (user_data_student and
                       not user_data_student.is_phantom and
                       not badge.is_owned and
                       badge.is_goal)

    template_values = {"badge": badge,
                       "user_badge": user_badge,
                       "extended_description": badge.safe_extended_description,
                       "frequency": frequency,
                       "can_become_goal": can_become_goal}

    return shared_jinja.get().render_template("badges/badge_block.html",
                                              **template_values)


def visible_context_names(badge):
    return badge.target_context_names[0:1]


def hidden_context_names(badge):
    return badge.target_context_names[1:]
