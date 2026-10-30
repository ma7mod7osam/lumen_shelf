"""Install and migrate: the app's two roles. Nothing else is set up, and nothing
has to be: every setting has a default."""

import frappe

ROLES = ("Shelf Manager", "Shelf User")


def ensure_roles():
	for name in ROLES:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(ignore_permissions=True)


def before_install():
	ensure_roles()


def after_install():
	ensure_roles()


def before_migrate():
	# the reports and the settings name these roles, so they must exist before
	# the doctypes and reports are synced
	if frappe.db.table_exists("Role"):
		ensure_roles()


def after_migrate():
	ensure_roles()
