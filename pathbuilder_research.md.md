# Integrating with Pathbuilder 2e: a technical deep dive

Pathbuilder 2e exposes an **unauthenticated JSON API endpoint** at `https://pathbuilder2e.com/json.php?id={BUILD_ID}` that returns complete character data — and this is the definitive integration path for any third-party app. The developer, David Wilson (Redrazors), designed this system explicitly for third-party tools and built the first Foundry VTT import module himself. No formal API documentation exists, but the endpoint is stable, actively used by a dozen community projects, and returns a rich JSON payload covering stats, feats, spells, inventory, proficiencies, and pets. PDF parsing is not viable. The recommended architecture is straightforward: user exports JSON from Pathbuilder, receives a 6-digit ID, pastes it into your app, and your backend fetches the character data server-side.

## The JSON API endpoint is simple and proven

The core integration mechanism is a single REST endpoint:

```
GET https://pathbuilder2e.com/json.php?id={BUILD_ID}
```

**No authentication is required.** No API key, no OAuth, no session token. The endpoint accepts a numeric build ID (typically 6 digits) and returns `Content-Type: application/json`. The response wraps data in a success flag:

```json
{"success": true, "build": { ... }}  // Valid ID
{"success": false}                    // Invalid or expired ID
```

This endpoint was confirmed by examining the Pathbuilder developer's own Foundry VTT module source code (`Doctor-Unspeakable/foundry-pathbuilder2e-import`), which contains this exact fetch call:

```javascript
xmlhttp.open("GET", "https://www.pathbuilder2e.com/json.php?id=" + buildID, true);
```

**Important caveats:** Build IDs appear to be temporary and may expire after some period — an ID like `122550` that was once valid now returns 403. CORS headers are unconfirmed for browser-side requests; all known integrations (Foundry VTT, Discord bots) fetch server-side. Your backend should make the request, not the browser.

The **share link** feature uses a separate URL pattern — `https://pathbuilder2e.com/launch.html?build={BUILD_ID}` — which opens the character in Pathbuilder's web app. These share IDs and JSON export IDs may use different ID systems. For data extraction, use the `json.php` endpoint exclusively.

## The JSON schema covers everything a campaign tool needs

The exported JSON is comprehensive and well-structured. Below is the full schema reconstructed from live API responses and corroborated by parsing code across Pathmuncher, Build20, and the Kobold Discord bot:

| Category | Fields | Format |
|----------|--------|--------|
| Identity | `name`, `class`, `dualClass`, `level`, `ancestry`, `heritage`, `background`, `alignment`, `gender`, `age`, `deity` | Strings/numbers |
| Size | `size` (0–5 numeric), `sizeName` ("Medium", etc.) | Number + string |
| Ability scores | `abilities.str/dex/con/int/wis/cha` with full `breakdown` (ancestry, background, class, leveled boosts) | Numbers (final scores, not modifiers) |
| HP & Speed | `attributes.ancestryhp`, `classhp`, `bonushp`, `bonushpPerLevel`, `speed`, `speedBonus` | Numbers |
| Proficiencies | `proficiencies.classDC`, `perception`, `fortitude`, `reflex`, `will`, armor types, weapon types, casting traditions | 0/2/4/6/8 = Untrained/Trained/Expert/Master/Legendary |
| Skills | `acrobatics`, `arcana`, `athletics`, ... `thievery` (all 17 skills as top-level keys) | Same 0/2/4/6/8 encoding |
| Lores | `lores` array of `[name, proficiency]` tuples | Array |
| Feats | `feats` array with entries containing feat name, display name, source type, and level | Array |
| Spellcasters | `spellCasters` array with tradition, type (prepared/spontaneous), ability, proficiency, focus points, spells by level | Nested objects |
| Weapons | `weapons` array with name, die, potency rune, striking rune, material, damage type, attack bonus, damage bonus | Object array |
| Armor | `armor` array with name, proficiency category, potency, resilient, material | Object array |
| Equipment | `equipment` array, `specificItems` array | Arrays |
| Money | `money.pp`, `gp`, `sp`, `cp` | Numbers |
| AC | `acTotal.acProfBonus`, `acAbilityBonus`, `acItemBonus`, `acTotal`, `shieldBonus` | Numbers |
| Pets | `pets` array (animal companions, eidolons, familiars) with their own stat blocks | Object array |
| Other | `languages`, `resistances`, `rituals`, `specials`, `formula`, `inventorMods`, `keyability` | Various arrays |

**One notable gap**: for prepared spellcasters, the JSON exports all *known* spells but does **not** indicate which are currently prepared. Pathmuncher's changelog explicitly calls this out as a limitation. Your app would need to let users select prepared spells separately.

## Six community projects show exactly how to integrate

A rich ecosystem of open-source projects already parses Pathbuilder data. These are the most valuable references for implementation:

- **Pathmuncher** (`MrPrimate/pathmuncher`) is the gold standard — **28+ stars, 436 commits, actively maintained** through February 2026 (v7.10.1). This Foundry VTT module contains the most complete JSON parsing logic, handling feats, spells, equipment, pets, formulas, focus spells, and lores. MIT licensed. The `src/app/` directory contains all parsing logic and is the single best reference for understanding every JSON field.

- **Kobold** (`significantotter/kobold`) is a TypeScript Discord bot that imports characters by build ID and generates slash-command rolls for skills, saves, attacks, and spells. It also tracks initiative — directly relevant to your campaign tool's use case. This demonstrates server-side fetching and persistent character storage.

