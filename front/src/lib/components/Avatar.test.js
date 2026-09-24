import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Avatar from './Avatar.svelte';

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
		expect(avatarOf({ name: lea, size: 32 }).style.getPropertyValue('--avatar-size')).toBe('32px');
		expect(avatarOf({ name: lea, size: '6rem' }).style.getPropertyValue('--avatar-size')).toBe('6rem');
	});

	it('leaves --avatar-size to the page without a size, so a media query can set it', () => {
		expect(avatarOf({ name: lea }).style.getPropertyValue('--avatar-size')).toBe('');
	});
});
