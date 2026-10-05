<script>
	import RegistrationForm from '$lib/components/RegistrationForm.svelte';
	import { useT } from '$lib/i18n';

	export let data;
	export let form;

	const t = useT();
</script>

<svelte:head>
	<title>{t('register.title', { year: data.registration.edition.year })}</title>
</svelte:head>

<div class="page">
	<h1>{t('register.title', { year: data.registration.edition.year })}</h1>
	<RegistrationForm registration={data.registration} {form} />
</div>

<style>
	h1 {
		margin: 0.2rem 0 1rem;
		overflow-wrap: anywhere;
	}

	.page {
		padding-bottom: 3rem;
	}
</style>
