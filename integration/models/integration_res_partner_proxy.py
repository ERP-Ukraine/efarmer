# See LICENSE file for full copyright and licensing details.

import logging

from typing import Any, Dict, List, Tuple

from odoo import api, fields, models, tools, _
from odoo.modules.registry import Registry
from odoo.tools import escape_psql

from .sale_integration import SEARCH_CUSTOMER_FIELDS


_logger = logging.getLogger(__name__)

PROXY_FIELDS = [
    'pricelist_id',
    'person_name',
    'email',
    'language',
    'person_id_number',
    'company_name',
    'company_reg_number',
    'street',
    'street2',
    'city',
    'country',
    'country_code',
    'state',
    'state_code',
    'phone',
    'phone_sanitized',
    'other',
    'zip',
]

ADDRESS_MATCH_SIMPLE_FIELDS = [
    'street',
    'street2',
    'city',
    'zip',
    'email',
    'phone',
]

ADDRESS_MATCH_COMPLEX_FIELDS = [
    'country_id',
    'state_id',
]

PROXY_TYPES = [
    'customer',
    'shipping_address',
    'billing_address',
    'other_address',
]

MANDATORY_PARTNER_SEARCH_CRITERIA = [
    ('parent_id', '='),
    ('is_company', '='),
    ('type', '='),
    ('company_id', 'in'),
]

MANDATORY_COMPANY_SEARCH_CRITERIA = [
    ('name', '=ilike'),
    ('is_company', '='),
    ('company_id', 'in'),
]

MANDATORY_ADDRESS_SEARCH_CRITERIA = [
    ('name', '=ilike'),
    ('parent_id', '='),
    ('company_id', 'in'),
]


