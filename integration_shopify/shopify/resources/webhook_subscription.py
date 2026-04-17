# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead, DeleteMixin


class WebhookSubscription(ShopifyResourceRead, DeleteMixin):

    _gid_name = 'WebhookSubscription'
    _request_name = 'webhookSubscription'
    _body = ShopifyResourceRead._tmpl.WEBHOOK_SUBSCRIPTION_BODY

    MUTATION_CREATE = ShopifyResourceRead._tmpl.MUTATION_WEBHOOK_SUBSCRIPTION_CREATE
    MUTATION_DELETE = ShopifyResourceRead._tmpl.MUTATION_WEBHOOK_SUBSCRIPTION_DELETE

    def create(self, topic: str, callback_uri: str):
        # FIXME: handle error "Address for this topic has already been taken"
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

    def delete(self):
        self.ensure_one()
        return DeleteMixin.delete(self)
