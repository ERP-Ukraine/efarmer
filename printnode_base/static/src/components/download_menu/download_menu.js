/** @odoo-module **/

import { AccountMoveListController } from "@account/views/account_move_list/account_move_list_controller";
import { FileUploadListController } from "@account/views/file_upload_list/file_upload_list_controller";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { session } from "@web/session";
import { ListController } from "@web/views/list/list_controller";


class DownloadActionMenus extends ActionMenus {

  async setup() {
    await super.setup(...arguments);
    this.dpcEnabled = session.dpc_user_enabled;
  }

  get downloadItems() {
    if (!this.dpcEnabled) {
      return [];
    }

    const printActions = this.props.items.print || [];
    return printActions.map((action) => ({
      action: { ...action, download_only: true },
      description: action.name,
      key: action.id,
    }));
  }

  async executeAction(action) {
    if (this.dpcEnabled) {
      // Add additional option to avoid printing
      this.props.context.download_only = action.download_only === true;
    }

    // Call parent
    return super.executeAction(...arguments);
  }
}

// sale.order tree view has custom controller, so we need to override it as well
FileUploadListController.components.ActionMenus = DownloadActionMenus;

ListController.components.ActionMenus = DownloadActionMenus;

// account.move tree view has custom controller, so we need to override it as well
AccountMoveListController.components.ActionMenus = DownloadActionMenus;
