/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { AttachmentList } from "@mail/core/common/attachment_list";

patch(AttachmentList.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.notification = useService("notification");
    },

    canPrint() {
        return session.dpc_company_enabled && session.dpc_user_enabled;
    },

    async onClickPrint(attachment) {
        try {
            const [message] = await this.orm.call(
                "ir.attachment",
                "dpc_print",
                [[attachment.id]]
            );

            this.notification.add(message, {
                type: "success",
            });

        } catch (err) {
            const fileName = attachment.name || "Document";

            this.notification.add(`Failed to print "${fileName}". Please make sure that printers are
                selected at the user or company level.`, {
                type: "danger",
            });
        }
    },
});
