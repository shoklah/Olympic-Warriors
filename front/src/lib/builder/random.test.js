import { describe, expect, it } from 'vitest';
import { newSeed, rng, shuffled } from './random.js';

describe('rng', () => {
	it('gives the same sequence for the same seed and stays in [0, 1)', () => {
		const a = rng(42);
		const b = rng(42);
		const first = [a(), a(), a()];
		expect(first).toEqual([b(), b(), b()]);
		expect(first.every((x) => x >= 0 && x < 1)).toBe(true);
		expect(rng(43)()).not.toBe(first[0]);
	});
});

describe('shuffled', () => {
	it('is a permutation, reproducible per seed, and leaves its input alone', () => {
		const input = [1, 2, 3, 4, 5, 6];
		const out = shuffled(input, rng(1));
		expect([...out].sort()).toEqual(input);
		expect(shuffled(input, rng(1))).toEqual(out);
		expect(input).toEqual([1, 2, 3, 4, 5, 6]);
	});
});

describe('newSeed', () => {
	it('is a non-negative integer below 2**31', () => {
		for (let i = 0; i < 20; i++) {
			const seed = newSeed();
			expect(Number.isInteger(seed) && seed >= 0 && seed < 2 ** 31).toBe(true);
		}
	});
});
