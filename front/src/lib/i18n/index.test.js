import { describe, expect, it } from 'vitest';
import { I18N, disciplineName, t, translator } from './index.js';

describe('t', () => {
	it('returns the message of the locale', () => {
		expect(t('fr', 'nav.ranking')).toBe('Classement');
		expect(t('en', 'nav.ranking')).toBe('Ranking');
	});

	it('fills placeholders', () => {
		expect(t('en', 'game.referee', { name: 'Cerfs' })).toBe('ref: Cerfs');
		expect(t('fr', 'game.referee', { name: 'Cerfs' })).toBe('arbitre : Cerfs');
		expect(t('en', 'discipline.round', { n: 2 })).toBe('Round 2');
	});

	it('leaves an unknown placeholder in place', () => {
		expect(t('en', 'game.referee', {})).toBe('ref: {name}');
		expect(t('en', 'game.referee', { name: null })).toBe('ref: {name}');
		expect(t('en', 'game.referee', { name: undefined })).toBe('ref: {name}');
	});

	it('ignores inherited object keys', () => {
		expect(t('en', 'toString')).toBe('toString');
	});

	it('picks the plural form of the locale', () => {
		expect(t('en', 'discipline.games', { n: 1 })).toBe('1 game');
		expect(t('en', 'discipline.games', { n: 3 })).toBe('3 games');
		expect(t('en', 'discipline.games', { n: 0 })).toBe('0 games');
		expect(t('fr', 'discipline.games', { n: 1 })).toBe('1 match');
		expect(t('fr', 'discipline.games', { n: 3 })).toBe('3 matchs');
		expect(t('fr', 'discipline.games', { n: 0 })).toBe('0 match');
	});

	it('falls back to French for an unknown locale and to the key for an unknown key', () => {
		expect(t('de', 'nav.ranking')).toBe('Classement');
		expect(t('en', 'nope.nothing')).toBe('nope.nothing');
	});

	it('exposes the context key', () => {
		expect(I18N).toBe('i18n');
	});
});

describe('translator', () => {
	it('binds the locale', () => {
		const tr = translator('fr');
		expect(tr('nav.disciplines')).toBe('Épreuves');
		expect(tr('discipline.round', { n: 1 })).toBe('Tour 1');
	});
});

describe('disciplineName', () => {
	it('ignores inherited object keys', () => {
		expect(disciplineName('fr', 'constructor')).toBe('constructor');
	});

	it('translates a mapped discipline in French', () => {
		expect(disciplineName('fr', 'Relay')).toBe('Relais');
		expect(disciplineName('fr', 'Hide and Seek')).toBe('Cache-cache');
	});

	it('keeps the database name in English and for an unmapped discipline', () => {
		expect(disciplineName('en', 'Relay')).toBe('Relay');
		expect(disciplineName('fr', 'Rugby')).toBe('Rugby');
		expect(disciplineName('fr', 'Underwater Chess')).toBe('Underwater Chess');
	});
});
