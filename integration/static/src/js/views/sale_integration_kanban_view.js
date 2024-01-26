/** @odoo-module **/

import KanbanView from 'web.KanbanView';
import KanbanController from 'web.KanbanController';
import viewRegistry from 'web.view_registry';

const SaleIntegrationKanbanController = KanbanController.extend({
    buttons_template: 'SaleIntegrationKanbanView.buttons',
});

const SaleIntegrationKanbanView = KanbanView.extend({
  config: _.extend({}, KanbanView.prototype.config, {
    Controller: SaleIntegrationKanbanController,
  }),
});

viewRegistry.add('sale_integration_kanban_view', SaleIntegrationKanbanView);

export default SaleIntegrationKanbanView;
