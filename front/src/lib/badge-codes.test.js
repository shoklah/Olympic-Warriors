import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import * as codes from './badge-codes.js';
import * as badges from './badges.js';

// Vitest runs from the front root.
const source = (path) => readFileSync(path, 'utf8');
/** The code alone, comments left out (they may name what the module must not do). */
const code = (path) => source(path).replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
const imports = (path) => [...source(path).matchAll(/^import\b[^;]*?from\s+'([^']+)'/gm)].map((m) => m[1]);

describe('badge-codes', () => {
	it('is what badges.js re-exports, so either import gives the same catalogue', () => {
		expect(badges.BADGES).toBe(codes.BADGES);
		expect(badges.isKnownBadge).toBe(codes.isKnownBadge);
		expect(badges.isTiered).toBe(codes.isTiered);
	});

	// badges.js bundles every glyph (import.meta.glob, inlined as data URIs): a page that
	// only needs a name or a code check must not download them through players.js.
	it('imports nothing, so it never carries the glyphs', () => {
		expect(imports('src/lib/badge-codes.js')).toEqual([]);
		expect(code('src/lib/badge-codes.js')).not.toMatch(/import\.meta\.glob|\.svg/);
	});

	it('is where players.js, loaded by the ranking and team pages, takes its badge checks', () => {
		const from = imports('src/lib/players.js');
		expect(from).toContain('$lib/badge-codes');
		expect(from.filter((path) => /(^|\/)badges(\.js)?$/.test(path))).toEqual([]);
	});
});
