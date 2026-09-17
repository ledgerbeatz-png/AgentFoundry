# AgentFoundry Design System

> **Forge your local intelligence.**

AgentFoundry combines a precise local-AI control surface with a restrained mythic visual identity inspired by Roman antiquity, digital deities, celestial diagrams, marble, bronze, and modern technical instrumentation.

The product UI must remain functional and readable first. The mythic layer adds atmosphere, identity, and memorability without turning the application into a game interface.

## Core visual direction

**Product layer:** dark, minimal, technical, calm, premium.

**Brand layer:** monumental, mythic, celestial, sculptural, digital.

**Brand formula:**

`Local AI + Classical Power + Digital Precision`

## Palette

### Foundation

| Token | Hex | Usage |
| --- | --- | --- |
| Obsidian | `#0A0D12` | Main app background |
| Midnight | `#0F1724` | Elevated panels / navigation |
| Graphite | `#171C25` | Cards, inputs, secondary surfaces |
| Border | `#273342` | Dividers and neutral outlines |
| Marble Mist | `#D7D9DD` | Primary light text |
| Ash | `#8B919A` | Secondary text |

### Signature accents

| Token | Hex | Usage |
| --- | --- | --- |
| Imperial Gold | `#C9A15A` | Primary brand accent, key controls |
| Antique Gold | `#E0C48A` | Fine borders, highlights |
| Digital Azure | `#69B7FF` | Holograms, active technical state |
| Quantum Violet | `#8D72FF` | Experimental AI / model activity |
| Electric Amber | `#F2B544` | Runtime activity / attention |
| Emerald | `#34D17A` | Healthy / ready / connected |
| Bronze Warning | `#C9833B` | Warning state |
| Critical | `#C94A4A` | Error / stop / destructive action |

### Color balance

- 80% dark neutral surfaces
- 15% text and structural neutrals
- 5% signature accents

Gold should feel scarce and intentional. It is a prestige signal, not a general fill color.

## Typography

### Interface

Use a clean modern sans-serif for everything operational.

Recommended direction:

- Segoe UI (native Windows fallback)
- Inter
- Manrope
- IBM Plex Sans

Use for navigation, buttons, tables, settings, model metadata, hardware metrics and status labels.

### Brand / hero typography

Use a restrained classical serif only for major brand moments.

Recommended direction:

- Cinzel
- Cormorant Garamond
- Playfair Display
- Libre Baskerville

Use for the AgentFoundry wordmark, splash screen, hero headings, release artwork and short mottoes.

**Rule:** UI speaks clearly. Branding speaks monumentally.

Do not bundle third-party font files in the repository without verifying redistribution rights.

## Digital deity art direction

The visual world may include male and female Roman-inspired figures, but they should read as **digital archetypes**, not literal religious depictions.

### Characteristics

- sculptural anatomy / marble or bronze surfaces
- subtle circuit paths or luminous data veins
- holographic celestial geometry
- restrained halos, orbit lines, constellations and star maps
- Roman architectural references: arches, pillars and carved stone
- dramatic but controlled rim lighting
- technology integrated into the sculpture rather than pasted on top

### Archetypal roles

Male figures may communicate:

- infrastructure
- guardianship
- structure
- execution
- power

Female figures may communicate:

- knowledge
- orchestration
- insight
- navigation
- strategy

Both should feel equally capable and central to the brand world.

## Mythic functional naming

Names are secondary labels, never replacements for clear functionality.

- **Minerva** — models, intelligence, model profiles
- **Vulcan** — runtime, inference engine, hardware tuning
- **Jupiter** — overall system / orchestration state
- **Hermes** — agents, tool calling, connections
- **Apollo** — benchmarks and performance

Example navigation treatment:

`Models · Minerva`

not simply:

`Minerva`

A new user should never need knowledge of mythology to use the application.

## UI language

### Panels

- near-black / midnight surfaces
- 1px low-contrast borders
- occasional thin gold edge on high-value panels
- restrained corner radius; avoid overly soft consumer-app styling
- subtle internal glow on active states

