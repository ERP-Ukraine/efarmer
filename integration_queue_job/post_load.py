import logging

from odoo import http

_logger = logging.getLogger(__name__)


def post_load():
    # DEPRECATED: kept only as a fallback. The job runner now sends the target
    # database in the 'X-Odoo-Database' header (see jobrunner/runner.py), which
    # Odoo resolves natively during routing. That mechanism does not rely on
    # this hook, which is important because Odoo skips the 'post_load' hook when
    # the module is already imported as a dependency of another module (e.g. a
    # connector imports 'odoo.addons.integration_queue_job.job' at module load
    # time), see odoo/modules/module.py 'load_openerp_module()'. This patch is
    # scheduled for removal in a future release.
    _logger.warning(
        "DEPRECATED: integration_queue_job '_get_session_and_dbname' monkey "
        "patch is deprecated in favor of the 'X-Odoo-Database' header sent by "
        "the job runner and will be removed in a future release."
    )
    _get_session_and_dbname_orig = http.Request._get_session_and_dbname

    def _get_session_and_dbname(self):
        session, dbname = _get_session_and_dbname_orig(self)
        if (
            not dbname
            and self.httprequest.path == "/queue_job/runjob"
            and self.httprequest.args.get("db")
        ):
            dbname = self.httprequest.args["db"]
        return session, dbname

    http.Request._get_session_and_dbname = _get_session_and_dbname
