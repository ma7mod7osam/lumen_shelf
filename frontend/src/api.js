// Calls to the site. Every figure the app shows comes from
// lumen_shelf.restock.app (or the existing request and settings methods),
// which run the same checks as the desk.

export class ApiError extends Error {
	constructor(message, status) {
		super(message);
		this.status = status;
	}
}

function plain(html) {
	const d = document.createElement("div");
	d.innerHTML = html || "";
	return (d.textContent || "").trim();
}

function serverMessage(js) {
	try {
		const list = JSON.parse(js._server_messages || "[]")
			.map((m) => {
				try {
					return JSON.parse(m).message;
				} catch (e) {
					return m;
				}
			})
			.map(plain)
			.filter(Boolean);
		if (list.length) return list.join("\n");
	} catch (e) {
		/* not a list */
	}
	if (js.exception) return plain(String(js.exception).replace(/^[\w.]+:\s*/, ""));
	return "";
}

export async function call(method, args = {}) {
	let res;
	try {
		res = await fetch("/api/method/" + method, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
				"X-Frappe-CSRF-Token": window.csrf_token || "",
			},
			body: JSON.stringify(args),
		});
	} catch (e) {
		throw new ApiError("", 0);
	}
	let js = {};
	try {
		js = await res.json();
	} catch (e) {
		/* an HTML error page */
	}
	if (res.status === 401 || (res.status === 403 && js.exc_type === "CSRFTokenError")) {
		window.location.href = "/login?redirect-to=" + encodeURIComponent("/shelf" + window.location.hash);
		throw new ApiError("", res.status);
	}
	if (!res.ok || js.exc) throw new ApiError(serverMessage(js), res.status);
	return js.message;
}

export const app = (name, args) => call("lumen_shelf.restock.app." + name, args);
