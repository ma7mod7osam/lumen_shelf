<script setup>
// A dialog. `html` is text the server built and escaped (the material
// request tables from restock/requests.py).
import { onMounted, onBeforeUnmount } from "vue";
import Icon from "./Icon.vue";

defineProps({
	title: { type: String, default: "" },
	html: { type: String, default: "" },
	busy: { type: Boolean, default: false },
});
const emit = defineEmits(["close"]);

function onKey(e) {
	if (e.key === "Escape") emit("close");
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
	<div class="modal-back" @mousedown.self="emit('close')">
		<div class="modal" role="dialog" aria-modal="true">
			<div class="modal-head">
				<h2>{{ title }}</h2>
				<button class="icon-btn" type="button" :aria-label='__("Close")' @click="emit('close')"><Icon name="close" :size="18" /></button>
			</div>
			<div class="modal-body">
				<div v-if="html" class="server-html" v-html="html"></div>
				<slot />
			</div>
			<div class="modal-foot">
				<slot name="actions" />
			</div>
			<div v-if="busy" class="modal-busy"><span class="spinner"></span></div>
		</div>
	</div>
</template>
