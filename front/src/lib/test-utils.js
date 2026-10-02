import { render } from '@testing-library/svelte';
import { I18N } from '$lib/i18n';
import { ORGANISER } from '$lib/session';

/**
 * Render a component with the locale and the organiser flag in context, as the root
 * layout does at runtime. Existing tests assert English text, so `en` is the default;
 * French and the organiser view are opt-in.
 */
export const renderWith = (Component, props = {}, locale = 'en', organiser = false) =>
	render(Component, {
		props,
		context: new Map([
			[I18N, locale],
			[ORGANISER, organiser]
		])
	});
