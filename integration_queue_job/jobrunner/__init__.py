# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import time
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from threading import Thread

from odoo.service import server
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Our settings live in their own [queue_job] section of odoo.conf, which we parse
# ourselves. Odoo only ever iterates the [options] section (tools/config.py,
# `for name, value in p.items('options')`) and logs a warning for every key it
# does not recognise, so settings kept there cost one warning apiece on every
# process start. It never enumerates the other sections, so a section of our own
# is both silent and, incidentally, the layout every OCA queue_job doc assumes.
QUEUE_JOB_SECTION = 'queue_job'

# Before the section, the same settings were flat 'queue_job_*' keys under
# [options]. Odoo stores unknown keys as-is, which is how they reached us. Still
# honoured, so that upgrading the module does not silently repoint a live runner,
# but the section wins wherever both define a key.
LEGACY_PREFIX = 'queue_job_'
LEGACY_KEYS = ('channels', 'scheme', 'host', 'port')


def _read_config_section():
    """Return the [queue_job] section of odoo.conf as a dict."""
    cfg_path = config.get('config')
    if not cfg_path:
        return {}

    parser = ConfigParser(interpolation=None)
    try:
        parser.read(cfg_path)
    except (OSError, ConfigParserError):
        _logger.exception(
            'Could not read %s. The job runner falls back to its defaults.', cfg_path
        )
        return {}

    if not parser.has_section(QUEUE_JOB_SECTION):
        return {}
    return {key: value for key, value in parser[QUEUE_JOB_SECTION].items() if value}


def _read_legacy_options():
    """Return the deprecated flat 'queue_job_*' keys from [options]."""
    return {
        key: config.get(f'{LEGACY_PREFIX}{key}')
        for key in LEGACY_KEYS
        if config.get(f'{LEGACY_PREFIX}{key}')
    }


def _build_queue_job_config():
    settings = _read_config_section()
    legacy = _read_legacy_options()

    if legacy:
        _logger.warning(
            'odoo.conf still configures the job runner through %s under [options]. '
            'Odoo warns about every key it does not know there, and only a '
            '[queue_job] section can carry the jobrunner_db_* and http_auth_* '
            'settings. Move them:\n\n[queue_job]\n%s\n',
            ', '.join(f'{LEGACY_PREFIX}{key}' for key in sorted(legacy)),
            '\n'.join(f'{key} = {value}' for key, value in sorted(legacy.items())),
        )

    # A key defined in both places is a half-finished migration. Take the section:
    # it is what the admin wrote most recently, and the legacy key is the one Odoo
    # is already complaining about.
    for key, value in legacy.items():
        settings.setdefault(key, value)

    # An absent key must stay absent rather than acquire a default here: the runner
    # falls back to Odoo's own http_interface/http_port, and a default of ours
    # would shadow that and pin the runner to localhost:8069 no matter what Odoo is
    # really listening on.
    return settings


queue_job_config = _build_queue_job_config()


from .runner import QueueJobRunner, _channels  # NOQA: E402

START_DELAY = 5


# Here we monkey patch the Odoo server to start the job runner thread
# in the main server process (and not in forked workers). This is
# very easy to deploy as we don't need another startup script.


class QueueJobRunnerThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.runner = QueueJobRunner.from_environ_or_config()

    def run(self):
        # sleep a bit to let the workers start at ease
        time.sleep(START_DELAY)
        self.runner.run()

    def stop(self):
        self.runner.stop()


class WorkerJobRunner(server.Worker):
    """Jobrunner workers"""

    def __init__(self, multi):
        super().__init__(multi)
        self.watchdog_timeout = None
        self.runner = QueueJobRunner.from_environ_or_config()
        self._recover = False

    def sleep(self):
        pass

    def signal_handler(self, sig, frame):  # pylint: disable=missing-return
        _logger.debug("WorkerJobRunner (%s) received signal %s", self.pid, sig)
        super().signal_handler(sig, frame)
        self.runner.stop()

    def process_work(self):
        if self._recover:
            _logger.info("WorkerJobRunner (%s) runner is reinitialized", self.pid)
            self.runner = QueueJobRunner.from_environ_or_config()
            self._recover = False
        _logger.debug("WorkerJobRunner (%s) starting up", self.pid)
        time.sleep(START_DELAY)
        self.runner.run()

    def signal_time_expired_handler(self, n, stack):
        _logger.info(
            "Worker (%d) CPU time limit (%s) reached.Stop gracefully and recover",
            self.pid,
            config["limit_time_cpu"],
        )
        self._recover = True
        self.runner.stop()


runner_thread = None


def _is_runner_enabled():
    return not _channels().strip().startswith("root:0")


def _start_runner_thread(server_type):
    global runner_thread
    if not config["stop_after_init"]:
        if _is_runner_enabled():
            _logger.info("starting jobrunner thread (in %s)", server_type)
            runner_thread = QueueJobRunnerThread()
            runner_thread.start()
        else:
            _logger.info(
                "jobrunner thread (in %s) NOT started, "
                "because the root channel's capacity is set to 0",
                server_type,
            )


orig_prefork__init__ = server.PreforkServer.__init__
orig_prefork_process_spawn = server.PreforkServer.process_spawn
orig_prefork_worker_pop = server.PreforkServer.worker_pop
orig_threaded_start = server.ThreadedServer.start
orig_threaded_stop = server.ThreadedServer.stop


def prefork__init__(server, app):
    res = orig_prefork__init__(server, app)
    server.jobrunner = {}
    return res


def prefork_process_spawn(server):
    orig_prefork_process_spawn(server)
    if not hasattr(server, "jobrunner"):
        # if 'integration_queue_job' is not in server wide modules, PreforkServer is
        # not initialized with a 'jobrunner' attribute, skip this
        return
    if not server.jobrunner and _is_runner_enabled():
        server.worker_spawn(WorkerJobRunner, server.jobrunner)


def prefork_worker_pop(server, pid):
    res = orig_prefork_worker_pop(server, pid)
    if not hasattr(server, "jobrunner"):
        # if 'integration_queue_job' is not in server wide modules, PreforkServer is
        # not initialized with a 'jobrunner' attribute, skip this
        return res
    if pid in server.jobrunner:
        server.jobrunner.pop(pid)
    return res


def threaded_start(server, *args, **kwargs):
    res = orig_threaded_start(server, *args, **kwargs)
    _start_runner_thread("threaded server")
    return res


def threaded_stop(server):
    global runner_thread
    if runner_thread:
        runner_thread.stop()
    res = orig_threaded_stop(server)
    if runner_thread:
        runner_thread.join()
        runner_thread = None
    return res


server.PreforkServer.__init__ = prefork__init__
server.PreforkServer.process_spawn = prefork_process_spawn
server.PreforkServer.worker_pop = prefork_worker_pop
server.ThreadedServer.start = threaded_start
server.ThreadedServer.stop = threaded_stop
