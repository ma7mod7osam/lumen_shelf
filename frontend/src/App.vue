<script setup>
// The frame: the side menu (a bar at the bottom on a phone), the company,
// the theme, and the dialogs and notes every screen shares.
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { screens } from "./screens.js";
import { __, rememberCompany, state, toggleTheme } from "./store.js";
import { closeRequest, confirmRequest, dialog } from "./requests.js";
import Icon from "./components/Icon.vue";
import Modal from "./components/Modal.vue";

// the app's icon, served by the site (not bundled)
const ICON = "/assets/lumen_shelf/images/icon.svg";
const route = useRoute();
const menuOpen = ref(false);

const nav = computed(() => {
	const b = state.boot;
	if (!b || !b.can_view) return b && b.can_settings ? [{ to: "/settings", label: __("Settings"), icon: "settings" }] : [];
	const list = screens(b);
	const main = list.filter((s) => !s.idea);
	const out = [{ to: "/", label: __("Today"), icon: "today" }];
	for (const s of main) out.push({ to: "/s/" + s.name, label: s.title, short: s.short, icon: s.icon });
	if (list.some((s) => s.idea)) out.splice(Math.min(4, out.length), 0, { to: "/ideas", label: __("Product ideas"), icon: "ideas" });
	if (b.can_settings) out.push({ to: "/settings", label: __("Settings"), icon: "settings" });
	return out;
});
function active(to) {
	if (to === "/") return route.path === "/";
	return route.path === to || route.path.startsWith(to + "/");
}
// on a phone: the first four at the bottom, the rest under "More"
const bottom = computed(() => nav.value.slice(0, 4));
const more = computed(() => nav.value.slice(4));

const company = computed({
	get: () => state.company || "",
	set: (v) => rememberCompany(v),
});
const dark = computed(() => state.theme && document.documentElement.getAttribute("data-theme") === "dark");
</script>

<template>
	<div class="shell" :class="{ rtl: state.boot && state.boot.rtl }">
		<aside class="rail">
			<div class="brand">
				<img :src="ICON" alt="" width="28" height="28" />
				<span>Lumen Shelf</span>
			</div>
			<nav>
				<router-link v-for="n in nav" :key="n.to" :to="n.to" class="nav-item" :class="{ active: active(n.to) }">
					<Icon :name="n.icon" />
					<span>{{ n.label }}</span>
				</router-link>
			</nav>
			<div class="rail-foot">
				<a class="nav-item" href="/app" :title='__("Back to ERPNext")'>
					<Icon name="desk" />
					<span>{{ __("Back to ERPNext") }}</span>
				</a>
			</div>
		</aside>

		<div class="main">
			<header class="topbar">
				<div class="brand mobile-only">
					<img :src="ICON" alt="" width="24" height="24" />
					<span>Lumen Shelf</span>
				</div>
				<label v-if="state.boot && state.boot.companies.length > 1" class="company">
					<span class="sr-only">{{ __("Company") }}</span>
					<select v-model="company" class="input">
						<option v-for="c in state.boot.companies" :key="c" :value="c">{{ c }}</option>
					</select>
				</label>
				<span v-else-if="state.company" class="company-name">{{ state.company }}</span>
				<div class="topbar-end">
					<button class="icon-btn" type="button" :aria-label='__("Light or dark")' :title='__("Light or dark")' @click="toggleTheme">
						<Icon :name="dark ? 'sun' : 'moon'" :size="18" />
					</button>
					<span class="user muted small desktop-only">{{ state.boot && state.boot.full_name }}</span>
				</div>
			</header>

			<main class="content">
				<div v-if="state.boot && !state.boot.enabled" class="notice warning">
					{{ __("Lumen Shelf is switched off. Switch it on in the settings.") }}
				</div>
				<router-view />
			</main>
		</div>

		<nav class="bottom-bar">
			<router-link v-for="n in bottom" :key="n.to" :to="n.to" class="bottom-item" :class="{ active: active(n.to) }">
				<Icon :name="n.icon" />
				<span>{{ n.short || n.label }}</span>
			</router-link>
			<button v-if="more.length" class="bottom-item" type="button" :class="{ active: menuOpen }" @click="menuOpen = !menuOpen">
				<Icon name="menu" />
				<span>{{ __("More screens") }}</span>
			</button>
		</nav>
		<div v-if="menuOpen" class="more-sheet" @click.self="menuOpen = false">
			<div class="more-list">
				<router-link v-for="n in more" :key="n.to" :to="n.to" class="nav-item" :class="{ active: active(n.to) }" @click="menuOpen = false">
					<Icon :name="n.icon" />
					<span>{{ n.label }}</span>
				</router-link>
				<a class="nav-item" href="/app"><Icon name="desk" /><span>{{ __("Back to ERPNext") }}</span></a>
			</div>
		</div>

		<Modal
			v-if="dialog.open"
			:title='dialog.step === "made" ? __("Material requests") : __("Create material requests")'
			:html="dialog.html"
			:busy="dialog.busy"
			@close="closeRequest"
		>
			<template #actions>
				<template v-if="dialog.step === 'confirm'">
					<button class="btn" type="button" @click="closeRequest">{{ __("Cancel") }}</button>
					<button class="btn primary" type="button" :disabled="dialog.busy" @click="confirmRequest">{{ __("Create them") }}</button>
				</template>
				<button v-else class="btn" type="button" @click="closeRequest">{{ __("Close") }}</button>
			</template>
		</Modal>

		<div class="toasts" aria-live="polite">
			<div v-for="t in state.toasts" :key="t.id" class="toast" :class="'toast-' + t.tone">{{ t.message }}</div>
		</div>
	</div>
</template>
