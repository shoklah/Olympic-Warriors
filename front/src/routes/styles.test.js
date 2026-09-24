import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// Vitest runs from the front root; import.meta.url is a Vite URL here, not file://.
const css = readFileSync('src/routes/styles.css', 'utf8');

/** The custom properties declared in the one rule whose selector is exactly `selector`. */
const tokens = (selector) => {
	const at = css.indexOf(`${selector} {`);
	expect(at, `no rule for ${selector}`).toBeGreaterThan(-1);
	const body = css.slice(css.indexOf('{', at) + 1, css.indexOf('}', at));
	return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
};

const dark = tokens(':root');
const light = tokens(":root[data-theme='light']:not(:has([data-always-dark]))");
const systemLight = tokens(":root[data-theme='system']:not(:has([data-always-dark]))");

// Shared by both themes, so only `:root` declares them.
const LAYOUT = ['--font-display', '--font-body', '--radius', '--radius-lg', '--radius-pill', '--page', '--tabbar'];

/** WCAG 2 contrast ratio of two `#rrggbb` colours. */
const contrast = (a, b) => {
	const luminance = (hex) => {
		const [r, g, b] = [1, 3, 5]
			.map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
			.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * b;
	};
	const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (hi + 0.05) / (lo + 0.05);
};

describe('themes', () => {
	it('declares the same light theme for a chosen and a device-picked light', () => {
		expect(systemLight).toEqual(light);
	});

	it('redefines every theme token of the dark default, and nothing else', () => {
		const themed = Object.keys(dark).filter((name) => !LAYOUT.includes(name));
		expect(Object.keys(light).sort()).toEqual(themed.sort());
	});

	describe.each([
		['dark', dark],
		['light', light]
	])('%s', (_name, theme) => {
		const surfaces = ['--bg', '--bg-raised', '--bg-sunken'];

		// Body-size text: headings, body, links, secondary lines, medals and outcomes.
		it.each(['--ink', '--text', '--accent', '--muted', '--gold', '--silver', '--bronze', '--win', '--loss', '--todo'])(
			'%s reads at 4.5:1 on every surface',
			(token) => {
				for (const surface of surfaces) {
					expect(contrast(theme[token], theme[surface]), `${token} on ${surface}`).toBeGreaterThanOrEqual(4.5);
				}
			}
		);

		it('--faint, large text only, reads at 3:1 on every surface', () => {
			for (const surface of surfaces) {
				expect(contrast(theme['--faint'], theme[surface]), surface).toBeGreaterThanOrEqual(3);
			}
		});

		it('--bg reads at 4.5:1 on an accent fill (buttons, the ORGA pill)', () => {
			expect(contrast(theme['--bg'], theme['--accent'])).toBeGreaterThanOrEqual(4.5);
		});
	});
});
