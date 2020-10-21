odoo.define('efarmer_sale_workflow.InventoryReportListController', function (require) {
"use strict";

var InventoryReportListController = require('stock.InventoryReportListController');

InventoryReportListController.include({
    /** [OVERRIDDEN]
     *
     * [REF] Move context creation into _get_context_for_action method.
     */
    _onOpenWizard: function () {
        this.do_action({
            res_model: 'stock.quantity.history',
            views: [[false, 'form']],
            target: 'new',
            type: 'ir.actions.act_window',
            context: this._get_context_for_action(),
        });
    },
    _get_context_for_action: function () {
        var state = this.model.get(this.handle, {raw: true});
        var stateContext = state.getContext();
        var context = {
            active_model: this.modelName,
        };
        if (stateContext.default_product_id) {
            context.product_id = stateContext.default_product_id;
        } else if (stateContext.product_tmpl_id) {
            context.product_tmpl_id = stateContext.product_tmpl_id;
        }

        // [ADD] Keep 'inventorization_location_id' in the context.
        if (stateContext.inventorization_location_id) {
            context.inventorization_location_id = stateContext.inventorization_location_id;
        }

        return context;
    },
});

});
