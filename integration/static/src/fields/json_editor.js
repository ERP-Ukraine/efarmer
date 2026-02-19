/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { registry } from '@web/core/registry';
import { AceField } from '@web/views/fields/ace/ace_field';

export class JsonEditorField extends AceField {
    static template = 'integration.JsonEditorField';
    static props = {
        ...AceField.props,
        maxLines: { type: Number, optional: true },
    };

    static defaultProps = {
        ...AceField.defaultProps,
        mode: 'javascript',
    };

    get maxLines() {
        // Render all lines for browser search to work
        return this.props.maxLines || Infinity;
    }
}

export const jsonEditorField = {
    component: JsonEditorField,
    displayName: _t('JSON Editor'),
    supportedOptions: [
        {
            label: _t('Max Lines'),
            name: 'maxLines',
            type: 'number',
        },
    ],
    supportedTypes: ['text'],
    extractProps: ({ options }) => ({
        maxLines: options.maxLines,
    }),
};

registry.category('fields').add('json_editor', jsonEditorField);
