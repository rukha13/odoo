# -*- coding: utf-8 -*-
import base64
import io
import re
from datetime import date, datetime

import openpyxl

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_TASK_SHEET = "90_TASKS_OUT"
_MAT_SHEET = "91_MATERIALS_OUT"


def _norm(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def _to_bool_yn(val):
    v = _norm(val).upper()
    return v in ("Y", "YES", "TRUE", "1")


def _to_float(val, default=0.0):
    if val in (None, ""):
        return default
    try:
        return float(val)
    except Exception:
        return default


def _to_date(val):
    # openpyxl can return datetime, date, or strings
    if val is None or val == "":
        return False
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = _norm(val)
    # try YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass
    # try DD/MM/YYYY
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        pass
    return False


class ConstructionPlanImportWizard(models.TransientModel):
    _name = "construction.plan.import.wizard"
    _description = "Import Construction Plan from Excel"

    file = fields.Binary(string="Excel File", required=True)
    filename = fields.Char(string="Filename")

    # Behavior toggles
    update_existing = fields.Boolean(
        string="Update Existing Records", default=True)
    create_stage_if_missing = fields.Boolean(
        string="Create Task Stages if Missing", default=True)
    create_product_if_missing = fields.Boolean(
        string="Create Products if Missing", default=True)
    create_uom_if_missing = fields.Boolean(string="Create UoMs if Missing (Unsafe)", default=False,
                                           help="If enabled, missing UoMs will be created in a generic category. "
                                           "Prefer to configure UoMs in Odoo instead.")
    create_dependencies = fields.Boolean(
        string="Create Task Dependencies", default=True)
    import_materials = fields.Boolean(
        string="Import Planned Materials", default=True)

    # Optional: auto-prefix project name
    project_name_prefix = fields.Char(string="Project Name Prefix", default="")

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Please upload an Excel file."))

        content = base64.b64decode(self.file)
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        except Exception as e:
            raise UserError(_("Failed to read Excel file: %s") % e)

        # Use savepoint for transactional integrity
        try:
            return self._do_import(wb)
        except Exception as e:
            self.env.cr.rollback()
            raise

    def _do_import(self, wb):
        """Internal import logic wrapped in transaction."""
        if _TASK_SHEET not in wb.sheetnames:
            raise UserError(_("Missing sheet '%s'. Found: %s") %
                            (_TASK_SHEET, ", ".join(wb.sheetnames)))
        if self.import_materials and _MAT_SHEET not in wb.sheetnames:
            raise UserError(_("Missing sheet '%s'. Found: %s") %
                            (_MAT_SHEET, ", ".join(wb.sheetnames)))

        task_rows = self._read_sheet(wb[_TASK_SHEET])
        self._validate_required_columns(
            task_rows,
            required=[
                "Task_Key", "Revision", "Project_Code", "Block_Code", "WBS_Code", "Task_Name",
                "Stage", "Start_Date", "Deadline", "Assigned_Role",
                "Predecessor_Task_Keys", "Requires_Approval(Y/N)", "Drawing_Refs",
                "Confidence(0-1)", "Rationale",
            ],
            sheet=_TASK_SHEET,
        )

        mat_rows = []
        if self.import_materials:
            mat_rows = self._read_sheet(wb[_MAT_SHEET])
            self._validate_required_columns(
                mat_rows,
                required=[
                    "Task_Key", "Revision", "Odoo_Product_Name", "Qty_Planned", "UoM",
                    "Waste_Factor", "Procurement_Method", "Confidence(0-1)", "Notes",
                ],
                sheet=_MAT_SHEET,
            )

        projects = self._upsert_projects(task_rows)
        tasks_map, tasks_by_rev_key = self._upsert_tasks(task_rows, projects)

        if self.create_dependencies:
            self._link_dependencies(task_rows, tasks_map, projects)

        if self.import_materials:
            self._upsert_materials(mat_rows, tasks_by_rev_key)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import complete"),
                "message": _("Projects: %s | Tasks: %s | Materials lines: %s")
                % (len(projects), len(tasks_map), len(mat_rows)),
                "sticky": False,
                "type": "success",
            }
        }

    # ----------------------------
    # Helpers
    # ----------------------------
    def _read_sheet(self, ws):
        # First row is headers
        headers = []
        for cell in ws[1]:
            if cell.value is None:
                break
            headers.append(_norm(cell.value))
        rows = []
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if all(v is None or v == "" for v in row[:len(headers)]):
                continue
            rec = {"__rownum__": idx}
            for col_i, h in enumerate(headers):
                rec[h] = row[col_i] if col_i < len(row) else None
            rows.append(rec)
        return rows

    def _validate_required_columns(self, rows, required, sheet):
        if not rows:
            raise UserError(_("Sheet '%s' has no data rows.") % sheet)
        present = set(rows[0].keys())
        missing = [c for c in required if c not in present]
        if missing:
            raise UserError(_("Sheet '%s' is missing columns: %s") %
                            (sheet, ", ".join(missing)))

    def _upsert_projects(self, task_rows):
        Project = self.env["project.project"]
        projects = {}  # (code, revision) -> project
        for r in task_rows:
            code = _norm(r.get("Project_Code"))
            rev = _norm(r.get("Revision"))
            if not code:
                raise UserError(_("Row %s: Project_Code is empty") %
                                r["__rownum__"])
            key = (code, rev)
            if key in projects:
                continue

            project = Project.search(
                [("x_project_code", "=", code), ("x_revision", "=", rev)], limit=1)
            if not project:
                name = f"{self.project_name_prefix}{code}"
                if rev:
                    name = f"{name} ({rev})"
                project = Project.create({
                    "name": name,
                    "x_project_code": code,
                    "x_revision": rev,
                })
            elif self.update_existing:
                # Keep name as user may have edited, but ensure codes are stored
                vals = {}
                if not project.x_project_code:
                    vals["x_project_code"] = code
                if rev and project.x_revision != rev:
                    vals["x_revision"] = rev
                if vals:
                    project.write(vals)

            projects[key] = project
        return projects

    def _get_or_create_stage(self, project, stage_name):
        stage_name = _norm(stage_name) or "Draft"
        TaskType = self.env["project.task.type"]
        stage = TaskType.search(
            [("name", "=", stage_name), ("project_ids", "in", project.id)], limit=1)
        if stage:
            return stage
        stage = TaskType.search(
            [("name", "=", stage_name), ("project_ids", "=", False)], limit=1)
        if stage:
            stage.write({"project_ids": [(4, project.id)]})
            return stage
        if not self.create_stage_if_missing:
            raise UserError(_("Project '%s': missing stage '%s' and auto-create is disabled.")
                            % (project.display_name, stage_name))
        return TaskType.create({"name": stage_name, "project_ids": [(4, project.id)]})

    def _upsert_tasks(self, task_rows, projects):
        Task = self.env["project.task"]
        tasks_map = {}  # (project_id, task_key) -> task
        tasks_by_rev_key = {}  # (project_code, revision, task_key) -> task
        for r in task_rows:
            rownum = r["__rownum__"]
            task_key = _norm(r.get("Task_Key"))
            if not task_key:
                raise UserError(_("Row %s: Task_Key is empty") % rownum)

            rev = _norm(r.get("Revision"))
            p_code = _norm(r.get("Project_Code"))
            block = _norm(r.get("Block_Code"))
            wbs = _norm(r.get("WBS_Code"))
            name = _norm(r.get("Task_Name")) or task_key
            stage_name = _norm(r.get("Stage")) or "Draft"

            project = projects.get((p_code, rev))
            if not project:
                raise UserError(_("Row %s: Could not find or create project (%s, %s).")
                                % (rownum, p_code, rev))

            stage = self._get_or_create_stage(project, stage_name)

            vals = {
                "name": name,
                "project_id": project.id,
                "stage_id": stage.id,
                "date_deadline": _to_date(r.get("Deadline")),
                "x_start_date": _to_date(r.get("Start_Date")),
                "x_task_key": task_key,
                "x_revision": rev,
                "x_project_code": p_code,
                "x_block_code": block,
                "x_wbs_code": wbs,
                "x_assigned_role": _norm(r.get("Assigned_Role")),
                "x_predecessor_task_keys": _norm(r.get("Predecessor_Task_Keys")),
                "x_requires_approval": _to_bool_yn(r.get("Requires_Approval(Y/N)")),
                "x_drawing_refs": _norm(r.get("Drawing_Refs")),
                "x_confidence": _to_float(r.get("Confidence(0-1)"), 0.0),
                "x_rationale": r.get("Rationale"),
            }

            existing = Task.search([
                ("project_id", "=", project.id),
                ("x_task_key", "=", task_key),
            ], limit=1)
            if existing:
                if self.update_existing:
                    existing.write(vals)
                task = existing
            else:
                task = Task.create(vals)

            tasks_map[(project.id, task_key)] = task
            tasks_by_rev_key[(p_code, rev, task_key)] = task

        return tasks_map, tasks_by_rev_key

    def _link_dependencies(self, task_rows, tasks_map, projects):
        # Second pass, all tasks exist
        dependency_graph = {}  # task_id -> list of predecessor_ids

        for r in task_rows:
            task_key = _norm(r.get("Task_Key"))
            rev = _norm(r.get("Revision"))
            p_code = _norm(r.get("Project_Code"))
            project = projects.get((p_code, rev))
            if not project:
                continue
            task = tasks_map.get((project.id, task_key))
            if not task:
                continue

            raw = _norm(r.get("Predecessor_Task_Keys"))
            if not raw:
                continue

            preds = []
            # Split on semicolon or comma, then clean each part
            for key in re.split(r"[;,]", raw):
                k = _norm(key)
                if not k:
                    continue
                if k == task_key:
                    continue
                pred_task = tasks_map.get((project.id, k))
                if not pred_task:
                    # Ignore missing predecessor keys but store raw
                    continue
                preds.append(pred_task.id)

            if not preds:
                continue

            dependency_graph[task.id] = preds

        # Check for circular dependencies
        self._check_circular_dependencies(dependency_graph)

        # Now apply dependencies
        for task_id, pred_ids in dependency_graph.items():
            task = self.env["project.task"].browse(task_id)
            task.write({"x_predecessor_ids": [(6, 0, pred_ids)]})

            # If native dependency field exists, sync it too
            if "depend_on_ids" in task._fields:
                task.write({"depend_on_ids": [(6, 0, pred_ids)]})

    def _check_circular_dependencies(self, dependency_graph):
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()

        def has_cycle(node, path):
            if node in rec_stack:
                cycle_path = path[path.index(node):] + [node]
                Task = self.env["project.task"]
                cycle_names = [Task.browse(t).x_task_key or str(t)
                               for t in cycle_path]
                raise UserError(
                    _("Circular dependency detected: %s") % " -> ".join(cycle_names)
                )
            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in dependency_graph.get(node, []):
                if has_cycle(neighbor, path + [node]):
                    return True

            rec_stack.remove(node)
            return False

        for node in dependency_graph:
            if node not in visited:
                has_cycle(node, [])

    def _resolve_uom(self, uom_text):
        uom_text = _norm(uom_text)
        if not uom_text:
            raise UserError(_("UoM is empty"))
        Uom = self.env["uom.uom"]

        # Common normalization: m2/m3 variants
        canon = uom_text.replace("^2", "²").replace("^3", "³")
        canon = canon.replace("m2", "m²").replace("m3", "m³")
        canon = canon.replace("sq.m", "m²").replace("cu.m", "m³")

        uom = Uom.search([("name", "=", canon)], limit=1)
        if uom:
            return uom
        # try case-insensitive
        uom = Uom.search([("name", "ilike", canon)], limit=1)
        if uom:
            return uom

        if not self.create_uom_if_missing:
            raise UserError(
                _("Unknown UoM '%s'. Configure it in Odoo first or enable 'Create UoMs if Missing'.") % uom_text)

        # Creating UoMs is not recommended - just return a default "Units" UoM
        # Users should configure proper UoMs in Odoo before importing
        default_uom = Uom.search(
            [("name", "in", ["Unit", "Units", "unit", "units"])], limit=1)
        if not default_uom:
            default_uom = Uom.search([], limit=1)

        if not default_uom:
            raise UserError(
                _("Cannot find any UoM in system. Please configure at least one UoM before importing."))

        # Log a warning that we're using a fallback
        import logging
        _logger = logging.getLogger(__name__)
        _logger.warning(
            "UoM '%s' not found. Using fallback UoM '%s'. Please configure proper UoMs before importing.",
            uom_text, default_uom.name
        )

        return default_uom

    def _resolve_product(self, product_name, uom):
        product_name = _norm(product_name)
        if not product_name:
            raise UserError(_("Product name is empty"))
        Product = self.env["product.product"]
        prod = Product.search([("name", "=", product_name)], limit=1)
        if prod:
            return prod

        if not self.create_product_if_missing:
            raise UserError(
                _("Unknown product '%s'. Create it in Odoo first or enable 'Create Products if Missing'.") % product_name)

        Template = self.env["product.template"]
        tmpl = Template.create({
            "name": product_name,
            "type": "product",
            "uom_id": uom.id,
        })
        return tmpl.product_variant_id

    def _resolve_proc_method(self, val):
        v = _norm(val).lower()
        if v in ("purchase", "buy", "procure"):
            return "purchase"
        if v in ("rental", "rent"):
            return "rental"
        if v in ("subcontract", "subcontractor", "service"):
            return "subcontract"
        return "other"

    def _upsert_materials(self, mat_rows, tasks_by_rev_key):
        Line = self.env["construction.task.material.line"]
        for r in mat_rows:
            rownum = r["__rownum__"]
            task_key = _norm(r.get("Task_Key"))
            rev = _norm(r.get("Revision"))
            p_code = _norm(r.get("Project_Code"))
            if not task_key:
                raise UserError(
                    _("Materials row %s: Task_Key is empty") % rownum)

            task = None
            if p_code:
                task = tasks_by_rev_key.get((p_code, rev, task_key))
            else:
                # Backward-compat: older files may not include Project_Code in materials
                candidates = [
                    t for (pc, rv, tk), t in tasks_by_rev_key.items()
                    if rv == rev and tk == task_key
                ]
                if len(candidates) == 1:
                    task = candidates[0]
                elif len(candidates) > 1:
                    raise UserError(
                        _("Materials row %s: Task_Key '%s' is ambiguous. Add Project_Code to materials.")
                        % (rownum, task_key)
                    )
            if not task:
                raise UserError(
                    _("Materials row %s: Task_Key '%s' not found in imported tasks. "
                      "Check Task_Key, Revision, and Project_Code.") % (rownum, task_key))

            uom = self._resolve_uom(r.get("UoM"))
            product = self._resolve_product(r.get("Odoo_Product_Name"), uom)
            method = self._resolve_proc_method(r.get("Procurement_Method"))

            vals = {
                "task_id": task.id,
                "product_id": product.id,
                "qty_planned": _to_float(r.get("Qty_Planned"), 0.0),
                "uom_id": uom.id,
                "waste_factor": _to_float(r.get("Waste_Factor"), 0.0),
                "procurement_method": method,
                "confidence": _to_float(r.get("Confidence(0-1)"), 0.0),
                "notes": r.get("Notes"),
            }

            existing = Line.search([
                ("task_id", "=", task.id),
                ("product_id", "=", product.id),
                ("procurement_method", "=", method),
            ], limit=1)

            if existing:
                if self.update_existing:
                    existing.write(vals)
            else:
                Line.create(vals)
