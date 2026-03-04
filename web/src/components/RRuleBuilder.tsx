/**
 * Visual RRULE builder + free-form AI text-to-RRULE conversion.
 *
 * Provides a GUI for constructing iCal RRULE strings without memorising the
 * syntax, plus an AI-powered natural-language input ("every other Thursday").
 *
 * Usage:
 *   <RRuleBuilder guildId={guildId} value={rrule} onChange={setRrule} />
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { useMutation } from '@tanstack/react-query';
import client from '../api/client';

/* ------------------------------------------------------------------ */
/* Types & constants                                                   */
/* ------------------------------------------------------------------ */

interface RRuleBuilderProps {
  /** Guild ID — needed for the AI endpoint. */
  guildId: string;
  /** Current RRULE value (controlled). */
  value: string;
  /** Called whenever the RRULE changes. */
  onChange: (rrule: string) => void;
}

type Frequency = 'DAILY' | 'WEEKLY' | 'MONTHLY';

const FREQ_OPTIONS: { value: Frequency; label: string }[] = [
  { value: 'DAILY', label: 'Daily' },
  { value: 'WEEKLY', label: 'Weekly' },
  { value: 'MONTHLY', label: 'Monthly' },
];

const WEEKDAYS = [
  { value: 'MO', label: 'Mon' },
  { value: 'TU', label: 'Tue' },
  { value: 'WE', label: 'Wed' },
  { value: 'TH', label: 'Thu' },
  { value: 'FR', label: 'Fri' },
  { value: 'SA', label: 'Sat' },
  { value: 'SU', label: 'Sun' },
] as const;

/* ------------------------------------------------------------------ */
/* RRULE ↔ state helpers                                               */
/* ------------------------------------------------------------------ */

interface RRuleParts {
  freq: Frequency;
  interval: number;
  byDay: string[];
}

function parseRrule(rrule: string): RRuleParts {
  const parts: RRuleParts = { freq: 'WEEKLY', interval: 1, byDay: [] };
  if (!rrule) return parts;

  for (const segment of rrule.split(';')) {
    const [key, val] = segment.split('=');
    switch (key) {
      case 'FREQ':
        if (['DAILY', 'WEEKLY', 'MONTHLY'].includes(val)) parts.freq = val as Frequency;
        break;
      case 'INTERVAL':
        parts.interval = Math.max(1, parseInt(val, 10) || 1);
        break;
      case 'BYDAY':
        parts.byDay = val.split(',').filter(Boolean);
        break;
    }
  }
  return parts;
}

function buildRrule(parts: RRuleParts): string {
  const segments: string[] = [`FREQ=${parts.freq}`];
  if (parts.interval > 1) segments.push(`INTERVAL=${parts.interval}`);
  if (parts.byDay.length > 0 && parts.freq !== 'DAILY') {
    segments.push(`BYDAY=${parts.byDay.join(',')}`);
  }
  return segments.join(';');
}

