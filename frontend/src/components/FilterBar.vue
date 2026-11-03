<script setup>
// A screen's filters. The company is the app's own (top bar), so it is not
// repeated here.
import LinkInput from "./LinkInput.vue";
import { state } from "../store.js";

defineProps({ filters: { type: Array, default: () => [] }, model: { type: Object, required: true } });
</script>

<template>
	<div class="filters">
		<template v-for="f in filters" :key="f.fieldname">
			<label v-if="f.type !== 'company'" class="filter">
				<span class="filter-label">{{ f.label }}</span>
				<LinkInput
					v-if="f.type === 'link'"
					v-model="model[f.fieldname]"
					:doctype="f.doctype"
					:company="f.doctype === 'Warehouse' ? state.company || '' : ''"
					:placeholder="f.label"
				/>
				<select v-else-if="f.type === 'select'" v-model="model[f.fieldname]" class="input">
					<option v-for="o in f.options" :key="o.value" :value="o.value">{{ o.label }}</option>
				</select>
				<input v-else-if="f.type === 'number'" v-model.lazy="model[f.fieldname]" class="input" type="number" min="0" step="any" inputmode="decimal" />
			</label>
		</template>
	</div>
</template>
