"""The few places Frappe v13 to v16 differ for this app."""

import frappe


def cache():
	"""frappe.cache is a function on v13 and v14, an object that is also
	callable on v15. frappe.cache() works on v13, v14 and v15; on v16 the object
	is no longer callable."""
	c = frappe.cache
	return c() if callable(c) and not hasattr(c, "get_value") else c


def cache_get(key):
	try:
		return cache().get_value(key)
	except Exception:
		return None


def cache_set(key, value, seconds):
	try:
		cache().set_value(key, value, expires_in_sec=seconds)
	except Exception:
		pass


def allowed_docs(doctype, user=None):
	"""The names a user is limited to by User Permissions on `doctype`, or None
	when there is no such limit. The same reading ERPNext does for the POS
	(frappe.permissions.get_user_permissions + get_allowed_docs_for_doctype)."""
	from frappe.permissions import get_user_permissions

	user = user or frappe.session.user
	perms = (get_user_permissions(user) or {}).get(doctype)
	if not perms:
		return None
	try:
		from frappe.permissions import get_allowed_docs_for_doctype

		docs = get_allowed_docs_for_doctype(perms, doctype)
	except ImportError:
		docs = [p.get("doc") for p in perms if not p.get("applicable_for") or p.get("applicable_for") == doctype]
	return set(docs) if docs else None
