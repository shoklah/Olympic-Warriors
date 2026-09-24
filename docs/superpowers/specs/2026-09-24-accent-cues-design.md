# Accent cues — design

Date: 2026-09-24

## Problem

`--accent` is the brand colour: cream on black in the dark theme, near-black on
warm paper in the light one. It is almost the colour of the body text in both
(1.06:1 dark, 1.16:1 light), so wherever the accent alone marks a piece of text
against body text, nobody can see the difference (WCAG 1.4.1). An audit of the
rendered pages found two such places:

- **The own team on the team page's game rows.** In a draw or a game played
  without a score, the own team (accent) and the opponent (`--text`) differ by
  colour alone. A win or a loss also changes weight and opacity, so those read.
  The opponent is a link styled as text, so the colours even pointed the wrong way.
- **Links among text.** The profile's edition year (accent) and team (`--text`)
  are both links, told apart from text by colour only, or not at all; the
  discipline schedule's team names are links styled as text.

The accent's other uses are fine: fills, borders and focus rings contrast with
the surface, and the current tab, breadcrumb item and language segment stand
against `--muted` neighbours.

## Why not a colour

Text told apart by colour alone needs 3:1 against the body text (technique G183)
and 4.5:1 against the page. In the light theme, `--text` `#2a2718` and `--bg`
`#f5f2e8` leave no room: 3:1 from the text needs a relative luminance of at
least 0.160, 4.5:1 on the page at most 0.158. In the dark theme the window is
0.207 to 0.243, a single mid tone. And every free hue is taken: gold, silver
and bronze for medals, green, red and blue for outcomes. So the cue is a shape,
and the palette does not change.

## Decisions

Chosen from prototypes on the real pages (marker dot, outlined tag, weight):

- **Own team: a dot** on the outer side of its name (before it on the left,
  after it on the right), `0.45em`, in the name's colour, so a lost game fades
  it with the name. Drawn by `GameRow`'s `.team.own::before` / `.team.own.right::after`;
  the win and loss styling is unchanged. The outlined tag was clearer but heavy
  on every row and looked like the real tags and buttons; bold alone failed in
  a loss, where both names are bold.
- **Links among text: `.quiet-link`**, a utility in `styles.css`: a 1px
  underline in `--faint` (3:1 on every surface, already pinned by
  `styles.test.js`), offset `0.22em`, turning accent on hover. On `GameRow`'s
  team links (discipline schedule, team page opponents), the profile's edition
  year and team links, and the badge partner link. `GameRow`'s `.team` and the
  profile's `.year` lose their `text-decoration: none`, which would override it.
- Links inside a box (cards, rows, pills, buttons) or a navigation keep no
  underline: the box is the cue. The profile's position line (« 3 général »,
  linking to the leaderboard) stands alone under the title and keeps its hover
  cue only.

## Tests

`GameRow.test.js` pins `quiet-link` on the team links and its absence on the
own team (which is no link, and carries `own`, the dot's hook). The profile's
`page.test.js` pins it on an edition row's two links and the badge partner.
The dot and the underline are CSS: they were checked in Chromium in both
themes at phone width, and a link audit of the rendered pages found no other
unboxed link outside a navigation without an underline.
