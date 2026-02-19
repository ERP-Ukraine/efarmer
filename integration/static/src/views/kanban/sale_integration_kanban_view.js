/** @odoo-module **/

import { registry } from '@web/core/registry';
import { kanbanView } from '@web/views/kanban/kanban_view';
import { KanbanRenderer } from '@web/views/kanban/kanban_renderer';
import { useEffect } from '@odoo/owl';
import { useService } from "@web/core/utils/hooks";


class SaleIntegrationKanbanRenderer extends KanbanRenderer {
    setup() {
        super.setup();

        this.actionService = useService("action");

        useEffect(() => {
            const handleClick = async (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                this.actionService.doAction('integration.integration_configuration_action');
            };

            const rootElement = this.rootRef.el;
            if (rootElement) {
                const guideLink = rootElement.querySelector('a.integration-getting-started-guide');
                if (guideLink) {
                    guideLink.addEventListener('click', handleClick);
                }
            }

            return () => {
                if (rootElement) {
                    const guideLink = rootElement.querySelector('a.integration-getting-started-guide');
                    if (guideLink) {
                        guideLink.removeEventListener('click', handleClick);
                    }
                }
            };
        }, () => [this.rootRef]);
    }
}

registry.category('views').add('sale_integration_kanban_view', {
    ...kanbanView,
    Renderer: SaleIntegrationKanbanRenderer,
    buttonTemplate: 'integration.SaleIntegrationKanbanView.Buttons',
});
