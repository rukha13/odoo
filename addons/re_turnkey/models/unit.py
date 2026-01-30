# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class REUnit(models.Model):
    _name = "re.unit"
    _description = "Real Estate Unit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "building_id, floor, name"

    name = fields.Char(string="Unit No", required=True, tracking=True)
    building_id = fields.Many2one("re.building", required=True, tracking=True)
    project_id = fields.Many2one(
        related="building_id.project_id", store=True, readonly=True)

    floor = fields.Integer(tracking=True)
    unit_type = fields.Selection(
        [
            ("studio", "Studio"),
            ("1br", "1 Bedroom"),
            ("2br", "2 Bedroom"),
            ("3br", "3 Bedroom"),
            ("other", "Other"),
        ],
        default="other",
        tracking=True,
    )
    area_sqm = fields.Float(string="Area (sqm)", tracking=True)
    list_price = fields.Monetary(string="List Price", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id.id)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("sold", "Sold"),
            ("handover_ready", "Handover Ready"),
            ("handed_over", "Handed Over"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )

    partner_id = fields.Many2one(
        "res.partner", string="Customer", tracking=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="Sale Order", tracking=True)
    opportunity_id = fields.Many2one(
        "crm.lead", string="Opportunity", tracking=True)

    handover_ids = fields.One2many(
        "re.handover", "unit_id", string="Handovers")
    handover_count = fields.Integer(compute="_compute_counts")

    task_ids = fields.One2many("project.task", "re_unit_id", string="Tasks")
    task_count = fields.Integer(compute="_compute_counts")

    @api.depends("handover_ids", "task_ids")
    def _compute_counts(self):
        for rec in self:
            rec.handover_count = len(rec.handover_ids)
            rec.task_count = len(rec.task_ids)

    @api.constrains("state", "partner_id", "sale_order_id")
    def _check_state_dependencies(self):
        for rec in self:
            if rec.state in ("reserved", "sold", "handover_ready", "handed_over") and not rec.partner_id:
                raise ValidationError(
                    "Customer is required when a unit is Reserved/Sold/Handover.")
            if rec.state in ("sold", "handover_ready", "handed_over") and not rec.sale_order_id:
                # You may relax this if you support non-sales handovers
                raise ValidationError(
                    "Sale Order is required when a unit is Sold/Handover.")
