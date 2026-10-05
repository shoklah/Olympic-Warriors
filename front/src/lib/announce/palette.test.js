import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { PALETTE } from './palette.js';

const css = readFileSync(resolve(process.cwd(), 'src/routes/styles.css'), 'utf8');
const dark = css.slice(css.indexOf(':root {'), css.indexOf('}', css.indexOf(':root {')));
const token = (name) => new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`).exec(dark)?.[1].toLowerCase();

describe('PALETTE', () => {
	it.each([
		['bg', '--bg'],
		['raised', '--bg-raised'],
		['sunken', '--bg-sunken'],
		['line', '--line'],
		['ink', '--ink'],
		['text', '--text'],
		['muted', '--muted'],
		['accent', '--accent'],
		['gold', '--gold']
	])('%s is the dark theme token %s', (key, name) => {
		expect(token(name), name).toBeDefined();
		expect(PALETTE[key].toLowerCase()).toBe(token(name));
	});
});
