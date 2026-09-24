<script>
	import { initials } from '$lib/avatar';

	/** The photo's URL (a payload's `small` or `large`), or null to draw the initials. */
	export let photo = null;
	/**
	 * The person's name as the payloads carry it, `{ first_name, last_name }` (a profile, a
	 * leaderboard row, a roster player, the partner of a Comrades badge, `me`). Only the
	 * initials read it: the name itself is always printed beside the avatar.
	 */
	export let name = null;
	/**
	 * The diameter, a number of pixels or a CSS length. Without it `--avatar-size` comes from
	 * the page (24px by default), so a media query around the avatar can change it.
	 */
	export let size = null;

	$: diameter = typeof size === 'number' ? `${size}px` : size;
</script>

<!-- Purely visual, like Badge: the name printed beside it says who it is, so the photo is
     decorative (alt="") and the initials are not read out a second time. -->
<span class="avatar" class:initials={!photo} style:--avatar-size={diameter} aria-hidden="true">
	{#if photo}
		<img src={photo} alt="" />
	{:else}
		{initials(name?.first_name, name?.last_name)}
	{/if}
</span>

<style>
	/* `--avatar-size` lets a page scale it, as `--badge-size` does for Badge. */
	.avatar {
		--size: var(--avatar-size, 24px);
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--size);
		height: var(--size);
		border-radius: 50%;
		overflow: hidden;
	}

	img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.initials {
		background: var(--bg-sunken);
		color: var(--muted);
		border: 1px solid var(--line);
		font-family: var(--font-display);
		font-size: calc(var(--size) * 0.5);
		line-height: 1;
		letter-spacing: 0.04em;
		white-space: nowrap;
		user-select: none;
	}
</style>
