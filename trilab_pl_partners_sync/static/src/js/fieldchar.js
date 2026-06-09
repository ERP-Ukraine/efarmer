/** @odoo-module **/

import {
    PartnerAutoCompleteCharField,
    partnerAutoCompleteCharField,
} from "@partner_autocomplete/js/partner_autocomplete_fieldchar"
import { registry } from "@web/core/registry"
import { _t } from "@web/core/l10n/translation"
import { loadJS } from "@web/core/assets"

import { trilabUsePartnerAutocomplete } from "@trilab_pl_partners_sync/js/autocomplete_core"

export class TrilabPartnerAutoCompleteCharField extends PartnerAutoCompleteCharField {
    setup() {
        super.setup()
        this.trilabPartnerAutocomplete = trilabUsePartnerAutocomplete()
    }

    get sources() {
        let self = this
        return super.sources.concat({
            options: async (request, shouldSearchWorldWide) => {
                // Lazyload jsvat only if the component is being used.
                await loadJS("/partner_autocomplete/static/lib/jsvat.js")
                if (request && (await self.trilabPartnerAutocomplete.isPlVAT(request))) {
                    const suggestions = await self.trilabPartnerAutocomplete.gusAutocomplete(request)
                    suggestions.forEach(suggestion => {
                        suggestion.classList = "partner_autocomplete_dropdown_char gus"
                    })
                    return suggestions
                } else {
                    return []
                }
            },
            optionTemplate: "trilab_pl_partners_sync.CharFieldDropdownOption",
            placeholder: _t("Searching GUS..."),
        })
    }

    async onSelect(option) {
        if (option.x_pl_gus_update_date) {
            // Checks that it is GUS autocomplete option
            let data = await this.trilabPartnerAutocomplete.getCreateData(Object.getPrototypeOf(option))
            data = data.company

            data.is_company = true

            let fieldsToRemove = ["logo", "label", "description", "classList"]

            // Some fields are unnecessary in res.company
            if (this.props.record.resModel === "res.company") {
                fieldsToRemove.concat(["comment", "child_ids", "additional_info"])
            }

            fieldsToRemove.forEach(field => {
                delete data[field]
            })

            // Format the many2one fields
            const many2oneFields = ["country_id", "state_id"]
            many2oneFields.forEach(field => {
                if (data[field]) {
                    data[field] = [data[field].id, data[field].display_name]
                }
            })
            this.props.record.update(data)
        } else {
            return super.onSelect(option)
        }
    }
}

export const trilabPartnerAutoCompleteCharField = {
    ...partnerAutoCompleteCharField,
    component: TrilabPartnerAutoCompleteCharField,
}

registry.category("fields").add("field_partner_autocomplete", trilabPartnerAutoCompleteCharField, { force: true })
