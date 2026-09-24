# Profile Badge Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- A « Badges » tab on the player profile showing all 63 badges as a collection (earned or locked, grouped into nine families with progress, a detail sheet on tap);
- a badge-count card next to the average-rank and signature-event cards.

**Architecture:**
- Front only. The profile payload already carries the earned badges, and `src/lib/badges.js` knows every code.
- New pure helpers in `badges.js`: `FAMILIES`, `TIER_THRESHOLDS`, `badgeCollection`, `nextThreshold`.
- `Badge.svelte` gains a `locked` style.
- Two new components: `BadgeCollection.svelte` and `BadgeSheet.svelte`.
- The profile page gets tabs (`?tab=badges` links), the third card, and a relaid-out figures grid.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS), Vitest + @testing-library/svelte.

**Spec:** `docs/superpowers/specs/2026-09-24-profile-badge-collection-design.md` is the source of truth for wording, rules and layout.

---

## Rules for whoever executes this

- Branch `claude/profile-badges-collection`, main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`. Never switch branches, never `git stash`, never push, never `git add -A`.
- Never touch the dev database. This task needs no server; read-only curls against http://localhost:3003 and http://localhost:5173 are fine. The compose front serves this checkout with HMR; real profile: http://localhost:5173/players/39 has 28 badges.
- Front tests: `cd front && npx vitest run <paths>`, the whole suite with `npm test`, the build with `npm run build`.
- Test-first: write the tests, see them fail, implement, see them pass, commit. Commit messages end with a `Co-Authored-By` line.
- Conventions (CLAUDE.md, "Frontend architecture"):
  - Scoreboard tokens only, no hard-coded colours;
  - uppercase comes only from CSS (`.label`);
  - every string goes through `t`, and `fr.js` and `en.js` stay at parity;
  - `useT()` and `useLocale()` are called at init only;
  - page tests assert on text shapes, rendered through `renderWith`;
  - every translated surface has a French test.

---

### Task 1: Catalogue helpers, locked medallion, collection and sheet components

**Files:**
- `front/src/lib/badges.js`, `badges.test.js`
- `front/src/lib/components/Badge.svelte`, `Badge.test.js`
- Create `front/src/lib/components/BadgeCollection.svelte`, `BadgeCollection.test.js`, `BadgeSheet.svelte`
- `front/src/lib/i18n/fr.js`, `en.js`

- [ ] **Step 1: Tests for the helpers (`badges.test.js`)**

Add to `badges.test.js`:

```js
describe('FAMILIES', () => {
	it('covers every code exactly once, in catalogue order inside each family', () => {
		const codes = FAMILIES.flatMap((f) => f.codes);
		expect([...codes].sort()).toEqual(Object.keys(BADGES).sort());
		expect(new Set(codes).size).toBe(codes.length);
		const order = Object.keys(BADGES);
		for (const f of FAMILIES) {
			const idx = f.codes.map((c) => order.indexOf(c));
			expect(idx).toEqual([...idx].sort((a, b) => a - b));
		}
		expect(FAMILIES.map((f) => f.key)).toEqual([
			'podiums', 'streaks', 'loyalty', 'teammates', 'hall-of-fame', 'disciplines', 'olympus', 'games', 'awards'
		]);
		expect(FAMILIES.map((f) => f.codes.length)).toEqual([5, 13, 6, 2, 7, 8, 10, 6, 6]);
	});
});

describe('TIER_THRESHOLDS and nextThreshold', () => {
	it('lists the six tiered codes with the server thresholds', () => {
		expect(TIER_THRESHOLDS).toEqual({
			veteran: [3, 5, 10], 'ever-present': [4, 6, 8], networker: [20, 40, 60],
			specialist: [2, 3, 4], 'all-rounder': [3, 5, 8], 'golden-whistle': [5, 10, 20]
		});
		expect(Object.keys(TIER_THRESHOLDS).sort()).toEqual(Object.keys(BADGES).filter(isTiered).sort());
	});

	it('gives the next threshold, the first for a locked slot, and none at the top or untiered', () => {
		expect(nextThreshold('veteran', 0)).toBe(3);
		expect(nextThreshold('veteran', 1)).toBe(5);
		expect(nextThreshold('veteran', 2)).toBe(10);
		expect(nextThreshold('veteran', 3)).toBeNull();
		expect(nextThreshold('champion', 0)).toBeNull();
	});
});

