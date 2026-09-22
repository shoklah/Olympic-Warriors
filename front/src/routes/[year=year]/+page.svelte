<script>
	import EditionHub from '$lib/components/EditionHub.svelte';

	export let data;
</script>

<EditionHub summary={data.summary} editions={data.editions} />
