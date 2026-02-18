# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class Address(GqlDict):

    _gid_name = 'Address'
    _body = GqlDict._tmpl.MAILING_ADDRESS_BODY
