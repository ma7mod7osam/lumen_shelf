<script setup>
// Today: the four numbers that matter, what to do, and product ideas. From
// lumen_shelf.restock.home.overview, the same engine as the detail screens.
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { app } from "../api.js";
import { __, place, rememberCompany, seen, state } from "../store.js";
import { REPORT_SCREEN } from "../screens.js";
import { startRequest } from "../requests.js";
import { money, num } from "../format.js";
import Icon from "../components/Icon.vue";
import LinkInput from "../components/LinkInput.vue";
import WithAmount from "../components/WithAmount.vue";

const router = useRouter();
const data = ref(null);
const loading = ref(false);
const error = ref("");
const warehouse = ref("");
const kind = ref("");
let asked = 0;

async function load() {
	const n = ++asked;
	loading.value = true;
	error.value = "";
	try {
		const got = await app("overview", { company: state.company || null, warehouse: warehouse.value || null });
		if (n !== asked) return;
		data.value = got;
		if (got.company && got.company !== state.company) rememberCompany(got.company);
	} catch (e) {
		if (n === asked) error.value = e.message || __("Could not reach the site.");
	} finally {
		if (n === asked) loading.value = false;
	}
}

watch(
	() => state.company,
	(c, old) => {
		if (old && c !== old) warehouse.value = "";
		load();
	},
	{ immediate: true }
);
watch(warehouse, load);

const KINDS = computed(() => [
	["", __("All")],
	["low", __("Restock")],
	["move", __("Move between branches")],
	["expiry", __("May expire")],
	["stuck", __("Not selling")],
]);
const kinds = computed(() => (data.value ? KINDS.value.filter(([k]) => !k || data.value.tasks.some((t) => t.kind === k)) : []));
const shown = computed(() => {
	if (!data.value) return [];
	const k = kinds.value.some(([x]) => x === kind.value) ? kind.value : "";
	return data.value.tasks.filter((t) => !k || t.kind === k);
});
const canAll = computed(() => data.value && data.value.can_request && data.value.tasks.some((t) => t.kind === "low" && t.request));
const ideas = computed(() => (data.value ? data.value.ideas.filter((b) => b.count) : []));

const SCREEN_OF = { low: "running_low", move: "transfers", expiry: "stock_health", stuck: "stock_health" };

function open(screen) {
	const s = REPORT_SCREEN[screen] || screen;
	const query = {};
	if (warehouse.value) query[s === "transfers" ? "to_warehouse" : "warehouse"] = warehouse.value;
	router.push({ path: "/s/" + s, query });
}

// where, and the item code only when the name differs from it
function sub(t) {
	return [t.place || place(t.warehouse), t.item_code !== t.item_name ? t.item_code : ""].filter(Boolean).join(" · ");
}
const ICON = { low: "alert", move: "move", expiry: "clock", stuck: "box" };
function worth(t) {
	return t.kind === "expiry" ? __("Value at risk: {0}") : __("Money tied up: {0}");
}

// the welcome note: shown until "Got it", and again from "How it works"
const intro = ref(!seen("intro"));
function gotIt() {
	seen("intro", true);
	intro.value = false;
}
const showBasis = ref(false);

function requestTask(t) {
	startRequest(t.request.scope, { company: data.value.company, ...t.request.filters }, load);
}
function requestAll() {
	startRequest("running_low", { company: data.value.company, warehouse: warehouse.value || "" }, load);
}
</script>

