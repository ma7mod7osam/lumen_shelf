<script setup>
// A report's rows as a table: sort by any column, search, and save as a file
// for Excel. The columns, labels and values are the report's own. Only the
// screen's main columns show until "Show all columns" (the file has them all).
import { computed, ref } from "vue";
import { cell, NUMERIC } from "../format.js";
import { look } from "../screens.js";
import { __, place } from "../store.js";
import Icon from "./Icon.vue";

const props = defineProps({
	name: { type: String, required: true },
	title: { type: String, default: "" },
	columns: { type: Array, default: () => [] },
	rows: { type: Array, default: () => [] },
	currency: { type: String, default: "" },
	rowAction: { type: Object, default: null }, // { label, run(row) }
	main: { type: Array, default: () => [] }, // fieldnames shown first
	showAll: { type: Boolean, default: false },
});
const emit = defineEmits(["update:showAll"]);

const q = ref("");
const sortBy = ref("");
const desc = ref(false);

const every = computed(() => props.columns.filter((c) => !c.hidden));
const fewer = computed(() => {
	if (!props.main.length) return every.value;
	const byName = Object.fromEntries(every.value.map((c) => [c.fieldname, c]));
	return props.main.map((f) => byName[f]).filter(Boolean);
});
const cols = computed(() => (props.showAll ? every.value : fewer.value));
const canToggle = computed(() => fewer.value.length < every.value.length);

// warehouses as people say them: "Stores", not "Stores - LUMD"
const PLACES = ["warehouse", "from_warehouse", "to_warehouse", "sells_in", "transfer_from"];

function text(c, r) {
	const l = look(props.name, c, r);
	if (l && l.text !== undefined) return l.text;
	if (c.options === "Warehouse" || PLACES.includes(c.fieldname)) return place(cell(c, r, props.currency));
	return cell(c, r, props.currency);
}

const shown = computed(() => {
	const needle = q.value.trim().toLowerCase();
	let out = props.rows;
	if (needle) out = out.filter((r) => every.value.some((c) => String(r[c.fieldname] ?? "").toLowerCase().includes(needle)));
	if (sortBy.value) {
		const c = every.value.find((x) => x.fieldname === sortBy.value);
		const numeric = c && NUMERIC.includes(c.fieldtype);
		out = [...out].sort((a, b) => {
			let x = a[sortBy.value];
			let y = b[sortBy.value];
			if (numeric) {
				x = x === null || x === undefined || x === "" ? -Infinity : Number(x);
				y = y === null || y === undefined || y === "" ? -Infinity : Number(y);
				return desc.value ? y - x : x - y;
			}
			const r = String(x ?? "").localeCompare(String(y ?? ""));
			return desc.value ? -r : r;
		});
	}
	return out;
});

function sort(c) {
	if (sortBy.value === c.fieldname) {
		if (desc.value) sortBy.value = "";
		desc.value = !desc.value;
	} else {
		sortBy.value = c.fieldname;
		desc.value = NUMERIC.includes(c.fieldtype);
	}
}

function itemHref(r, c) {
	if (c.options === "Item" && r[c.fieldname]) return "/app/item/" + encodeURIComponent(r[c.fieldname]);
	// the name opens the item when its code is not on screen
	if (c.fieldname === "item_name" && r.item_code && !cols.value.some((x) => x.fieldname === "item_code"))
		return "/app/item/" + encodeURIComponent(r.item_code);
	return null;
}

function save() {
	// a CSV file Excel opens with Arabic intact (BOM)
	const esc = (v) => '"' + String(v ?? "").replace(/"/g, '""') + '"';
	const lines = [every.value.map((c) => esc(c.label)).join(",")];
	for (const r of shown.value) lines.push(every.value.map((c) => esc(NUMERIC.includes(c.fieldtype) ? r[c.fieldname] : text(c, r))).join(","));
	const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
	const a = document.createElement("a");
	a.href = URL.createObjectURL(blob);
	a.download = (props.title || props.name) + ".csv";
	a.click();
	setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
</script>

<template>
	<div class="table-box">
		<div class="table-tools">
			<div class="search">
				<Icon name="search" :size="16" />
				<input v-model="q" class="input" :placeholder='__("Search in this list")' />
			</div>
			<span class="muted small"><bdi>{{ __("{0} rows", [shown.length]) }}</bdi></span>
			<button v-if="canToggle" class="btn ghost" type="button" @click="emit('update:showAll', !showAll)">
				<Icon name="columns" :size="16" />{{ showAll ? __("Show fewer columns") : __("Show all columns ({0})", [every.length]) }}
			</button>
			<button class="btn" type="button" :disabled="!shown.length" @click="save"><Icon name="download" :size="16" />{{ __("Save for Excel") }}</button>
		</div>
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th
							v-for="c in cols"
							:key="c.fieldname"
							:class="{ num: NUMERIC.includes(c.fieldtype), sorted: sortBy === c.fieldname }"
							:style="{ minWidth: Math.max(80, Math.min(c.width || 110, 220)) + 'px' }"
							@click="sort(c)"
						>
							{{ c.label }}<span v-if="sortBy === c.fieldname" class="arrow">{{ desc ? "↓" : "↑" }}</span>
						</th>
						<th v-if="rowAction"></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(r, i) in shown" :key="i">
						<td v-for="c in cols" :key="c.fieldname" :class="[{ num: NUMERIC.includes(c.fieldtype) }]">
							<template v-for="l in [look(name, c, r)]" :key="'l'">
								<a v-if="itemHref(r, c)" :href="itemHref(r, c)" target="_blank" rel="noopener" class="cell-link">{{ text(c, r) }}</a>
								<span v-else :class="[l && l.tone ? 'tone-' + l.tone : '', l && l.bold ? 'strong' : '']"><bdi :dir="NUMERIC.includes(c.fieldtype) || (l && l.text) ? 'ltr' : null">{{ text(c, r) }}</bdi></span>
							</template>
						</td>
						<td v-if="rowAction" class="row-act">
							<button class="btn small" type="button" @click="rowAction.run(r)">{{ rowAction.label }}</button>
						</td>
					</tr>
				</tbody>
			</table>
			<div v-if="!shown.length" class="empty">
				<Icon name="empty" :size="28" />
				<div>{{ q ? __("Nothing matches the search.") : __("Nothing to show here.") }}</div>
			</div>
		</div>
	</div>
</template>
