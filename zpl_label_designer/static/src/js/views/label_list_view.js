/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';
import viewRegistry from 'web.view_registry';
import rpc from 'web.rpc';

const LabelListController = ListController.extend({
  init: function () {
    this._super(...arguments);

    // Load URL from server
    rpc.query({
      model: 'zld.label',
      method: 'get_label_designer_url',
    }).then((url) => {
      this.designerURL = url;
    });
  },

  _onCreateRecord: function (ev) {
    ev.preventDefault();
    window.open(this.designerURL, '_blank');
  },
});

const LabelListView = ListView.extend({
  config: _.extend({}, ListView.prototype.config, {
    Controller: LabelListController,
  }),
});

viewRegistry.add('zld_label_list_view', LabelListView);

export default LabelListView;
