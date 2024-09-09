# See LICENSE file for full copyright and licensing details.

from typing import Any, Dict, List, Tuple

from odoo import api, fields, models, registry

from .sale_integration import SEARCH_CUSTOMER_FIELDS

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
    'mobile',
    'other',
    'zip',
]

ADDRESS_MATCH_FIELDS = [
    'street',
    'street2',
    'city',
    'zip',
    'email',
    'phone',
    'mobile',
]

PROXY_TYPES = [
    'customer',
    'shipping_address',
    'billing_address',
    'other_address',
]


class IntegrationResPartnerProxy(models.TransientModel):
    _name = 'integration.res.partner.proxy'
    _description = 'Integration Res Partner Proxy'

    type = fields.Selection([
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
        string='Integration',
        comodel_name='sale.integration',
        related='factory_id.integration_id',
        help=(
            'The Sale integration associated with this proxy.'
        ),
    )

    partner_id = fields.Many2one(
        string='Partner',
        comodel_name='res.partner',
        help=(
            'Technical field for storing the current parent.'
        ),
    )

    # Fields for customer
    external_id = fields.Char(string='External ID')
    pricelist_id = fields.Char(string='Pricelist ID')
    person_name = fields.Char(string='Person Name')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
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

    def get_proxy_fields(self) -> List:
        return PROXY_FIELDS

    def get_address_match_fields(self) -> List:
        return ADDRESS_MATCH_FIELDS

    def create_proxy(self, type_: str, factory_id: int, data: dict) -> models.Model:
        """
        Create a proxy instance with cleaned values based on the provided data.
        Args:
            type_: The type of the proxy.
            factory_id: The ID of the factory associated with the proxy.
            data : The input data dictionary.
        Returns:
            Recordset: The created proxy instance.
        """
        data = self._prepare_data(type_, data)

        if not data:
            return self.env['integration.res.partner.proxy']

        data['factory_id'] = factory_id

        return self.create([data])

    def _prepare_data(self, type_: str, data: Dict) -> Dict:
        """
        Prepare data for creating an instance of the proxy class with cleaned values.
        Args:
            type_: The type of the proxy.
            data: The input data dictionary.
        Returns:
            dict: A dictionary containing cleaned values for creating an instance of the proxy class
        """
        if type_ not in PROXY_TYPES:
            raise ValueError(f'Proxy type should be one of {PROXY_TYPES}, "{type_}" specified.')

        if not isinstance(data, dict):
            raise ValueError(f'Data should be a dictionary; "{data}" specified.')

        # Remove 'type' key as it's no longer needed and remove keys with empty values
        data.pop('type', None)
        data = {k: v for k, v in data.items() if v not in ['', None, [], {}]}
        if not data:
            return {}

        proxy_fields = self.get_proxy_fields()
        prepared_data = {
            'type': type_,
            **self._clear_optional_fields_values(data, proxy_fields),
        }

        if type_ == 'customer':
            prepared_data['external_id'] = data.get('id', '').strip()

        return prepared_data

    def _clear_optional_fields_values(self, data: Dict, field_names: List) -> Dict:
        """
        Retrieve optional string fields from data, stripping whitespace if present.
        Args:
            data: The input data dictionary.
            field_names: A list of field names to retrieve from the data dictionary.
        Returns:
            dict: A dictionary containing optional string fields with whitespace stripped.
        """
        cleaned_data = dict()

        for key, value in data.items():
            if key in field_names:
                if isinstance(value, str):
                    cleaned_data[key] = value.strip()
                else:
                    cleaned_data[key] = value

        return cleaned_data

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
        Get or create a partner.

        This method retrieves an existing partner based on the external ID,
        or creates a new partner if no matching partner is found.
        If a company name is provided, it also retrieves or creates the company
        associated with the partner. Additionally, it links the external partner
        if it exists, and checks for an existing mapping between the integration
        and the external ID, creating one if none is found.

        Returns:
            models.Model: The retrieved or created partner instance.
        """
        ResPartner = self.env['res.partner']

        company = ResPartner
        if self.company_name:
            company = self._get_or_create_company()

        partner = ResPartner
        if self.external_id:
            partner = self.get_customer(False)

        # If the mapped partner is a company, we cannot use it as a contact and skip this partner.
        if partner.is_company:
            partner = ResPartner

        # If the mapped partner is a company, we cannot use it as a contact and skip this partner.
        if partner.is_company:
            partner = ResPartner

        # Company for contact from mapping may be different, in this case we should create a new
        # contact with correct company
        if company and partner.parent_id and partner.parent_id != company:
            partner = ResPartner

        partner_vals = self._prepare_partner_vals()

        # If mapping exists and contact from mapping has the correct company we can use it
        if partner:
            partner.write(partner_vals)
            self.partner_id = partner

            return partner

        domain = self._collect_partner_search_domain(partner_vals)

        partner = ResPartner.search(domain)
        if len(partner) > 1:
            partner = min(partner, key=lambda p: p.create_date)

        if partner:
            partner.write(partner_vals)
        else:
            partner = self._create_partner(partner_vals)

        # Get and set customer's pricelist from external system (if this feature is enabled)
        if self.integration_id.pricelist_integration and self.pricelist_id:
            pricelist = self.env['product.pricelist'].from_external(
                self.integration_id,
                self.pricelist_id,
                raise_error=False,
            )
            if pricelist:
                partner = partner.with_company(self.integration_id.company_id)
                partner.property_product_pricelist = pricelist.id

        self.partner_id = partner

        if self.external_id:
            # Check if there's no existing mapping for the integration and external ID
            self._create_or_update_mapping()

            # Link external partner
            partner._link_external_partner(self.integration_id, self.external_id)

        return partner

    def _prepare_partner_vals(self) -> Dict:
        """
        Prepare partner values based on the provided data.
        Returns:
            A dictionary containing prepared partner values.
        """
        partner_vals = {
            'name': ' '.join(self.person_name.split()) if self.person_name else '',
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'parent_id': False,
            'is_company': False,
        }

        # Link this address to the company by setting its parent ID.
        # This step is important for maintaining data integrity and reducing duplicates,
        # as it ensures that the created address is associated with the correct company.
        if self.company_name:
            company = self._get_or_create_company()
            partner_vals['parent_id'] = company.id

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
        }

        # Add VAT field value if available
        company_vals.update(self._get_vat())

        return company_vals

    @api.model
    def _get_or_create_company(self) -> models.Model:
        """
        Get or create an Odoo company based on company values.
        Returns:
            models.Model: The retrieved or created company partner record.
        """
        ResPartner = self.env['res.partner']

        company_vals = self._prepare_company_vals()

        domain = self._collect_company_search_domain(company_vals)
        company = ResPartner.search(domain, limit=1)

        if not company:
            tag = self._get_integration_tag()
            company_vals['category_id'] = [(6, 0, tag.ids)]

            # The context key 'no_vat_validation' allows you to store/set a VAT number without
            # doing validations.
            ctx = dict(self.env.context)
            if self.integration_id.ignore_vat_validation:
                ctx.update({'no_vat_validation': True})

            company = ResPartner.with_context(ctx).create(company_vals)

        return company

    def _collect_partner_search_domain(self, partner_vals: Dict) -> List[Tuple[str, str, str]]:
        """
        Collects the search domain based on partner values.
        Args:
            partner_vals : A dictionary containing partner values.
        Returns:
            list: A list of tuples representing the search domain criteria.
        """

        def _get_operator(field: str) -> str:
            return '=ilike' if field == 'name' else '='

        search_criteria = [('parent_id', '='), ('is_company', '=')]

        customer_field_names = self.integration_id.search_customer_fields_ids.mapped('name')
        for field_name in customer_field_names:
            if partner_vals.get(field_name):
                search_criteria.append((field_name, _get_operator(field_name),))

        # If the user has selected to search partners by specific fields, but there are no values
        # in partner_vals for those fields, the search will be performed using all possible fields.
        if len(search_criteria) == 2 and SEARCH_CUSTOMER_FIELDS != customer_field_names:
            for field_name in SEARCH_CUSTOMER_FIELDS:
                if partner_vals.get(field_name):
                    search_criteria.append((field_name, _get_operator(field_name),))

        domain = self._build_search_domain(search_criteria, partner_vals)

        # Add personal ID field to the domain if specified
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
        search_criteria = [('name', '=ilike'), ('is_company', '=')]

        # Check if there is a company VAT field defined in the integration settings
        company_vat_field = self.integration_id.customer_company_vat_field
        if company_vat_field and company_vals.get(company_vat_field.name):
            if self.integration_id.use_vat_only_company_search:
                # If configured to use VAT only for company search, update search criteria
                # accordingly
                search_criteria = [(company_vat_field.name, '='), ('is_company', '=')]
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

        ctx = {'res_partner_search_mode': 'customer'}
        partner = self.env['res.partner'].with_context(**ctx).create(partner_vals)

        return partner

    @api.model
    def _get_or_create_address(self) -> models.Model:
        """
        Get or create an address based on the prepared address values.
        Returns:
            models.Model: The created or existing address partner record.
        """
        ResPartner = self.env['res.partner']

        address_vals = self._prepare_address_vals()

        domain = self._collect_address_search_domain(address_vals)
        address = ResPartner.search(domain)

        if not address:
            tag = self._get_integration_tag()
            address_vals['category_id'] = [(6, 0, tag.ids)]

            address = ResPartner.create(address_vals)

        # If 'type' is provided in address_vals, filter the results
        elif 'type' in address_vals:
            address = address.filtered(lambda x: x.type == address_vals['type']) or address

        return address[0] if address else ResPartner

    def _collect_address_search_domain(self, address_vals: Dict) -> List[Tuple]:
        """
        Build a search domain for finding addresses based on the provided address values.
        """
        search_criteria = [('name', '=ilike'), ('parent_id', '=')]

        for field in ['email', 'phone']:
            if address_vals.get(field):
                search_criteria.append((field, '='))

        search_criteria.extend([
            ('street', '=ilike'),
            ('street2', '=ilike'),
            ('city', '=ilike'),
            ('zip', '=ilike'),
            ('state_id', '='),
            ('country_id', '='),
            ('external_company_name', '='),
        ])

        domain = self._build_search_domain(search_criteria, address_vals)

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
            'name': ' '.join(self.person_name.split()) if self.person_name else '',
            'type': 'other',
            'parent_id': self.factory_id.customer_id.id,
        }

        # Set the company as the parent for the address by linking its ID.
        # This step is important for maintaining data integrity and reducing duplicates,
        # as it ensures that the created address is associated with the correct company.

        # If manual customer mapping is enabled and a company is present on the address, we
        # skip processing the company. This is because, with manual mapping, we retrieve the
        # partner from the mapping and do not add a company to it.
        if self.company_name and not self.integration_id.use_manual_customer_mapping:
            company = self._get_or_create_company()
            address_vals['parent_id'] = company.id

        country = self._find_odoo_country()
        if country:
            address_vals['country_id'] = country.id

        state = self._find_odoo_state(country)
        if state:
            address_vals['state_id'] = state.id

        address_match_fields = self.get_address_match_fields()
        for key in address_match_fields:
            if hasattr(self, key):
                address_vals[key] = getattr(self, key)

        if self.language:
            language = self.env['res.lang'].from_external(self.integration_id, self.language)
            if language:
                address_vals['lang'] = language.code

        # Adding Company Specific fields
        if self.company_name:
            address_vals['external_company_name'] = self.company_name

        return address_vals

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
        main_tag = self.env.ref('integration.main_integration_tag', False) or ResPartnerTag

        tag = ResPartnerTag.search([
            ('name', '=', self.integration_id.name),
            ('parent_id', '=', main_tag.id),
        ])

        if not tag:
            tag = ResPartnerTag.create({
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

            if value:
                domain.append((key, op, value))
            else:
                # If there is no value, use the 'in' operator and an empty list for filtering
                domain.append((key, 'in', ['', False]))

        return domain

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
                db_registry = registry(self.env.cr.dbname)
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

    def _post_update_partner(self, partner: models.Model):
        return partner

    def _get_vat(self) -> Dict:
        """
        Prepare VAT value.
        """
        vals = {}

        company_vat_field = self.integration_id.customer_company_vat_field
        company_reg_number = self.company_reg_number
        country = self._find_odoo_country()

        if company_vat_field and company_reg_number and country:
            is_valid_vat, error_msg = self._validate_vat(company_reg_number, country)

            partner = self.factory_id.customer_id
            if is_valid_vat:
                vals[company_vat_field.name] = company_reg_number

            # Log validation failure message if applicable
            elif error_msg and partner:
                message = f'VAT validation failed "{company_reg_number}"\n. Error: {error_msg}.'

                partner._message_log(
                    body=message,
                    subject='Issue with VAT number',
                    author_id=self.env.user.partner_id.id,
                    message_type='comment',
                )

        return vals

    def _validate_vat(self, company_reg_number: str, country: str) -> tuple:
        """
        Validate VAT number based on the integration settings.
        """
        if self.integration_id.ignore_vat_validation:
            return True, None

        return self.env['res.partner']._validate_integration_vat(company_reg_number, country)
