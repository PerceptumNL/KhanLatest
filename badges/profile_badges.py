import badges
from promo_record_model import PromoRecord


# All badges awarded for various activity related to profile management
@badges.active_badge
class ProfileCustomizationBadge(badges.Badge):
    def __init__(self):
        badges.Badge.__init__(self)
        self.description = "Geef jezelf weer"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0
        
    def is_already_owned_by(self, user_data, *args, **kwargs):
        return False
        
    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        user_id = user_data.user_id
        promo_avatar = ProfileCustomizationBadge._PROMO_NAME_AVATAR
        promo_display_case = ProfileCustomizationBadge._PROMO_NAME_DISPLAY_CASE
        return (PromoRecord.has_user_seen_promo(promo_avatar, user_id) and
                PromoRecord.has_user_seen_promo(promo_display_case, user_id))

    def extended_description(self):
        return "Pas je profiel aan en kies je profiel avatar"
    
    def is_manually_awarded(self):
        return True
    
    _PROMO_NAME_AVATAR = "profile milestone changed avatar"
    _PROMO_NAME_DISPLAY_CASE = "profile milestone filled display case"
    
    @staticmethod
    def mark_avatar_changed(user_data):
        """ Marks a user as changing her avatar.
        Returns whether or not they should achieve a ProfileCustomizationBadge
        after this action.
        """
        changed = PromoRecord.record_promo(
                ProfileCustomizationBadge._PROMO_NAME_AVATAR,
                user_data.user_id)

        return changed and PromoRecord.has_user_seen_promo(
                ProfileCustomizationBadge._PROMO_NAME_DISPLAY_CASE,
                user_data.user_id)
    
    @staticmethod
    def mark_display_case_filled(user_data):
        """ Marks a user as filled her displaycase.
        Returns whether or not they should achieve a ProfileCustomizationBadge
        after this action.
        """
        changed = PromoRecord.record_promo(
                ProfileCustomizationBadge._PROMO_NAME_DISPLAY_CASE,
                user_data.user_id)

        return changed and PromoRecord.has_user_seen_promo(
                ProfileCustomizationBadge._PROMO_NAME_AVATAR,
                user_data.user_id)