describe('badgeCollection', () => {
	const entry = (code, extra = {}) => ({ code, tier: 0, years: [2026], discipline: null, partner: null, ...extra });

	it('counts earned slots overall and per family, ignoring unknown codes', () => {
		const c = badgeCollection([entry('champion', { years: [2021, 2024] }), entry('rookie'), entry('future-badge')]);
		expect(c.total).toBe(63);
		expect(c.earned).toBe(2);
		const podiums = c.families.find((f) => f.key === 'podiums');
		expect([podiums.earned, podiums.total]).toEqual([1, 5]);
		expect(c.families.reduce((n, f) => n + f.slots.length, 0)).toBe(63);
	});

	it('counts repeats, disciplines and partners, but a tier once', () => {
		const c = badgeCollection([
			entry('champion', { years: [2021, 2024] }),
			entry('specialist', { tier: 1, discipline: 'Rugby' }),
			entry('specialist', { tier: 2, discipline: 'Crossfit', years: [2025] }),
			entry('comrades', { partner: { id: 1, first_name: 'A', last_name: 'B' } }),
			entry('comrades', { partner: { id: 2, first_name: 'C', last_name: 'D' } }),
			entry('comrades', { partner: { id: 3, first_name: 'E', last_name: 'F' } }),
			entry('veteran', { tier: 2, years: [2024, 2026] })
		]);
		const slot = (code) => c.families.flatMap((f) => f.slots).find((s) => s.code === code);
		expect(slot('champion').count).toBe(2);
		expect(slot('specialist').count).toBe(2);
		expect(slot('specialist').medal.discipline).toBe('Crossfit'); // highest tier drawn
		expect(slot('comrades').count).toBe(3);
		expect(slot('veteran').count).toBe(1);
		expect(slot('veteran').earned).toBe(true);
	});

	it('gives a locked slot a stub medal and no entries', () => {
		const slot = badgeCollection([]).families[0].slots[0];
		expect(slot).toEqual({
			code: 'champion', entries: [], count: 0, earned: false,
			medal: { code: 'champion', tier: 0, years: [], discipline: null, partner: null }
		});
	});
});
```

Run `cd front && npx vitest run src/lib/badges.test.js` and see the tests fail.

- [ ] **Step 2: Implement the helpers**

- Add `FAMILIES` (the spec's table), `TIER_THRESHOLDS`, `nextThreshold(code, tier)` and `badgeCollection(badges)` to `badges.js`, each with JSDoc in the file's style.
- `badgeCollection` groups the known entries by code and builds each family's slots in `FAMILIES` order.
- Count rule: a tiered entry counts 1, any other entry `max(1, years.length)`.
- Medal: the entry with the highest `badgeTier` for a tiered code, else the first entry. A locked slot gets the stub shown in the test.
- `earned` counts the slots with at least one entry.

Run the tests and see them pass.

- [ ] **Step 3: `Badge.svelte` `locked`**

- Test first in `Badge.test.js`: rendering `{ badge: { code: 'veteran', tier: 0, years: [] }, locked: true }` gives the root the class `locked`, and no `.pip.on`.
- Implement it:
  - `export let locked = false;`
  - `class:locked` on the root;
  - CSS: `.locked .medal { border-style: dashed; border-color: var(--ghost); }`, `.locked .medal::after { display: none; }`, `.locked img { opacity: 0.35; }`;
  - pips: none `on` when `locked`.

- [ ] **Step 4: i18n**

Add the spec's keys (section "i18n") to both dictionaries:
- `profile.tabs`, `profile.tab.profile`, `profile.tab.badges`, `profile.seeCollection`;
- `badge.progress`;
- `badge.family.<9 keys>`;
- `badge.earned`, `badge.locked`, `badge.statusEarned`, `badge.statusLocked`;
- `badge.next.<6 codes>` and `badge.first.<6 codes>` as `{ one, other }` plurals over `{n}`;
- `badge.topTier`, `badge.close`.

French wording: « Prochain niveau : {n} éditions », « {n} éditions de suite », « {n} coéquipiers », « {n} titres dans l'épreuve », « {n} épreuves gagnées », « {n} matchs arbitrés ». Use the `{ one, other }` forms sensibly; `n` is always 2 or more in practice. English mirrors them: "Next tier: {n} editions", etc. `parity.test.js` must pass.

- [ ] **Step 5: `BadgeSheet.svelte` and `BadgeCollection.svelte`, tests first**

**`BadgeCollection.test.js`**, rendered with `renderWith(BadgeCollection, { badges }, locale)` and a fixture list built inline: `champion` ×2 (2021, 2024), `veteran` tier 1 (2026), `specialist` Relay tier 1, a `comrades` entry with partner Léa Martin (id 12), and `future-badge`. Assert that:
- the text `4 badges out of 63` is shown (champion, veteran, specialist and comrades are the four known earned codes);
- the heading `Podiums 1/5` exists (`getByRole('heading', { name: /Podiums\s*1\/5/ })`), and so do `Loyalty 1/6` and `Teammates 1/2`;
- there are 63 slot buttons;
- the Champion button is named `Champion, badge earned, ×2` and shows `×2`, and the Wooden spoon button is named `Wooden spoon, badge locked`;
- clicking Veteran opens a dialog named `Veteran` containing `Badge earned`, the rule, `Tier 1 · 2026` and `Next tier: 5 editions`;
- clicking Comrades in arms shows a link `Léa Martin` → `/players/12`;
- clicking Networker (locked) shows `Badge locked` and `First tier: 20 teammates`;
- a tier 3 veteran shows `Top tier`;
- Escape closes the dialog and focus returns to the slot button;
- the French version shows `Palmarès 1/5`, `4 badges sur 63`, the button named `Cuillère de bois, badge à débloquer`, and `Prochain niveau : 5 éditions` in the sheet.

Implement the two components per the spec, sections "BadgeCollection.svelte" and "BadgeSheet.svelte":
- `BadgeSheet` copies the `ScoreSheet` shell (backdrop, `role="dialog"`, `aria-modal`, Escape, focus on open; a bottom sheet below 1000px and centred from 1000px) without the form. Its title `h2` is referenced by `aria-labelledby`.
- The entry lines reuse `badgeDetail(entry, t, locale)` for the parts, joined like the current profile tiles: the ` · ` separators are `aria-hidden`, and the partner link comes first.
- `BadgeCollection` holds `let openCode = null`, and remembers the button that opened the sheet, to focus it again on close.
- Slots: `repeat(auto-fill, minmax(5.5rem, 1fr))`, `--badge-size: 48px`. The ×N chip is `.num` on `--accent` with `--bg` text, in the medallion's corner. The name is on 2 lines at most (`-webkit-line-clamp: 2`).
- The progress bar is a `div` with a filled inner `div`, `aria-hidden`.

Run the component tests, then `npm test`.

- [ ] **Step 6: Commit**

`[FEAT] front: badge collection (families, locked slots, detail sheet)`, plus a Co-Authored-By line.

---

### Task 2: Profile tabs, badge-count card, figures layout

**Files:**
- `front/src/routes/players/[id]/+page.svelte`, `page.test.js`
- `front/src/lib/fixtures/players.js` (only if the tests need it)

- [ ] **Step 1: Tests first (`[id]/page.test.js`)**

The page reads `$page.url.searchParams`. Mock `$app/stores` the way `Header.test.js` does, with a store whose URL the test can set per case: use `vi.hoisted` for a mutable holder, or `vi.doMock` plus a dynamic import.

Tests:
- the tabs `nav` is named `Profile sections`, with links `Profile` (href `?` or the path without a query) and `Badges · 4/63` (href `?tab=badges`): the `profile` fixture has four known codes (veteran, comrades, specialist, clean-sweep) plus `future-badge`, which is ignored;
- without `tab`, `Profile` has `aria-current="page"`, the Éditions heading shows, and there are no slot buttons;
- with `?tab=badges`, `Badges …` has `aria-current`, the collection shows (the progress line and family headings), and there is no Éditions heading;
- the badge-count card (`getByTestId('badge-count')`) reads `/Badges\s*\d+\s*\/\s*63/`, links to `?tab=badges`, and its accessible name ends with `see the collection`;
- `profileUnranked` shows `0 / 63` in the card;
- French: `Profil`, `Sections du profil`, and `voir la collection` in the card's name.

Replace the old badges-section tests; the collection has its own tests now.

- [ ] **Step 2: Implement**

- **Script:**
  - `import { page } from '$app/stores';`, then `$: tab = $page.url.searchParams.get('tab') === 'badges' ? 'badges' : 'profile';`
  - `$: collection = badgeCollection(profile.badges ?? []);`
- **Markup:** the tabs `nav` after the position line. The links carry `data-sveltekit-noscroll` and `aria-current={tab === '…' ? 'page' : undefined}`, and are styled like the header tabs: display face, tracked, the current one in `--accent` with a 2px underline.
- **`{#if tab === 'badges'}`:** `<BadgeCollection badges={profile.badges ?? []} />`. **`{:else}`:** the current Profil content (figures, counts, Éditions, Par épreuve) with the old badges section removed.
- **Third card** in `.figures`:

```svelte
<a class="figure count-card" href="?tab=badges" data-sveltekit-noscroll data-testid="badge-count">
	<span class="label">{t('profile.badges')}</span>
	<span class="value"><span class="num">{collection.earned}</span> <span class="num total">/ {collection.total}</span></span>
	<span class="bar" aria-hidden="true"><span style="width: {(100 * collection.earned) / collection.total}%"></span></span>
	<span class="visually-hidden">{t('profile.seeCollection')}</span>
</a>
```

  An inline `style="width: …"` is allowed for a computed width: it isn't a colour.
- **Figures CSS:**
  - `.figures { grid-template-columns: repeat(3, minmax(0, 14rem)); }`
  - `@media (max-width: 599.98px) { .figures { grid-template-columns: repeat(2, minmax(0, 1fr)); } .figure[data-testid='best-discipline'] { grid-column: 1 / -1; order: 3; } }`
  - Remove the old < 360px stacking rule.
  - The card-link gets hover and `focus-visible` states that match the site: an accent border, and the usual outline.
- **Clean-up:** remove the old badges section's markup and styles (`.badges`, `.tile`, `.detail`, `.sep`, `.rule`) if nothing else uses them.

- [ ] **Step 3: Verify and commit**

- `cd front && npm test && npm run build`.
- Live checks on `/players/39`:
  - at 375px and 1280px, on both tabs: no horizontal scroll (`document.documentElement.scrollWidth === innerWidth`);
  - the sheet opens and closes;
  - the tab links switch without scrolling to the top.
- Commit: `[FEAT] front: profile tabs, badge-count card`, plus a Co-Authored-By line.

---

### Task 3: Docs and verification (coordinator)

- **`CLAUDE.md`:** in the front paragraphs, the profile's tabs, the badge-count card and `BadgeCollection`/`BadgeSheet`; in the `badges.js` description, `FAMILIES` and `TIER_THRESHOLDS`, with the three-place tuning note. Mark the #91 badge-section text as superseded.
- **Full suites:** front and build. The Django suite should be unaffected, but run it anyway.
- **Browser:** a profile with many badges and one with none, on both tabs, at 375px and desktop.

---

## Rarity (added 2026-09-24)

Spec: the "Rarity" section of `docs/superpowers/specs/2026-09-24-profile-badge-collection-design.md`. Same rules as above; Django tests run with `--noinput`.

### Task R1: Server, `badge_stats` on the profile

**Files:**
- Modify `server/olympic_warriors/badges.py` (`badge_stats`), `server/olympic_warriors/views.py` (`getProfile`) and `server/olympic_warriors/serializer.py` (`ProfileSerializer.badge_stats`).
- Tests go in `server/olympic_warriors/tests/test_profiles.py` or `test_badges.py`, whichever holds the profile badge tests.

- [ ] **Tests first.** Using the existing badge test setup (create `Badge` rows directly, test database only):
  - `badge_stats(ids)` counts each person once per code, whatever their disciplines, partners or years;
  - it ignores revoked rows (`is_active=False`), inactive editions, and people outside `ids`;
  - `tiers[code]` is the at-least-k count;
  - `players == len(ids)`;
  - `/profile/<id>/` carries `badge_stats` with that shape, and the profile's query pin becomes one more than today (e.g. `PROFILES_QUERIES + 2`);
  - `/profiles/` is unchanged.
- [ ] **Implement.** Build `badge_stats` from one `values_list("code", "user_id", "tier")` query. Tiered codes: reuse the server's own notion of tiered codes if `badges.py`/`Badge.Codes` has one, otherwise the six codes. Wire it into `getProfile` with the ids from the `leaderboard()` it already computes, and pass it to the serializer context. Update the `getProfile` OpenAPI summary.
- [ ] **Run and commit.** Run the whole Django suite with `--noinput`, then commit `[ADD] badges: badge_stats (holders per code and tier) on the profile` with a Co-Authored-By line.

### Task R2: Front, rarity lines in the sheet

**Files:**
- `front/src/lib/badges.js` (`badgeRarity`) and `badges.test.js`;
- `BadgeSheet.svelte`, and the `BadgeCollection`/`BadgeSheet` tests;
- `fr.js`, `en.js`;
- `front/src/lib/fixtures/players.js` (add `badge_stats` to `profile`);
- the profile page, to pass `profile.badge_stats` down.

- [ ] **Tests first.**
  - `badgeRarity`:
    - the normal case gives the rounded percent;
    - `holders > 0` rounding to 0 gives the under-1 % case, and 0 holders gives none;
    - a tier reads `tiers[code][tier - 1]`;
    - missing stats or 0 players give `null`.
  - Sheet:
    - an earned untiered badge shows `26% of players have it (12 of 47)`;
    - a locked badge with 0 holders shows `Nobody has it yet`;
    - an earned tiered badge at tier 2 shows the badge line and `6% at tier 2 or above (3 of 47)`;
    - without `badge_stats`, no rarity line appears;
    - in French, `26 % des joueurs l'ont obtenu (12 sur 47)` with a no-break space.
- [ ] **Implement** per the spec. Thread `badge_stats` from `+page.svelte` through `BadgeCollection` to `BadgeSheet`.
- [ ] **Run and commit.** Run `npm test` and `npm run build`, then commit `[FEAT] front: badge rarity in the detail sheet` with a Co-Authored-By line.
