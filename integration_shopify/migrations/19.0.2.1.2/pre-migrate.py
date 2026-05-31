# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """
    Clear all existing order risk records.
    They contain legacy REST API float scores or broken string-based scores that
    cannot be migrated to the new GraphQL schema (sentiment + risk_level fields).
    Records will be re-populated on the next order sync.
    """
    # Guard against multi-version upgrades where pre-migrations of all pending
    # versions run before any module is loaded — the table may not exist yet.
    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'external_order_risk'
    """)
    if not cr.fetchone():
        return

    cr.execute('DELETE FROM external_order_risk')
