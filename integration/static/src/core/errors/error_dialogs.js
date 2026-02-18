import { registry } from "@web/core/registry";
import { WarningDialog } from "@web/core/errors/error_dialogs";


registry
    .category("error_dialogs")
    .add("odoo.addons.integration.exceptions.ApiImportError", WarningDialog);
