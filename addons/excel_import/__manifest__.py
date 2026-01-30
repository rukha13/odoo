{
    'name': 'Excel Import',
    'version': '19.0.1.0.0',
    'summary': 'Import data from Excel files',
    'description': """
        This module allows you to:
        - Upload Excel files (.xlsx, .xls)
        - Create records in Odoo from Excel data
    """,
    'category': 'Tools',
    'author': 'Farrukh Dadamukhamedov',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/material_views.xml',
        'wizard/excel_import_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
