/** @odoo-module **/

import { KeepLast } from "@web/core/utils/concurrency"
import { useService } from "@web/core/utils/hooks"
import { usePartnerAutocomplete } from "@partner_autocomplete/js/partner_autocomplete_core"
import { parseDate } from "@web/core/l10n/dates"
import { _t } from "@web/core/l10n/translation"
import { loadJS } from "@web/core/assets"

/**
 * Extend autocomplete of companies to use GUS
 */
export function trilabUsePartnerAutocomplete() {
    const partner_autocomplete = usePartnerAutocomplete()

    const keepLastGus = new KeepLast()

    const orm = useService("orm")
    const notification = useService("notification")

    function sanitizeVAT(request) {
        let response = ""

        if (!!request) {
            let parts = request.match(/^(?<c>[A-Z]{2})?(?<v>.*)/i)

            if (!!parts.groups.c) {
                response = parts.groups.c
            } else {
            }
            if (!!parts.groups.v) {
                response = response + parts.groups.v.replace(/\D/g, "")
            }
        }

        return response
    }

    async function isVATNumber(value) {
        // Lazyload jsvat only if the component is being used.
        await loadJS("/partner_autocomplete/static/lib/jsvat.js")

        // checkVATNumber is defined in library jsvat.
        // It validates that the input has a valid VAT number format
        return checkVATNumber(sanitizeVAT(value))
    }

    async function isPlVAT(request) {
        let vat = sanitizeVAT(request)
        if (vat.match(/^\d{10}$/)) {
            vat = `PL${vat}`
        }
        const isVAT = await isVATNumber(vat)
        return vat.startsWith("PL") && (await isVATNumber(vat))
    }

    async function autocomplete(value, isVAT = false) {
        // noinspection JSUnresolvedReference
        return partner_autocomplete.autocomplete(value, isVAT)
    }

    async function gusAutocomplete(value) {
        value = value.trim()

        const is_vat = await isPlVAT(value)
        let finalSuggestions = []
        let suggestions = []

        if (is_vat) {
            try {
                suggestions = await getGUSSuggestions(value)
            } catch (err) {
                notification.add(err.data.message || err, {
                    title: _t("GUS autocomplete error"),
                    type: "warning",
                })
            }

            finalSuggestions = suggestions.filter(suggestion => {
                return !suggestion.ignored
            })

            finalSuggestions.forEach(suggestion => {
                delete suggestion.ignored
            })
        }

        return finalSuggestions
    }

    function getCreateData(company) {
        if (!!company.x_pl_gus_update_date) {
            // we do not need to enrich data from GUS

            const dateFields = ["x_pl_gus_update_date", "x_pl_gus_inactive_date"]
            dateFields.forEach(field => {
                if (!!company[field]) {
                    company[field] = parseDate(company[field])
                }
            })

            return new Promise(resolve => {
                if (company.error) {
                    // noinspection JSUnresolvedReference
                    notification.add(company.error_message)
                }

                resolve({
                    company,
                })
            })
        } else {
            // noinspection JSUnresolvedReference
            return partner_autocomplete.getCreateData(company)
        }
    }

    async function getGUSSuggestions(value) {
        const prom = orm.silent.call("res.partner", "x_gus_autocomplete", [value])

        const suggestions = await keepLastGus.add(prom)

        await Promise.all(
            suggestions.map(async suggestion => {
                suggestion.logo = ""
                suggestion.label = suggestion.name
                if (suggestion.vat) suggestion.description = suggestion.vat
                else if (suggestion.website) suggestion.description = suggestion.website

                if (suggestion.country_id && suggestion.country_id.display_name) {
                    if (suggestion.description) suggestion.description += ` (${suggestion.country_id.display_name})`
                    else suggestion.description += suggestion.country_id.display_name
                }

                return suggestion
            })
        )

        return suggestions
    }

    return { autocomplete, getCreateData, gusAutocomplete, isVATNumber, isPlVAT }
}
