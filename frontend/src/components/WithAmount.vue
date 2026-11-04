<script setup>
// A sentence with an amount in it ("Worth {0}"), the amount kept left to
// right so Arabic does not flip "25,206.46 USD" into "USD 25,206.46".
import { computed } from "vue";

const props = defineProps({ text: { type: String, required: true }, amount: { type: String, default: "" } });
const parts = computed(() => {
	const i = props.text.indexOf("{0}");
	return i < 0 ? [props.text, ""] : [props.text.slice(0, i), props.text.slice(i + 3)];
});
</script>

<template>
	<span>{{ parts[0] }}<bdi dir="ltr">{{ amount }}</bdi>{{ parts[1] }}</span>
</template>