class IntegrationResPartnerProxy(models.TransientModel):
    _name = 'integration.res.partner.proxy'
    _description = 'Integration Res Partner Proxy'

    # Fields that should be ignored when comparing addresses for uniqueness
    ADDRESS_UNIQUENESS_IGNORED_FIELDS = [
        'parent_id',
        'type',
        'external_company_name',
        'category_id',
        'lang',
        'active',
        'create_date',
        'write_date',
    ]

    type = fields.Selection(
        selection=[
            ('customer', 'Customer'),
            ('shipping_address', 'Shipping Address'),
            ('billing_address', 'Billing Address'),
            ('other_address', 'Other Address'),
        ],
        string='Proxy Type',
        required=True,
    )

    factory_id = fields.Many2one(
        string='Factory',
        comodel_name='integration.res.partner.factory',
        help=(
            'Factory associated with this proxy.'
        ),
    )

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        related='factory_id.integration_id',
        help=(
            'The Sale integration associated with this proxy.'
        ),
    )

    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        related='integration_id.company_id',
        store=True,
        readonly=True,
        help='Company context inherited from the integration.',
    )

    partner_id = fields.Many2one(
        string='Partner',
        comodel_name='res.partner',
        help=(
            'Technical field for storing the current parent.'
        ),
    )

    company_partner_id = fields.Many2one(
        string='Company Contact',
        comodel_name='res.partner',
        help=(
            'Technical field for storing the current company.'
        ),
    )

    is_vat_verified = fields.Boolean(string='Is Verified VAT', default=True)

    # Fields for customer
    external_id = fields.Char(string='External ID')
    pricelist_id = fields.Char(string='Pricelist ID')
    person_name = fields.Char(string='Person Name', default='')
    email = fields.Char(string='Email', default='')
    phone = fields.Char(string='Phone', default='')
    phone_sanitized = fields.Char(string='Phone Sanitized', default='')
    language = fields.Char(string='Language')

    # Fields for address
    person_id_number = fields.Char(string='Person ID Number')
    company_name = fields.Char(string='Company Name')
    company_reg_number = fields.Char(string='Company Reg Number')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    country = fields.Char(string='Country')
    country_code = fields.Char(string='Country Code')
    state = fields.Char(string='State')
    state_code = fields.Char(string='State Code')
    other = fields.Char(string='Other')
    zip = fields.Char(string='Zip')

    # ================================
    # I. TECHNICAL / UTILITY METHODS
    # ================================

    def get_proxy_fields(self) -> List:
        return PROXY_FIELDS

    def get_address_match_simple_fields(self) -> List:
        """
        Returns list of simple fields that are used for address matching.
        In most cases it is important to additionally add relative fields to get a unique match.
        (e.g. countr_id, state_id, etc.)
        """
        return ADDRESS_MATCH_SIMPLE_FIELDS

    def get_address_match_complex_fields(self) -> List:
        """
        Returns list of complex fields that are used for address matching.
        """
        return ADDRESS_MATCH_COMPLEX_FIELDS

    def get_address_match_fields(self) -> List:
        """
        Returns list of fields that are used for address matching.
        """
        return ADDRESS_MATCH_SIMPLE_FIELDS + ADDRESS_MATCH_COMPLEX_FIELDS

    def create_proxy(self, type_: str, integration_id: int, factory_id: int, data: dict) -> models.Model:
        """
        Create a proxy instance with cleaned values based on the provided data.
        Args:
            type_: The type of the proxy.
            integration_id: The ID of the integration associated with the proxy.
            factory_id: The ID of the factory associated with the proxy.
            data : The input data dictionary.
        Returns:
            Recordset: The created proxy instance.
        """
        if not isinstance(data, dict):
            raise ValueError(f'Data should be a dictionary; "{type(data)}" specified.')
        if type_ not in PROXY_TYPES:
            raise ValueError(f'Invalid proxy type: {type_}')

        ctx = dict(self.env.context)
        if type_ == 'customer':
            ctx['type_'] = 'customer'

        proxy_values = self.with_context(**ctx)._prepare_proxy_values(integration_id, data)

        if not proxy_values or not self._validate_required_values(proxy_values):
            return self.env['integration.res.partner.proxy']

        proxy_values['type'] = type_
        proxy_values['factory_id'] = factory_id

        vals = self._prepare_special_values(proxy_values, data)

        proxy = self.create(vals)

        return proxy

    def _prepare_proxy_values(self, integration_id: int, data: dict) -> Dict:
        """Prepare proxy values based on the provided data."""
        proxy_fields = self.get_proxy_fields()
        vals = {}

        for key, value in data.items():
            if key not in proxy_fields:
                continue

            # We skip empty values, but not `False`, because it is a valid value for Boolean fields.
            if value in ['', None, [], {}]:
                continue

            prepared_value = self._prepare_proxy_value(key, value)
            vals[key] = prepared_value

        # Separate method for extra pre-processing (emails, phones)
        if vals.get('email'):
            vals['email'] = tools.email_normalize(vals['email']) or vals['email'].lower()

        if vals.get('phone'):
            # Format phone number using Odoo's built-in formatter
            formatted_phone = self._proxy_phone_format(integration_id, vals['phone'], data)
            if formatted_phone:
                vals['phone_sanitized'] = formatted_phone

        return vals

    def _prepare_proxy_value(self, key: str, value: str) -> str:
        """Prepare individual proxy value."""
        if not isinstance(value, str):
            return value

        prepared_value = value.strip()

        return prepared_value

    def _validate_required_values(self, vals: dict) -> bool:
        """Check if vals contains required values."""
        return bool(vals.get('person_name', '') or vals.get('email', ''))

    def _prepare_special_values(self, vals: dict, data: dict) -> dict:
        """Process special fields that require additional handling."""
        if vals.get('type') == 'customer':
            vals['external_id'] = data.get('id', '').strip()

        return vals

    @api.model
    def _find_odoo_country(self) -> models.Model:
        """
        Find the corresponding Odoo country based on the provided data.
        """
        country = self.env['res.country']

        if self.country:
            country = country.from_external(self.integration_id, self.country)
        elif self.country_code:
            country = self.env['res.country'].search([
                ('code', '=ilike', self.country_code),
            ], limit=1)

        return country

    def _find_odoo_state(self, odoo_country: models.Model) -> models.Model:
        """
        Find the corresponding Odoo state based on the provided country.
        """
        state = self.env['res.country.state']

        if not state.search([('country_id', '=', odoo_country.id)]):
            return state

        if self.state:
            state = state.from_external(self.integration_id, self.state)
        elif self.state_code and odoo_country:
            state = state.search([
                ('country_id', '=', odoo_country.id),
                ('code', '=ilike', self.state_code),
            ], limit=1)

        return state

    def _get_integration_tag(self) -> models.Model:
        """
        Retrieve or create an integration tag for the current integration.
        """
        ResPartnerTag = self.env['res.partner.category']
        main_tag = self.env.ref('integration.main_integration_tag', raise_if_not_found=False)
        if not main_tag:
            raise ValueError(
                'Integration main tag "integration.main_integration_tag" is missing. Please install or restore it.'
            )

        tag = ResPartnerTag.search([
            ('name', '=', self.integration_id.name),
            ('parent_id', '=', main_tag.id),
        ])

        if not tag:
            tag = ResPartnerTag.sudo().create({
                'name': self.integration_id.name,
                'parent_id': main_tag.id,
            })

        return tag

    def _build_search_domain(self, search_criteria: List, values: Dict) -> List:
        """
        Build a search domain based on the provided search criteria and values.
        """
        domain = []

        for key, op in search_criteria:
            value = values.get(key, '')

            if not value:
                domain.append((key, 'in', ['', False]))
                continue

            # Escape ilike values
            if isinstance(value, str) and op == '=ilike':
                value = escape_psql(value)
                if not value:
                    continue

            # Special case: email → search in both email and email_normalized
            if key == 'email':
                domain.extend([
                    '|',
                    (key, op, value),
                    ('email_normalized', '=', value),
                ])
                continue

            # Special case: phone → search in both phone and phone_sanitized
            if key == 'phone':
                sanitized_value = values.get('phone_sanitized') or value
                domain.extend([
                    '|',
                    (key, op, value),
                    ('phone_sanitized', '=', sanitized_value),
                ])
                continue

            # Special case: company_id → add False value
            if key == 'company_id':
                if value:
                    domain.extend([(key, op, [value, False])])
                continue

            domain.append((key, op, value))

        return domain

    def _proxy_phone_format(self, integration_id: int, phone_number: str, data: Dict) -> str:
        """Format phone number using Odoo's built-in formatter."""
        integration = self.env['sale.integration'].browse(integration_id)
        country = self.env['res.country']

        if data.get('country'):
            country = country.from_external(integration, data['country'])
        elif data.get('country_code'):
            country = country.search([
                ('code', '=ilike', data['country_code']),
            ], limit=1)

        if not country:
            return phone_number

        # Use Odoo's phone formatting utility - E.164 format
        formatted = self._phone_format(
            number=phone_number,
            country=country,
        )

        return formatted or phone_number

    # ================================
    # II. MAIN BUSINESS LOGIC — CUSTOMER & PARTNER HANDLING
    # ================================

    @api.model
    def get_customer(self, raise_error: bool = True) -> models.Model:
        """
        Get the mapped customer.

        This method retrieves the customer partner that has been mapped
        by the user.

        Returns:
            models.Model: The retrieved customer partner instance.
        """
        partner = self.env['res.partner'].from_external(
            self.integration_id, self.external_id, raise_error,
        )
        self.partner_id = partner
        return partner

    @api.model
    def get_or_create_partner(self) -> models.Model:
        """
        Get or create a partner with priority to external mapping.

        Priority order:
        1. Try to use existing external mapping (if compatible)
        2. If skip_individual_contacts + company_name: return company partner
        3. Search for existing partner by domain
        4. Create new partner

        Returns:
            models.Model: The retrieved or created partner instance.
        """
        # Try to get compatible mapped partner
        partner = self._get_compatible_mapped_partner()
        if partner:
            self.partner_id = partner
            self._configure_partner(partner)
            return partner

        # Return for company-only mode
        if self.integration_id.skip_individual_contacts and self.company_name:
            self._log_partner_trace(
                'Company-only mode',
                f'skip_individual_contacts=True with company "{self.company_name}" '
                f'→ using company partner directly',
            )
            return self._get_or_create_company_partner()

        # If no mapped partner, search or create new one
        if not partner:
            partner = self._search_or_create_partner()

        # Apply final configurations
        self._configure_partner(partner)

        return partner

    def _get_compatible_mapped_partner(self) -> models.Model:
        """
        Get mapped partner only if it's compatible with current context.
        """
        if not self.external_id:
            return self.env['res.partner']

        mapped_partner = self.get_customer(False)
        if not mapped_partner:
            return self.env['res.partner']

        # Do not use inactive (archived) partners from mapping.
        if not mapped_partner.active:
            self._log_partner_trace(
                'Mapped partner archived',
                f'Mapped partner "{mapped_partner.display_name}" (ID: {mapped_partner.id}) '
                f'is archived → skipping mapping',
            )
            return self.env['res.partner']

        if self._is_mapping_compatible(mapped_partner):
            self._log_partner_trace(
                'Mapped partner found',
                f'Using mapped partner "{mapped_partner.display_name}" (ID: {mapped_partner.id}) '
                f'for external_id="{self.external_id}"',
            )
            return mapped_partner

        return self.env['res.partner']

    def _is_mapping_compatible(self, mapped_partner: models.Model) -> bool:
        """
        Check if mapped partner is compatible with current context.
        """
        # Do not use inactive (archived) partners from mapping.
        if mapped_partner and not mapped_partner.active:
            return False

        skip_individual = self.integration_id.skip_individual_contacts

        company = self.env['res.partner']
        if self.company_name:
            company = self._get_or_create_company_contact()

        # Check company context
        if mapped_partner.company_id and mapped_partner.company_id != self.company_id:
            self._log_partner_trace(
                'Mapped partner incompatible',
                f'Partner "{mapped_partner.display_name}" belongs to Odoo company '
                f'"{mapped_partner.company_id.name}" but integration uses '
                f'"{self.company_id.name}"',
            )
            return False

        # Mapped partner is company, but we're creating individual contact
        if mapped_partner.is_company and not skip_individual:
            self._log_partner_trace(
                'Mapped partner incompatible',
                f'Mapped partner "{mapped_partner.display_name}" is a company record '
                f'but integration is in individual contact mode '
                f'(skip_individual_contacts=False)',
            )
            return False

        # Mapped partner is contact, but we're in company-only mode
        if not mapped_partner.is_company and skip_individual:
            self._log_partner_trace(
                'Mapped partner incompatible',
                f'Mapped partner "{mapped_partner.display_name}" is an individual contact '
                f'but integration is in company-only mode '
                f'(skip_individual_contacts=True)',
            )
            return False

        # Mapped partner has no parent company, but current context expects one
        if company and not skip_individual and not mapped_partner.is_company and not mapped_partner.parent_id:
            self._log_partner_trace(
                'Mapped partner incompatible',
                f'Mapped partner "{mapped_partner.display_name}" has no parent company, '
                f'but expected "{company.display_name}"',
            )
            return False

        # Mapped partner has different parent company
        if mapped_partner.parent_id and company:
            if mapped_partner.parent_id != company:
                self._log_partner_trace(
                    'Mapped partner incompatible',
                    f'Mapped partner "{mapped_partner.display_name}" parent company is '
                    f'"{mapped_partner.parent_id.display_name}" but expected '
                    f'"{company.display_name}"',
                )
                return False

            # Mapped partner has parent company, but integration uses different company
            if mapped_partner.parent_id.company_id and mapped_partner.parent_id.company_id != self.company_id:
                self._log_partner_trace(
                    'Mapped partner incompatible',
                    f'Mapped partner "{mapped_partner.display_name}" parent company '
                    f'"{mapped_partner.parent_id.display_name}" belongs to Odoo company '
                    f'"{mapped_partner.parent_id.company_id.name}" but integration uses '
                    f'"{self.company_id.name}"',
                )
                return False

        # Mapped partner is different company than expected
        if skip_individual and mapped_partner.is_company and company:
            if mapped_partner != company:
                self._log_partner_trace(
                    'Mapped partner incompatible',
                    f'In company-only mode: mapped company is '
                    f'"{mapped_partner.display_name}" (ID: {mapped_partner.id}) '
                    f'but expected "{company.display_name}" (ID: {company.id})',
                )
                return False

            # Mapped partner has company, but integration uses different company
            if mapped_partner.company_id and mapped_partner.company_id != self.company_id:
                self._log_partner_trace(
                    'Mapped partner incompatible',
                    f'In company-only mode: mapped company "{mapped_partner.display_name}" '
                    f'belongs to Odoo company "{mapped_partner.company_id.name}" '
                    f'but integration uses "{self.company_id.name}"',
                )
                return False

        return True

    def _get_or_create_company_partner(self) -> models.Model:
        """
        Handle company-only partner creation/retrieval.
        """
        company = self._get_or_create_company_contact()

        # Apply final configurations
        self._configure_partner(company)

        return company

    def _search_or_create_partner(self) -> models.Model:
        """
        Search for existing partner or create new one.
        """
        partner_vals = self._prepare_partner_vals()
        domain = self._collect_partner_search_domain(partner_vals)

        partner = self.env['res.partner'].search(domain, order='create_date asc', limit=1)

        if partner:
            self._write_address_fields_if_empty(partner)
            self._log_partner_trace(
                'Contact found',
                f'Search domain: {domain}\n'
                f'→ Found: "{partner.display_name}" (ID: {partner.id})',
            )
        else:
            partner = self._create_partner(partner_vals)
            self._log_partner_trace(
                'Contact created',
                f'Search domain: {domain}\n'
                f'→ No match found, created: "{partner.display_name}" (ID: {partner.id})',
            )

        return partner

    def _configure_partner(self, partner: models.Model):
        """
        Apply final configuration to the partner.
        """
        self.partner_id = partner

        if not self.is_vat_verified and self.company_reg_number and not partner.is_company:
            self._log_message(
                partner,
                _('VAT validation was not completed'),
                _(
                    'VAT number "%s" could not be validated because the VIES service was '
                    'temporarily unavailable. Please verify it manually.'
                ) % self.company_reg_number,
            )

        # Set up external mapping
        if self.external_id:
            self._create_or_update_mapping()
            partner._link_external_partner(self.integration_id, self.external_id)

        # Set pricelist if enabled
        self._set_partner_pricelist(partner)

    def _set_partner_pricelist(self, partner: models.Model):
        """
        Set partner pricelist from external system if enabled.
        """
        if not (self.integration_id.pricelist_integration and self.pricelist_id):
            return

        pricelist = self.env['product.pricelist'].from_external(
            self.integration_id,
            self.pricelist_id,
            raise_error=False,
        )

        if pricelist:
            # If partner has a parent, apply pricelist to parent (company)
            partner = partner.parent_id if partner.parent_id else partner
            partner = partner.with_company(self.integration_id.company_id)
            partner.property_product_pricelist = pricelist.id

    def _prepare_partner_vals(self) -> Dict:
        """
        Prepare partner values based on the provided data.
        Returns:
            A dictionary containing prepared partner values.
        """
        partner_vals = {
            'parent_id': False,
            'is_company': False,
            'type': 'contact',
            'company_id': self.company_id.id,
        }

        if self.person_name:
            partner_vals['name'] = ' '.join(self.person_name.split())

        if self.email:
            partner_vals['email'] = self.email

        if self.phone:
            partner_vals['phone'] = self.phone

        if self.phone_sanitized:
            partner_vals['phone_sanitized'] = self.phone_sanitized

        # Link this address to the company by setting its parent ID.
        # This step is important for maintaining data integrity and reducing duplicates,
        # as it ensures that the created address is associated with the correct company.
        if self.company_name:
            company = self._get_or_create_company_contact()
            partner_vals['parent_id'] = company.id

        # Since billing_address is written to partner,
        # it is necessary to fill in all fields that are used for the address.
        address_match_fields = self.get_address_match_simple_fields()
        for key in address_match_fields:
            if hasattr(self, key):
                partner_vals[key] = getattr(self, key)

        # Additionally add relative address fields to get a unique match.
        country = self._find_odoo_country()
        if country:
            partner_vals['country_id'] = country.id

        state = self._find_odoo_state(country)
        if state:
            partner_vals['state_id'] = state.id

        # Set customer language if available
        if self.language:
            language = self.env['res.lang'].from_external(self.integration_id, self.language)

            if language:
                partner_vals['lang'] = language.code

        # Handle `Person ID`
        person_id_field = self.integration_id.customer_personal_id_field
        if person_id_field:
            partner_vals[person_id_field.name] = self.person_id_number

        return partner_vals

    def _prepare_company_vals(self) -> Dict:
        """
        Prepare company values for creating a new company partner.
        Returns:
            dict: A dictionary containing the prepared company values.
        """
        company_vals = {
            'name': self.company_name,
            'parent_id': False,
            'is_company': True,
            'company_id': self.company_id.id,
        }

        # Set company language if available
        if self.language:
            language = self.env['res.lang'].from_external(self.integration_id, self.language)

            if language:
                company_vals['lang'] = language.code

        # Add VAT field value if available
        company_vals.update(self._get_vat())

        return company_vals

    def _get_or_create_company(self):
        _logger.info(
            'Deprecated _get_or_create_company method called. This method may be removed in next releases. '
            'Please use _get_or_create_company_contact instead'
        )
        return self._get_or_create_company_contact()

    @api.model
    def _get_or_create_company_contact(self) -> models.Model:
        """
        Get or create an Odoo company based on company values.
        If company exists, fills address fields only if all necessary fields are available.
        Returns:
            models.Model: The retrieved or created company partner record.
        """
        if self.company_partner_id:
            return self.company_partner_id

        ResPartner = self.env['res.partner']

        company_vals = self._prepare_company_vals()
        domain = self._collect_company_search_domain(company_vals)

        company = ResPartner.search(domain, limit=1)
        if not company:
            # If company does not exist, create a new one
            tag = self._get_integration_tag()
            company_vals['category_id'] = [(6, 0, tag.ids)]

            vat_field = self.integration_id.customer_company_vat_field
            vat_value = ''
            # Odoo doesn't allow to ignore VAT validation during contact creation (no_vat_validation key in context)
            # so we have to create contact without VAT and then assign it in separate write() call
            if vat_field:
                vat_value = company_vals.pop(vat_field.name, '')

            # The context key 'no_vat_validation' allows you to store/set a VAT number without doing validations.
            ctx = dict(self.env.context)
            if self.integration_id.ignore_vat_validation and vat_field and vat_value:
                ctx.update({'no_vat_validation': True})

            company = ResPartner.with_context(ctx).create(company_vals)

            if vat_field and vat_value:
                # Write the VAT number to the company
                company.write({vat_field.name: vat_value})

            self._log_partner_trace(
                'Company created',
                f'Search domain: {domain}\n'
                f'→ No match found, created: "{company.display_name}" (ID: {company.id})',
            )
        else:
            self._log_partner_trace(
                'Company found',
                f'Search domain: {domain}\n'
                f'→ Found: "{company.display_name}" (ID: {company.id})',
            )

        # Check if address fields are empty and if so, write the address fields to the company
        self._write_address_fields_if_empty(company)

        self.company_partner_id = company

        return company

    def _collect_partner_search_domain(self, partner_vals: Dict) -> List[Tuple[str, str, str]]:
        """
        Build partner search domain based on integration configuration.

        Logic:
        - If integration restricts search to specific fields and those fields
        have values → search strictly by them (+ mandatory criteria).
        - Otherwise fallback to SEARCH_CUSTOMER_FIELDS.
        - Personal ID is appended only when search is not restricted.
        """

        def _operator(field: str) -> str:
            return '=ilike' if field in ['name', 'email'] else '='

        search_criteria = MANDATORY_PARTNER_SEARCH_CRITERIA.copy()

        # Get configured fields from integration settings
        configured_fields = set(
            self.integration_id
            .sudo()
            .search_customer_fields_ids
            .mapped('name')
        )

        # Fields that actually have values
        available_configured = {
            field for field in configured_fields
            if partner_vals.get(field)
        }

        # Whether the user explicitly restricted search to a subset of all defaults
        is_restricted = configured_fields and configured_fields != set(SEARCH_CUSTOMER_FIELDS)

        if available_configured:
            fields_to_use = available_configured
            self._log_partner_trace(
                'Contact search fields',
                f'Using configured search fields: {sorted(fields_to_use)}',
            )
        elif is_restricted:
            # User explicitly restricted search fields but the incoming customer has no value
            # for any of them (e.g. email-only config, order without email).
            # We cannot identify the customer — force new contact creation instead of
            # falling back to name-based matching which would produce false positives.
            self._log_partner_trace(
                'New contact forced (no search field values)',
                f'Configured search fields: {", ".join(sorted(configured_fields))}.\n'
                f'None of them had a value for the incoming customer. '
                f'A new contact will be created instead of falling back to name-based matching.',
            )
            return [('id', '=', False)]
        else:
            fields_to_use = {
                field for field in SEARCH_CUSTOMER_FIELDS
                if partner_vals.get(field)
            }
            self._log_partner_trace(
                'Contact search fields',
                f'No configured search fields → using defaults: {sorted(fields_to_use)}',
            )

        for field_name in fields_to_use:
            search_criteria.append((field_name, _operator(field_name)))

        domain = self._build_search_domain(search_criteria, partner_vals)

        if is_restricted and available_configured:
            return domain

        # Add personal ID if defined
        person_id_field = self.integration_id.customer_personal_id_field
        if person_id_field and self.person_id_number:
            domain.append((person_id_field.name, '=', self.person_id_number))

        return domain

    def _collect_company_search_domain(self, company_vals: Dict) -> List[Tuple[str, str, Any]]:
        """
        Collect the search domain for finding companies based on the provided company values.
        Args:
            company_vals: Dictionary of company values.
        Returns:
            The search domain criteria.
        """
        search_criteria = MANDATORY_COMPANY_SEARCH_CRITERIA.copy()

        # Check if there is a company VAT field defined in the integration settings
        company_vat_field = self.integration_id.customer_company_vat_field
        if company_vat_field and company_vals.get(company_vat_field.name):
            if self.integration_id.use_vat_only_company_search:
                # If configured to use VAT only for company search, update search criteria
                # accordingly
                self._log_partner_trace(
                    'Company search mode',
                    f'use_vat_only_company_search=True → searching by VAT field '
                    f'"{company_vat_field.name}" only',
                )
                search_criteria = [(company_vat_field.name, '='), ('is_company', '='), ('company_id', 'in')]
                # After this line, no new search criteria should be added to 'search_criteria'.
                return self._build_search_domain(search_criteria, company_vals)
            else:
                search_criteria.append((company_vat_field.name, '='))

        return self._build_search_domain(search_criteria, company_vals)

    @api.model
    def _create_partner(self, partner_vals: Dict) -> models.Model:
        """
        Create an Odoo partner based on the provided partner values.

        This method adds a tag with the integration name for the new partner.
        It creates the partner record with the provided values.
        It also creates a mapping between the integration and the external partner.
        """
        # Add tag with integration Name for new partner
        tag = self._get_integration_tag()
        partner_vals['category_id'] = [(6, 0, tag.ids)]

        dni_field = self.integration_id.customer_personal_id_field
        dni_value = ''
        # Odoo doesn't allow to ignore VAT validation during contact creation (no_vat_validation key in context)
        # so we have to create contact without VAT and then assign it in separate write() call
        if dni_field:
            dni_value = partner_vals.pop(dni_field.name, '')

        # The context key 'no_vat_validation' allows you to store/set a VAT number without doing validations.
        ctx = {'res_partner_search_mode': 'customer'}
        if self.integration_id.ignore_vat_validation:
            ctx.update({'no_vat_validation': True})

        partner = self.env['res.partner'].with_context(**ctx).create(partner_vals)

        # Write the DNI number to the contact
        if dni_field and dni_value:
            partner.write({dni_field.name: dni_value})

        return partner

    def _write_address_fields_if_empty(self, partner: models.Model) -> None:
        """
        Write address fields to a contact if they are empty.
        """
        if all(not partner[field] for field in self.get_address_match_fields()):
            company_address_vals = {}
            address_match_fields = self.get_address_match_simple_fields()
            for key in address_match_fields:
                if hasattr(self, key):
                    company_address_vals[key] = getattr(self, key)

            # Add relative address fields to get a unique match
            country = self._find_odoo_country()
            if country:
                company_address_vals['country_id'] = country.id

            state = self._find_odoo_state(country)
            if state:
                company_address_vals['state_id'] = state.id

            partner.write(company_address_vals)

    # ================================
    # III. ADDRESS HANDLING
    # ================================

    def _has_address_changes(
            self, partner: models.Model, new_address_vals: Dict,
    ) -> Tuple[bool, List[str]]:
        """
        Compare existing partner's address fields with new address values to determine
        if a new address record is needed.

        This method checks if there are any differences between the existing partner's address fields
        and the new address values that would warrant creating a new address record. It handles both
        relational fields (like country_id, state_id) and text fields with special comparison rules.
        Certain fields are ignored during comparison as they don't affect the address uniqueness.

        Args:
            partner: The existing partner record to compare against
            new_address_vals: Dictionary containing new address values to compare with

        Returns:
            Tuple[bool, List[str]]: (True, [changed fields]) if there are significant differences
                 that require a new address record, (False, []) if the existing address can be reused
        """
        changed_fields = []

        for field, new_value in new_address_vals.items():
            # Skip fields that don't affect address uniqueness
            if field in self.ADDRESS_UNIQUENESS_IGNORED_FIELDS:
                continue

            # Handle relational fields (Many2one, etc.)
            if not hasattr(partner, field):
                _logger.warning('Field %s does not exist on res.partner model.', field)
                continue

            if isinstance(partner[field], models.Model):
                partner_value_id = partner[field].id

                if field == 'company_id':
                    if partner_value_id not in [False, new_value]:
                        changed_fields.append(field)
                    continue

                if partner_value_id != new_value:
                    changed_fields.append(field)
                continue

            # Skip if both values are empty
            if not bool(partner[field]) and not bool(new_value):
                continue

            # Convert values to strings for comparison
            partner_value = str(partner[field]) if partner[field] else ''
            new_val_str = str(new_value) if new_value else ''

            # Fields that require case-insensitive comparison
            case_insensitive_fields = ['name', 'street', 'street2', 'city', 'zip', 'email']
            if field in case_insensitive_fields:
                if partner_value.strip().lower() != new_val_str.strip().lower():
                    changed_fields.append(field)
            else:
                if partner_value.strip() != new_val_str.strip():
                    changed_fields.append(field)

        return bool(changed_fields), changed_fields

    @api.model
    def _get_or_create_address(self) -> models.Model:
        """
        Get or create an address based on the prepared address values.
        Returns:
            models.Model: The created or existing address partner record.
        """
        ResPartner = self.env['res.partner']

        if not self.factory_id or not self.factory_id.customer_id:
            _logger.warning('No customer set in factory. Cannot create address.')
            return self.env['res.partner']

        partner = self.factory_id.customer_id

        address_vals = self._prepare_address_vals()

        # Remove keys from address_vals as it is not needed for the validation.
        vals = address_vals.copy()
        vals.pop('type', None)
        vals.pop('parent_id', None)

        address_type = self.type  # e.g. 'billing_address' / 'shipping_address'

        # If address_vals is written on the partner, return the partner
        if (
            # If the option to skip individual contacts is enabled, we should use the
            # company as a contact.
            not self.integration_id.skip_individual_contacts
            or not self.company_name
        ):
            has_changes, changed_fields = self._has_address_changes(partner, address_vals)
            if not has_changes:
                self._log_partner_trace(
                    f'[{address_type}] Address unchanged',
                    f'No differences found vs "{partner.display_name}" (ID: {partner.id}) '
                    f'→ reusing existing contact as address',
                )
                return partner
            self._log_partner_trace(
                f'[{address_type}] Address changed',
                f'Differs in fields: {changed_fields} vs "{partner.display_name}" '
                f'(ID: {partner.id}) → searching for separate address record',
            )
        elif self.company_name:
            company = self._get_or_create_company_contact()

            # In most cases it makes no sense to do this check because name in company contact
            # and name in address are not the same (address will have person name)
            has_changes, changed_fields = self._has_address_changes(company, address_vals)
            if not has_changes:
                self._log_partner_trace(
                    f'[{address_type}] Address unchanged',
                    f'No differences found vs company "{company.display_name}" (ID: {company.id}) '
                    f'→ reusing company as address',
                )
                return company
            self._log_partner_trace(
                f'[{address_type}] Address changed',
                f'Differs in fields: {changed_fields} vs company "{company.display_name}" '
                f'(ID: {company.id}) → searching for separate address record',
            )

        domain = self._collect_address_search_domain(address_vals)
        address = ResPartner.search(domain)

        if not address:
            tag = self._get_integration_tag()
            address_vals['category_id'] = [(6, 0, tag.ids)]

            # The context key 'no_vat_validation' allows assign an address to contact with a VAT number.
            ctx = {'res_partner_search_mode': 'customer'}
            if self.integration_id.ignore_vat_validation:
                ctx.update({'no_vat_validation': True})

            address = ResPartner.with_context(**ctx).create(address_vals)
            self._log_partner_trace(
                f'[{address_type}] Address created',
                f'Search domain: {domain}\n'
                f'→ No match found, created: "{address.display_name}" (ID: {address.id})',
            )
        else:
            # If 'type' is provided in address_vals, filter the results
            if 'type' in address_vals:
                address = address.filtered(lambda x: x.type == address_vals['type']) or address
            self._log_partner_trace(
                f'[{address_type}] Address found',
                f'Search domain: {domain}\n'
                f'→ Found: "{address[0].display_name}" (ID: {address[0].id})',
            )

        return address[0] if address else ResPartner

    def _collect_address_search_domain(self, address_vals: Dict) -> List[Tuple]:
        """
        Build a search domain for finding addresses based on the provided address values.
        """
        search_criteria = MANDATORY_ADDRESS_SEARCH_CRITERIA.copy()

        for field in ['email', 'phone']:
            if address_vals.get(field):
                search_criteria.append((field, '=ilike'))

        search_criteria.extend([
            ('street', '=ilike'),
            ('street2', '=ilike'),
            ('city', '=ilike'),
            ('zip', '=ilike'),
            ('state_id', '='),
            ('country_id', '='),
        ])

        # phone_sanitized is used only for matching and must not be written explicitly.
        search_values = dict(address_vals)
        if self.phone_sanitized:
            search_values['phone_sanitized'] = self.phone_sanitized

        domain = self._build_search_domain(search_criteria, search_values)

        domain.append(('type', 'in', ['other', 'invoice', 'delivery']))

        return domain

    def _prepare_address_vals(self) -> Dict:
        """
        Prepare address values.
        This method constructs a dictionary containing the values required to create or update
        an address record in Odoo. It gathers basic address information such as the name, type,
        parent company, country, state, and additional address fields specified by the integration
        settings. It also handles company-specific fields such as the external company name and VAT.
        Returns:
            A dictionary containing the prepared address values.
        """
        address_vals = {
            'parent_id': self.factory_id.customer_id.id,
            'company_id': self.company_id.id,
        }

        # Set the address type based on the proxy type.
        if self.type == 'billing_address':
            address_vals['type'] = 'invoice'
        elif self.type == 'shipping_address':
            address_vals['type'] = 'delivery'
        else:
            address_vals['type'] = 'other'

        # Remove extra spaces from name
        if self.person_name:
            address_vals['name'] = ' '.join(self.person_name.split())

        # Set the company as the parent for the address by linking its ID.
        # This step is important for maintaining data integrity and reducing duplicates,
        # as it ensures that the created address is associated with the correct company.

        # If manual customer mapping is enabled and a company is present on the address, we
        # skip processing the company. This is because, with manual mapping, we retrieve the
        # partner from the mapping and do not add a company to it.
        if self.company_name and not self.integration_id.use_manual_customer_mapping:
            company = self._get_or_create_company_contact()
            address_vals['parent_id'] = company.id

        address_match_fields = self.get_address_match_simple_fields()
        for key in address_match_fields:
            if hasattr(self, key):
                address_vals[key] = getattr(self, key)

        # Add relative address fields to get a unique match.
        country = self._find_odoo_country()
        if country:
            address_vals['country_id'] = country.id

        state = self._find_odoo_state(country)
        if state:
            address_vals['state_id'] = state.id

        # Set customer language if available
        if self.language:
            language = self.env['res.lang'].from_external(self.integration_id, self.language)
            if language:
                address_vals['lang'] = language.code

        # Adding Company Specific fields
        if self.company_name:
            address_vals['external_company_name'] = self.company_name

        return address_vals

    # ================================
    # IV. MAPPINGS, VAT, LOGGING, ETC.
    # ================================

    def _log_partner_trace(self, event_name, message):
        """Write a customer-type log linked to the source input file if available."""
        input_file = self.factory_id.input_file_id
        self.env['integration.logging'].write_log(
            integration=self.integration_id,
            event_type='customer',
            event_name=event_name,
            message=message,
            res_model='sale.integration.input.file' if input_file else None,
            res_id=input_file.id if input_file else None,
        )

    @api.model
    def _create_or_update_mapping(self, with_new_cursor=False) -> models.Model:
        """
        Creates or updates a mapping for the integration and external partner.
        If a mapping exists, updates the partner_id. Otherwise, creates a new one.
        Args:
            with_new_cursor: Whether to create the mapping with a new cursor.
        Returns:
            models.Model: The created or updated mapping.
        """
        if not self.external_id:
            return self.env['integration.res.partner.mapping']

        ResPartner = self.env['res.partner']
        external_mapping = ResPartner.get_mapping(self.integration_id, self.external_id)

        if external_mapping:
            external_mapping.partner_id = self.partner_id
        else:
            # Use Odoo's transaction mechanism for isolation
            if with_new_cursor:
                db_registry = Registry(self.env.cr.dbname)
                with db_registry.cursor() as new_cr:
                    new_env = api.Environment(new_cr, self.env.uid, {})
                    integration_id = new_env['sale.integration'].browse(self.integration_id.id)
                    external_mapping = new_env['res.partner'].create_mapping(
                        integration_id,
                        self.external_id,
                        extra_vals={'name': self.person_name},
                    )
            else:
                external_mapping = self.partner_id.create_mapping(
                    self.integration_id,
                    self.external_id,
                    extra_vals={'name': self.person_name},
                )

        return external_mapping

    def _get_vat(self) -> Dict:
        """
        Prepare VAT value.
        """
        vals = {}

        company_vat_field = self.integration_id.customer_company_vat_field
        company_reg_number = self.company_reg_number or ''
        if company_reg_number:
            company_reg_number = company_reg_number.replace(' ', '').replace('-', '')

        if not company_vat_field or not company_reg_number:
            return vals

        country = self._find_odoo_country()

        is_valid_vat, error_msg = self._validate_vat(company_reg_number, country)

        if is_valid_vat is True:
            vals[company_vat_field.name] = company_reg_number
            return vals

        if is_valid_vat is None:
            self.is_vat_verified = False
            return vals

        # Log validation failure message if applicable
        partner = self.factory_id.customer_id
        if error_msg and partner:
            self._log_message(
                partner,
                _('Issue with VAT number'),
                _('VAT validation failed for "%s". Error: %s.') % (company_reg_number, error_msg),
            )

        return vals

    def _validate_vat(self, company_reg_number: str, country: str) -> tuple:
        """
        Validate VAT number based on the integration settings.
        """
        if self.integration_id.ignore_vat_validation:
            return True, None

        # If no country is found, add the VAT number to the partner without validation
        if not country:
            return True, 'VAT cannot be validated as no country is specified for the address.'

        return self.env['res.partner']._validate_integration_vat(company_reg_number, country)

    def _log_message(self, partner, subject, body):
        """
        Log a message for the given partner.
        """
        partner._message_log(
            body=body,
            subject=subject,
            author_id=self.env.user.partner_id.id,
            message_type='comment',
        )

    def _post_update_partner(self, partner: models.Model):
        """Hook for extensions. Can be overridden in child classes."""
        return partner
