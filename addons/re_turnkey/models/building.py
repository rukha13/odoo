# -*- coding: utf-8 -*-
from odoo import api, fields, models


class REBuilding(models.Model):
    _name = "re.building"
    _description = "Building / Block"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    project_id = fields.Many2one("project.project", string="Project", tracking=True)
    address = fields.Char()

    unit_ids = fields.One2many("re.unit", "building_id", string="Units")
    unit_count = fields.Integer(compute="_compute_unit_count")

    @api.depends("unit_ids")
    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)
