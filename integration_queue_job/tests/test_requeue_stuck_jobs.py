# Copyright (c) 2026 VentorTech (https://ventor.tech)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import fields
from odoo.tests import common
from odoo.tools import config, mute_logger


class TestRequeueStuckJobs(common.TransactionCase):
    """The 'Jobs Garbage Collector' cron is the only thing that recovers a job
    whose dispatch was lost, so its retry accounting is what decides whether a
    job that dies on every single run eventually fails or is rescued forever.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.job_model = cls.env["queue.job"]

    def _create_job(self, state, retry=0, max_retries=5, minutes_ago=30):
        """Create a job that has been sitting in ``state`` for ``minutes_ago``."""
        stale = fields.Datetime.now() - timedelta(minutes=minutes_ago)
        vals = {
            "uuid": str(uuid4()),
            "user_id": self.env.user.id,
            "state": state,
            "model_name": "queue.job",
            "method_name": "write",
            "args": (),
            "retry": retry,
            "max_retries": max_retries,
        }
        if state == "enqueued":
            vals["date_enqueued"] = stale
        elif state == "started":
            vals["date_enqueued"] = stale
            vals["date_started"] = stale
        return self.job_model.with_context(
            _job_edit_sentinel=self.job_model.EDIT_SENTINEL
        ).create(vals)

    @mute_logger('odoo.addons.integration_queue_job.models.queue_job')
    def _collect(self, enqueued_delta=5, started_delta=20):
        """Run the cron exactly as ``data/queue_data.xml`` does.

        Muted: every test in this class deliberately puts a job in a state the
        GC is meant to warn about (that's the behavior under test), so the
        "stuck job(s)" / "Giving up on job" warnings are expected noise here.
        """
        self.job_model.requeue_stuck_jobs(
            enqueued_delta=enqueued_delta, started_delta=started_delta
        )

    def test_enqueued_job_is_requeued_without_spending_an_attempt(self):
        job = self._create_job("enqueued", retry=2)

        self._collect()

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 2, "an enqueued job never reached a worker")

    def test_dead_started_job_is_requeued_and_charged_one_attempt(self):
        job = self._create_job("started", retry=0)

        self._collect()

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 1, "the run it died in counts as an attempt")

    def test_dead_started_job_fails_once_out_of_retries(self):
        job = self._create_job("started", retry=4, max_retries=5)

        self._collect()

        self.assertEqual(job.state, "failed", "must not be requeued a 6th time")
        self.assertEqual(job.retry, 5)
        self.assertEqual(job.exc_name, "JobFoundDead")

    def test_failure_message_carries_this_modules_own_subtype(self):
        """Guard the module rename.

        ``message_post`` resolves ``subtype_xmlid`` through ``_xmlid_to_res_id``,
        which returns False for an unknown xml id and then silently falls back to
        ``mail.mt_note``. An xml id left over from the upstream module name
        therefore costs no error -- only a subtype nobody is subscribed to.
        """
        job = self._create_job("started", retry=4, max_retries=5)

        self._collect()

        self.assertEqual(job.state, "failed")
        self.assertIn(
            self.env.ref("integration_queue_job.mt_job_failed"),
            job.message_ids.subtype_id,
        )

    def test_dead_started_job_with_infinite_retries_is_never_failed(self):
        # max_retries = 0 means "retry indefinitely", everywhere in the module.
        job = self._create_job("started", retry=999, max_retries=0)

        self._collect()

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 1000)

    def test_jobs_within_the_deadline_are_left_alone(self):
        started = self._create_job("started", minutes_ago=5)
        enqueued = self._create_job("enqueued", minutes_ago=1)

        self._collect(enqueued_delta=5, started_delta=20)

        self.assertEqual(started.state, "started")
        self.assertEqual(started.retry, 0)
        self.assertEqual(enqueued.state, "enqueued")

    def test_dead_job_fails_after_exactly_max_retries_passes(self):
        """A job killed mid-run on every attempt must not be rescued forever.

        This is the shape of the dispatch storm: the worker never stores the
        ``retry`` increment that ``perform()`` made, so before the fix the cron
        saw a pristine job every 5 minutes.
        """
        job = self._create_job("started", retry=0, max_retries=3)
        stale = fields.Datetime.now() - timedelta(minutes=30)

        for attempt in (1, 2):
            self._collect()
            self.assertEqual(job.state, "pending", f"gave up on attempt {attempt}")
            self.assertEqual(job.retry, attempt)
            # The runner dispatches it again, and the worker is killed again
            # before it can store anything.
            job.write({"state": "started", "date_started": stale})

        self._collect()

        self.assertEqual(job.state, "failed")
        self.assertEqual(job.retry, 3)
        self.assertEqual(job.exc_name, "JobFoundDead")

    def test_started_delta_is_raised_to_what_limit_time_real_allows(self):
        """The cron body cannot know this deployment's limit_time_real.

        With limit_time_real=900s a job can still be alive 18 minutes in, so a
        job started 16 minutes ago must be left alone even though the caller
        asked for 15.
        """
        job = self._create_job("started", minutes_ago=16)

        with patch.dict(config.options, {"limit_time_real": 900}):
            self._collect(started_delta=15)

        self.assertEqual(job.state, "started", "the job may still be running")
        self.assertEqual(job.retry, 0)

    def test_job_older_than_the_raised_delta_is_still_rescued(self):
        job = self._create_job("started", minutes_ago=25)

        with patch.dict(config.options, {"limit_time_real": 900}):
            self._collect(started_delta=15)

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 1)

    def test_a_generous_started_delta_is_left_alone(self):
        # Clamping only ever raises the deadline, it never lowers it.
        job = self._create_job("started", minutes_ago=25)

        with patch.dict(config.options, {"limit_time_real": 900}):
            self._collect(started_delta=30)

        self.assertEqual(job.state, "started")

    def test_started_delta_zero_still_disables_the_started_check(self):
        job = self._create_job("started", minutes_ago=600)

        with patch.dict(config.options, {"limit_time_real": 900}):
            self._collect(started_delta=0)

        self.assertEqual(job.state, "started", "0 means never requeue a started job")

    def test_manual_requeue_still_resets_retry(self):
        job = self._create_job("failed", retry=3)

        job.requeue()

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 0, "a user asking for a retry wants a fresh one")
