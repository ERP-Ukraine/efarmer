import { describe, expect, test } from "@odoo/hoot";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";

import { IntegrationStatusMenu } from "@integration/components/status_menu/status_menu";

describe.current.tags("desktop");

// The mail services of the web client start together with the systray and need their models
defineMailModels();

test("every status menu link starts the navigation from scratch", async () => {
    patchWithCleanup(user, { hasGroup: async () => true });
    onRpc("sale.integration", "get_status_menu_data", () => []);
    onRpc("sale.integration", "get_failed_jobs_action", () => ({
        type: "ir.actions.act_window",
        name: "Failed Jobs",
        res_model: "queue.job",
        views: [[false, "list"]],
    }));
    onRpc("integration.product.public.category.mapping", "fields_get", () => ({}));

    const calls = [];
    mockService("action", {
        doAction(action, options) {
            calls.push({ action, options });
        },
    });

    const menu = await mountWithCleanup(IntegrationStatusMenu);

    await menu.openIntegration(1);
    await menu.openOrders(1);
    await menu.openUnprocessedOrders(1);
    await menu.openProducts(1);
    await menu.openFailedJobs(1);
    await menu.openMissingMappings(1, "integration.product.public.category.mapping");

    expect(calls.map(({ action }) => action.name)).toEqual([
        "Integration",
        "Orders",
        "Unprocessed Orders",
        "Products",
        "Failed Jobs",
        "Missing Mappings",
    ]);
    for (const { options } of calls) {
        expect(options).toEqual({ clearBreadcrumbs: true });
    }
});