<template>
	<section class="screen today">
		<header class="screen-head">
			<h1>{{ __("Today") }}</h1>
			<div class="screen-actions">
				<button v-if="!intro" class="btn ghost" type="button" @click="intro = true"><Icon name="help" :size="16" />{{ __("How it works") }}</button>
				<label class="filter inline">
					<LinkInput v-model="warehouse" doctype="Warehouse" :company="state.company || ''" :placeholder='__("All branches")' />
				</label>
				<button class="btn" type="button" :disabled="loading" @click="load"><Icon name="refresh" :size="16" />{{ __("Refresh") }}</button>
			</div>
		</header>

		<div v-if="intro" class="box welcome">
			<h2>{{ __("What Lumen Shelf does for you") }}</h2>
			<ol class="steps">
				<li>
					<strong>{{ __("It reads your sales and stock every day") }}</strong>
					<span class="muted">{{ __("From the invoices and the stock already in ERPNext. You do not enter anything.") }}</span>
				</li>
				<li>
					<strong>{{ __("It tells you what needs doing") }}</strong>
					<span class="muted">{{ __("What will run out, what to move between branches, and what is not selling.") }}</span>
				</li>
				<li>
					<strong>{{ __("One button prepares the request") }}</strong>
					<span class="muted">{{ __("It creates the purchase or transfer request in ERPNext. You look at it and approve it.") }}</span>
				</li>
			</ol>
			<button class="btn primary" type="button" @click="gotIt">{{ __("Got it") }}</button>
		</div>

		<div v-if="error" class="notice danger">{{ error }}</div>
		<div v-else-if="!data" class="loading"><span class="spinner"></span></div>
		<template v-else>
			<p class="basis">
				{{ data.intro }}
				<button class="link" type="button" @click="showBasis = !showBasis">{{ showBasis ? __("Hide the details") : __("How we calculated this") }}</button>
			</p>
			<p v-if="showBasis" class="basis detail">{{ data.basis }}</p>
			<div class="cards" :class="{ dim: loading }">
				<button v-for="c in data.cards" :key="c.key" class="card" type="button" @click="open(c.report)">
					<span class="card-label">{{ c.label }}</span>
					<span class="card-count" :class="c.count ? 'tone-' + c.tone : 'tone-muted'"><bdi dir="ltr">{{ num(c.count) }}</bdi></span>
					<span class="card-note">
						<WithAmount v-if="c.value" :text='__("Worth {0}")' :amount="money(c.value, data.currency)" />
						<template v-else>{{ c.note || "" }}</template>
					</span>
					<span class="card-help">{{ c.help }}</span>
				</button>
			</div>

			<div class="box" :class="{ dim: loading }">
				<div class="box-head">
					<div>
						<h2>{{ __("Today's tasks") }}</h2>
						<div class="muted small">{{ __("Each line says what is happening, why, and what we suggest.") }}</div>
					</div>
					<button v-if="canAll" class="btn primary" type="button" @click="requestAll">{{ __("Request all shortages") }}</button>
				</div>
				<div v-if="kinds.length > 2" class="chips">
					<button v-for="[k, l] in kinds" :key="k" type="button" class="chip" :class="{ active: k === kind }" @click="kind = k">{{ l }}</button>
				</div>
				<div v-if="!shown.length" class="empty">
					<Icon name="box" :size="28" />
					<div>{{ __("Nothing to do today. Every item is stocked.") }}</div>
				</div>
				<div v-for="(t, i) in shown" :key="i" class="task">
					<span class="task-icon" :class="'tone-' + t.tone"><Icon :name="ICON[t.kind] || 'box'" :size="20" /></span>
					<div class="task-body">
						<div class="task-title">
							<a class="task-name" :href="'/app/item/' + encodeURIComponent(t.item_code)" target="_blank" rel="noopener">{{ t.item_name || t.item_code }}</a>
							<span class="muted small">{{ sub(t) }}</span>
						</div>
						<div class="task-when" :class="'tone-' + t.tone">{{ t.when }}</div>
						<div class="task-why muted">{{ t.why }}</div>
						<div class="task-todo">
							<span class="muted">{{ __("Our suggestion:") }}</span> {{ t.todo }}
						</div>
						<div v-if="t.value" class="muted small"><WithAmount :text="worth(t)" :amount="money(t.value, data.currency)" /></div>
					</div>
					<div class="task-act">
						<button v-if="t.request" class="btn" type="button" @click="requestTask(t)">{{ __("Prepare the request") }}</button>
						<button v-else class="btn ghost" type="button" @click="open(SCREEN_OF[t.kind])">{{ __("Show details") }}</button>
					</div>
				</div>
				<div v-if="data.more_tasks" class="muted small more">{{ __("And {0} more on the detail screens.", [data.more_tasks]) }}</div>
			</div>

			<template v-if="ideas.length">
				<h2 class="section-title">{{ __("Product ideas") }}</h2>
				<div class="ideas">
					<div v-for="b in ideas" :key="b.key" class="box">
						<div class="box-head">
							<h3>{{ b.title }}</h3>
							<button class="link" type="button" @click="open(b.report)">{{ __("See all ({0})", [b.count]) }}</button>
						</div>
						<p class="muted small idea-help">{{ b.help }}</p>
						<div v-for="(x, i) in b.items" :key="i" class="idea">
							<div>{{ x.text }}</div>
							<div class="muted small">{{ x.note || "" }}</div>
						</div>
					</div>
				</div>
			</template>
		</template>
	</section>
</template>
