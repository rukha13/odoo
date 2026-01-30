# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    re_unit_id = fields.Many2one("re.unit", string="Interested Unit", tracking=True)
