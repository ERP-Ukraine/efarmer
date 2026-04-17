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

    def parse(self, risklevel: str = 'HIGH'):
        self.ensure_one()

        result = []
        for record in self.assessments:
            if record['riskLevel'] == risklevel:

                for fact in record.get('facts', []):
                    result.append({
                        **fact,
                        'recommendation': self.recommendation,
                    })

        return result
