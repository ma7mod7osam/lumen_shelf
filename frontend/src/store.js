// What the whole app shares: who is looking (boot), the company, the theme,
// and the short notes shown at the bottom of the screen.
import { reactive } from "vue";

export const state = reactive({
	boot: null,
	company: null,
	theme: "light",
	toasts: [],
});

let messages = {};

export function setMessages(m) {
	messages = m || {};
}

// The app's own texts, translated by the server (restock/app.py boot).
export function __(text, args) {
	let out = messages[text] || text;
	if (args) out = out.replace(/\{(\d+)\}/g, (m, i) => (args[i] === undefined ? m : String(args[i])));
	return out;
}

export function toast(message, tone = "info") {
	if (!message) return;
	const t = { id: Date.now() + Math.random(), message, tone };
	state.toasts.push(t);
	setTimeout(() => {
		const i = state.toasts.indexOf(t);
		if (i >= 0) state.toasts.splice(i, 1);
	}, tone === "danger" ? 9000 : 5000);
}

function remember(key, value) {
	try {
		if (value === undefined) return window.localStorage.getItem(key);
		window.localStorage.setItem(key, value);
	} catch (e) {
		/* private window: nothing kept */
	}
	return null;
}

export function applyTheme(theme) {
	state.theme = theme;
	const dark = theme === "dark" || (theme === "automatic" && window.matchMedia("(prefers-color-scheme: dark)").matches);
	document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}

export function startTheme(fromUser) {
	applyTheme(remember("lumen_shelf_theme") || fromUser || "light");
}

export function toggleTheme() {
	const dark = document.documentElement.getAttribute("data-theme") === "dark";
	const next = dark ? "light" : "dark";
	remember("lumen_shelf_theme", next);
	applyTheme(next);
}

export function rememberCompany(c) {
	state.company = c;
	if (c) remember("lumen_shelf_company", c);
}

export function savedCompany() {
	return remember("lumen_shelf_company");
}
