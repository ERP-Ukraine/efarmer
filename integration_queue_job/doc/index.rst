=====================
Integration Queue Job
=====================

Overview
--------
The **Integration Queue Job** module is a lightweight fork of the OCA `queue_job` addon.
It provides background job processing for Odoo, optimized to work seamlessly with
VentorTech's e-commerce connectors (`https://ecosystem.ventor.tech/ <https://ecosystem.ventor.tech/>`_).

This fork keeps only the features needed for our connectors, simplifying the codebase
while remaining compatible with the original `queue_job`. You can safely use either
module with our connectors.

Why this fork?
--------------
- Focused and simplified job queue system (reduced complexity).
- Fully compatible with VentorTech e-commerce connectors.
- Preserves compatibility with the original OCA `queue_job`.
- Easier maintenance across Odoo versions.

Usage Example
-------------
You can postpone method calls to be executed asynchronously:

.. code:: python

   class MyModel(models.Model):
       _name = 'my.model'

       def my_method(self, a, k=None):
           _logger.info("executed with a=%s, k=%s", a, k)

   class MyOtherModel(models.Model):
       _name = 'my.other.model'

       def button_do_stuff(self):
           # This will run in the background
           self.env['my.model'].with_delay().my_method('a', k=2)

Release Notes
-------------
* 1.0.9 (2026-07-14)
    - The job runner now reads its settings from a ``[queue_job]`` section of
      ``odoo.conf``. Odoo only parses the ``[options]`` section and logs a
      warning for every key it does not recognise, so the ``queue_job_*`` keys
      cost four warnings on every process start -- on one production instance,
      132 log lines a day. It never enumerates the other sections, so a section
      of our own is silent. It is also the layout OCA's ``queue_job``
      documentation assumes, and the only one that can carry the
      ``jobrunner_db_*`` and ``http_auth_*`` settings: ``runner.py`` reads them,
      but they were unreachable from a flat key and always resolved to ``None``.

      .. code:: ini

         [options]
         server_wide_modules = base,web,integration_queue_job,...

         ; Keep this section at the end of the file: in an .ini file every key
         ; below a section header belongs to that section.
         [queue_job]
         channels = root:1
         scheme = https
         host = mycompany.odoo.com
         port = 443

      **No action required.** The old ``queue_job_*`` keys under ``[options]``
      still work, so an existing ``odoo.conf`` keeps its current behaviour --
      upgrading will not silently repoint a live runner. While they are in use,
      the runner logs one warning naming them, with the section to copy in their
      place. Where both define the same key, the section wins.

