# Player profile: badge collection

## Goal

The badges from #91 are shown today as one long list of tiles on the profile. 28 badges
make the list about 1,100px tall on desktop, and it pushes the editions down. This spec
turns them into a **collection**:
- a « Badges » tab on the profile;
- every badge of the catalogue in a slot, earned or locked, grouped by family with its
  progress;
- a detail sheet that opens on tap;
- a badge-count card next to the average-rank and signature-event cards.

A highlight of the best badges on the profile tab comes in a later step.

Decisions taken while brainstorming (2026-09-24):
1. **Collection progress first**, and the highlight later.
2. **A tab** on the profile, not a separate page.
3. **Locked badges stay visible**, with their name and rule, so the collection shows how
   to earn each one.
4. **Tiered badges show the tier reached and the next goal**, read from the catalogue.
   No live counters.
5. **Compact slots** (medallion and name), with the details in a sheet opened on tap.
6. **A « Badges » card** next to « Classement moyen » and « Épreuve fétiche ».

This is front-end only. `/profile/<id>/` already carries the earned badges, and
`src/lib/badges.js` already knows all 63 codes.

## Definitions

- **Slot.** One per catalogue code (63 of them), in catalogue order inside its family.
- **Entries of a slot.** The profile's `badges` entries with that code. There can be
  several: one per discipline (`specialist`, `unbeaten`, `perfect-run`, `steamroller`) or one per partner
  (`comrades`). Codes the front doesn't know are ignored, as today.
- **Earned.** A slot is earned when it has at least one entry. A tiered badge is earned
  from tier 1.
- **Count ("×N").** The number of times the slot was earned:
  - a tiered entry counts 1;
  - any other entry counts `max(1, years.length)`;
  - the count is the sum over the slot's entries.

  The chip only shows when the count is above 1. For example, Champion in 2021 and 2024
  gives ×2, Specialist in Rugby and Crossfit gives ×2, and three comrades give ×3.
- **Slot medallion.**
  - Earned: the entry with the highest tier, else the first entry, drawn by `Badge.svelte`
    as today. That keeps the metal, the pips and the specialist discipline icon.
  - Locked: `Badge.svelte` with `locked` set: a dashed `--ghost` ring, the glyph at 0.35
    opacity and no metal. A locked specialist shows the fallback glyph.
- **Progress.**
  - Overall: `earned / 63`.
  - Per family: earned slots out of that family's slots.
- **Families**, in this order. The two lists match the catalogue and must cover every code
  exactly once:

  | Key | FR | EN | Codes |
  |---|---|---|---|
  | `podiums` | Palmarès | Podiums | champion, runner-up, bronze, chocolate, wooden-spoon |
  | `streaks` | Séries | Streaks | back-to-back … lucky-charm (13) |
  | `loyalty` | Fidélité | Loyalty | rookie, veteran, argonaut, ever-present, homecoming, globetrotter |
  | `teammates` | Coéquipiers | Teammates | comrades, networker |
  | `hall-of-fame` | Panthéon | Hall of fame | goat … rocket (7) |
  | `disciplines` | Épreuves | Disciplines | specialist … photo-finish (8) |
  | `olympus` | Olympe | Olympus | athena … olympus (10) |
  | `games` | Matchs | Games | unbeaten … perfect-pitch (6) |
  | `awards` | Distinctions | Awards | mvp, fair-play, hype, costume, wounded, torchbearer |

- **Tier thresholds**, in the front catalogue, mirroring `badges.py`:

  | Code | Thresholds | Unit |
  |---|---|---|
  | `veteran` | 3, 5, 10 | editions |
  | `ever-present` | 4, 6, 8 | editions in a row |
  | `networker` | 20, 40, 60 | teammates |
  | `specialist` | 2, 3, 4 | titles in the discipline |
  | `all-rounder` | 3, 5, 8 | disciplines won |
  | `golden-whistle` | 5, 10, 20 | games refereed |

  - **Next goal of a tiered entry:** the threshold of `tier + 1`, or none at tier 3.
  - **First goal of a locked tiered slot:** the tier 1 threshold.
  - **Tuning a threshold** now means changing `badges.py`, both dictionaries' rules, and
    this table.

