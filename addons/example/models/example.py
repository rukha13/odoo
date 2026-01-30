from odoo import models, fields

class ExampleModel(models.Model):
    _name = 'example.model'
    _description = 'Example Model'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)