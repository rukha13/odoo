# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionTaskMaterialLine(models.Model):
    _name = "construction.task.material.line"
    _description = "Planned Material for Task"
    _order = "task_id, id"

    task_id = fields.Many2one(
        "project.task", required=True, ondelete="cascade", index=True)
    project_id = fields.Many2one(
        related="task_id.project_id", store=True, index=True)
    product_id = fields.Many2one("product.product", required=True, index=True)
    qty_planned = fields.Float(string="Planned Quantity", default=0.0)
    uom_id = fields.Many2one("uom.uom", string="UoM", required=True)
    waste_factor = fields.Float(string="Waste Factor", default=0.0,
                                help="E.g. 0.05 = 5% waste.")
    procurement_method = fields.Selection(
        selection=[
            ("purchase", "Purchase"),
            ("rental", "Rental"),
            ("subcontract", "Subcontract"),
            ("other", "Other"),
        ],
        default="purchase",
        required=True,
    )
    confidence = fields.Float(string="Confidence (0-1)")
    notes = fields.Text()
    has_vendor = fields.Boolean(
        string="Has Vendor",
        compute="_compute_has_vendor",
        store=False,
        help="Indicates if this product has at least one vendor configured"
    )

    _sql_constraints = [
        ("task_product_procurement_uniq",
         "unique(task_id, product_id, procurement_method)",
         "A planned material line for this task + product + procurement method already exists."),
    ]

    @api.depends('product_id', 'product_id.seller_ids')
    def _compute_has_vendor(self):
        for line in self:
            line.has_vendor = bool(line.product_id.seller_ids)

    def action_create_purchase_order(self):
        """Create purchase orders from planned materials"""
        # Check if Purchase module is installed
        if 'purchase.order' not in self.env:
            raise UserError(
                "Purchase module is not installed. Please install the Purchase app first."
            )

        # Filter only purchase method materials
        purchase_lines = self.filtered(
            lambda l: l.procurement_method == 'purchase')
        if not purchase_lines:
            raise UserError(
                "No materials with 'Purchase' procurement method selected. "
                "Only materials marked for purchase can be ordered."
            )

        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        # Group materials by supplier (use product's default vendor)
        materials_by_vendor = {}
        materials_no_vendor = []

        for line in purchase_lines:
            # Get vendor from product's supplier info
            vendor = False
            if line.product_id.seller_ids:
                vendor = line.product_id.seller_ids[0].partner_id

            if vendor:
                if vendor.id not in materials_by_vendor:
                    materials_by_vendor[vendor.id] = {
                        'vendor': vendor, 'lines': []}
                materials_by_vendor[vendor.id]['lines'].append(line)
            else:
                materials_no_vendor.append(line)

        # Create purchase orders per vendor
        created_pos = []
        for vendor_data in materials_by_vendor.values():
            vendor = vendor_data['vendor']

            # Create PO
            po = PurchaseOrder.create({
                'partner_id': vendor.id,
                'origin': f"Construction Materials - {', '.join([l.task_id.name for l in vendor_data['lines'][:3]])}",
            })

            # Create PO lines
            for mat_line in vendor_data['lines']:
                qty_with_waste = mat_line.qty_planned * \
                    (1 + mat_line.waste_factor)

                PurchaseOrderLine.create({
                    'order_id': po.id,
                    'product_id': mat_line.product_id.id,
                    'name': f"[{mat_line.task_id.name}] {mat_line.product_id.name}",
                    'product_qty': qty_with_waste,
                    'product_uom_id': mat_line.uom_id.id,
                    'price_unit': mat_line.product_id.standard_price or 0.0,
                    'date_planned': mat_line.task_id.date_deadline or fields.Date.today(),
                })

            created_pos.append(po)

        # Show warning if some materials have no vendor
        warning_msg = ""
        if materials_no_vendor:
            warning_msg = f"\n\nWarning: {len(materials_no_vendor)} material(s) skipped (no vendor configured): "
            warning_msg += ", ".join(
                [m.product_id.name for m in materials_no_vendor[:5]])
            if len(materials_no_vendor) > 5:
                warning_msg += f" and {len(materials_no_vendor) - 5} more"

        if not created_pos:
            raise UserError(
                "No purchase orders created. Please configure vendors for your products first.\n"
                "Go to Inventory > Products > select product > Purchase tab > Add vendor."
            )

        # Return action to open created POs
        if warning_msg:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Purchase Orders Created',
                    'message': warning_msg.strip(),
                    'sticky': True,
                    'type': 'warning',
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Created Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [po.id for po in created_pos])],
            'context': {
                'default_origin': 'Construction Materials',
            },
            'target': 'current',
        }
