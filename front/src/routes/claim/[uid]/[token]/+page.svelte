<script>
	import PasswordLinkForm from '$lib/components/PasswordLinkForm.svelte';

	export let data;
	export let form;
</script>

<PasswordLinkForm
	{data}
	{form}
	action="claim"
	prefix="claim"
	titleKey="claim.title"
	greetingKey="claim.greeting"
	submitKey="claim.submit"
	invalidKey="claim.invalidLink"
/>
