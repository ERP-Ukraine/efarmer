import { describe, expect, test } from "@odoo/hoot";
import { click, contains, defineMailModels } from "@mail/../tests/mail_test_helpers";
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

const TOGGLE = ".o-integration-IntegrationStatusMenu-class button";

function prepareMenu(integrations) {
    patchWithCleanup(user, { hasGroup: async () => true });
    onRpc("sale.integration", "get_status_menu_data", () => integrations);
    const calls = [];
    mockService("action", {
        doAction(action, options) {
            calls.push({ action, options });
        },
    });
    return calls;
}

test("the status menu without active stores explains it and links to the store list", async () => {
    const calls = prepareMenu([]);

    await mountWithCleanup(IntegrationStatusMenu);
    await click(TOGGLE);

    await contains(".o-integration-IntegrationStatusMenu-empty");
    await contains(".o-integration-IntegrationStatusMenu-empty", { text: "No active stores" });
    await contains(".o_IntegrationStatusMenu_item", { count: 0 });

    await click(".o-integration-IntegrationStatusMenu-empty-action");
    expect(calls).toHaveLength(1);
    expect(calls[0].action).toBe("integration.integrations_list_action");
    expect(calls[0].options).toEqual({ clearBreadcrumbs: true });
});

test("the status menu with an active store keeps the store card and shows no empty state", async () => {
    prepareMenu([
        {
            id: 1,
            name: "Main store",
            type_api: "shopify",
            orders_count: 3,
            unprocessed_orders_count: 0,
            products_count: 5,
            failed_jobs_count: 0,
            missing_mappings_count: 0,
            missing_mappings_by_type: [],
        },
    ]);

    await mountWithCleanup(IntegrationStatusMenu);
    await click(TOGGLE);

    await contains(".o_IntegrationStatusMenu_item", { text: "Main store" });
    await contains(".o-integration-IntegrationStatusMenu-empty", { count: 0 });
});
