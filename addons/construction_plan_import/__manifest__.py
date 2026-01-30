# -*- coding: utf-8 -*-
{
    "name": "Construction Plan Import (Excel)",
    "version": "19.0.1.0.0",
    "category": "Project",
    "summary": "Import construction projects, tasks, dependencies, and planned materials from Excel",
    "license": "LGPL-3",
    "author": "Your Company",
    "depends": [
        "project",
        "product",
        "uom",
        "purchase",
    ],
    "data": [
        "security/construction_plan_import_groups.xml",
        "security/ir.model.access.csv",
        "views/project_project_views.xml",
        "views/project_task_views.xml",
        "views/construction_task_material_views.xml",
        "wizard/construction_plan_import_wizard_views.xml",
        "views/menu.xml",
    ],
    "application": True,
    "installable": True,
}
