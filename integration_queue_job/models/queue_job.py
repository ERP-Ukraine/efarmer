# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
from datetime import datetime, timedelta

from odoo import _, api, exceptions, fields, models
from odoo.fields import Domain
from odoo.tools import config, html_escape

from odoo.addons.base_sparse_field.models.fields import Serialized

from ..delay import Graph
from ..exception import JobError
from ..fields import JobSerialized
from ..job import (
    CANCELLED,
    DONE,
    ENQUEUED,
    FAILED,
    PENDING,
    STARTED,
    STATES,
    WAIT_DEPENDENCIES,
    Job,
)

_logger = logging.getLogger(__name__)

# How many job uuids the garbage collector spells out in a single log line. An
# outage leaves a whole backlog stuck at once, and a 36-character uuid per job
# turns one WARNING into hundreds of kilobytes.
LOG_STUCK_JOBS_SAMPLE = 10

# Odoo stops a request once it has run for 'limit_time_real' seconds, but it does
# not kill the thread at that instant. Reading odoo/service/server.py: the main
# loop only notices on its next pass (SLEEP_INTERVAL = 60s), then waits for the
# other in-flight requests before reloading (up to another SLEEP_INTERVAL), then
# joins the threads (1s).
KILL_DELAY_SECONDS = 2 * 60 + 1


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""

    _name = "queue.job"
    _description = "Queue Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _log_access = False

    _order = "date_created DESC, date_done DESC"

    _removal_interval = 30  # days
    _default_related_action = "related_action_open_record"

    # This must be passed in a context key "_job_edit_sentinel" to write on
    # protected fields. It protects against crafting "queue.job" records from
    # RPC (e.g. on internal methods). When ``with_delay`` is used, the sentinel
    # is set.
    EDIT_SENTINEL = object()
    _protected_fields = (
        "uuid",
        "name",
        "date_created",
        "model_name",
        "method_name",
        "func_string",
        "channel_method_name",
        "job_function_id",
        "records",
        "args",
        "kwargs",
    )

    uuid = fields.Char(string="UUID", readonly=True, index=True, required=True)
    graph_uuid = fields.Char(
        string="Graph UUID",
        readonly=True,
        index=True,
        help="Single shared identifier of a Graph. Empty for a single job.",
    )
    user_id = fields.Many2one(comodel_name="res.users", string="User ID")
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", index=True
    )
    name = fields.Char(string="Description", readonly=True)

    model_name = fields.Char(string="Model", readonly=True)
    method_name = fields.Char(readonly=True)
    records = JobSerialized(
        string="Record(s)",
        readonly=True,
        base_type=models.BaseModel,
    )
    dependencies = Serialized(readonly=True)
    # dependency graph as expected by the field widget
    dependency_graph = Serialized(compute="_compute_dependency_graph")
    graph_jobs_count = fields.Integer(compute="_compute_graph_jobs_count")
    args = JobSerialized(readonly=True, base_type=tuple)
    kwargs = JobSerialized(readonly=True, base_type=dict)
    func_string = fields.Char(string="Task", readonly=True)

    state = fields.Selection(STATES, readonly=True, required=True, index=True)
    priority = fields.Integer()
    exc_name = fields.Char(string="Exception", readonly=True)
    exc_message = fields.Char(string="Exception Message", readonly=True, tracking=True)
    exc_info = fields.Text(string="Exception Info", readonly=True)
    result = fields.Text(readonly=True)

    date_created = fields.Datetime(string="Created Date", readonly=True)
    date_started = fields.Datetime(string="Start Date", readonly=True)
    date_enqueued = fields.Datetime(string="Enqueue Time", readonly=True)
    date_done = fields.Datetime(readonly=True)
    exec_time = fields.Float(
        string="Execution Time (avg)",
        aggregator="avg",
        help="Time required to execute this job in seconds. Average when grouped.",
    )
    date_cancelled = fields.Datetime(readonly=True)

    eta = fields.Datetime(string="Execute only after")
    retry = fields.Integer(string="Current try")
    max_retries = fields.Integer(
        string="Max. retries",
        help="The job will fail if the number of tries reach the "
        "max. retries.\n"
        "Retries are infinite when empty.",
    )
    # FIXME the name of this field is very confusing
    channel_method_name = fields.Char(string="Complete Method Name", readonly=True)
    job_function_id = fields.Many2one(
        comodel_name="queue.job.function",
        string="Job Function",
        readonly=True,
    )

    channel = fields.Char(index=True)

    identity_key = fields.Char(readonly=True)
    worker_pid = fields.Integer(readonly=True)

    def init(self):
        self.env.cr.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = %s ",
            ("queue_job_identity_key_state_partial_index",),
        )
        if not self.env.cr.fetchone():
            self.env.cr.execute(
                "CREATE INDEX queue_job_identity_key_state_partial_index "
                "ON queue_job (identity_key) WHERE state in ('pending', "
                "'enqueued', 'wait_dependencies') AND identity_key IS NOT NULL;"
            )

    @api.depends("dependencies")
    def _compute_dependency_graph(self):
        jobs_groups = self.env["queue.job"]._read_group(
            [
                (
                    "graph_uuid",
                    "in",
                    [uuid for uuid in self.mapped("graph_uuid") if uuid],
                )
            ],
            ["graph_uuid", "ids:array_agg(id)"],
            ["graph_uuid"],
        )
        ids_per_graph_uuid = {
            group["graph_uuid"]: group["ids"] for group in jobs_groups
        }
        for record in self:
            if not record.graph_uuid:
                record.dependency_graph = {}
                continue

            graph_jobs = self.browse(ids_per_graph_uuid.get(record.graph_uuid) or [])
            if not graph_jobs:
                record.dependency_graph = {}
                continue

            graph_ids = {graph_job.uuid: graph_job.id for graph_job in graph_jobs}
            graph_jobs_by_ids = {graph_job.id: graph_job for graph_job in graph_jobs}

            graph = Graph()
            for graph_job in graph_jobs:
                graph.add_vertex(graph_job.id)
                for parent_uuid in graph_job.dependencies["depends_on"]:
                    parent_id = graph_ids.get(parent_uuid)
                    if not parent_id:
                        continue
                    graph.add_edge(parent_id, graph_job.id)
                for child_uuid in graph_job.dependencies["reverse_depends_on"]:
                    child_id = graph_ids.get(child_uuid)
                    if not child_id:
                        continue
                    graph.add_edge(graph_job.id, child_id)

            record.dependency_graph = {
                # list of ids
                "nodes": [
                    graph_jobs_by_ids[graph_id]._dependency_graph_vis_node()
                    for graph_id in graph.vertices()
                ],
                # list of tuples (from, to)
                "edges": graph.edges(),
            }

    def _dependency_graph_vis_node(self):
        """Return the node as expected by the JobDirectedGraph widget"""
        default = ("#D2E5FF", "#2B7CE9")
        colors = {
            DONE: ("#C2FABC", "#4AD63A"),
            FAILED: ("#FB7E81", "#FA0A10"),
            STARTED: ("#FFFF00", "#FFA500"),
        }
        return {
            "id": self.id,
            "title": (
                f"<strong>{html_escape(self.display_name)}</strong><br/>"
                f"{html_escape(self.func_string)}"
            ),
            "color": colors.get(self.state, default)[0],
            "border": colors.get(self.state, default)[1],
            "shadow": True,
        }

    def _compute_graph_jobs_count(self):
        jobs_groups = self.env["queue.job"]._read_group(
            [
                (
                    "graph_uuid",
                    "in",
                    [uuid for uuid in self.mapped("graph_uuid") if uuid],
                )
            ],
            ["graph_uuid"],
            ["graph_uuid"],
        )
        count_per_graph_uuid = {
            group["graph_uuid"]: group["graph_uuid_count"] for group in jobs_groups
        }
        for record in self:
            record.graph_jobs_count = count_per_graph_uuid.get(record.graph_uuid) or 0

    @api.model_create_multi
    def create(self, vals_list):
        if not vals_list:
            return self.browse()

        if self.env.context.get("_job_edit_sentinel") is not self.EDIT_SENTINEL:
            # Prevent to create a queue.job record "raw" from RPC.
            # ``with_delay()`` must be used.
            raise exceptions.AccessError(
                _("Queue jobs must be created by calling 'with_delay()'.")
            )

        return super(
            QueueJob,
            self.with_context(mail_create_nolog=True, mail_create_nosubscribe=True),
        ).create(vals_list)

    def write(self, vals):
        if self.env.context.get("_job_edit_sentinel") is not self.EDIT_SENTINEL:
            write_on_protected_fields = [
                fieldname for fieldname in vals if fieldname in self._protected_fields
            ]
            if write_on_protected_fields:
                raise exceptions.AccessError(
                    _("Not allowed to change field(s): {}").format(
                        write_on_protected_fields
                    )
                )

        different_user_jobs = self.browse()
        if vals.get("user_id"):
            different_user_jobs = self.filtered(
                lambda records: records.env.user.id != vals["user_id"]
            )

        if vals.get("state") == "failed":
            self._message_post_on_failure()

        result = super().write(vals)

        for record in different_user_jobs:
            # the user is stored in the env of the record, but we still want to
            # have a stored user_id field to be able to search/groupby, so
            # synchronize the env of records with user_id
            super(QueueJob, record).write(
                {"records": record.records.with_user(vals["user_id"])}
            )
        return result

    def open_related_action(self):
        """Open the related action associated to the job"""
        self.ensure_one()
        job = Job.load(self.env, self.uuid)
        action = job.related_action()
        if action is None:
            raise exceptions.UserError(_("No action available for this job"))
        return action

    def open_graph_jobs(self):
        """Return action that opens all jobs of the same graph"""
        self.ensure_one()
        jobs = self.env["queue.job"].search([("graph_uuid", "=", self.graph_uuid)])

        action = self.env["ir.actions.act_window"]._for_xml_id(
            "integration_queue_job.action_queue_job"
        )
        action.update(
            {
                "name": _("Jobs for graph %s") % (self.graph_uuid),
                "context": {},
                "domain": [("id", "in", jobs.ids)],
            }
        )
        return action

    def _change_job_state(self, state, result=None, reset_retry=True):
        """Change the state of the `Job` object

        Changing the state of the Job will automatically change some fields
        (date, result, ...).
        """
        for record in self:
            job_ = Job.load(record.env, record.uuid)
            if state == DONE:
                job_.set_done(result=result)
                job_.store()
                record.env["queue.job"].flush_model()
                job_.enqueue_waiting()
            elif state == PENDING:
                job_.set_pending(result=result, reset_retry=reset_retry)
                job_.store()
            elif state == CANCELLED:
                job_.set_cancelled(result=result)
                job_.store()
                record.env["queue.job"].flush_model()
                job_.cancel_dependent_jobs()
            else:
                raise ValueError(f"State not supported: {state}")

    def button_done(self):
        result = _("Manually set to done by {}").format(self.env.user.name)
        self._change_job_state(DONE, result=result)
        return True

    def button_cancelled(self):
        result = _("Cancelled by {}").format(self.env.user.name)
        self._change_job_state(CANCELLED, result=result)
        return True

    def requeue(self, reset_retry=True):
        """Send jobs back to 'pending'.

        :param reset_retry: clear the retry counter, as a user asking for a
            fresh attempt would expect. Automatic requeues must pass False: the
            garbage collector runs every 5 minutes, and wiping the counter on
            every pass would hide a job that has been failing all along.
        """
        jobs_to_requeue = self.filtered(lambda job_: job_.state != WAIT_DEPENDENCIES)
        jobs_to_requeue._change_job_state(PENDING, reset_retry=reset_retry)
        return True

    def _message_post_on_failure(self):
        # subscribe the users now to avoid to subscribe them
        # at every job creation
        domain = self._subscribe_users_domain()
        base_users = self.env["res.users"].search(domain)
        for record in self:
            users = base_users | record.user_id
            record.message_subscribe(partner_ids=users.mapped("partner_id").ids)
            msg = record._message_failed_job()
            if msg:
                record.message_post(body=msg, subtype_xmlid="integration_queue_job.mt_job_failed")

    def _subscribe_users_domain(self):
        """Subscribe all users having the 'Queue Job Manager' group"""
        group = self.env.ref("integration_queue_job.group_queue_job_manager")
        if not group:
            return None
        companies = self.mapped("company_id")
        domain = [("group_ids", "=", group.id)]
        if companies:
            domain.append(("company_id", "in", companies.ids))
        return domain

    def _message_failed_job(self):
        """Return a message which will be posted on the job when it is failed.

        It can be inherited to allow more precise messages based on the
        exception informations.

        If nothing is returned, no message will be posted.
        """
        self.ensure_one()
        return _(
            "Something bad happened during the execution of the job. "
            "More details in the 'Exception Information' section."
        )

    def _needaction_domain_get(self):
        """Returns the domain to filter records that require an action

        :return: domain or False is no action
        """
        return [("state", "=", "failed")]

    def autovacuum(self):
        """Delete all jobs done based on the removal interval defined on the
           channel

        Called from a cron.
        """
        for channel in self.env["queue.job.channel"].search([]):
            deadline = datetime.now() - timedelta(days=int(channel.removal_interval))
            while True:
                jobs = self.search(
                    [
                        "|",
                        ("date_done", "<=", deadline),
                        ("date_cancelled", "<=", deadline),
                        ("channel", "=", channel.complete_name),
                    ],
                    limit=1000,
                )
                if jobs:
                    jobs.unlink()
                    if not config["test_enable"]:
                        self.env.cr.commit()  # pylint: disable=E8102
                else:
                    break
        return True

    def _minimum_started_delta(self):
        """Minutes after which a 'started' job is provably dead, 0 if never.

        Odoo stops a request once it has run for ``limit_time_real`` seconds, but
        it does not kill the thread at that instant -- see KILL_DELAY_SECONDS.

        Returns 0 when ``limit_time_real`` is disabled: a job may then run for as
        long as it likes, and no deadline can prove it dead.
        """
        limit_time_real = config.get("limit_time_real") or 0
        if limit_time_real <= 0:
            return 0
        # Round up. A partial minute of grace is not grace.
        return (limit_time_real + KILL_DELAY_SECONDS + 59) // 60

    def _safe_started_delta(self, started_delta):
        """Never let a caller requeue a job that could still be running.

        Nothing locks a running job, so requeuing one executes it a second time,
        in parallel. The deadline at which a job is safely dead depends on this
        deployment's ``limit_time_real`` -- a number hardcoded in the cron body
        cannot know it.
        """
        if not started_delta:
            # 0 means "never requeue a started job", the conservative choice.
            return 0

        minimum = self._minimum_started_delta()
        if not minimum:
            _logger.warning(
                "Jobs Garbage Collector: 'limit_time_real' is disabled, so a "
                "started job can never be proven dead. Requeuing one after %s "
                "minutes may execute it a second time, in parallel.",
                started_delta,
            )
            return started_delta

        if started_delta < minimum:
            _logger.warning(
                "Jobs Garbage Collector: started_delta=%s minutes, but on this "
                "deployment a job can still be alive %s minutes after it started. "
                "Using %s instead, so that a running job is not executed twice.",
                started_delta,
                minimum,
                minimum,
            )
            return minimum
        return started_delta

    def requeue_stuck_jobs(self, enqueued_delta=5, started_delta=0):
        """Rescue jobs the runner has abandoned.

        :param enqueued_delta: after how many minutes in 'enqueued' a job is
                               considered never dispatched. 0 disables the check.

        :param started_delta: after how many minutes in 'started' a job is
                              considered dead. 0 disables the check. Raised to
                              ``_minimum_started_delta()`` when it is too small to
                              be safe, so the cron body does not have to know this
                              deployment's ``limit_time_real``.
        """
        started_delta = self._safe_started_delta(started_delta)
        stuck_jobs = self._get_stuck_jobs_to_requeue(
            enqueued_delta=enqueued_delta, started_delta=started_delta
        )
        # Explain the rescue before it happens, while we can still see which
        # state each job was found in.
        self._log_stuck_jobs(stuck_jobs, enqueued_delta, started_delta)

        # A job found in 'started' died in the middle of a run, so that run
        # counts as a spent attempt. One found in 'enqueued' never reached a
        # worker, so nothing was spent on it and it is simply requeued.
        dead_jobs = stuck_jobs.filtered(lambda job_: job_.state == STARTED)
        dead_jobs._rescue_dead_jobs()

        # Never reset 'retry' here: this cron runs every 5 minutes, and a job it
        # keeps rescuing would have its retry budget wiped on every pass and so
        # never reach max_retries.
        (stuck_jobs - dead_jobs).requeue(reset_retry=False)
        return True

    def _rescue_dead_jobs(self):
        """Requeue jobs that died mid-run, giving up on those out of retries.

        ``Job.perform()`` increments ``retry`` as soon as a job starts running,
        but the new value only reaches the database once the job finishes, fails
        or is postponed. A job killed in the middle of a run -- by
        ``limit_time_real``, the OOM killer, or a hard restart -- leaves no trace
        of the attempt. Charging it here is what lets ``max_retries`` eventually
        be reached; without it, a job that dies on every single run is rescued
        every 5 minutes forever.

        As everywhere else, ``max_retries = 0`` means "retry indefinitely".

        A job out of retries is failed rather than requeued, and that is also the
        safer branch: nothing locks a running job, so if the 'started' deadline
        misjudged a job that is in fact still alive, failing it costs a wrong
        state that the job itself overwrites on completion, whereas requeuing it
        would run a second copy in parallel.
        """
        for record in self:
            job_ = Job.load(record.env, record.uuid)
            job_.retry += 1
            if job_.max_retries and job_.retry >= job_.max_retries:
                job_.set_failed(
                    exc_name="JobFoundDead",
                    exc_message=_(
                        "Job found dead after %(retry)s attempts", retry=job_.retry
                    ),
                    exc_info=_(
                        "The job was still in state 'started' long after it "
                        "should have finished, so it is assumed dead, and its "
                        "%(max_retries)s retries are exhausted.",
                        max_retries=job_.max_retries,
                    ),
                )
                _logger.warning(
                    "Giving up on job %s: found dead after %s attempts",
                    job_.uuid,
                    job_.retry,
                )
            else:
                job_.set_pending(reset_retry=False)
            job_.store()

    def _log_stuck_jobs(self, stuck_jobs, enqueued_delta, started_delta):
        """Record why each stuck job was picked up, in the log and in its chatter.

        The job runner deliberately draws no conclusion from a request timeout,
        so a job whose dispatch was lost stays 'enqueued' until this cron
        rescues it. Without a trace, that reads as a job stuck for no reason.
        """
        if not stuck_jobs:
            return

        delta_by_state = {ENQUEUED: enqueued_delta, STARTED: started_delta}
        bodies = {}
        for job in stuck_jobs:
            bodies[job.id] = _(
                "Found stuck by the Jobs Garbage Collector: the job stayed in "
                "state '%(state)s' for more than %(delta)s minutes.",
                state=job.state,
                delta=delta_by_state.get(job.state),
            )

        # Not "requeuing": one out of retries is failed instead, see
        # _rescue_dead_jobs().
        uuids = stuck_jobs.mapped("uuid")
        sample, rest = uuids[:LOG_STUCK_JOBS_SAMPLE], uuids[LOG_STUCK_JOBS_SAMPLE:]
        _logger.warning(
            "Found %s stuck job(s): %s%s",
            len(uuids),
            ", ".join(sample),
            f", and {len(rest)} more (raise this logger to DEBUG for the rest)"
            if rest
            else "",
        )
        if rest:
            _logger.debug("Remaining stuck jobs: %s", ", ".join(rest))

        # Each job also gets a note, so an individual job explains itself without
        # digging through the log. This is one batched INSERT, not one per job.
        stuck_jobs._message_log_batch(bodies=bodies)

    def _get_stuck_jobs_domain(self, queue_dl, started_dl):
        domain = []
        now = fields.Datetime.now()
        if queue_dl:
            queue_dl = now - timedelta(minutes=queue_dl)
            domain.append(
                [
                    "&",
                    ("date_enqueued", "<=", fields.Datetime.to_string(queue_dl)),
                    ("state", "=", "enqueued"),
                ]
            )
        if started_dl:
            started_dl = now - timedelta(minutes=started_dl)
            domain.append(
                [
                    "&",
                    ("date_started", "<=", fields.Datetime.to_string(started_dl)),
                    ("state", "=", "started"),
                ]
            )
        if not domain:
            raise exceptions.ValidationError(
                _("If both parameters are 0, ALL jobs will be requeued!")
            )
        return Domain.OR(domain)

    def _get_stuck_jobs_to_requeue(self, enqueued_delta, started_delta):
        job_model = self.env["queue.job"]
        stuck_jobs = job_model.search(
            self._get_stuck_jobs_domain(enqueued_delta, started_delta)
        )
        return stuck_jobs

    def related_action_open_record(self):
        """Open a form view with the record(s) of the job.

        For instance, for a job on a ``product.product``, it will open a
        ``product.product`` form view with the product record(s) concerned by
        the job. If the job concerns more than one record, it opens them in a
        list.

        This is the default related action.

        """
        self.ensure_one()
        records = self.records.exists()
        if not records:
            return None
        action = {
            "name": _("Related Record"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": records._name,
        }
        if len(records) == 1:
            action["res_id"] = records.id
        else:
            action.update(
                {
                    "name": _("Related Records"),
                    "view_mode": "list,form",
                    "domain": [("id", "in", records.ids)],
                }
            )
        return action

    def _test_job(self, failure_rate=0):
        _logger.info("Running test job.")
        if random.random() <= failure_rate:
            raise JobError("Job failed")
