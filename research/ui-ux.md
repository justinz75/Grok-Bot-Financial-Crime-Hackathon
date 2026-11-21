# UI/UX research for Track 2

Researched on 21 Nov 2026. Sources: Diligent's site, docs and YC launch pages; the event site, its Track 2 brief and submit page; computed styles read from both live sites.
## 1. What the hackathon actually asks for

- **The scored deliverable has no UI.** It's a command-line program (`system/run <data> <out>`, standard libraries only, models via OpenRouter only), plus `output/dev.jsonl` and a README. "UX" in this deliverable means:
  - the `reason` text: 2–4 sentences naming the decisive facts
  - the `evidence` IDs, so every decision can be traced
  - a README a judge can follow, with a diagram and three explained cases
- **Where a visual UI does count:**
  - the **2-minute video**, which every team submits
  - the **optional live demo link**
  - the **3-minute live demo** if we make the Top 5
- The judging criteria are execution, working prototype, solves the problem, creativity and UX. No weights are given. Judges also read the code, and an automatic repo analysis runs on the latest commit.
- So a review viewer is worth building only as a thin, separate layer that reads `output/dev.jsonl` and the data files. It must not be inside `system/`, which has to stay standard-library only.

## 2. The organisers' own visual language

The event site's worked example (John Doe, six steps) shows the presentation style the organisers find natural. Copy its structure:

- **A plain-English question as the card heading:** "Is this the same person?", "Should we take him on?", "Should we report this?"
- **A case ID chip** on every card (`SCR-77102`, `APP-20431`).
- **A side-by-side comparison:** "Our customer" on one side, the list entry on the other. One row per attribute (Name, Born, Nationality, Job, Photo), each with a short outcome tag: "Similar", "21 yrs apart", "Differs", "No match".
- **One result pill** at the bottom: "Different person · cleared", "Low risk · accepted", "Suspicious · escalated". The verdict comes first, with its consequence after the dot.
- **Short status tags everywhere** ("Pass", "Low", "Clear", "Unusual"), and evidence written as plain sentences ("Same phone logs in to 2 other accounts").

The event site's look: dark background (`#0A0A0A`), light text (`#EDEDED`), Geist Sans with Geist Mono for IDs and code, and a burnt-orange accent (`#CC5533`).

## 3. What Diligent likes

**Values they repeat** (site, about page, docs):

- "Every output should be explainable, auditable, and defensible."
- "Structured reasoning" and "a clear, defensible audit trail".
- "Keep humans in the loop", and "analyst review until you're comfortable scaling automation".
- "Stop data processing. Start investigating." They pitch the agent as "a new employee added to your team".
- On the event site: "We use language models to codify and automate risk operations", with steps ending in "Run as code", and the tagline "Frontier intelligence. Bank-grade precision."
  - Their pitch contrasts "armies of analysts" (nuanced, but slow) with "rigid rules" (fast, but they miss nuance).
  - Our UI should show both halves: the rules decide, and the model's reading is visible and cited.

**How their screening product presents a decision** (name screening docs; no screenshots are public):

- A determination plus a confidence score and a human-readable explanation, for example "FALSE_POSITIVE (Score: 0/100)".
- Each piece of evidence has a **direction and a strength**: "MATCH (STRONG)", "MATCH (MODERATE)", "MISMATCH (STRONG)".
- The rule "strong contradicting evidence (temporal impossibility) → immediate false positive" is spelled out.
- Per-category policy: auto-resolve, or comment only so that a human decides.
- Comments written back carry a "Diligent AI: " prefix, and existing analyst comments are kept.
- Statuses: `UNREMEDIATED`, `PENDING_SYNC`, `REMEDIATED_SYNCED`, `REMEDIATED_UNSYNCED`. Their app also labels absent evidence "Missing information".

**Their look** (computed styles from godiligent.ai):

| Token                 | Value                                                                       |
| --------------------- | --------------------------------------------------------------------------- |
| Font                  | **DM Sans** (Google Fonts, weights 300–700) for everything; body 16–18px, H1 48px weight 500 |
| Background            | White `#FFFFFF`; a faint indigo tint `#F9F9FF` for sections                 |
| Text                  | Black `#000000`; secondary grey `#9A9A9A`; near-black `#1F1F1F`             |
| Accent                | One indigo, **`#5251FA`**, also used at about 3% opacity as a wash          |
| Lines and fills       | Grey at low opacity (`rgba(146,146,146,0.06)`, `rgba(138,138,138,0.5)`)     |
| Feel                  | Light, monochrome, lots of white space, one accent colour. Their portal is Next.js and probably MUI. |

