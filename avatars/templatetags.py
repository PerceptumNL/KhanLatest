import util_avatars


def get_src_for_user(user_data):
    avatar = util_avatars.avatar_for_name(user_data.avatar_name)
    return avatar.image_src