- **Build20** (`zmenciso/Build20`) is a Python tool converting Pathbuilder JSON to Roll20 macros. Its source shows clean Python parsing patterns for abilities, proficiencies, weapons, and spellcasters — useful if your backend is Python.

- **foundry-pathbuilder2e-import** (`zarmstrong/foundry-pathbuilder2e-import`, originally by the Pathbuilder developer himself) — the original integration pattern in a single `pathbuilder-import.js` file. Now deprecated for Foundry v11+ but remains a clean reference implementation.

- **Alseta's Passage** is a Chrome/Firefox extension that bridges Pathbuilder and Discord via webhooks, intercepting data from the Pathbuilder web app DOM in real-time. This demonstrates a browser-extension approach, though it's more complex than the JSON API pattern.

- **pathbuilder-viewer** (`plasticmacaroni/pathbuilder-viewer`) is an Apache-2.0 licensed character viewer using YAML configuration for field mapping — a useful reference for building display layers.

## PDF export is a dead end for data extraction

Pathbuilder's PDF export generates **flat rendered output, not form-fillable PDFs**. The character data is drawn onto a visual layout — there are no named form fields, no tagged structure, and no semantic markup. Standard PDF libraries (PyPDF2, pdfplumber, pdf.js) would require fragile positional text extraction that breaks on any layout change.

Worse, the PDF is **lossy**: GitLab issue #707 documents that class features like Flurry of Blows, Powerful Fist, and Incredible Movement are missing from PDF output. The PDF contains a subset of what the JSON provides. **Zero community projects attempt PDF parsing** — every integration uses the JSON endpoint. Do not invest engineering time in PDF extraction.

## No legal barriers exist, and the developer actively encourages integration

No formal Terms of Service document exists at pathbuilder2e.com. The privacy policy states the service is provided "AS IS," character data is stored locally on devices, and shared characters are referenced by unique codes. There is **no published API usage policy** restricting third-party access.

More importantly, the developer's actions and statements are unambiguously supportive. On Patreon in 2020, Wilson wrote: *"I know other people have been asking for JSON for a while, so hopefully it will be useful for other projects too. The JSON file is uploaded to the pathbuilder2e website with a link to make it easier to transfer into other projects."* He built the first Foundry VTT import module himself, then handed it off to community developers. His patch notes reference "JSON export improvements to help Pathmuncher," showing active cooperation with third-party tool authors.

**No projects have reported being blocked or rate-limited.** The 6-digit code system provides natural access control — users must explicitly export their character to generate an ID. There is no evidence of IP blocking, request throttling, or hostile responses to automated access. That said, since this is an informal API from a solo developer, responsible usage matters. Implement reasonable caching and avoid polling the endpoint repeatedly for the same ID.

## Recommended architecture for your campaign tool

Given a TypeScript/Node/Python stack building a campaign management tool with shared party view, initiative tracker, inventory management, and session notes, here is the recommended implementation:

**Fetch layer (Node.js/TypeScript):**
```typescript
interface PathbuilderResponse {
  success: boolean;
  build?: PathbuilderBuild;
}

async function fetchCharacter(buildId: string): Promise<PathbuilderBuild> {
  const res = await fetch(`https://pathbuilder2e.com/json.php?id=${buildId}`);
  const data: PathbuilderResponse = await res.json();
  if (!data.success || !data.build) throw new Error('Invalid or expired build ID');
  return data.build;
}
```

**End-to-end flow:** User pastes their 6-digit build ID into your app → your backend fetches the JSON from Pathbuilder's server (not the browser, to avoid CORS issues) → you parse and normalize the data into your own schema → store in your database → display in the shared party view. Since build IDs expire, **fetch and store immediately** — do not rely on re-fetching later. Offer users a "re-import" button to update their character with a new build ID after leveling up.

**For your specific features**, the JSON provides everything needed. The party view can pull `name`, `class`, `level`, `ancestry`, `acTotal`, `attributes` (HP, speed), and `abilities`. The initiative tracker can compute initiative from `proficiencies.perception` + ability modifier (or Stealth for characters with the Avoid Notice exploration activity — check `specials` for relevant features). Inventory management maps directly to `weapons`, `armor`, `equipment`, `specificItems`, and `money`. Session notes would be your own data layer, but can reference character names and levels from the imported data.

**Known gotchas to plan for:** feat and item names in Pathbuilder may not match other data sources exactly — projects like Pathmuncher maintain mapping tables for name mismatches. Proficiency values use a 0/2/4/6/8 encoding (not the TEML labels). The `size` field is numeric (0=Tiny through 5=Gargantuan). Ability scores are final values, not modifiers — compute modifiers as `Math.floor((score - 10) / 2)`. Dual-class support is described as "ropey at best" by Pathmuncher. And the JSON schema evolves over time as Pathbuilder adds features, so build defensive parsing that handles missing fields gracefully.

## Conclusion

The `json.php` endpoint is the clear, singular integration path — it is unauthenticated, stable, developer-endorsed, and battle-tested by half a dozen production tools over several years. Your strongest technical references are Pathmuncher's TypeScript source for comprehensive field coverage and Kobold's Discord bot architecture for the character-import-and-store pattern your campaign tool needs. The biggest architectural decision is handling ID expiration: fetch once, store immediately, and let users re-import. There are no legal obstacles, no authentication hurdles, and no need to parse PDFs. The entire integration can ship in a few hundred lines of TypeScript.
