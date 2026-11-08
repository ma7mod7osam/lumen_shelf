<script setup>
// Lumen Shelf Settings inside the app. The fields, labels and values are the
// doctype's own (restock/app.py settings), saved with doc.save(), so the
// doctype's checks and ERPNext's permissions apply as in the desk.
import { computed, onMounted, reactive, ref } from "vue";
import { app, call } from "../api.js";
import { __, toast } from "../store.js";
import { reboot } from "../boot.js";
import LinkInput from "../components/LinkInput.vue";
import Icon from "../components/Icon.vue";

const form = ref(null);
const values = reactive({});
const rows = ref([]);
const saving = ref(false);
const error = ref("");
let saved = "";

function fill(got) {
	form.value = got;
	for (const k of Object.keys(values)) delete values[k];
	Object.assign(values, got.values);
	rows.value = got.warehouses.map((r) => ({ ...r }));
	saved = snapshot();
}
function snapshot() {
	return JSON.stringify([values, rows.value]);
}
const dirty = computed(() => form.value && snapshot() !== saved);

async function load() {
	error.value = "";
	try {
		fill(await app("settings"));
	} catch (e) {
		error.value = e.message || __("Could not reach the site.");
	}
}
onMounted(load);

// the doctype's layout: sections, and columns inside them
const sections = computed(() => {
	if (!form.value) return [];
	const out = [];
	let sec = { label: "", columns: [[]] };
	out.push(sec);
	for (const f of form.value.fields) {
		if (f.fieldtype === "Section Break") {
			sec = { label: f.label, depends_on: f.depends_on, columns: [[]] };
			out.push(sec);
		} else if (f.fieldtype === "Column Break") {
			sec.columns.push([]);
		} else {
			sec.columns[sec.columns.length - 1].push(f);
		}
	}
	return out.filter((s) => s.columns.some((c) => c.length));
});

function visible(f) {
	const d = f.depends_on;
	if (!d) return true;
	if (d.startsWith("eval:")) {
		try {
			return !!new Function("doc", "return (" + d.slice(5) + ")")(values);
		} catch (e) {
			return true;
		}
	}
	return !!values[d];
}

const BUTTONS = {
	update_levels_now: "lumen_shelf.restock.reorder.update_now",
	refresh_trends_now: "lumen_shelf.restock.trend_products.refresh_now",
	refresh_bundles_now: "lumen_shelf.restock.bundles.refresh_now",
	check_credit: "lumen_shelf.restock.trend_products.check_credit",
};
const busy = ref("");
async function press(f) {
	if (f.fieldname === "top_up_credit") {
		if (values.trends_topup_url) window.open(values.trends_topup_url, "_blank", "noopener");
		else toast(__("Lumen has not set a top up link yet."), "warning");
		return;
	}
	if (dirty.value) return toast(__("Save the settings first."), "warning");
	const method = BUTTONS[f.fieldname];
	if (!method) return;
	busy.value = f.fieldname;
	try {
		const r = await call(method);
		if (typeof r === "string") toast(r, "info");
		else if (r && r.message) toast(r.message, "info");
		else toast(__("Done."), "info");
		await load();
	} catch (e) {
		toast(e.message, "danger");
	} finally {
		busy.value = "";
	}
}

async function save() {
	saving.value = true;
	try {
		fill(await app("save_settings", { values, warehouses: rows.value }));
		toast(__("Settings saved."), "info");
		await reboot();
	} catch (e) {
		toast(e.message, "danger");
	} finally {
		saving.value = false;
	}
}

function addRow() {
	rows.value.push({ company: "", warehouse: "", warehouse_role: "" });
}
const roleOptions = computed(() => {
	const f = form.value && form.value.warehouse_fields.find((x) => x.fieldname === "warehouse_role");
	return f ? f.options : [];
});
function when(v) {
	return v ? String(v).replace("T", " ").slice(0, 16) : "";
}
</script>

