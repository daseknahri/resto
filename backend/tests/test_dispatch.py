"""Unit tests for accounts.dispatch — the ranked-offer dispatch loop.

SimpleTestCase + mocks (no DB): we patch DeliveryJob, transaction.atomic, the
nearest-driver picker, and the push side-effect, and assert the state machine
(offer → cascade → open-pool fallback) behaves.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _job(**kw):
    base = dict(
        id=1, tenant_id=1, status="searching",
        declined_by=[], offer_round=0, offered_to=None, offered_to_id=None,
        offer_expires_at=None, is_open_pool=False, save=MagicMock(),
    )
    base.update(kw)
    return SimpleNamespace(**base)


class OfferToNextDriverTests(SimpleTestCase):
    @patch("accounts.dispatch._do_push")
    @patch("accounts.dispatch.pick_nearest_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_offers_to_nearest_driver(self, mock_dj, _atomic, mock_pick, mock_push):
        mock_dj.Status.SEARCHING = "searching"
        job = _job()
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        mock_pick.return_value = SimpleNamespace(id=7)

        from accounts.dispatch import offer_to_next_driver
        out = offer_to_next_driver(1)

        self.assertEqual(out.id, 7)
        self.assertEqual(job.offered_to.id, 7)
        self.assertIsNotNone(job.offer_expires_at)
        self.assertEqual(job.offer_round, 1)
        self.assertFalse(job.is_open_pool)
        job.save.assert_called_once()
        self.assertEqual(mock_push.call_args[0][0], ("offer", 7))

    @patch("accounts.dispatch._do_push")
    @patch("accounts.dispatch.pick_nearest_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_opens_pool_when_no_driver(self, mock_dj, _atomic, mock_pick, mock_push):
        mock_dj.Status.SEARCHING = "searching"
        job = _job()
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        mock_pick.return_value = None

        from accounts.dispatch import offer_to_next_driver
        out = offer_to_next_driver(1)

        self.assertIsNone(out)
        self.assertTrue(job.is_open_pool)
        self.assertIsNone(job.offered_to)
        self.assertEqual(mock_push.call_args[0][0], ("broadcast",))

    @patch("accounts.dispatch._do_push")
    @patch("accounts.dispatch.pick_nearest_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_max_rounds_opens_pool_without_offering(self, mock_dj, _atomic, mock_pick, mock_push):
        from accounts.dispatch import MAX_OFFER_ROUNDS
        mock_dj.Status.SEARCHING = "searching"
        job = _job(offer_round=MAX_OFFER_ROUNDS)
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        mock_pick.return_value = SimpleNamespace(id=9)  # should be ignored at the cap

        from accounts.dispatch import offer_to_next_driver
        offer_to_next_driver(1)

        mock_pick.assert_not_called()
        self.assertTrue(job.is_open_pool)

    @patch("accounts.dispatch._do_push")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_noop_when_not_searching(self, mock_dj, _atomic, mock_push):
        mock_dj.Status.SEARCHING = "searching"
        job = _job(status="assigned")
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        from accounts.dispatch import offer_to_next_driver
        out = offer_to_next_driver(1)

        self.assertIsNone(out)
        job.save.assert_not_called()
        mock_push.assert_not_called()


class DeclineOfferTests(SimpleTestCase):
    @patch("accounts.dispatch.offer_to_next_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_decline_records_and_cascades(self, mock_dj, _atomic, mock_offer):
        mock_dj.Status.SEARCHING = "searching"
        job = _job(offered_to_id=5)
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        from accounts.dispatch import decline_offer
        decline_offer(1, 5)

        self.assertIn(5, job.declined_by)
        self.assertIsNone(job.offered_to)
        job.save.assert_called_once()
        mock_offer.assert_called_once_with(1)

    @patch("accounts.dispatch.offer_to_next_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_decline_ignored_when_not_your_offer(self, mock_dj, _atomic, mock_offer):
        mock_dj.Status.SEARCHING = "searching"
        job = _job(offered_to_id=99)  # offered to someone else
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        from accounts.dispatch import decline_offer
        out = decline_offer(1, 5)

        self.assertIs(out, job)
        job.save.assert_not_called()
        mock_offer.assert_not_called()


class ExpireStaleOffersTests(SimpleTestCase):
    @patch("accounts.dispatch.offer_to_next_driver")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_expired_offer_is_cascaded(self, mock_dj, _atomic, mock_offer):
        mock_dj.Status.SEARCHING = "searching"
        past = timezone.now() - timedelta(minutes=5)
        job = _job(offered_to_id=5, offer_expires_at=past)
        mock_dj.objects.filter.return_value.values_list.return_value = [(1, 5)]
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        from accounts.dispatch import expire_and_cascade_stale_offers
        advanced = expire_and_cascade_stale_offers()

        self.assertEqual(advanced, 1)
        self.assertIn(5, job.declined_by)
        self.assertIsNone(job.offered_to)
        mock_offer.assert_called_once_with(1)
