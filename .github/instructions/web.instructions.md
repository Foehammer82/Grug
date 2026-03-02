---
applyTo: "web/src/**"
---

# Web UI Instructions (React + MUI)

## Tech Stack

- **React 18 + TypeScript + Vite** — dev server runs in Docker with HMR via volume mount
- **MUI v7** — full component library; GitHub Dark/Light themes defined in `web/src/theme.ts`
- **React Query (@tanstack/react-query)** — all API data fetching
- **React Router v6** — nested routes

## Theme

Two themes are defined in `web/src/theme.ts`: `darkTheme` (GitHub Dark) and `lightTheme` (GitHub Light). User preference is stored in `localStorage` under `grug-theme` ('light' | 'dark' | 'system'). Never introduce a third theme or palette switcher without explicit instruction.

Key token values:
- Dark: bg `#0d1117`, paper `#161b22`, appbar `#010409`, accent `#58a6ff`, border `#30363d`
- Light: bg `#ffffff`, paper `#f6f8fa`, accent `#0969da`, border `#d0d7de`

## Layout Architecture

- `AppLayout` — outer shell: NavBar top, `ServerSidebar` left, `<Outlet />` right
- `GuildLayout` — wraps all guild pages: server name heading + tabs (Config/Events/Tasks/Documents/Glossary) + `<Box sx={{ p: 4 }}><Outlet /></Box>`
- **Pages must NOT add their own padding wrappers.** `GuildLayout` provides `p: 4` on the outlet. Never wrap page content in `<main style={{ padding: '2rem' }}>` or equivalent.

## Discord Snowflake IDs — Precision Warning

Discord entity IDs (channel, guild, user, etc.) are 64-bit integers called snowflakes (~19 digits). They exceed JavaScript's `Number.MAX_SAFE_INTEGER` (2⁵³−1, ~16 digits). **Never use `parseInt()` or cast them to `number` in the frontend.** Always keep them as strings end-to-end.

- The channels endpoint returns `id` as a string — keep it that way.
- The config endpoint returns `announce_channel_id` as a string (serialized via `@field_serializer` in the Pydantic schema).
- When sending a channel ID to the API via a PATCH, send the raw string from the channel object (`value?.id`), never `parseInt(value)`.
- On the backend, convert to `int` once in Python (no precision loss): `int(val) if val is not None else None`.

## Channel Selection — Use Autocomplete

Always use MUI `Autocomplete` (not `Select`) for channel pickers. It provides free-text search filtering and handles the option-object-to-value comparison cleanly:

```tsx
<Autocomplete
  size="small"
  fullWidth
  options={channels ?? []}
  loading={channelsLoading}
  // Match by string ID, not object reference
  value={channels?.find((c) => c.id === config.announce_channel_id) ?? null}
  onChange={(_, ch) => mutation.mutate({ announce_channel_id: ch?.id ?? null })}
  getOptionLabel={(ch) => `#${ch.name}`}
  // Search by both name and ID
  filterOptions={(opts, { inputValue }) => {
    const q = inputValue.toLowerCase();
    return opts.filter((ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q));
  }}
  isOptionEqualToValue={(a, b) => a.id === b.id}
  renderOption={(props, ch) => (
    <Box component="li" {...props} key={ch.id}>
      <span>#{ch.name}</span>
      <Typography component="span" variant="caption" color="text.disabled" sx={{ ml: 1 }}>
        {ch.id}
      </Typography>
    </Box>
  )}
  renderInput={(params) => <TextField {...params} label="Bot Channel" />}
/>
```

Key points:
- `isOptionEqualToValue` must compare by `id` string, not object reference.
- `renderOption` needs an explicit `key` prop on the `<Box>` (MUI passes it via `props` but forwarding to a custom element is safer with explicit key).
- The selected value is derived by finding the matching channel object from the loaded list, not stored separately.



- **Always use MUI components** — never raw HTML elements (`<h2>`, `<p>`, `<button>`, `<input>`, `<table>`, `<select>`) in page components.
- **Never hardcode colors** — use MUI theme tokens (`color: 'text.secondary'`, `bgcolor: 'action.hover'`, etc.) or `sx` props. Hardcoded hex values like `#f0f0f0` or `#eee` break dark mode.
- Use `Typography` for all text, `Button` for all actions, `TextField` for inputs, `Table*` components for tables.
- Use `CircularProgress` centered in a `Box` for loading states, `Typography color="text.secondary"` for empty states.
- Loading/empty states should be early-return guards, not conditional renders deep inside JSX.

## MUI Select — Common Pitfalls

### Label overlap with `displayEmpty`
**Never** use `displayEmpty` alone. It renders the placeholder value inside the input before the label has floated, causing them to collide. Options:
- If the value can be empty/null and you want a visible placeholder in the closed state: use `displayEmpty` **together with** `shrink` on `InputLabel` and `notched` on `Select`.
- Prefer using `renderValue` to fully control the closed-state display.

### Showing enriched content in dropdown options
Use `renderValue` on `<Select>` to display a richer view of the selected value (e.g. channel name + muted ID), independent from the `MenuItem` children. This avoids the selected value looking different from what the user sees in the list.

```tsx
<Select
  renderValue={(val) => {
    const ch = channels?.find((c) => c.id === val);
    if (!ch) return <em style={{ opacity: 0.5 }}>Loading…</em>;
    return (
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
        <span>#{ch.name}</span>
        <Typography component="span" variant="caption" color="text.disabled">{ch.id}</Typography>
      </Box>
    );
  }}
>
```

### Selected value not in the options list (race condition)
If `value` is set before the options have loaded (e.g. config loads before channels), MUI renders blank. Handle this in `renderValue` by showing a graceful fallback (e.g. "Loading…") rather than adding a phantom `<MenuItem>` for the raw ID.

## Tab Focus Rings

MUI `Tab` components show a blue focus outline by default. Suppress it with:
```tsx
disableRipple
disableFocusRipple
sx={{ '&.Mui-focusVisible': { outline: 'none', boxShadow: 'none', backgroundColor: 'transparent' } }}
```
This is already applied globally in `GuildLayout.tsx`.

## Live-Edit Forms

Config forms use live PATCH on change — no save buttons. Fire the mutation in the `onChange` handler. Use `model_fields_set` on the backend to distinguish "field not sent" from "field explicitly set to null".
