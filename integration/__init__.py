# See LICENSE file for full copyright and licensing details.

from . import patch
from . import models
from . import wizard
from . import controllers
import logging

_logger = logging.getLogger(__name__)

def pre_init_hook(cr):
    _logger.info("Cleaning config parameter before integration load")

    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key = 'integration.import_data_block_size'
    """)

def post_init_hook(env):
    """ Generate API key for the installed integration. """
    env['sale.integration'].generate_integration_api_key()
