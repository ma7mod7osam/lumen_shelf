app_name = "lumen_restock"
app_title = "Lumen Restock"
app_publisher = "Lumen Solutions"
app_description = "Smart restocking for ERPNext: sales speed, days left, reorder points, transfer and purchase suggestions"
app_email = "hello@lumen-solutions.co"
app_license = "Proprietary"

required_apps = ["erpnext"]

# Frappe's apps screen (v15, v16). Shown to whoever may see the suggestions.
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/lumen_restock/images/icon.svg",
		"title": app_title,
		"route": "/app/lumen-restock",
		"has_permission": "lumen_restock.restock.access.can_view",
	}
]

# Roles are created on install and checked again on every migrate (Frappe
# Cloud deploys run migrate, never a shell).
before_install = "lumen_restock.install.before_install"
after_install = "lumen_restock.install.after_install"
before_migrate = "lumen_restock.install.before_migrate"
after_migrate = "lumen_restock.install.after_migrate"

# Tests only: complete ERPNext's setup on a bare test site (Frappe v16 runs
# just the tested app's before_tests hooks).
before_tests = "lumen_restock.tests.bootstrap.before_tests"

# Phase 1 is read only: no doc_events, no scheduler, no overrides.
#
# Other apps may name extra roles that can see the restock lists, for the
# lists only (not the settings). LumenPOS uses this to let its own manager role
# in, in its own hooks.py:
#     lumen_restock_viewer_roles = ["LumenPOS Manager"]
# Warehouse user permissions still decide which outlets each person sees.