### Primary button

Preferred treatment:

- dark or Imperial Gold fill
- high contrast label
- restrained hover bloom

Examples:

- `Launch Stack`
- `Start Model`
- `Connect Hermes`

### Secondary button

- transparent / dark glass
- thin graphite or antique-gold border
- subtle hover elevation

### Status indicators

Status must remain instantly readable:

- Emerald = healthy / running
- Azure = connecting / active process
- Amber = attention / tuning
- Critical red = failure / stopped unexpectedly

Examples:

- Model: Loaded
- Runtime: Running
- Hermes: Connected
- Hardware: Optimized

### Logs

Logs should look technical, not decorative.

- true dark background
- monospace font
- timestamps in muted gray
- success / warning / error colors used sparingly
- user-selectable text
- no decorative artwork behind logs

## Layout rules

### Desktop app

Preferred architecture:

- left navigation rail
- central working canvas
- optional right contextual / status rail
- top runtime strip
- expandable logs area at bottom

Suggested sections:

1. Dashboard
2. Models
3. Runtime
4. Hardware
5. Agents
6. Downloads
7. Logs
8. Settings

### Dashboard composition

Prioritize:

- current model
- server status
- Hermes status
- GPU / RAM snapshot
- context window
- GPU layers / offload
- quick launch / stop controls

A faint sculptural or celestial motif may occupy unused negative space, but never behind dense controls or logs.

## Motion

Motion should feel deliberate and monumental.

Allowed:

- slow light sweeps
- subtle orbital rotation
- faint constellation drift
- restrained parallax
- 150–250 ms UI transitions

Avoid:

- glitch spam
- constant particles over controls
- rapid cyberpunk flicker
- game-like animated borders

## Image usage hierarchy

### Strong mythic treatment

Use for:

- GitHub hero artwork
- website landing hero
- release cards
- splash screen
- promotional artwork

### Subtle mythic treatment

Use for:

- application background texture
- empty states
- onboarding
- model cards
- about screen

### No decorative art

Prefer purely functional UI for:

- logs
- hardware detail tables
- advanced runtime arguments
- error dialogs

## Logo direction

The AgentFoundry mark should combine some of these ideas:

- forge / anvil geometry
- classical seal or laurel structure
- central compute core / chip
- subtle wing motif as a nod to Hermes
- celestial node network

Avoid robot heads, generic AI brains, meme aesthetics and cryptocurrency-style emblems.

The ideal result should feel like a seal from a future technical academy.

## Brand voice

Tone:

- calm
- exact
- capable
- confident
- slightly elevated

Preferred phrases:

- **Forge your local intelligence.**
- **Choose. Optimize. Launch.**
- **Local models. Full control.**
- **Modern tools. Ancient discipline.**
- **Your models. Your tools. Your machine.**

Avoid domineering, cult-like, fantasy-roleplay-heavy or unsubstantiated claims about intelligence, consciousness or autonomy.

## Product rule

> Mythology is the atmosphere. The interface is the instrument.

If a visual flourish makes model selection, configuration, logs, status, or troubleshooting harder to understand, remove the flourish.

## GitHub / website hero direction

Hero artwork should combine:

- AgentFoundry UI centered as the product
- dark monumental architecture
- one male and one female digital deity framing the composition
- subtle circuitry / data illumination
- restrained gold and azure accents
- enough negative space for product name and tagline
- no fake unreadable microtext
- no dense fantasy battle scene

Primary headline:

**AgentFoundry**

Tagline:

**Forge your local intelligence.**

Secondary line:

**Local model management, hardware-aware tuning and agent orchestration.**

## Current visual direction decision

The preferred direction combines:

1. A product-focused dark premium interface with Roman / classical accents.
2. A more expressive brand layer featuring balanced male and female digital deities.

The application itself should stay closer to direction 1. Marketing, splash and hero artwork may move closer to direction 2.
