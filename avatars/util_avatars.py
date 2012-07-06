import layer_cache
from avatars import AvatarPointsCategory, PointsAvatar


@layer_cache.cache()
def all_avatars():
    """ Authoritative list of all avatars available to users. """

    return [
        PointsAvatar("greenleaf", "Green Leaf",
                     "/images/avatars/leaf-green.png", 0),
        PointsAvatar("blueleaf", "Blue Leaf",
                     "/images/avatars/leaf-blue.png", 0),
        PointsAvatar("greyleaf", "Grey Leaf",
                     "/images/avatars/leaf-grey.png", 0),
        PointsAvatar("redleaf", "Red Leaf",
                     "/images/avatars/leaf-red.png", 0),
        PointsAvatar("orangeleaf", "Orange Leaf",
                     "/images/avatars/leaf-orange.png", 0),
        PointsAvatar("yellowleaf", "Yellow Leaf",
                     "/images/avatars/leaf-yellow.png", 0),

        PointsAvatar("spunkysam", "Spunky Sam",
                     "/images/avatars/spunky-sam.png", 10000),
        PointsAvatar("marcimus", "Marcimus",
                     "/images/avatars/marcimus.png", 10000),
        PointsAvatar("mrpink", "Mr. Pink",
                     "/images/avatars/mr-pink.png", 10000),

        PointsAvatar("amelia", "Amelia",
                     "/images/avatars/robot_female_1.png", 50000),
        PointsAvatar("johnny", "Johnny",
                     "/images/avatars/robot_male_1.png", 50000),
        PointsAvatar("ojsquid", "Orange Juice Squid",
                     "/images/avatars/orange-juice-squid.png", 50000),
        PointsAvatar("purplepi", "Purple Pi",
                     "/images/avatars/purple-pi.png", 50000),

        PointsAvatar("ada", "Ada",
                     "/images/avatars/robot_female_2.png", 100000),
        PointsAvatar("donald", "Donald",
                     "/images/avatars/robot_male_2.png", 100000),
        PointsAvatar("mrpants", "Pants",
                     "/images/avatars/mr-pants.png", 100000),
        PointsAvatar("ospiceman", "Old Spice Man",
                     "/images/avatars/old-spice-man.png", 100000),

        PointsAvatar("grace", "Grace",
                     "/images/avatars/robot_female_3.png", 250000),
        PointsAvatar("hal", "Hal",
                     "/images/avatars/robot_male_3.png", 250000),
    ]


@layer_cache.cache()
def avatars_by_name():
    """ Full list of avatars in a dict, keyed by their unique names """
    return dict([(avatar.name, avatar) for avatar in all_avatars()])


def avatar_for_name(name=None):
    """ Returns the avatar for the specified name.

    If name is None or an invalid avatar, defaults to the "default" avatar.
    """
    avatars = avatars_by_name()
    if name in avatars:
        return avatars[name]

    return all_avatars()[0]


@layer_cache.cache()
def avatars_by_category():
    """ Full list of all avatars available to users segmented by AvatarCategory
    """
    categories = [
        AvatarPointsCategory("Starter", 0),
        AvatarPointsCategory("Common", 10000),
        AvatarPointsCategory("Uncommon", 50000),
        AvatarPointsCategory("Rare", 100000),
        AvatarPointsCategory("Epic", 250000),
    ]

    avatars = all_avatars()

    for i, category in enumerate(categories):

        # Pull out all avatars that fit in this category
        category_avatars = category.filter_avatars(avatars)

        categories[i] = {
            'title': category.title,
            'avatars': category_avatars,
        }

        # Remove this category's avatars from list of eligible avatars
        # so they won't be included in the next category.
        avatars = [a for a in avatars if a not in category_avatars]

    return categories
