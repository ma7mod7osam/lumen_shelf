"""The Lumen Shelf app's page: /shelf (and /shelf/... for the app's own
screens). Signed-in people only. The app itself is frontend/, built into
public/shelf; every figure it shows comes from restock/app.py."""

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/shelf"
		raise frappe.Redirect
	from lumen_shelf import __version__

	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.shelf_version = __version__
	context.lang = frappe.local.lang or "en"
	context.rtl = context.lang.split("-")[0] in ("ar", "he", "fa", "ur")
	return context