## Front

### `src/lib/badges.js`

New exports:
- `FAMILIES`: an ordered list of `{ key, codes }`.
- `TIER_THRESHOLDS`: `code → [t1, t2, t3]`.
- `badgeCollection(badges)`: builds the collection from the profile's `badges`:
  - it returns `{ earned, total, families: [{ key, earned, total, slots: [{ code, entries, count, medal, earned }] }] }`;
  - `medal` is the entry to draw, or `{ code, tier: 0, years: [], discipline: null, partner: null }` for a locked slot;
  - unknown codes are ignored.
- `nextThreshold(code, tier)`: the next threshold, or `null` at tier 3. For a locked
  tiered slot, `tier` is 0, so it returns the first threshold. It returns `null` for an
  untiered code.

### `Badge.svelte`

Gains a `locked` prop, false by default. When set:
- the ring is dashed in `--ghost`;
- there is no inner ring;
- the glyph sits at 0.35 opacity;
- the pip row stays, with every pip unfilled on a tiered code, so the sizes still line up.

### `BadgeCollection.svelte`

Props: `collection`, the page's `badgeCollection(profile.badges ?? [])`, computed once and
shared with the count card.

It renders:
- the overall line « 28 badges sur 63 » / "28 badges out of 63", a progress bar
  (decorative, `aria-hidden`; the line says the same thing), and the percentage;
- for each family:
  - a heading (`h3`, `.label`) with the family name and `earned/total` in the same heading,
    e.g. `Palmarès 4/5`;
  - a grid of slots, `repeat(auto-fill, minmax(4.75rem, 1fr))`: 4 per row on a 375px
    phone, 3 at 320px.

  The collection opens with a visually hidden `h2` « Badges », so the headings go
  h1 → h2 → h3. The family fraction is `aria-hidden`, next to a spoken « 3 sur 5 ».

Each slot is a `<button type="button">`:
- the medallion at 48px, with a "×N" chip in the medallion's corner when `count > 1`;
- the name, `badge.<code>.name`, small, with ellipsis on two lines at most;
- an accessible name made of the name and a status:
  - « Champion, badge obtenu 2 fois » / "Champion, badge earned 2 times" (a plural key);
  - « Cuillère de bois, badge à débloquer » / "Wooden spoon, badge locked".

  The phrasing uses « badge » so that French agreement never depends on the badge's gender.
- locked slots show their name in `--muted`.

Tapping a slot opens `BadgeSheet` for it. Closing the sheet returns focus to that slot.

### `BadgeSheet.svelte`

The same shell as the organiser `ScoreSheet`: a backdrop, `role="dialog"`,
`aria-modal="true"`, `aria-labelledby` pointing at its title, Escape and the backdrop
close it, and it takes focus when it opens. Tab and Shift+Tab cycle inside it, and the
page behind it doesn't scroll while it is open (jsdom has no `showModal`, so the trap is
hand-written rather than a native `<dialog>`). It is a bottom sheet below 1000px and a
centred dialog above. Props: `slot` and `open`; it dispatches `close`.

Content:
- the medallion at 64px, the name as the title (`h2`), and the status line:
  « Badge obtenu · ×2 » or « Badge à débloquer »;
- the rule, `badge.<code>.rule`;
- **earned:** one line per entry:
  - the discipline and partner (a link to their profile) when there is one;
  - the tier and years, as `badgeDetail` gives them, without its `×N` part: the status
    line already says it;
  - for a tiered entry, then: « Prochain niveau : 5 éditions » / "Next tier: 5 editions",
    or « Niveau maximum » / "Top tier" at tier 3;
- **locked tiered:** « Premier niveau : 3 éditions » / "First tier: 3 editions";
- a close button « Fermer » / "Close".

### Profile page (`/players/<id>`)

