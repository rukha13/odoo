# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    re_unit_id = fields.Many2one("re.unit", string="Unit", tracking=True)

    def action_confirm(self):
        res = super().action_confirm()
        for so in self:
            if so.re_unit_id:
                so.re_unit_id.partner_id = so.partner_id
                so.re_unit_id.sale_order_id = so
                if so.re_unit_id.state in ("draft", "available"):
                    so.re_unit_id.state = "sold"
        return res
