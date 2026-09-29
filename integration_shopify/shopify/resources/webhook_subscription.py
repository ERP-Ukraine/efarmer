# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead, DeleteMixin
from ..exceptions import ShopifyApiError


class WebhookSubscription(ShopifyResourceRead, DeleteMixin):

    _gid_name = 'WebhookSubscription'
    _request_name = 'webhookSubscription'
    _body = ShopifyResourceRead._tmpl.WEBHOOK_SUBSCRIPTION_BODY

    MUTATION_CREATE = ShopifyResourceRead._tmpl.MUTATION_WEBHOOK_SUBSCRIPTION_CREATE
    MUTATION_DELETE = ShopifyResourceRead._tmpl.MUTATION_WEBHOOK_SUBSCRIPTION_DELETE

    _ADDRESS_TAKEN_ERROR = 'has already been taken'

    def create(self, topic: str, callback_uri: str):
        try:
            return self._create(topic, callback_uri)
        except ShopifyApiError as ex:
            if self._ADDRESS_TAKEN_ERROR not in str(ex):
                raise

            # A previous run can leave a subscription registered on Shopify without Odoo ever
            # recording it (e.g. it was created here but a later topic in the same batch failed
            # before any webhook_line was saved). Reclaim it instead of failing forever.
            self._delete_existing(topic, callback_uri)
            return self._create(topic, callback_uri)

    def _create(self, topic: str, callback_uri: str):
        response = self.execute(
            self.MUTATION_CREATE,
            variables={
                'topic': topic,
                'webhookSubscription': {
                    'format': 'JSON',
                    'uri': callback_uri,
                },
            },
            user_errors_path='data.webhookSubscriptionCreate.userErrors',
        )

        result = self._extract(response, 'data.webhookSubscriptionCreate.webhookSubscription', dict)

        return self.new(**result)

    def _delete_existing(self, topic: str, callback_uri: str):
        existing = self.get_batch(arguments=f'topics: [{topic}], uri: "{callback_uri}"')

        for subscription in existing:
            subscription.delete()

    def delete(self):
        self.ensure_one()

        return self.execute(
            self.MUTATION_DELETE,
            variables={'id': self.gid},
            user_errors_path='data.webhookSubscriptionDelete.userErrors',
        )
