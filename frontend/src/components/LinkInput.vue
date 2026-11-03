<script setup>
// A search box for a company, branch, item group or item. The list comes from
// the site with ERPNext's own permissions (restock/app.py lookup).
import { ref, watch } from "vue";
import { app } from "../api.js";
import { __ } from "../store.js";

const props = defineProps({
	modelValue: { type: String, default: "" },
	doctype: { type: String, required: true },
	company: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	clearable: { type: Boolean, default: true },
});
const emit = defineEmits(["update:modelValue"]);

const text = ref(props.modelValue || "");
const open = ref(false);
const items = ref([]);
const active = ref(-1);
let timer = null;
let asked = 0;

watch(
	() => props.modelValue,
	(v) => (text.value = v || "")
);

async function search() {
	const n = ++asked;
	try {
		const got = await app("lookup", { doctype: props.doctype, txt: text.value === props.modelValue ? "" : text.value, company: props.company || null });
		if (n === asked) {
			items.value = got || [];
			active.value = -1;
		}
	} catch (e) {
		items.value = [];
	}
}

function onFocus() {
	open.value = true;
	search();
}

function onInput() {
	open.value = true;
	clearTimeout(timer);
	timer = setTimeout(search, 200);
}

function pick(name) {
	text.value = name;
	open.value = false;
	if (name !== props.modelValue) emit("update:modelValue", name);
}

function onBlur() {
	setTimeout(() => {
		open.value = false;
		// a typed name that is not in the list is not kept
		if (!text.value) {
			if (props.modelValue) emit("update:modelValue", "");
		} else if (text.value !== props.modelValue) {
			const exact = items.value.find((i) => i.name.toLowerCase() === text.value.toLowerCase());
			if (exact) pick(exact.name);
			else text.value = props.modelValue || "";
		}
	}, 150);
}

function onKey(e) {
	if (!open.value) return;
	if (e.key === "ArrowDown") {
		active.value = Math.min(active.value + 1, items.value.length - 1);
		e.preventDefault();
	} else if (e.key === "ArrowUp") {
		active.value = Math.max(active.value - 1, 0);
		e.preventDefault();
	} else if (e.key === "Enter" && items.value[active.value]) {
		pick(items.value[active.value].name);
		e.preventDefault();
	} else if (e.key === "Escape") {
		open.value = false;
	}
}

function clear() {
	text.value = "";
	emit("update:modelValue", "");
}
</script>

<template>
	<div class="link-input">
		<input
			v-model="text"
			class="input"
			:placeholder="placeholder"
			autocomplete="off"
			@focus="onFocus"
			@input="onInput"
			@blur="onBlur"
			@keydown="onKey"
		/>
		<button v-if="clearable && modelValue" class="link-clear" type="button" :aria-label='__("Remove the choice")' @mousedown.prevent="clear">
			&times;
		</button>
		<ul v-if="open && items.length" class="link-list">
			<li
				v-for="(i, n) in items"
				:key="i.name"
				:class="{ active: n === active }"
				@mousedown.prevent="pick(i.name)"
			>
				<span>{{ i.item_name && i.item_name !== i.name ? i.item_name : i.name }}</span>
				<small v-if="i.item_name && i.item_name !== i.name">{{ i.name }}</small>
			</li>
		</ul>
	</div>
</template>
