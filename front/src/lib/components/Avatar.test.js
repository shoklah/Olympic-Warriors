import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Avatar from './Avatar.svelte';

// Vitest runs from the front root, and component styles are not loaded under jsdom: the
// sizes are read from the sources.
const source = (path) => readFileSync(path, 'utf8');

const lea = { first_name: 'Léa', last_name: 'Martin' };

const avatarOf = (props) => renderWith(Avatar, props).container.querySelector('.avatar');

describe('Avatar', () => {
	it('draws the photo as a decorative image: the name is always printed beside it', () => {
		const root = avatarOf({ photo: '/media/avatars/7-abc-sm.webp', name: lea });
		const img = root.querySelector('img');
		expect(img).toHaveAttribute('src', '/media/avatars/7-abc-sm.webp');
		expect(img).toHaveAttribute('alt', '');
		expect(root).not.toHaveTextContent('LM');
	});

	it('draws the initials when there is no photo', () => {
		const root = avatarOf({ photo: null, name: lea });
		expect(root.querySelector('img')).toBeNull();
		expect(root).toHaveTextContent(/^LM$/);
		expect(root).toHaveClass('initials');
	});

	it('draws one initial for a first name alone, and a question mark for no name', () => {
		expect(avatarOf({ name: { first_name: 'Léa' } })).toHaveTextContent(/^L$/);
		expect(avatarOf({ name: null })).toHaveTextContent(/^\?$/);
	});

	it('is hidden from assistive tech either way', () => {
		expect(avatarOf({ photo: '/media/avatars/7-abc-sm.webp', name: lea })).toHaveAttribute('aria-hidden', 'true');
		expect(avatarOf({ name: lea })).toHaveAttribute('aria-hidden', 'true');
	});

	it('sets --avatar-size from a number of pixels or a CSS length', () => {
		expect(avatarOf({ name: lea, size: 160 }).style.getPropertyValue('--avatar-size')).toBe('160px');
		expect(avatarOf({ name: lea, size: '2rem' }).style.getPropertyValue('--avatar-size')).toBe('2rem');
	});

	it('leaves --avatar-size to the page without a size, so a media query can set it', () => {
		expect(avatarOf({ name: lea }).style.getPropertyValue('--avatar-size')).toBe('');
	});

	// Beside a name it follows the default font size (a browser or system setting), as the
	// name does: 1.5rem when neither the prop nor the page sizes it.
	it('is 1.5rem by default', () => {
		expect(source('src/lib/components/Avatar.svelte')).toMatch(/--size: var\(--avatar-size, 1\.5rem\);/);
	});

	// The profile header's portrait (--avatar-size from the page) and the photo editor's
	// preview, over a canvas that draws pixels, are pictures rather than marks in the text.
	it('is sized in rem beside a name: only the photo editor passes pixels', () => {
		const sizes = readdirSync('src', { recursive: true })
			.map((path) => path.replaceAll('\\', '/'))
			.filter((path) => path.endsWith('.svelte'))
			.flatMap((path) =>
				[...source(`src/${path}`).matchAll(/<Avatar\b[^>]*?\bsize=(\{[^}]*\}|"[^"]*")/g)].map((m) => [path, m[1]])
			);
		expect(sizes.length).toBeGreaterThan(0);
		for (const [path, size] of sizes) {
			if (path === 'lib/components/PhotoEditor.svelte') expect(size).toBe('{160}');
			else expect(size, path).toMatch(/^"\d+(\.\d+)?rem"$/);
		}
	});

	it('loads the photo lazily only when asked, for long lists below the fold', () => {
		const photo = '/media/avatars/7-abc-sm.webp';
		expect(avatarOf({ photo, name: lea, lazy: true }).querySelector('img')).toHaveAttribute('loading', 'lazy');
		expect(avatarOf({ photo, name: lea }).querySelector('img')).not.toHaveAttribute('loading');
	});
});
