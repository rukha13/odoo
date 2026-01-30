# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    re_unit_id = fields.Many2one("re.unit", string="Unit", tracking=True)
    building_id = fields.Many2one(
        related="re_unit_id.building_id", store=True, readonly=True)
    re_project_id = fields.Many2one(
        related="re_unit_id.project_id", store=True, readonly=True, string="Unit Project")
