from testutil import gae_model
from promo_record_model import PromoRecord


class PromoRecordTest(gae_model.GAEModelTestCase):
    # Shorthand
    def r(self, promo_name, user_id):
        return PromoRecord.record_promo(promo_name, user_id)

    def test_promo_record(self):
        u1 = "http://facebookid.khanacademy.org/1234"
        u2 = "http://googleid.khanacademy.org/5678"
        p1 = "Public profiles"
        p2 = "Skynet"

        # First time
        self.assertTrue(self.r(p1, u1))
        # Second time and onwards
        for i in range(10):
            self.assertFalse(self.r(p1, u1))

        # Different user
        self.assertTrue(self.r(p1, u2))

        # Different promo
        self.assertTrue(self.r(p2, u1))
