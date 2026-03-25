# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """
    Clear all existing order risk records.
    They contain legacy REST API float scores or broken string-based scores that
    cannot be migrated to the new GraphQL schema (sentiment + risk_level fields).
    Records will be re-populated on the next order sync.
    """
    cr.execute('DELETE FROM external_order_risk')
