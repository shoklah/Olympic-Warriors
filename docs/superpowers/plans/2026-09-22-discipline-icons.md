# Discipline Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan inline; the drawing is done directly, not delegated. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hand-drawn white SVG icons for the seven discipline models that still fall back to the star, with a test that keeps every model covered.

**Architecture:** Seven SVG files dropped into `front/src/lib/img/icons/` are picked up by the existing `import.meta.glob` in `icons.js`; no code change. A contact sheet in the scratchpad previews them in the browser before commit. One test change and one new test.

**Tech Stack:** SVG, Vitest, the built-in browser for the preview.

**Spec:** `docs/superpowers/specs/2026-09-22-discipline-icons-design.md`

---

Worktree: `/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/edition-aware-front`, branch `claude/edition-aware-front` (the open PR #61).

### Task 1: Coverage test (fails first)

**Files:**
- Modify: `front/src/lib/icons.test.js`
- Modify: `front/src/lib/components/EditionHub.test.js`

- [ ] **Step 1: Add the coverage test** to `icons.test.js`:

```js
/** Every `self.name = '...'` in server/olympic_warriors/models/*.py. Keep in sync by hand. */
const DISCIPLINE_NAMES = [
	'Basketball',
	'Blindtest',
	'Crossfit',
	'Darts',
	'Dodgeball',
	'Fair',
	'General Culture Quizz',
	'Geography Quizz',
	'Hide and Seek',
	'Obstacle Course',
	'Orienteering',
	'Petanque',
	'Relay',
	'Rugby'
];

describe('every discipline model has an icon', () => {
	it.each(DISCIPLINE_NAMES)('%s', (name) => {
		expect(iconFor(name)).not.toMatch(/default\.svg$/);
	});
});
```

- [ ] **Step 2: Flip the hub assertion** in `EditionHub.test.js`: Relay's `src` matches `/relay\.svg$/`.
- [ ] **Step 3: Run `npm test`**: expect 7 failures in `icons.test.js` (the seven missing) and 1 in the hub test.

### Task 2: Draw the seven icons

**Files:** create `front/src/lib/img/icons/{relay,basketball,petanque,fair,obstaclecourse,geographyquizz,generalculturequizz}.svg`.

- [ ] **Step 1:** each file: `<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">`, white filled shapes (`fill="white"`), strokes only for thin lines, `stroke="white"`, silhouettes at least 120 units thick.
- [ ] **Step 2:** write a contact sheet `scratchpad/icons.html` that inlines all fourteen SVGs at 100 px on black and at 70 px on `#F9F3C1`, open it in the browser pane, screenshot, adjust until every icon reads.
- [ ] **Step 3:** `npm test` → all green (the new coverage test and the hub test pass).

### Task 3: Docs and commit

**Files:** modify `CLAUDE.md`.

- [ ] **Step 1:** in the Frontend section replace the "(today: blindtest, …, rugby)" list with "every discipline model has one and `icons.test.js` fails when a new model lacks one"; in step 5 of "Adding a discipline" say the same.
- [ ] **Step 2:** commit the SVGs and tests as `[FEAT] front: icons for the seven remaining disciplines`, then CLAUDE.md as `[DOCS] CLAUDE.md: every discipline has an icon`, both with the Co-Authored-By trailer. Push.
