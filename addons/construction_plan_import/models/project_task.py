# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    x_task_key = fields.Char(string="Task Key", index=True)
    x_revision = fields.Char(string="Revision")
    x_project_code = fields.Char(string="Project Code", index=True)
    x_block_code = fields.Char(string="Block Code")
    x_wbs_code = fields.Char(string="WBS Code")
    x_assigned_role = fields.Char(string="Assigned Role")
    x_requires_approval = fields.Boolean(string="Requires Approval")
    x_drawing_refs = fields.Char(string="Drawing References")
    x_confidence = fields.Float(string="Confidence (0-1)")
    x_rationale = fields.Text(string="Rationale")
    x_start_date = fields.Date(string="Planned Start Date")
    x_predecessor_task_keys = fields.Char(string="Predecessor Task Keys (Raw)")
    x_predecessor_ids = fields.Many2many(
        comodel_name="project.task",
        relation="construction_task_predecessor_rel",
        column1="task_id",
        column2="predecessor_id",
        string="Predecessors (Imported)",
        help="Task predecessors imported from Excel. Importer will also sync to native dependencies if available."
    )

    _sql_constraints = [
        ("construction_task_key_uniq",
         "unique(project_id, x_task_key)",
         "A task with the same Task Key already exists in this project."),
    ]

    @api.constrains('x_start_date', 'date_deadline')
    def _check_dates(self):
        for task in self:
            if task.x_start_date and task.date_deadline:
                if task.x_start_date > task.date_deadline:
                    raise ValidationError(
                        "Task '%s': Start date (%s) must be before deadline (%s)." %
                        (task.name, task.x_start_date, task.date_deadline)
                    )