/** Human-readable description of the RRULE. */
export function describeRrule(rrule: string): string {
  if (!rrule) return '';
  const p = parseRrule(rrule);

  const dayNames: Record<string, string> = {
    MO: 'Monday', TU: 'Tuesday', WE: 'Wednesday', TH: 'Thursday',
    FR: 'Friday', SA: 'Saturday', SU: 'Sunday',
  };

  const intervalWord =
    p.interval === 1 ? 'every' :
    p.interval === 2 ? 'every other' :
    `every ${p.interval}`;

  const freqWord: Record<Frequency, string> = {
    DAILY: 'day',
    WEEKLY: 'week',
    MONTHLY: 'month',
  };

  let desc = `${intervalWord} ${freqWord[p.freq]}`;
  if (p.byDay.length > 0) {
    const names = p.byDay.map((d) => dayNames[d] ?? d);
    desc += ` on ${names.join(', ')}`;
  }

  // Capitalise first letter
  return desc.charAt(0).toUpperCase() + desc.slice(1);
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function RRuleBuilder({ guildId, value, onChange }: RRuleBuilderProps) {
  const [mode, setMode] = useState<'visual' | 'ai' | 'raw'>('visual');
  const [aiText, setAiText] = useState('');

  // Parse external value into visual state
  const parts = useMemo(() => parseRrule(value), [value]);

  // Update helpers that rebuild the RRULE string
  const setParts = useCallback(
    (updater: (prev: RRuleParts) => RRuleParts) => {
      const next = updater(parseRrule(value));
      onChange(buildRrule(next));
    },
    [value, onChange],
  );

  // AI conversion mutation
  const aiMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await client.post<{ rrule: string }>(
        `/api/guilds/${guildId}/events/rrule-from-text`,
        { text },
      );
      return res.data.rrule;
    },
    onSuccess: (rrule) => {
      onChange(rrule);
      setMode('visual'); // switch to visual so user can see/tweak the result
    },
  });

  // Keep raw text field in sync when switching to raw mode
  const [rawValue, setRawValue] = useState(value);
  useEffect(() => { setRawValue(value); }, [value]);

  const description = describeRrule(value);

  return (
    <Box>
      {/* Mode selector */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          Build with:
        </Typography>
        <Chip
          label="Visual"
          size="small"
          variant={mode === 'visual' ? 'filled' : 'outlined'}
          onClick={() => setMode('visual')}
        />
        <Chip
          label="AI"
          size="small"
          variant={mode === 'ai' ? 'filled' : 'outlined'}
          onClick={() => setMode('ai')}
          icon={<AutoFixHighIcon sx={{ fontSize: 14 }} />}
        />
        <Chip
          label="Raw"
          size="small"
          variant={mode === 'raw' ? 'filled' : 'outlined'}
          onClick={() => setMode('raw')}
        />
      </Stack>

      {/* ── Visual mode ── */}
      {mode === 'visual' && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1.5}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Frequency</InputLabel>
              <Select
                label="Frequency"
                value={parts.freq}
                onChange={(e) =>
                  setParts((p) => ({ ...p, freq: e.target.value as Frequency }))
                }
              >
                {FREQ_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Every N"
              type="number"
              size="small"
              sx={{ width: 90 }}
              slotProps={{ htmlInput: { min: 1, max: 52 } }}
              value={parts.interval}
              onChange={(e) =>
                setParts((p) => ({
                  ...p,
                  interval: Math.max(1, parseInt(e.target.value, 10) || 1),
                }))
              }
            />
          </Stack>
          {parts.freq !== 'DAILY' && (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                On days
              </Typography>
              <ToggleButtonGroup
                size="small"
                value={parts.byDay}
                onChange={(_, newDays: string[]) =>
                  setParts((p) => ({ ...p, byDay: newDays }))
                }
              >
                {WEEKDAYS.map((d) => (
                  <ToggleButton key={d.value} value={d.value} sx={{ px: 1.2, py: 0.3, fontSize: '0.75rem' }}>
                    {d.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
          )}
        </Stack>
      )}

      {/* ── AI mode ── */}
      {mode === 'ai' && (
        <Stack spacing={1}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <TextField
              size="small"
              fullWidth
              placeholder='e.g. "every other Thursday evening"'
              value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && aiText.trim()) {
                  e.preventDefault();
                  aiMutation.mutate(aiText.trim());
                }
              }}
              disabled={aiMutation.isPending}
            />
            <Button
              variant="outlined"
              size="small"
              sx={{ whiteSpace: 'nowrap', flexShrink: 0, height: 40 }}
              disabled={!aiText.trim() || aiMutation.isPending}
              onClick={() => aiMutation.mutate(aiText.trim())}
              startIcon={<AutoFixHighIcon />}
            >
              {aiMutation.isPending ? 'Converting…' : 'Convert'}
            </Button>
          </Box>
          {aiMutation.isError && (
            <Typography variant="caption" color="error">
              Could not convert — try rephrasing or switch to Visual mode.
            </Typography>
          )}
        </Stack>
      )}

      {/* ── Raw mode ── */}
      {mode === 'raw' && (
        <TextField
          size="small"
          fullWidth
          value={rawValue}
          onChange={(e) => setRawValue(e.target.value)}
          onBlur={() => onChange(rawValue)}
          placeholder="FREQ=WEEKLY;INTERVAL=2;BYDAY=TH"
          helperText="iCal RRULE — press Tab or click away to apply."
          inputProps={{ style: { fontFamily: 'monospace' } }}
        />
      )}

      {/* Preview */}
      {value && (
        <Box sx={{ mt: 1.5 }}>
          {description && (
            <Typography variant="body2" color="text.secondary">
              📅 {description}
            </Typography>
          )}
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.disabled' }}>
            {value}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
