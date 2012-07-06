"""Mark when a user has viewed a one-time event of some sort.

The motivation for this class is for marking when users have seen promos.
"""

import urllib

from google.appengine.ext import db


class PromoRecord(db.Model):
    """A record to mark when a user has viewed a one-time event."""
    def __str__(self):
        return self.key().name()

    @staticmethod
    def has_user_seen_promo(promo_name, user_id):
        return PromoRecord.get_for_values(promo_name, user_id) is not None

    @staticmethod
    def get_for_values(promo_name, user_id):
        key_name = PromoRecord._build_key_name(promo_name, user_id)
        return PromoRecord.get_by_key_name(key_name)

    @staticmethod
    def _build_key_name(promo_name, user_id):
        escaped_promo_name = urllib.quote(promo_name)
        escaped_user_id = urllib.quote(user_id)
        return "%s:%s" % (escaped_promo_name, escaped_user_id)

    @staticmethod
    def record_promo(promo_name, user_id, skip_check=False):
        """ Attempt to mark that a user has seen a one-time promotion.
        Returns True if the registration was successful, and returns False
        if the user has already seen that promotion.

        If skip_check is True, it will forcefully create a promo record
        and avoid any checks for existing ones. Use with care.
        """
        key_name = PromoRecord._build_key_name(promo_name, user_id)
        if not skip_check:
            record = PromoRecord.get_by_key_name(key_name)
            if record is not None:
                # Already shown the promo.
                return False
        record = PromoRecord(key_name=key_name)
        record.put()
        return True
