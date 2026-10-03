<script>
	import { page } from '$app/stores';
	import Login from './login.svelte';

	export let form;
</script>

<div class="login">
	<Login {form} next={form?.next ?? $page.url.searchParams.get('next') ?? ''} />
</div>

<style>
	@media (max-width: 1100px) {
		.login {
			margin-top: 2rem;
		}
	}
</style>
