import { render } from '@testing-library/svelte';
import { I18N } from '$lib/i18n';

/**
 * Render a component with the locale in context, as the root layout does at runtime.
 * Existing tests assert English text, so `en` is the default here; French is opt-in.
 */
export const renderWith = (Component, props = {}, locale = 'en') =>
	render(Component, { props, context: new Map([[I18N, locale]]) });
