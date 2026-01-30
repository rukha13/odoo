from odoo import models, fields


class Material(models.Model):
    _name = 'excel.material'
    _description = 'Material'
    _order = 'number'

    number = fields.Integer(string='Number')
    name = fields.Char(string='Used Materials Name', required=True)
    unit = fields.Char(string='Measurement Unit')
    quantity = fields.Integer(string='Quantity')
    price = fields.Float(string='Price', digits=(16, 2))
    total_price = fields.Float(string='Total Price', digits=(16, 2))
    entity_number = fields.Integer(string='Entity Number')
