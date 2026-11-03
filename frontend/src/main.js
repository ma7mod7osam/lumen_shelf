// Lumen Shelf app: one page at /shelf with everything in it, like LumenPOS
// at /pos. The screens are routes after the # so the server needs only
// /shelf.
import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import { start } from "./boot.js";
import { __, state } from "./store.js";
import { screens } from "./screens.js";
import "./styles.css";
import TodayView from "./views/TodayView.vue";
import ScreenView from "./views/ScreenView.vue";
import IdeasView from "./views/IdeasView.vue";
import SettingsView from "./views/SettingsView.vue";

const router = createRouter({
	history: createWebHashHistory(),
	routes: [
		{ path: "/", component: TodayView },
		{
			path: "/s/:name",
			component: ScreenView,
			props: true,
			// an idea screen lives under Product ideas
			beforeEnter: (to) => {
				const s = state.boot && screens(state.boot).find((x) => x.name === to.params.name);
				if (s && s.idea) return { path: "/ideas/" + s.name, query: to.query };
				return true;
			},
		},
		{ path: "/ideas/:tab?", component: IdeasView },
		{ path: "/settings", component: SettingsView },
		{ path: "/:rest(.*)*", redirect: "/" },
	],
	scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach((to) => {
	const b = state.boot;
	// someone who may only change the settings (the app is off): settings
	if (b && !b.can_view && to.path !== "/settings") return "/settings";
	return true;
});

function fail(message) {
	document.getElementById("app").innerHTML =
		'<div class="boot-fail"><img src="/assets/lumen_shelf/images/icon.svg" width="40" height="40" alt=""><p></p><a href="/app"></a></div>';
	document.querySelector(".boot-fail p").textContent = message;
	document.querySelector(".boot-fail a").textContent = __("Back to ERPNext");
}

start()
	.then(() => {
		const app = createApp(App);
		app.config.globalProperties.__ = __;
		app.use(router);
		app.mount("#app");
	})
	.catch((e) => fail((e && e.message) || __("Lumen Shelf could not start.")));
