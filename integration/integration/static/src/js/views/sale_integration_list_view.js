/** @odoo-module **/

import ListView from 'web.ListView';
import ListController from 'web.ListController';
import viewRegistry from 'web.view_registry';

const SaleIntegrationListController = ListController.extend({
    buttons_template: 'SaleIntegrationListView.buttons',
});

const SaleIntegrationListView = ListView.extend({
  config: _.extend({}, ListView.prototype.config, {
    Controller: SaleIntegrationListController,
  }),
});

viewRegistry.add('sale_integration_list_view', SaleIntegrationListView);

export default SaleIntegrationListView;
