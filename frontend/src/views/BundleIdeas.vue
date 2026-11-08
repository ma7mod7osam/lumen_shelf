<script setup>
// Bundle ideas as cards: the two items, why they belong together, the price
// worked out on the server (restock/bundles.py), and for a Shelf Manager the
// buttons to make it an ERPNext Product Bundle or to drop it for good.
import { computed, ref, watch } from "vue";
import { app, call } from "../api.js";
import { __, state, toast } from "../store.js";
import { money, num } from "../format.js";
import Icon from "../components/Icon.vue";
import Modal from "../components/Modal.vue";
import WithAmount from "../components/WithAmount.vue";

const data = ref(null);
const loading = ref(false);
const error = ref("");
const showOthers = ref(false);
const confirm = ref(null);
const busy = ref(false);
let asked = 0;

async function load() {
	if (!state.company) return;
	const n = ++asked;
	loading.value = true;
	error.value = "";
	try {
		const got = await app("screen", { name: "bundle_ideas", filters: { company: state.company } });
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
watch(() => state.company, load, { immediate: true });

const rows = computed(() => (data.value ? data.value.rows : []));
const fresh = computed(() => rows.value.filter((r) => r.status_key === "New"));
const created = computed(() => rows.value.filter((r) => r.status_key === "Created"));
const rejected = computed(() => rows.value.filter((r) => r.status_key === "Not a match"));
const canAct = computed(() => !!(state.boot && state.boot.can_settings));
const pct = (v) => num(v, 1) + "%";

async function create() {
	const r = confirm.value;
	busy.value = true;
	try {
		const got = await call("lumen_shelf.restock.bundles.create", { name: r.name });
		toast(__("Bundle {0} created at {1}.", [got.item_name, money(got.price, got.currency)]), "info");
		confirm.value = null;
		await load();
	} catch (e) {
		toast(e.message, "danger");
	} finally {
		busy.value = false;
	}
}
async function dismiss(r) {
	try {
		await call("lumen_shelf.restock.bundles.dismiss", { name: r.name });
		data.value.rows = data.value.rows.filter((x) => x.name !== r.name);
	} catch (e) {
		toast(e.message, "danger");
	}
}
async function askAgain() {
	try {
		toast(await call("lumen_shelf.restock.bundles.refresh_now", { company: state.company }), "info");
	} catch (e) {
		toast(e.message, "danger");
	}
}
</script>

<template>
	<section class="screen">
		<p class="screen-intro">{{ __("Items your customers buy together that make a natural set. Sell them as one bundle at a small discount.") }}</p>
		<div class="screen-bar">
			<span></span>
			<div class="screen-actions">
				<button v-if="canAct" class="btn" type="button" @click="askAgain"><Icon name="spark" :size="16" />{{ __("Ask for new ideas") }}</button>
				<button class="btn" type="button" :disabled="loading" @click="load"><Icon name="refresh" :size="16" />{{ __("Refresh") }}</button>
			</div>
		</div>
		<p v-if="data && data.message" class="basis detail">{{ data.message }}</p>
		<div v-if="error" class="notice danger">{{ error }}</div>
		<div v-else-if="!data && loading" class="loading"><span class="spinner"></span></div>
		<template v-else-if="data">
			<div v-if="!fresh.length" class="notice">{{ __("No bundle ideas right now.") }}</div>
			<div class="bundles" :class="{ dim: loading }">
				<article v-for="r in fresh" :key="r.name" class="box bundle">
					<h3 class="bundle-name">{{ r.bundle_name }}</h3>
					<div class="bundle-items">
						<span>{{ r.item_name }}</span>
						<Icon name="plus" :size="14" />
						<span>{{ r.partner_name }}</span>
					</div>
					<p class="muted small">{{ r.reason }}</p>
					<p class="muted small">{{ __("Bought together on {0} invoices", [r.together]) }}</p>
					<div v-if="r.bundle_price" class="bundle-price">
						<div>
							<span class="muted small">{{ __("Price of the two") }}</span>
							<s v-if="r.bundle_price < r.full_price"><bdi dir="ltr">{{ money(r.full_price, r.currency) }}</bdi></s>
							<span v-else><bdi dir="ltr">{{ money(r.full_price, r.currency) }}</bdi></span>
						</div>
						<div>
							<span class="muted small">{{ __("Bundle price") }}</span>
							<strong class="tone-blue"><bdi dir="ltr">{{ money(r.bundle_price, r.currency) }}</bdi></strong>
						</div>
						<div>
							<span class="muted small">{{ __("Customer saves") }}</span>
							<span><bdi dir="ltr">{{ pct(r.discount) }}</bdi></span>
						</div>
						<div v-if="r.margin !== null && r.margin !== undefined">
							<span class="muted small">{{ __("Your profit") }}</span>
							<span><bdi dir="ltr">{{ pct(r.margin) }}</bdi></span>
						</div>
					</div>
					<div v-if="r.note" class="notice warning small">{{ r.note }}</div>
					<div v-if="canAct" class="bundle-act">
						<button class="btn primary" type="button" :disabled="!r.can_create" @click="confirm = r">{{ __("Create bundle") }}</button>
						<button class="btn ghost" type="button" @click="dismiss(r)">{{ __("Not interested") }}</button>
					</div>
				</article>
			</div>
			<div v-if="created.length || rejected.length" class="others">
				<button class="link" type="button" @click="showOthers = !showOthers">
					<Icon name="chevron" :size="14" />{{ showOthers ? __("Hide the rest") : __("Made into bundles ({0}), not a match ({1})", [created.length, rejected.length]) }}
				</button>
				<div v-if="showOthers" class="box">
					<div v-for="r in created" :key="r.name" class="idea">
						<div>{{ r.bundle_name }} <span class="muted small">· {{ __("Made into a bundle") }}: {{ r.bundle_item }}</span></div>
						<div class="muted small">{{ r.item_name }} + {{ r.partner_name }}</div>
					</div>
					<div v-for="r in rejected" :key="r.name" class="idea">
						<div>{{ r.item_name }} + {{ r.partner_name }} <span class="muted small">· {{ __("Not a match") }}</span></div>
						<div class="muted small">{{ r.reason }}</div>
					</div>
				</div>
			</div>
		</template>
		<Modal v-if="confirm" :title='__("Create bundle")' :busy="busy" @close="confirm = null">
			<p>{{ __("This makes three things in ERPNext:") }}</p>
			<ul class="bundle-make">
				<li>{{ __("A new item {0}, not kept in stock.", [confirm.bundle_name]) }}</li>
				<li>{{ __("A Product Bundle of {0} and {1}, one of each.", [confirm.item_name, confirm.partner_name]) }}</li>
				<li><WithAmount :text='__("Its selling price: {0}")' :amount="money(confirm.bundle_price, confirm.currency)" /></li>
			</ul>
			<p class="muted small">{{ __("Selling the bundle takes the two items out of stock.") }}</p>
			<template #actions>
				<button class="btn" type="button" @click="confirm = null">{{ __("Cancel") }}</button>
				<button class="btn primary" type="button" :disabled="busy" @click="create">{{ __("Create bundle") }}</button>
			</template>
		</Modal>
	</section>
</template>
