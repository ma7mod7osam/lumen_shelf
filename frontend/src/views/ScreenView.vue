<script setup>
// One detail screen: the report's rows, filters, totals and, where the desk
// screen has it, the button that turns the suggestions into requests.
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { app, call } from "../api.js";
import { screens } from "../screens.js";
import { __, state, toast } from "../store.js";
import { startRequest } from "../requests.js";
import { money, num } from "../format.js";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import Icon from "../components/Icon.vue";

const props = defineProps({ name: { type: String, required: true }, embedded: { type: Boolean, default: false } });
const route = useRoute();
const router = useRouter();

const def = computed(() => screens(state.boot).find((s) => s.name === props.name));
const model = reactive({});
const data = ref(null);
const loading = ref(false);
const error = ref("");
let asked = 0;

function resetModel() {
	for (const k of Object.keys(model)) delete model[k];
	for (const f of def.value ? def.value.filters : []) if (f.type !== "company") model[f.fieldname] = route.query[f.fieldname] || "";
}

let lastKey = "";
async function load(force) {
	if (!def.value || !state.company) return;
	// the same screen with the same filters is asked once (filters and the
	// screen change together when the menu is used)
	const key = JSON.stringify([props.name, state.company, model]);
	if (!force && key === lastKey) return;
	lastKey = key;
	const n = ++asked;
	loading.value = true;
	error.value = "";
	try {
		const got = await app("screen", { name: props.name, filters: { ...model, company: state.company } });
		if (n === asked) data.value = got;
	} catch (e) {
		if (n === asked) {
			data.value = null;
			error.value = e.message || __("Could not reach the site.");
		}
	} finally {
		if (n === asked) loading.value = false;
	}
}

watch(
	() => props.name,
	() => {
		data.value = null;
		resetModel();
		load();
	},
	{ immediate: true }
);
watch(
	() => state.company,
	() => load()
);
watch(
	model,
	() => {
		if (!props.embedded) {
			const query = Object.fromEntries(Object.entries(model).filter(([, v]) => v));
			router.replace({ query });
		}
		load();
	},
	{ deep: true }
);

// plain words: what the screen is for, what its columns mean, and on request
// how the numbers were worked out
const showAll = ref(false);
const showHelp = ref(false);
const showBasis = ref(false);
watch(
	() => props.name,
	() => {
		showAll.value = showHelp.value = showBasis.value = false;
	}
);
const helpRows = computed(() => {
	if (!data.value || !def.value) return [];
	const help = def.value.help || {};
	const main = def.value.main || [];
	const cols = data.value.columns.filter((c) => !c.hidden && (showAll.value || !main.length || main.includes(c.fieldname)));
	return cols.filter((c) => help[c.fieldname]).map((c) => ({ label: c.label, text: help[c.fieldname] }));
});

const canRequest = computed(() => def.value && def.value.scope && state.boot.can_request && data.value && data.value.rows.length);
function request() {
	startRequest(def.value.scope, { ...model, company: state.company }, () => load(true));
}

function summaryValue(s) {
	if (s.datatype === "Currency") return money(s.value, s.currency || (data.value && data.value.currency));
	if (s.datatype === "Percent") return num(s.value, 1) + "%";
	return typeof s.value === "number" ? num(s.value) : s.value;
}
const TONE = { Red: "danger", Orange: "warning", Blue: "blue", Gray: "muted", Grey: "muted" };

// trending products: a Shelf Manager may hide one for good, or ask again now
const rowAction = computed(() =>
	props.name === "trending_products" && state.boot.can_settings
		? {
				label: __("Not interested"),
				run: async (r) => {
					try {
						await app("dismiss_trend", { name: r.name });
						data.value.rows = data.value.rows.filter((x) => x.name !== r.name);
					} catch (e) {
						toast(e.message, "danger");
					}
				},
		  }
		: null
);
async function refreshTrends() {
	try {
		toast(await call("lumen_shelf.restock.trend_products.refresh_now", { company: state.company }), "info");
	} catch (e) {
		toast(e.message, "danger");
	}
}
</script>

<template>
	<section v-if="def" class="screen">
		<header v-if="!embedded" class="screen-head">
			<h1>{{ def.title }}</h1>
		</header>
		<p v-if="def.intro" class="screen-intro">{{ def.intro }}</p>
		<div class="screen-bar">
			<FilterBar :filters="def.filters" :model="model" />
			<div class="screen-actions">
				<button v-if="name === 'trending_products' && state.boot.can_settings" class="btn" type="button" @click="refreshTrends">
					<Icon name="spark" :size="16" />{{ __("Ask for new ideas") }}
				</button>
				<button class="btn" type="button" :disabled="loading" @click="load(true)"><Icon name="refresh" :size="16" />{{ __("Refresh") }}</button>
				<button v-if="canRequest" class="btn primary" type="button" @click="request">{{ __("Create material requests") }}</button>
			</div>
		</div>
		<p v-if="data" class="basis">
			<button v-if="helpRows.length" class="link" type="button" @click="showHelp = !showHelp">
				{{ showHelp ? __("Hide the explanation") : __("What the columns mean") }}
			</button>
			<button v-if="data.message" class="link" type="button" @click="showBasis = !showBasis">
				{{ showBasis ? __("Hide the details") : __("How we calculated this") }}
			</button>
		</p>
		<p v-if="data && data.message && showBasis" class="basis detail">{{ data.message }}</p>
		<div v-if="showHelp && helpRows.length" class="col-help">
			<strong>{{ __("What the columns mean") }}</strong>
			<dl>
				<template v-for="h in helpRows" :key="h.label">
					<dt>{{ h.label }}</dt>
					<dd>{{ h.text }}</dd>
				</template>
			</dl>
		</div>
		<div v-if="data && data.summary.length" class="summary">
			<div v-for="s in data.summary" :key="s.label" class="summary-item">
				<span class="muted small">{{ s.label }}</span>
				<strong :class="'tone-' + (TONE[s.indicator] || 'none')"><bdi dir="ltr">{{ summaryValue(s) }}</bdi></strong>
			</div>
		</div>
		<div v-if="error" class="notice danger">{{ error }}</div>
		<div v-else-if="!data && loading" class="loading"><span class="spinner"></span></div>
		<DataTable
			v-else-if="data"
			:name="name"
			:title="def.title"
			:columns="data.columns"
			:rows="data.rows"
			:currency="data.currency || ''"
			:row-action="rowAction"
			:main="def.main || []"
			v-model:show-all="showAll"
			:class="{ dim: loading }"
		/>
	</section>
	<section v-else class="screen">
		<div class="notice">{{ __("This part of Lumen Shelf is switched off or not open to you.") }}</div>
	</section>
</template>
