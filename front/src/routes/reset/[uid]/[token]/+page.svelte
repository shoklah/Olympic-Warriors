<script>
	import PasswordLinkForm from '$lib/components/PasswordLinkForm.svelte';
	import { useT } from '$lib/i18n';

	export let data;
	export let form;

	const t = useT();
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
>
	<a slot="invalid" class="quiet-link" href="/forgot">{t('login.forgot')}</a>
</PasswordLinkForm>
