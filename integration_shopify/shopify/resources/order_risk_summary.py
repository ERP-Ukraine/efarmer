# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class OrderRiskSummary(GqlDict):

    _gid_name = 'OrderRiskSummary'
    _body = GqlDict._tmpl.ORDER_RISK_SUMMARY_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def assessments(self):
        self.ensure_one()
        return self['assessments'] or []

    @property
    def recommendation(self):
        self.ensure_one()
        return (self['recommendation'] or '').lower()

    def parse(self):
        self.ensure_one()

        result = []

        for record in self.assessments:
            if 'riskLevel' not in record:
                raise ValueError('Shopify risk assessment missing riskLevel')

            risk_level = record['riskLevel']

            for fact in record.get('facts', []):
                result.append({
                    **fact,
                    'riskLevel': risk_level,
                    'recommendation': self.recommendation,
                })

        return result
