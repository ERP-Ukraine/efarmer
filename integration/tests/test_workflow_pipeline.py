# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch, Mock, PropertyMock

from psycopg2 import OperationalError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkflowPipeline(TransactionCase):
    """Cover the auto-workflow pipeline branching logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pipeline = cls.env['integration.workflow.pipeline']
        cls.Line = cls.env['integration.workflow.pipeline.line']

        partner = cls.env['res.partner'].create({'name': 'Pipeline Test Partner'})
        order = cls.env['sale.order'].create({'partner_id': partner.id})
        cls.pipeline = cls.Pipeline.create({'order_id': order.id})

    def _add_task(self, step_method, state):
        return self.Line.create({
            'pipeline_id': self.pipeline.id,
            'current_step_method': step_method,
            'state': state,
        })

    def test_get_dependent_steps(self):
        """Returns the transitive closure of dependents; a leaf returns nothing."""
        self.assertEqual(
            self._add_task('validate_order', 'todo')._get_dependent_steps(),
            {'apply_advance_payment', 'validate_picking', 'create_invoice',
             'validate_invoice', 'send_invoice', 'register_payment'},
        )
        self.assertEqual(self._add_task('send_invoice', 'todo')._get_dependent_steps(), set())

    def test_skip_allowed_only_for_failed(self):
        self.assertFalse(self._add_task('create_invoice', 'todo').skip_allowed)

    def test_skip_allowed_false_when_dependent_enabled(self):
        failed = self._add_task('create_invoice', 'failed')
        self._add_task('validate_invoice', 'todo')  # depends on create_invoice
        self.assertFalse(failed.skip_allowed)

    def test_skip_allowed_true_when_no_enabled_dependent(self):
        failed = self._add_task('create_invoice', 'failed')
        self._add_task('validate_invoice', 'skip')
        self.assertTrue(failed.skip_allowed)

    # --- _compute_alert -------------------------------------------------------

    def test_alert_not_configured_when_all_skipped(self):
        self._add_task('validate_order', 'skip')
        self.assertEqual(self.pipeline.alert_type, 'not_configured')

    def test_alert_succeed_when_done(self):
        self._add_task('validate_order', 'done')
        self.assertEqual(self.pipeline.alert_type, 'succeed')

    def test_alert_failed_when_task_failed(self):
        self._add_task('validate_order', 'done')
        self._add_task('create_invoice', 'failed')
        self.assertEqual(self.pipeline.alert_type, 'failed')

    def test_alert_processing_when_pending(self):
        self._add_task('validate_order', 'todo')
        self.assertEqual(self.pipeline.alert_type, 'processing')

    # --- _execute_order_method ------------------------------------------------

    def test_execute_order_method_reraises_concurrency_error(self):
        """Concurrency errors must propagate so the job gets requeued."""
        task = self._add_task('validate_order', 'todo')

        def raise_concurrency():
            raise OperationalError()

        with patch.object(type(task), '_retrieve_current_order_method',
                          return_value=raise_concurrency):
            with self.assertRaises(OperationalError):
                task._execute_order_method()

    def test_execute_order_method_captures_failure(self):
        """Business errors are caught, reported and stored as a traceback."""
        task = self._add_task('validate_order', 'todo')

        def boom():
            raise ValueError('boom')

        with patch.object(type(task), '_retrieve_current_order_method', return_value=boom):
            result, message = task._execute_order_method()

        self.assertFalse(result)
        self.assertIn('boom', message)
        self.assertTrue(task.pipeline_id.error_traceback)

    # --- _integration_apply_advance_payment -----------------------------------

    def test_advance_payment_skipped_when_not_confirmed(self):
        """A draft order can't be paid in advance; the step passes as a no-op."""
        order = self.pipeline.order_id  # created in draft
        result, message = order._integration_apply_advance_payment()
        self.assertTrue(result)
        self.assertIn('not confirmed', message)

    def test_advance_payment_reports_refund_error(self):
        """A refund (ValidationError) fails the step with a clean message, no traceback."""
        order = self.pipeline.order_id
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True), \
            patch.object(type(order), '_integration_apply_external_payments',
                         side_effect=ValidationError('REFUND TRANSACTION DETECTED')):
            result, message = order._integration_apply_advance_payment()

        self.assertFalse(result)
        self.assertIn('REFUND TRANSACTION DETECTED', message)

    def test_advance_payment_reports_failed_transaction(self):
        """A silently-failed transaction must fail the step, not pass it."""
        order = self.pipeline.order_id
        self.env['external.order.transaction'].create({
            'erp_order_id': order.id,
            'external_status': 'success',  # -> is_ecommerce_ok
            'internal_status': 'failed',
            'internal_info': 'boom',
        })
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True):
            result, message = order._integration_apply_advance_payment()

        self.assertFalse(result)
        self.assertIn('boom', message)

    def test_advance_payment_success(self):
        """No refund and no failed transaction -> step succeeds."""
        order = self.pipeline.order_id
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True), \
                patch.object(type(order), 'amount_residual', new_callable=PropertyMock,
                             return_value=0.0, create=True), \
                patch('odoo.addons.integration.models.sale_order.is_sale_advance_payment_installed',
                      return_value=True):
            result, message = order._integration_apply_advance_payment()

        self.assertTrue(result)
        self.assertIn('applied', message)

    def test_advance_payment_fails_when_module_missing_and_nothing_applied(self):
        """No real transaction covered the order and the OCA module isn't installed ->
        we can't tell whether anything is still due, so the step must fail loudly
        instead of silently reporting success (this is what let a forced-draft
        'apply_advance_payment' step complete as 'done' with no payment registered)."""
        order = self.pipeline.order_id
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True), \
                patch('odoo.addons.integration.models.sale_order.is_sale_advance_payment_installed',
                      return_value=False):
            result, message = order._integration_apply_advance_payment()

        self.assertFalse(result)
        self.assertIn('not installed', message)

    def test_advance_payment_noop_without_apply_external_payments_setting(self):
        """The real-transaction path (_integration_apply_external_payments) ignores any
        transaction data unless 'Auto-Apply Payments from E-Commerce System' is enabled --
        the manual fallback for this case lives one level up, in
        _integration_apply_advance_payment (see test_advance_payment_falls_back_*)."""
        order = self.pipeline.order_id
        txn = self.env['external.order.transaction'].create({
            'erp_order_id': order.id,
            'external_status': 'success',
        })
        fake_integration = Mock(apply_external_payments=False)
        with patch.object(type(order), 'integration_id', new_callable=PropertyMock,
                          return_value=fake_integration), \
                patch.object(type(txn), 'validate') as validate:
            order._integration_apply_external_payments(as_advance=True)

        validate.assert_not_called()

    def test_advance_payment_validates_with_advance_context_when_enabled(self):
        """With the setting enabled and real transaction data present, the advance step
        routes the transaction through validate() with the advance-payment context."""
        order = self.pipeline.order_id
        txn = self.env['external.order.transaction'].create({
            'erp_order_id': order.id,
            'external_status': 'success',
        })
        fake_integration = Mock(apply_external_payments=True)
        with patch.object(type(order), 'integration_id', new_callable=PropertyMock,
                          return_value=fake_integration), \
                patch.object(type(txn), 'validate', return_value=(True, [])) as validate:
            order._integration_apply_external_payments(as_advance=True)

        validate.assert_called_once()

    def test_advance_payment_falls_back_to_manual_payment_when_uncovered(self):
        """No real transaction covered the order -> book a manual advance payment for the
        residual, same fallback the register_payment step uses for invoices with no
        transaction data. Keeps both payment steps equally predictable."""
        order = self.pipeline.order_id
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True), \
                patch.object(type(order), 'amount_residual', new_callable=PropertyMock,
                             return_value=50.0, create=True), \
                patch('odoo.addons.integration.models.sale_order.is_sale_advance_payment_installed',
                      return_value=True), \
                patch.object(type(order), '_integration_register_advance_payment_fallback') as fallback:
            result, message = order._integration_apply_advance_payment()

        fallback.assert_called_once()
        self.assertTrue(result)

    def test_advance_payment_skips_fallback_when_already_covered(self):
        """No residual left (already paid/covered by a real payment) -> no manual fallback."""
        order = self.pipeline.order_id
        with patch.object(type(order), 'order_is_confirmed', new_callable=PropertyMock,
                          return_value=True), \
                patch.object(type(order), 'amount_residual', new_callable=PropertyMock,
                             return_value=0.0, create=True), \
                patch('odoo.addons.integration.models.sale_order.is_sale_advance_payment_installed',
                      return_value=True), \
                patch.object(type(order), '_integration_register_advance_payment_fallback') as fallback:
            result, message = order._integration_apply_advance_payment()

        fallback.assert_not_called()
        self.assertTrue(result)

    def test_apply_advance_payment_onchange_unchecks_register_payment(self):
        """Checking Register Advance Payment gives instant feedback by unchecking Register Payment."""
        rec = self.env['integration.sale.order.sub.status.external'].new({
            'register_payment': True,
        })
        rec.apply_advance_payment = True
        rec._onchange_apply_advance_payment()
        self.assertFalse(rec.register_payment)

    def test_register_payment_onchange_unchecks_apply_advance_payment(self):
        """Checking Register Payment gives instant feedback by unchecking Register Advance Payment."""
        rec = self.env['integration.sale.order.sub.status.external'].new({
            'apply_advance_payment': True,
        })
        rec.register_payment = True
        rec._onchange_register_payment()
        self.assertFalse(rec.apply_advance_payment)

    def test_advance_and_register_payment_mutually_exclusive(self):
        """Enabling both payment steps at once is rejected."""
        rec = self.env['integration.sale.order.sub.status.external'].new({
            'apply_advance_payment': True,
            'register_payment': True,
        })
        with self.assertRaises(ValidationError):
            rec._check_single_payment_step()

    # --- external.order.transaction.validate routing --------------------------

    def test_validate_routes_to_advance_only_with_context(self):
        """The advance step's context drives advance routing; nothing else does."""
        txn = self.env['external.order.transaction'].create({
            'erp_order_id': self.pipeline.order_id.id,
        })

        # With the advance context -> advance path, standard `_validate` untouched.
        with patch.object(type(txn), '_validate_as_advance_payment',
                          return_value=(True, [])) as advance, \
                patch.object(type(txn), '_validate', return_value=(True, [])) as standard:
            txn.with_context(integration_apply_advance_payment=True).validate()
            advance.assert_called_once()
            standard.assert_not_called()

        # Without it -> standard `_validate`, advance path untouched.
        with patch.object(type(txn), '_validate_as_advance_payment') as advance, \
                patch.object(type(txn), '_validate', return_value=(True, [])) as standard:
            txn.validate()
            advance.assert_not_called()
            standard.assert_called_once()

    # --- pipeline.status lifecycle --------------------------------------------

    def test_status_empty_pipeline_is_skipped(self):
        """A pipeline with no task lines reads as 'skipped' (nothing to run)."""
        self.assertEqual(self.pipeline.status, 'skipped')

    def test_status_failed_takes_precedence_over_done(self):
        self._add_task('validate_order', 'done')
        self._add_task('create_invoice', 'failed')
        self.assertEqual(self.pipeline.status, 'failed')

    def test_status_running_while_pending(self):
        self._add_task('validate_order', 'done')
        self._add_task('create_invoice', 'todo')
        self.assertEqual(self.pipeline.status, 'running')

    # --- _execute_order_method success ----------------------------------------

    def test_execute_order_method_passes_result_through(self):
        """On success the (result, message) tuple is returned and traceback cleared."""
        task = self._add_task('validate_order', 'todo')
        task.pipeline_id.error_traceback = 'stale'

        with patch.object(type(task), '_retrieve_current_order_method',
                          return_value=lambda: (True, 'ok')):
            result, message = task._execute_order_method()

        self.assertTrue(result)
        self.assertEqual(message, 'ok')
        self.assertFalse(task.pipeline_id.error_traceback)

    # --- action_skip_step -----------------------------------------------------

    def test_action_skip_step_requires_failed_state(self):
        task = self._add_task('validate_order', 'done')
        with self.assertRaises(UserError):
            task.action_skip_step()

    def test_action_skip_step_blocked_by_enabled_dependent(self):
        failed = self._add_task('create_invoice', 'failed')
        self._add_task('validate_invoice', 'todo')  # enabled dependent
        with self.assertRaises(UserError):
            failed.action_skip_step()

    def test_action_skip_step_skips_and_resumes(self):
        failed = self._add_task('create_invoice', 'failed')
        self._add_task('validate_invoice', 'skip')  # dependent disabled -> skip allowed
        with patch.object(type(failed), 'call_next_step_job') as resume:
            failed.action_skip_step()
            resume.assert_called_once()
        self.assertTrue(failed.is_skipped)

    # --- input-file actions degrade gracefully without a pipeline -------------

    def test_action_open_order_without_pipeline(self):
        """Opening the order must not require a pipeline (re-imported files have none)."""
        input_file = self.env['sale.integration.input.file'].new({
            'order_id': self.pipeline.order_id.id,
        })
        action = input_file.action_open_order()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn(str(self.pipeline.order_id.id), action['url'])

    def test_action_open_automation_statuses_without_pipeline_opens_unfiltered(self):
        """No pipeline -> open the full statuses list (no domain), not a singleton crash."""
        order = self.env['sale.order'].create({
            'partner_id': self.env['res.partner'].create({'name': 'No Pipeline'}).id,
        })
        input_file = self.env['sale.integration.input.file'].new({'order_id': order.id})
        statuses_action = self.env.ref(
            'integration.integration_sale_order_sub_status_external_auto_workflow_action'
        )
        action = input_file.action_open_automation_statuses()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'], f'/odoo/{statuses_action.path}')
