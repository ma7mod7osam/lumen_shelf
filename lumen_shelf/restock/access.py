"""Who may see what. Checked on the server for every list, report and API call,
never only hidden in the screen.

Three gates, in this order:
1. The app's own switch (Lumen Shelf Settings > Enabled), and the switch of
   the feature asked for (outlet transfers, stock health).
2. A role. Stock Manager, Purchase Manager and System Manager see the lists, as
   do the app's own roles Shelf Manager (lists and settings) and Shelf User
   (lists only). Another app may add roles for the lists through the hook
   `lumen_shelf_viewer_roles` (LumenPOS adds its manager role).
3. ERPNext's User Permissions on Company and Warehouse: a person limited to
   some outlets sees those outlets only, the same reading ERPNext's own POS does.
"""

import frappe
from frappe import _

from lumen_shelf.restock import compat
from lumen_shelf.restock.settings import get_settings

MANAGER_ROLE = "Shelf Manager"
USER_ROLE = "Shelf User"
VIEW_ROLES = ("System Manager", "Stock Manager", "Purchase Manager", MANAGER_ROLE, USER_ROLE)
SETTINGS_ROLES = ("System Manager", MANAGER_ROLE)

FEATURES = {
	"running_low": None,  # the master switch alone
	"transfers": "outlet_transfers",
	"stock_health": "stock_health",
}


def viewer_roles():
	roles = set(VIEW_ROLES)
	for r in frappe.get_hooks("lumen_shelf_viewer_roles") or []:
		if isinstance(r, str) and r.strip() and r.strip() not in ("Guest", "All"):
			roles.add(r.strip())
	return roles


def has_view_role(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(viewer_roles() & set(frappe.get_roles(user)))


def can_view(user=None):
	"""For the apps screen and for callers: never raises."""
	try:
		return bool(get_settings()["enabled"]) and has_view_role(user)
	except Exception:
		return False


def check_view(feature="running_low", user=None):
	"""Throw unless this person may see `feature` right now."""
	s = get_settings()
	if not s["enabled"]:
		frappe.throw(_("Lumen Shelf is switched off in Lumen Shelf Settings."), title=_("Switched off"))
	switch = FEATURES.get(feature)
	if switch and not s.get(switch):
		frappe.throw(_("This part of Lumen Shelf is switched off in Lumen Shelf Settings."), title=_("Switched off"))
	if not has_view_role(user):
		frappe.throw(_("You do not have a role that may see restock suggestions."), frappe.PermissionError)
	return s


def check_company(company, user=None):
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Please choose a company."))
	allowed = compat.allowed_docs("Company", user)
	if allowed is not None and company not in allowed:
		frappe.throw(_("You are not permitted to see this company."), frappe.PermissionError)


def allowed_warehouses(user=None):
	"""None (no limit) or the set of warehouses this person is limited to."""
	return compat.allowed_docs("Warehouse", user)
