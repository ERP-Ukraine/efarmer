from odoo import _, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def contacts_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_user_id': self.id},
                }

class WhatsappCrm(models.Model):
    _inherit = 'crm.lead'

    def crm_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_user_id': self.partner_id.id},
                }

class WhatsappInvoice(models.Model):
    _inherit = 'account.move'

    def invoice_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_template_id': self.env.ref('ss_whatsapp_connector.whatsapp_invoice_template').id},
                }

class WhatsappPurchase(models.Model):
    _inherit = 'purchase.order'

    def purchase_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_template_id': self.env.ref('ss_whatsapp_connector.whatsapp_purchase_template').id},
                }

class WhatsappSale(models.Model):
    _inherit = 'sale.order'

    def sale_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_template_id': self.env.ref('ss_whatsapp_connector.whatsapp_sales_template').id},
                }

class WhatsappPurchase(models.Model):
    _inherit = 'stock.picking'

    def stock_whatsapp(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Send Whatsapp Message'),
                'res_model': 'whatsapp.message.wizard',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_user_id': self.partner_id.id},
                }
