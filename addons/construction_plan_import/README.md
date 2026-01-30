# Construction Plan Import (Excel)

Imports Projects, Tasks, Task Dependencies, and Planned Materials from an Excel file matching these sheets:

- 90_TASKS_OUT
- 91_MATERIALS_OUT

## Install
1. Copy `construction_plan_import` into your Odoo addons path.
2. Update apps list
3. Install module: "Construction Plan Import (Excel)"

## Use
Construction → Imports → Import Plan (Excel)

## Notes
- Tasks are matched by `Task_Key` (stored as `x_task_key`) for idempotent re-import.
- Projects are matched by (`Project_Code`, `Revision`) stored as `x_project_code`, `x_revision`.
- Dependencies are stored in `x_predecessor_ids` and also synced into native `depend_on_ids` if present on your Odoo.
- Planned materials are stored in `construction.task.material.line`.

## Recommended setup (before import)
- Configure UoMs you expect (kg, m³, m², etc.) to avoid enabling "Create UoMs if Missing".