<template>
	<section class="screen settings">
		<header class="screen-head">
			<h1>{{ __("Settings") }}</h1>
			<div class="screen-actions">
				<span v-if="dirty" class="muted small">{{ __("Not saved yet") }}</span>
				<button class="btn primary" type="button" :disabled="!dirty || saving || !form || !form.write" @click="save">{{ __("Save") }}</button>
			</div>
		</header>
		<div v-if="error" class="notice danger">{{ error }}</div>
		<div v-else-if="!form" class="loading"><span class="spinner"></span></div>
		<template v-else>
			<div v-for="(s, si) in sections" v-show="visible(s)" :key="si" class="box">
				<h2 v-if="s.label">{{ s.label }}</h2>
				<div class="set-cols">
					<div v-for="(col, ci) in s.columns" :key="ci" class="set-col">
						<template v-for="f in col" :key="f.fieldname">
							<div v-if="visible(f)" class="set-field" :class="'ft-' + f.fieldtype.toLowerCase().replace(/ /g, '-')">
								<label v-if="f.fieldtype === 'Check'" class="switch">
									<input v-model="values[f.fieldname]" type="checkbox" :true-value="1" :false-value="0" :disabled="!!f.read_only" />
									<span class="switch-track"></span>
									<span>{{ f.label }}</span>
								</label>
								<button
									v-else-if="f.fieldtype === 'Button'"
									class="btn"
									type="button"
									:disabled="busy === f.fieldname"
									@click="press(f)"
								>
									{{ f.label }}
								</button>
								<template v-else-if="f.fieldtype === 'Table'">
									<span class="set-label">{{ f.label }}</span>
									<div v-if="form.detected.length" class="detected">
										<div v-for="d in form.detected" :key="d.company" class="muted small">
											<strong>{{ d.company }}</strong>:
											{{ d.main_warehouse ? __("Main warehouse: {0}", [d.main_warehouse]) : __("No main warehouse found.") }}
											{{ __("Outlets: {0}", [d.outlets.length]) }}
										</div>
									</div>
									<div class="wh-rows">
										<div v-for="(r, i) in rows" :key="i" class="wh-row">
											<LinkInput v-model="r.company" doctype="Company" :placeholder='__("Company")' />
											<LinkInput v-model="r.warehouse" doctype="Warehouse" :company="r.company" :placeholder='__("Branch or warehouse")' />
											<select v-model="r.warehouse_role" class="input">
												<option v-for="o in roleOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
											</select>
											<button class="icon-btn" type="button" :aria-label='__("Remove")' @click="rows.splice(i, 1)"><Icon name="close" :size="16" /></button>
										</div>
										<button class="btn ghost" type="button" @click="addRow">{{ __("Add a warehouse") }}</button>
									</div>
								</template>
								<template v-else>
									<span class="set-label">{{ f.label }}</span>
									<select v-if="f.fieldtype === 'Select'" v-model="values[f.fieldname]" class="input" :disabled="!!f.read_only">
										<option v-for="o in f.options" :key="o.value" :value="o.value">{{ o.label }}</option>
									</select>
									<div v-else-if="f.read_only" class="read-only"><bdi>{{ f.fieldtype === 'Datetime' ? when(values[f.fieldname]) : values[f.fieldname] }}</bdi></div>
									<input
										v-else-if="f.fieldtype === 'Int' || f.fieldtype === 'Float'"
										v-model.number="values[f.fieldname]"
										class="input"
										type="number"
										:step="f.fieldtype === 'Int' ? 1 : 'any'"
										min="0"
									/>
									<input
										v-else-if="f.fieldtype === 'Password'"
										v-model="values[f.fieldname]"
										class="input"
										type="password"
										autocomplete="new-password"
										:placeholder='values[f.fieldname + "_set"] ? __("Saved. Type a new one to change it.") : ""'
									/>
									<textarea v-else-if="f.fieldtype === 'Small Text'" v-model="values[f.fieldname]" class="input" rows="3"></textarea>
									<input v-else v-model="values[f.fieldname]" class="input" type="text" />
								</template>
								<p v-if="f.description" class="muted small">{{ f.description }}</p>
							</div>
						</template>
					</div>
				</div>
			</div>
		</template>
	</section>
</template>
