import base64
import io
from odoo import models, fields, _
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:
    openpyxl = None


class ExcelImportWizard(models.TransientModel):
    _name = 'excel.import.wizard'
    _description = 'Excel Import Wizard'

    file = fields.Binary(string='Excel File', required=True)
    filename = fields.Char(string='Filename')

    def action_import(self):
        """Import data from Excel file to excel.material model"""
        self.ensure_one()
        if not self.file:
            raise UserError(_('Please upload an Excel file.'))

        if not openpyxl:
            raise UserError(_('openpyxl library is required.'))

        # Read Excel file
        file_content = base64.b64decode(self.file)
        file_io = io.BytesIO(file_content)
        wb = openpyxl.load_workbook(file_io, read_only=True, data_only=True)
        ws = wb.active

        # Read all rows
        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if len(rows) < 2:
            raise UserError(
                _('Excel file must have headers and at least one data row.'))

        # Skip header row (first row), import data rows
        Material = self.env['excel.material']
        records_created = 0

        for row in rows[1:]:
            # Skip empty rows
            if not any(row):
                continue

            # Map columns by position (fixed order)
            # Column 0: Number, 1: Name, 2: Unit, 3: Quantity, 4: Price, 5: Total Price, 6: Entity Number
            vals = {
                'number': int(row[0]) if row[0] else 0,
                'name': str(row[1]).strip() if row[1] else '',
                'unit': str(row[2]).strip() if row[2] else '',
                'quantity': int(row[3]) if row[3] else 0,
                'price': float(row[4]) if row[4] else 0.0,
                'total_price': float(row[5]) if row[5] else 0.0,
                'entity_number': int(row[6]) if len(row) > 6 and row[6] else 0,
            }

            if vals.get('name'):  # Only create if name exists
                Material.create(vals)
                records_created += 1

        # Show the materials list after import
        return {
            'type': 'ir.actions.act_window',
            'name': 'Materials',
            'res_model': 'excel.material',
            'view_mode': 'list,form',
            'target': 'current',
        }
