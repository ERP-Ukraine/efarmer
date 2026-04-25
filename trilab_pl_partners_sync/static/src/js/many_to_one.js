/** @odoo-module **/

import { PartnerMany2XAutocomplete } from "@partner_autocomplete/js/partner_autocomplete_many2one"
import { trilabUsePartnerAutocomplete } from "@trilab_pl_partners_sync/js/autocomplete_core"
import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field"
import { registry } from "@web/core/registry"
import { _t } from "@web/core/l10n/translation"
import { loadJS } from "@web/core/assets"

export class TrilabPartnerMany2XAutocomplete extends PartnerMany2XAutocomplete {
    setup() {
        super.setup()
        this.partnerAutocomplete = trilabUsePartnerAutocomplete()
    }

    get sources() {
        const sources = super.sources

        let self = this

        return sources.concat({
            options: async (request, shouldSearchWorldWide) => {
                // Lazyload jsvat only if the component is being used.
                await loadJS("/partner_autocomplete/static/lib/jsvat.js")
                if (await self.partnerAutocomplete.isPlVAT(request)) {
                    const suggestions = await self.partnerAutocomplete.gusAutocomplete(request)
                    suggestions.forEach(suggestion => {
                        suggestion.classList = "partner_autocomplete_dropdown_many2one gus"
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
        if (!!option.x_pl_gus_update_date) {
            // Checks that it is GUS autocomplete option
            const data = await this.partnerAutocomplete.getCreateData(Object.getPrototypeOf(option))
            let context = {
                default_is_company: true,
            }

            for (const [key, val] of Object.entries(data.company)) {
                context["default_" + key] = val && val.id ? val.id : val
            }

            return this.openMany2X({ context })
        } else {
            return super.onSelect(option)
        }
    }
}

export class TrilabPartnerAutoCompleteMany2one extends Many2OneField {}

TrilabPartnerAutoCompleteMany2one.components = {
    ...Many2OneField.components,
    Many2XAutocomplete: TrilabPartnerMany2XAutocomplete,
}

export const trilabPartnerAutoCompleteMany2one = {
    ...many2OneField,
    component: TrilabPartnerAutoCompleteMany2one,
}

registry.category("fields").add("res_partner_many2one", trilabPartnerAutoCompleteMany2one, { force: true })