**Recommendation:** make the viewer look like Diligent's product, not like the event site: light theme, DM Sans, black and grey, indigo `#5251FA` as the only accent. Add a monospace face (DM Mono or Geist Mono) for record IDs.

## 4. Good UX for an alert-review tool

These principles come from analyst case-management practice, applied to this task:

1. **Verdict first, evidence second.** Top of the card: the decision pill, the reason code, and the 2–4 sentence reason. The analyst should know the answer in 3 seconds and see why in 10.
2. **Compare side by side, row by row.** Customer (as resolved) next to the hit, one row per attribute: name, date of birth, country, entity type, dates of reports or death. Each row gets a status: agrees, contradicts, missing, not used.
   - Mirror Diligent's direction and strength ("MISMATCH · STRONG") and the event site's short tags ("21 yrs apart").
   - Show **which row decided it**, and mark it.
3. **Every fact links to its record.** Show the source record ID next to each value (`KYC-…`, `NOTE-…`, `SR-…`), in monospace. Clicking it opens the raw record. That's the audit trail, and it's what the brief's `evidence` field is for.
4. **Make "missing" explicit.** An absent date of birth isn't a blank cell. Show "Missing information" and say where we looked. That justifies every `REVIEW`.
5. **Show how the customer was found.** Draw the link path: alert → account → customer → onboarding → KYC check. Mark the path used: direct link, email, login, or fuzzy match on name and date of birth. For `AMBIGUOUS_CUSTOMER_RECORD`, list the candidates side by side and show why they disagree.
6. **Verified beats declared, visibly.** When the KYC check overrides a declared field, show both, with the verified one marked and the rejected or expired checks greyed out.
7. **Colour carries meaning, never on its own.**
   - `DIFFERENT_ENTITY`: neutral or green, "Different · cleared".
   - `REVIEW`: amber, "Needs review".
   - `SAME_ENTITY`: red, "Same person · to compliance".
   - Always pair colour with a word and an icon (colour-blind safe, prints in greyscale). Keep the indigo accent for interactive elements only.
8. **Queue view above the card view.**
   - One row per alert, with its hits rolled up. Remember an alert is cleared only if every hit is `DIFFERENT_ENTITY`.
   - Counts by decision and reason code at the top.
   - Filters for decision, reason code and "how the customer was found".
   - Sort `REVIEW` first, as an analyst would.
9. **Show it can be trusted.** A small header strip with the run ID, model and prompt version, the time and cost of the run, and the practice-label score (and how many runs agreed, if we test that). The UBS judge runs testing and assurance; consistency and measurement are what he'll look for.
10. **Dense but calm.** Analysts read many cases, so use compact rows and generous line height in the reason text, with one accent colour. Keyboard shortcuts (j/k for next and previous, enter to open) are a cheap win.
11. **Plain English over codes.** Show `DOB_MISMATCH` as "Birth years 21 apart", with the code underneath in small monospace.

## 5. Plan for the 2-minute video (where UX is actually judged)

- **0:00–0:15:** the headline. The practice-label score and how decisions split across the dev set, on one screen.
- **0:15–1:15:** three cases, the same three the README must explain:
  - a clear mismatch, ideally a temporal impossibility or birth years far apart
  - a match: name and date of birth agree, with a verified KYC check
  - a review: missing information or an ambiguous customer, showing the system declining to guess
- **1:15–1:45:** how it works. The diagram: link the customer → gather the hit's facts → rules from `POLICY.md` decide → the model reads only free text (notes, search results), and every quote is checked.
- **1:45–2:00:** consistency (same results every run), cost and time per run, and what it can't do.

## 6. Skills for building the UI

These are already enabled on this account, so every session can use them:

- **impeccable:** design, critique, audit and polish. Covers hierarchy, typography, colour, accessibility, empty and error states, and design tokens. Use it when building and reviewing the viewer.
- **emil-design-eng:** interaction polish and motion (easing, transitions, how components feel). Use it sparingly; this is a calm analyst tool.
- **dataviz:** for the headline chart (decision split, score) and any stat tiles.

A search of the skills catalog found nothing further relevant.
