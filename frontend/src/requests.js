// "Request" buttons: the same preview and create as the desk screens
// (lumen_shelf.restock.requests). Nothing is made before the person confirms.
import { reactive } from "vue";
import { call } from "./api.js";
import { __, toast } from "./store.js";

export const dialog = reactive({ open: false, step: "", html: "", busy: false, scope: "", filters: null, done: null });

const method = (m) => "lumen_shelf.restock.requests." + m;

export async function startRequest(scope, filters, done) {
	Object.assign(dialog, { open: true, step: "preview", html: "", busy: true, scope, filters, done });
	try {
		const p = await call(method("preview"), { scope, filters });
		dialog.html = p.message;
		dialog.step = p.count ? "confirm" : "nothing";
	} catch (e) {
		dialog.open = false;
		toast(e.message || __("Could not reach the site."), "danger");
	} finally {
		dialog.busy = false;
	}
}

export async function confirmRequest() {
	dialog.busy = true;
	try {
		const c = await call(method("create"), { scope: dialog.scope, filters: dialog.filters });
		dialog.html = c.message;
		dialog.step = "made";
		if (dialog.done) dialog.done(c);
	} catch (e) {
		toast(e.message || __("Could not reach the site."), "danger");
	} finally {
		dialog.busy = false;
	}
}

export function closeRequest() {
	dialog.open = false;
}
