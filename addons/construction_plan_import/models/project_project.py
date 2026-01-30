# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    x_project_code = fields.Char(string="Project Code", index=True)
    x_revision = fields.Char(string="Revision")

    _sql_constraints = [
        ("construction_project_code_revision_uniq",
         "unique(x_project_code, x_revision)",
         "A project with the same Project Code + Revision already exists."),
    ]