- **Tabs.** Under the position line, a `nav` labelled « Sections du profil » / "Profile
  sections":
  - two links, « Profil » / "Profile" (`?`, no parameter) and « Badges » (`?tab=badges`);
    the tab label carries no count (Hugo, 2026-09-24): the count card and the collection
    show it;
  - the current one has `aria-current="page"`;
  - they're plain links with `data-sveltekit-noscroll` and `data-sveltekit-keepfocus`, so
    they work without JavaScript and can be shared, and the page's load doesn't re-run;
  - the page reads the tab from `$page.url.searchParams`, and any other value means
    Profil.
- **Profil tab** holds what the page shows today, except the badges list:
  - the figures;
  - the counts;
  - Éditions;
  - Par épreuve.
- **Badges tab** holds `BadgeCollection`, and nothing else from the profile.
- **Figures:** a third card, `data-testid="badge-count"`:
  - a link to `?tab=badges`, labelled `profile.badges`;
  - a large `28` with a muted `/ 63`;
  - a thin progress bar;
  - the visually hidden text « voir la collection » / "see the collection" after the
    visible text, so the accessible name starts with what is shown (WCAG 2.5.3).
- **Figures layout:**
  - From 600px: three columns of at most 14rem each.
  - Below 600px: two columns. « Classement moyen » and « Badges » share the first row, and
    « Épreuve fétiche » spans the second (`grid-column: 1 / -1`, `order: 3`). The reading
    order in the DOM stays average, signature event, badges.
  - The < 360px stacking rule from #90 goes: two columns fit at 320px.
- **The old badges section** and its tile styles are removed; the collection replaces
  them.

### i18n (fr / en, kept at parity)

- `profile.tabs`: « Sections du profil » / "Profile sections".
- `profile.tab.profile`: « Profil » / "Profile".
- `profile.tab.badges`: « Badges » / "Badges".
- `profile.seeCollection`: « voir la collection » / "see the collection".
- `badge.progress`: a plural over `{n}` (earned), « {n} badge sur {total} » / « {n} badges sur
  {total} » (0 is singular in French), "{n} badge out of {total}" / "{n} badges out of {total}".
- `badge.family.<key>` for the nine families.
- `badge.earned` « badge obtenu » / "badge earned", and `badge.locked` « badge à
  débloquer » / "badge locked".
- `badge.statusEarned` « Badge obtenu » / "Badge earned", and `badge.statusLocked`
  « Badge à débloquer » / "Badge locked".
- `badge.next.<code>` and `badge.first.<code>` as plural messages over `{n}` for the six
  tiered codes, for example « Prochain niveau : {n} éditions » and « Premier niveau :
  {n} éditions ».
- `badge.topTier`: « Niveau maximum » / "Top tier".
- `badge.close`: « Fermer » / "Close".

`profile.badges` stays: it is the card label.

## Testing

- **`badges.test.js`:**
  - `FAMILIES` covers every `BADGES` code exactly once, in catalogue order inside each
    family;
  - `TIER_THRESHOLDS` has exactly the six tiered codes;
  - `badgeCollection`: the earned and total counts, the per-family counts, the count
    rules (a tiered entry, repeated years, several disciplines, several partners), the
    medal entry chosen by highest tier, a locked medal stub, and unknown codes ignored;
  - `nextThreshold`: tier 0 gives t1, tier 1 gives t2, tier 3 gives null, an untiered
    code gives null.
- **`Badge.test.js`:** `locked` draws the dashed ring class and unfilled pips.
- **Collection component tests:**
  - the progress line;
  - the family headings with their counts;
  - 63 slots;
  - the accessible names for an earned slot and a locked one;
  - the ×N chip;
  - clicking a slot opens the sheet, whose content covers entry lines, partner link,
    next goal, top tier and a locked first goal;
  - Escape closes the sheet and gives focus back to the slot;
  - one French test.
- **Profile page tests:**
  - the tabs, with `aria-current` following `?tab=badges`;
  - the Profil tab has no badge slots, and the Badges tab has the collection and no
    Éditions;
  - the badge-count card: its text, link and accessible name;
  - the old badges-section tests are replaced.

## Out of scope

- The highlight of the best badges on the Profil tab, and rarity.
- Live counters towards the next tier.
- Badges on the leaderboard rows, and a public catalogue page.
