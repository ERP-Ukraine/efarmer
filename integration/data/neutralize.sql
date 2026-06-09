-- deactivating important settings on the integration
UPDATE  sale_integration
SET     export_inventory_job_enabled = FALSE,
        export_template_job_enabled = FALSE,
        export_tracking_job_enabled = FALSE,
        export_sale_order_status_job_enabled = FALSE,
        run_action_on_cancel_so = FALSE,
        run_action_on_shipping_so = FALSE,
        run_action_on_so_invoice_status = FALSE;

-- removing webhooks on integrations
TRUNCATE TABLE integration_webhook_line;

-- deactivation of integration-related crones
UPDATE  ir_cron
SET     active = FALSE
WHERE   id IN (
        SELECT  ir_cron.id
        FROM    ir_cron
        JOIN    ir_act_server
                ON  ir_cron.ir_actions_server_id = ir_act_server.id
        JOIN    ir_model
                ON  ir_act_server.model_id = ir_model.id
        WHERE   ir_model.model = 'sale.integration'
);

-- deactivating integrations
UPDATE  sale_integration
SET     state = 'draft';
