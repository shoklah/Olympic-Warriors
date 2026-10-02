<script>
	import PasswordLinkForm from '$lib/components/PasswordLinkForm.svelte';

	export let data;
	export let form;
</script>

<PasswordLinkForm
	{data}
	{form}
	action="reset"
	prefix="reset"
	titleKey="reset.title"
	greetingKey="reset.greeting"
	submitKey="reset.submit"
	invalidKey="reset.invalidLink"
/>