* 1.0.8 (2026-07-14)
    - Fixed the job runner re-dispatching the same job about once per second
      until the platform answered HTTP 429. ``/queue_job/runjob`` only responds
      once the job has finished, so the runner's 1 second timeout means "we are
      not waiting for the result", not "the request failed". Treating it as a
      failure reset the job to ``pending``, which notified the runner, which
      re-dispatched it, and so on. A timeout is now ignored. Jobs whose request
      really was lost are still recovered by the ``Jobs Garbage Collector`` cron.
    - The runner no longer resets a job to ``pending`` on arbitrary request
      exceptions either. It only postpones on HTTP 429, with the ``Retry-After``
      backoff introduced in 1.0.5.
    - ``started_delta`` is now raised automatically to whatever this deployment's
      ``limit_time_real`` makes safe, and the cron ships with 20 minutes instead
      of 15. Odoo caps a request at ``limit_time_real`` but takes up to ~121s more
      to actually kill the thread, so a job could be requeued while it was still
      running and, since nothing locks a running job, executed a second time in
      parallel. A number written into the cron body cannot know that limit: 20
      minutes is right for Odoo.sh's 900s and still too short for a host running
      1200s. ``started_delta=0`` keeps meaning "never requeue a started job".

      **No action required on existing databases.** The cron is declared with
      ``noupdate="1"``, so upgrading does not rewrite its body — but a database
      left on ``started_delta=15`` is now clamped at runtime, with a warning in
      the log naming the value it used instead.
    - The ``Jobs Garbage Collector`` cron no longer resets the ``retry`` counter
      of the jobs it requeues. It runs every 5 minutes, so a job it kept
      rescuing had its retry budget wiped on every pass. Requeuing by hand, from
      the job form or the *Requeue Jobs* wizard, still resets ``retry``.
    - A job the cron finds dead in ``started`` now has that attempt counted, and
      is set to ``failed`` with ``JobFoundDead`` once ``max_retries`` is reached
      (``max_retries = 0`` still means retry indefinitely). ``retry`` is
      incremented by ``perform()`` when a job starts, but the new value only
      reaches the database once the job finishes, fails or is postponed — a job
      killed mid-run by ``limit_time_real`` left no trace of the attempt, so it
      was rescued every 5 minutes forever. Jobs found in ``enqueued`` never
      reached a worker and are requeued without spending an attempt.

      Failing an exhausted job is also the safer branch. Nothing locks a running
      job, so if the ``started_delta`` deadline misjudges a job that is in fact
      still alive, failing it costs a wrong state that the job overwrites when it
      completes — whereas requeuing it would run a second copy in parallel.
    - The ``Jobs Garbage Collector`` cron now says what it did: a warning in the
      log, and a note in each rescued job's chatter explaining which state it was
      found in and after how long. Previously it fixed jobs silently, which made
      a job sitting in ``enqueued`` look stuck for no reason. The log line spells
      out the first 10 job uuids and reports how many more it withheld — an
      outage strands the whole backlog at once, and one uuid per job would turn a
      single warning into hundreds of kilobytes.

      **This cron must stay enabled.** Since the runner no longer guesses from a
      request timeout, the cron is now the only mechanism that recovers a job
      whose dispatch was lost. With ``root:1`` a single unrecovered job blocks
      the whole queue. Note that Odoo.sh deactivates scheduled actions on
      staging branches by default.
    - Failure messages are posted under this module's own ``Job failed`` message
      subtype again. The code still referenced it by its upstream xml id
      (``queue_job.mt_job_failed``), and ``message_post`` answers an unknown xml
      id by silently falling back to ``mail.mt_note`` — so the subtype the module
      declares, and that *Queue Job Manager* users are subscribed to by default,
      was never the one used.

      **Expect notifications where there were none.** Managers now actually get
      notified when a job fails, by inbox or by e-mail depending on each user's
      notification preference. Combined with the garbage collector now producing
      ``failed`` jobs of its own, an instance with a failing connector will be
      noticeably louder than before.
    - ``queue_job_host`` / ``queue_job_port`` now fall back to Odoo's own
      ``http_interface`` / ``http_port`` when unset, instead of being pinned to
      ``localhost:8069``. ``queue_job_port`` is coerced to an integer.
    - Fixed a file descriptor leak: the runner's stop-pipe is closed again.

* 1.0.7 (2026-07-10)
    - Removed the deprecated ``Request._get_session_and_dbname`` monkey patch
      (``post_load`` hook). The ``X-Odoo-Database`` header introduced in 1.0.6
      fully replaces it.

* 1.0.6 (2026-06-11)
    - Fixed job runner failing with "'NoneType' object is not callable" on
      multi-database instances. The runner now passes the target database in
      the ``X-Odoo-Database`` header so Odoo binds it during routing, instead
      of relying on auto-detection of a single database.

* 1.0.5 (2026-05-21)
    - Fixed job runner retry loop on HTTP 429 responses by postponing rate-limited jobs according to Retry-After.

* 1.0.4 (2026-13-02)
    - Added automatic requeuing of stuck jobs (5 min enqueued, 15 min started).

* 1.0.3 (2025-11-10)
    - Fixed create method to handle empty vals_list (Odoo tests compatibility).

* 1.0.2 (2025-10-28)
    - Fixed database lock issues.

* 1.0.1 (2025-09-23)
    - Small fixes and improvements.

* 1.0.0 (2025-09-16)
    - Initial release (forked from OCA/queue, cleaned up for VentorTech connectors).

Credits
-------
**Original Authors (queue_job):**
- Camptocamp
- ACSONE SA/NV
- Odoo Community Association (OCA)

**Maintained Fork (integration_queue_job):**
- VentorTech (https://ventor.tech)

License
-------
LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
