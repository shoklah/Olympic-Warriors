import { describe, expect, it } from 'vitest';
import { emptyHistory, LIMIT, record, redo, undo } from './history.js';

describe('builder history', () => {
	it('has nothing to undo or redo at first', () => {
		expect(undo(emptyHistory(), 'now')).toBeNull();
		expect(redo(emptyHistory(), 'now')).toBeNull();
	});

	it('steps back and forward through the drafts', () => {
		let h = record(emptyHistory(), 'a'); // a -> b
		h = record(h, 'b'); // b -> c

		const back = undo(h, 'c');
		expect(back.draft).toBe('b');
		const back2 = undo(back.history, 'b');
		expect(back2.draft).toBe('a');
		expect(undo(back2.history, 'a')).toBeNull();

		const fwd = redo(back2.history, 'a');
		expect(fwd.draft).toBe('b');
		expect(redo(fwd.history, 'b').draft).toBe('c');
	});

	it('forgets the redo steps once something new is done', () => {
		const h = record(emptyHistory(), 'a');
		const back = undo(h, 'b');

		expect(record(back.history, 'a').future).toEqual([]);
	});

	it('makes one step of the edits sharing a key, until something else happens', () => {
		let h = record(emptyHistory(), 'a', 'perTeam'); // a -> b
		h = record(h, 'b', 'perTeam'); // b -> c, same step
		expect(h.past).toEqual(['a']);

		h = record(h, 'c'); // another kind of edit ends the run
		h = record(h, 'd', 'perTeam');
		expect(h.past).toEqual(['a', 'c', 'd']);
	});

	it('does not merge across an undo', () => {
		let h = record(emptyHistory(), 'a', 'perTeam');
		h = undo(h, 'b').history;
		h = redo(h, 'a').history;

		expect(record(h, 'b', 'perTeam').past).toEqual(['a', 'b']);
	});

	it('keeps the latest LIMIT steps', () => {
		let h = emptyHistory();
		for (let i = 0; i < LIMIT + 10; i++) h = record(h, i);

		expect(h.past).toHaveLength(LIMIT);
		expect(h.past[0]).toBe(10);
		expect(h.past.at(-1)).toBe(LIMIT + 9);
	});
});
