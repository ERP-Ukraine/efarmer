# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum


class WeightUnit(GQLEnum):

    g = 'GRAMS'
    kg = 'KILOGRAMS'
    lb = 'POUNDS'
    oz = 'OUNCES'

    @classmethod
    def convert_weight_unit_in(cls, value: str) -> str:
        return cls(value).name

    @classmethod
    def convert_weight_unit_out(cls, value: str) -> str:
        return getattr(cls, value).value
