<script>
	import Login from './login.svelte';

	export let form;
</script>

<div class="login">
	<Login {form} />
</div>

<style>
	@media (max-width: 1100px) {
		.login {
			margin-top: 2rem;
		}
	}
</style>
