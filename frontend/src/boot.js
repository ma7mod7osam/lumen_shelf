// Who is looking, in what language, and what they may open.
import { app } from "./api.js";
import { savedCompany, setMessages, startTheme, state } from "./store.js";

export async function reboot() {
	const b = await app("boot");
	setMessages(b.messages);
	state.boot = b;
	document.documentElement.lang = b.lang;
	document.documentElement.dir = b.rtl ? "rtl" : "ltr";
	if (!state.company || !b.companies.includes(state.company)) {
		const saved = savedCompany();
		state.company = saved && b.companies.includes(saved) ? saved : b.company || b.companies[0] || null;
	}
	return b;
}

export async function start() {
	const b = await reboot();
	startTheme(b.theme);
	return b;
}
