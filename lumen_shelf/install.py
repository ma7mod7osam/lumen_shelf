"""Install and migrate: the app's two roles, and one read-only field on
ERPNext's Item Reorder table (Item > Reorder Levels) that marks the levels
Lumen Shelf set in automatic mode, so it never touches a level the shop set.
Nothing else is set up, and nothing has to be: every setting has a default."""

import frappe

ROLES = ("Shelf Manager", "Shelf User")


def ensure_roles():
	for name in ROLES:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(ignore_permissions=True)


CUSTOM_FIELDS = {
	"Item Reorder": [
		{
			"fieldname": "lumen_shelf_managed",
			"label": "Set by Lumen Shelf",
			"fieldtype": "Check",
			"insert_after": "material_request_type",
			"read_only": 1,
			"no_copy": 1,
			"default": "0",
		}
	]
}


def ensure_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(CUSTOM_FIELDS, update=True)


def before_uninstall():
	"""Leave ERPNext as it was: the levels Lumen Shelf set, and its field."""
	from lumen_shelf.restock import reorder

	reorder.clear_all()
	for doctype, fields in CUSTOM_FIELDS.items():
		for f in fields:
			name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": f["fieldname"]})
			if name:
				frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def before_install():
	ensure_roles()


def after_install():
	ensure_roles()
	ensure_fields()


def before_migrate():
	# the reports and the settings name these roles, so they must exist before
	# the doctypes and reports are synced
	if frappe.db.table_exists("Role"):
		ensure_roles()


def after_migrate():
	ensure_roles()
	ensure_fields()
