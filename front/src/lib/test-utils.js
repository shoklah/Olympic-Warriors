import { render } from '@testing-library/svelte';
import { I18N } from '$lib/i18n';
import { ME, ORGANISER } from '$lib/session';

/**
 * Render a component with the locale, the organiser flag and the logged-in person
 * (`{ id, first_name, last_name, photo, is_person, photo_locked }`) in context, as the root layout does
 * at runtime. A component that takes `me` as a prop (Header) gets it through `props`.
 * Existing tests assert English text, so `en` is the default; French, the organiser view
 * and a logged-in person are opt-in.
 */
export const renderWith = (Component, props = {}, locale = 'en', organiser = false, me = null) =>
	render(Component, {
		props,
		context: new Map([
			[I18N, locale],
			[ORGANISER, organiser],
			[ME, me]
		])
	});
