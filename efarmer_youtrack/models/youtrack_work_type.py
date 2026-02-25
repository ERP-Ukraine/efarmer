# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class YoutrackWorkType(models.Model):
    _name = "youtrack.work.type"
    _description = "YouTrack Work Type"

    name = fields.Char(
        string="Name",
    )

    youtrack_id = fields.Char(
        string="Youtrack ID",
        readonly=True,
    )

    is_default = fields.Boolean(
        string="Default Type",
        default=False,
    )

    def write(self, vals):
        if "is_default" in vals and vals["is_default"]:
            exist_default_types = self.search([("is_default", "=", True)])
            if len(exist_default_types) > 0:
                raise ValidationError(
                    _("You can't have more than one default work types in the system.")
                )
        return super(YoutrackWorkType, self).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_default"):
                exist_default_types = self.search([("is_default", "=", True)])
                if len(exist_default_types) > 0:
                    raise ValidationError(
                        _(
                            "You can't create more than one default work types in the system."
                        )
                    )
        return super(YoutrackWorkType, self).create(vals_list)
