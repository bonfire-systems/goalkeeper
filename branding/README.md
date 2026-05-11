# goalkeeper — brand assets

Ship-ready brand assets for the goalkeeper plugin. Drafts and alternates live in `~/Documents/context-relay/projects/goalkeeper/branding/`.

## Assets

| File | Use |
|---|---|
| `mark.svg` | Icon-only mark (64×64). Favicon, plugin-list rows, GitHub avatar. |
| `wordmark.svg` | Wordmark-only (480×96). Headers where the icon would be redundant. |
| `lockup.svg` | Mark + wordmark together (640×96). The "logo proper" — README, docs hero, presentations. |
| `social-card.svg` | OG image for link unfurls (1200×630). Twitter, Slack, Discord. |

## Color

- **Primary:** `#0E7C66` — deep teal-emerald. Approval/passing color, evokes a sports field.
- **Background light:** `#F5F5F4` (warm off-white).
- **Background dark:** `#0A0A0A` (near-black). Social card uses this.
- **Body text on dark:** `#F5F5F4` (off-white), `#9CA3AF` (gray-400 for subhead), `#6B7280` (gray-500 for footer).

## Typography

- **Wordmark:** monospace stack — `ui-monospace, 'JetBrains Mono', 'SF Mono', 'Cascadia Mono', Menlo, Consolas, monospace`. Lowercase, weight 600, letter-spacing tightened.
- **Headlines (social card):** system sans — `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif`. Weight 700, tight letter-spacing.

## Tagline

**"Set durable goals. Approve at the gate."** — README hero + social card headline.

## Converting SVG → PNG

GitHub README renders SVG inline (no conversion needed). For platforms that don't render SVG (Twitter card image, Slack OG preview), convert:

```bash
# Using rsvg-convert (brew install librsvg)
rsvg-convert -w 1200 -h 630 branding/social-card.svg > branding/social-card.png

# Using ImageMagick (brew install imagemagick)
magick branding/mark.svg -resize 256x256 branding/mark.png
```

## Don't

- Don't redraw the mark by hand for new sizes — the SVG is the source of truth.
- Don't add gradients, drop shadows, or 3D effects. The mark is flat and stays flat.
- Don't combine with non-`#0E7C66` accents in the same surface unless it's the status accents in product UI illustrations.

## Drafts and alternates

See `~/Documents/context-relay/projects/goalkeeper/branding/concepts.md` for:
- Concept B (stylized G with gate-bar descender) — recoverable
- Concept C (checkmark gate) — recoverable
- Tagline alternates beyond the shipped one
