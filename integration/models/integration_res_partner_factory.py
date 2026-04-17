# See LICENSE file for full copyright and licensing details.

from typing import Dict, Optional, Tuple

from odoo import api, fields, models, registry, _

from ..exceptions import ApiImportError, NotMappedFromExternal
from ..tools import freeze_arguments


FIELDS_TO_COPY = [
    'person_name', 'company_name', 'company_reg_number', 'street', 'street2',
    'country', 'state', 'city', 'country_code', 'state_code', 'zip', 'phone', 'mobile',
]


class IntegrationResPartnerFactory(models.TransientModel):
    _name = 'integration.res.partner.factory'
    _description = 'Integration Res Partner Factory'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        required=True,
    )

    proxy_ids = fields.One2many(
        string='Proxies',
        comodel_name='integration.res.partner.proxy',
        inverse_name='factory_id',
        help=(
            'Proxies associated with this factory.'
        ),
    )

    is_initial_import = fields.Boolean(
        string='Initial Import',
        help='Flag indicating whether this is the initial import.',
    )

    @property
    def customer_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'customer')

    @property
    def shipping_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'shipping_address')

    @property
    def billing_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'billing_address')

    @property
    def customer_id(self):
        return self.customer_proxy.partner_id

    @api.model
    @freeze_arguments('customer_data', 'billing_data', 'shipping_data')
    def create_factory(
            self, integration_id: int, customer_data: Optional[Dict], *,
            billing_data: Optional[Dict] = None, shipping_data: Optional[Dict] = None,
            is_initial_import: bool = False,
    ) -> models.Model:
        """
        Creates a new factory and associated proxies.

        Args:
            integration_id : ID of the integration.
            customer_data: Customer data for creating customer proxy.
            billing_data: Billing data for creating billing proxy.
            shipping_data: Shipping data for creating shipping proxy.
            is_initial_import: Flag indicating if this is an initial import.
        Returns:
            models.Model: The created factory instance.
        """
        Proxy = self.env['integration.res.partner.proxy']
        factory = self.create({
            'integration_id': integration_id,
            'is_initial_import': is_initial_import,
        })

        # Helper function to create proxy
        def create_proxy_from_data(proxy_type: str, data: Dict) -> None:
            Proxy.create_proxy(proxy_type, integration_id, factory.id, data)

        # If the data is empty, we consider that there is no data
        if billing_data and all(not v for v in billing_data.values()):
            billing_data = None

        if shipping_data and all(not v for v in shipping_data.values()):
            shipping_data = None

        # Use shipping_data as billing_data fallback if billing_data is missing or empty
        # This is because billing_data is used to create the partner, so if it's not available,
        # we fallback to shipping_data (if it's filled).
        if not billing_data and shipping_data:
            billing_data = shipping_data

        # Update customer data with billing data if available
        customer_data = self._update_customer_data(customer_data, billing_data, shipping_data)

        # Create proxies
        # Use billing_data if customer_data is empty to create a partner for guest orders
        customer_proxy_data = customer_data or billing_data
        if customer_proxy_data:
            create_proxy_from_data('customer', customer_proxy_data)

        if billing_data:
            create_proxy_from_data('billing_address', billing_data)

        if shipping_data:
            create_proxy_from_data('shipping_address', shipping_data)

        return factory

    def _update_customer_data(
        self,
        customer_data: Optional[Dict],
        billing_data: Optional[Dict],
        shipping_data: Optional[Dict],
    ) -> Dict:
        """
            Update customer data with billing data if available.
            Args:
                customer_data: Customer data.
                billing_data: Billing data.
                shipping_data: Shipping data. Shipping data is not used in this method. For overriding this method.
        """
        # To correct process orders customer data should be present
        if not customer_data:
            if billing_data:
                return billing_data
            return shipping_data

        # Save information about company and person in customer data
        if billing_data:
            customer_data['person_id_number'] = billing_data.get('person_id_number', '')

            # Update company-related fields from billing data if available
            company_name = billing_data.get('company_name', '')
            if company_name:
                customer_data['company_name'] = company_name
                customer_data['company_reg_number'] = billing_data.get('company_reg_number', '')
                # Get the country or country_code from the billing data to validation VAT for the company
                customer_data['country'] = billing_data.get('country', '')
                customer_data['country_code'] = billing_data.get('country_code', '')

            # Update customer data with billing data if email and person_name matches (assume that the person who is
            # placing the order is the same as the person who is being billed)
            if (
                str(customer_data.get('email', '')).lower() == str(billing_data.get('email', '')).lower() and  # NOQA
                str(customer_data.get('person_name', '')).lower() == str(billing_data.get('person_name', '')).lower()
            ):
                for field in FIELDS_TO_COPY:
                    customer_data[field] = billing_data.get(field, '')

        return customer_data

    @api.model
    def get_partner_and_addresses(self) -> Tuple[models.Model, Dict]:
        """
        Create or retrieve customer and contact addresses.
        Returns:
            A tuple containing the customer partner record and a dictionary containing shipping,
            billing addresses.
        """
        self.validate_data()

        customer = self.integration_id.default_customer

        if self.customer_proxy:
            if self.integration_id.use_manual_customer_mapping:
                customer = self.customer_proxy.get_customer()
            else:
                customer = self.customer_proxy.get_or_create_partner()

            self.customer_proxy._post_update_partner(customer)

        if self.billing_proxy:
            billing = self.billing_proxy._get_or_create_address()
        else:
            billing = customer

        if self.shipping_proxy:
            shipping = self.shipping_proxy._get_or_create_address()
        else:
            shipping = customer

        return customer, {'shipping': shipping, 'billing': billing}

    def validate_data(self):
        """
        Validate the data before processing it.
        This method performs basic validation on the data provided.
        If the import is flagged as an initial import, additional validation specific to initial
        imports is performed. Otherwise, validation for sales orders is executed.
        """
        if self.is_initial_import:
            self._validate_for_initial_import()
        else:
            self._validate_for_sales_orders()

    def _validate_for_initial_import(self):
        """
        Validate data specific to initial imports.
        This method checks if the customer has an external ID, raising an error if it's missing.
        """
        if not self.customer_proxy.external_id:
            raise ApiImportError(
                _(
                    'Technical error: Customer external ID is missing during the initial import process. '
                    'This may indicate improper usage of the method or a bug.\n'
                    'Please contact support team for further investigation: https://support.ventor.tech'
                )
            )

        mapping = self.env['res.partner'].get_mapping(
            self.integration_id,
            self.customer_proxy.external_id,
        )

        # Handle manual partner mapping enabled case.
        if self.integration_id.use_manual_customer_mapping and not mapping.partner_id:
            # Create a new open mapping for the current external ID
            self.customer_proxy._create_or_update_mapping(with_new_cursor=True)

            # Raise an NotMappedFromExternal with a message indicating the failure in
            # mapping customers.
            raise NotMappedFromExternal(
                _(
                    'Manual customer mapping is enabled for the integration "%s".\n'
                    'The partner "%s" with external ID "%s" has not been mapped yet.\n\n'
                    'Please go to the "Mappings → Contacts" menu and manually map the partner.'
                ) % (
                    self.integration_id.name,
                    self.customer_proxy.person_name,
                    self.customer_proxy.external_id,
                ),
                model_name='integration.res.partner.mapping',
                code=self.customer_proxy.external_id,
                integration=self.integration_id,
            )

    def _validate_for_sales_orders(self) -> bool:
        """
        Validate data for sales orders.
        This method ensures that the customer, shipping, and billing information is available.
        If any of them is missing and the default customer setting is not enabled, it raises an
        error.
        """
        if not self.customer_proxy and not self.integration_id.default_customer:
            raise ApiImportError(
                _(
                    'Missing required customer or address information for the sales order.\n'
                    'In Odoo, sales orders cannot be created without Customer, Invoice Address, '
                    'and Delivery Address.\n\n'
                    'To resolve this issue, please enable the "Default Customer" setting in '
                    'the "Sales Order Defaults" tab:\n'
                    '1. Go to "E-Commerce Integrations → %s".\n'
                    '2. Navigate to the "Sales Orders" tab.\n'
                    '3. Select the "Default Customer" setting.\n\n'
                    'Once this is done, requeue the job, and the selected default partner will be used '
                    'to create the order.'
                ) % self.integration_id.name
            )

        # Handle manual partner mapping enabled case.
        if self.integration_id.use_manual_customer_mapping and not self.customer_proxy.get_customer(False):
            # If customer is not found in the order - skip sending notifications and apply
            # "Default customer" to the order
            if not self.customer_proxy.external_id:
                return True

            # Notify about the failure in mapping customers
            self._notify_about_missed_customer_mapping()

            # Create a new open mapping for the current external ID
            self.customer_proxy._create_or_update_mapping(with_new_cursor=True)

            # Raise an NotMappedFromExternal with a message indicating the failure in
            # mapping customers.
            raise NotMappedFromExternal(
                _(
                    'Manual customer mapping is enabled for the integration "%s".\n'
                    'The partner "%s" with external ID "%s" has not been mapped yet; notification emails '
                    'have been sent.\n\n'
                    'Please map partners in the "Mappings → Contacts" menu.'
                ) % (
                    self.integration_id.name,
                    self.customer_proxy.person_name,
                    self.customer_proxy.external_id,
                ),
                model_name='integration.res.partner.mapping',
                code=self.customer_proxy.external_id,
                integration=self.integration_id,
            )

        return True

    def _notify_about_missed_customer_mapping(self):
        """
        Sends notification emails about failed customer mapping using a separate database cursor.
        This ensures that the email is sent reliably, even if the main transaction is rolled back.
        """
        db_registry = registry(self.env.cr.dbname)
        with db_registry.cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, {})
            mail_template = new_env.ref('integration.mail_template_notify_failed_mapping')

            menu_id = new_env.ref('integration.menu_contacts_mapping').id
            model_name = 'integration_res_partner_mapping'
            url_menu = f'/web#view_type=list&model=integration.{model_name}&view_id=integration.' \
                       f'{model_name}_view_tree&menu_id={menu_id}'

            ctx = dict(self.env.context)
            ctx.update({
                'person_name': self.customer_proxy.person_name,
                'email': self.customer_proxy.email,
                'url_menu': url_menu,
            })

            for email in self.integration_id.emails_for_failed_mapping_notifications.split(','):
                email_values = {
                    'email_from': self.env.user.email_formatted,
                    'email_to': email,
                }

                mail_template.with_context(ctx).send_mail(
                    self.integration_id.id,
                    email_values=email_values,
                    force_send=True,
                )

        return True
