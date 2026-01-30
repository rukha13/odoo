# -*- coding: utf-8 -*-
from odoo import api, fields, models


class REHandover(models.Model):
    _name = "re.handover"
    _description = "Unit Handover"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "handover_date desc"

    name = fields.Char(required=True, copy=False, default="New")
    unit_id = fields.Many2one("re.unit", required=True, tracking=True)
    project_id = fields.Many2one(
        related="unit_id.project_id", store=True, readonly=True)
    partner_id = fields.Many2one(
        related="unit_id.partner_id", store=True, readonly=False)

    sale_order_id = fields.Many2one(
        related="unit_id.sale_order_id", store=True, readonly=False)

    handover_date = fields.Date(tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("scheduled", "Scheduled"),
         ("done", "Done"), ("cancelled", "Cancelled")],
        default="draft",
        tracking=True,
        required=True,
    )

    notes = fields.Html()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "re.handover") or "New"
        return super().create(vals_list)

    def action_mark_done(self):
        for rec in self:
            rec.state = "done"
            if rec.unit_id and rec.unit_id.state != "handed_over":
                rec.unit_id.state = "handed_over"

    def action_schedule(self):
        for rec in self:
            rec.state = "scheduled"
            if rec.unit_id and rec.unit_id.state not in ("handover_ready", "handed_over"):
                rec.unit_id.state = "handover_ready"
