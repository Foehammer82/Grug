import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import client from '../api/client';

type Preset = '1d' | '7d' | '1m' | '1y' | 'custom';

/* ------------------------------------------------------------------ */
/* Types (mirror api/routes/usage.py response shapes)                 */
/* ------------------------------------------------------------------ */

interface UsageRowOut {
  model: string;
  call_type: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
}

interface UsageSummaryOut {
  start_date: string;
  end_date: string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_estimated_cost_usd: number | null;
  cost_is_partial: boolean;
  by_model: UsageRowOut[];
  by_call_type: UsageRowOut[];
}

interface ChartPointOut {
  label: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
}

const PRESET_LABELS: Record<Preset, string> = {
  '1d': 'Last 24h',
  '7d': 'Last 7 days',
  '1m': 'Last 30 days',
  '1y': 'Last year',
  custom: 'Custom',
};

const CHART_TITLE: Record<Preset, string> = {
  '1d': 'Hourly Token Usage (Last 24 Hours)',
  '7d': 'Daily Token Usage (Last 7 Days)',
  '1m': 'Daily Token Usage (Last 30 Days)',
  '1y': 'Weekly Token Usage (Last Year)',
  custom: 'Token Usage (Custom Range)',
};

function summaryDates(preset: Preset, customStart: string, customEnd: string) {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const daysAgo = (n: number) => { const d = new Date(today); d.setDate(d.getDate() - n); return fmt(d); };
  if (preset === '1d') return { start: daysAgo(1), end: fmt(today) };
  if (preset === '7d') return { start: daysAgo(6), end: fmt(today) };
  if (preset === '1m') return { start: daysAgo(29), end: fmt(today) };
  if (preset === '1y') return { start: daysAgo(364), end: fmt(today) };
  return { start: customStart, end: customEnd };
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtCost(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v < 0.001) return '<$0.001';
  return `$${v.toFixed(4)}`;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function monthStartStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function fmtAxisLabel(label: string, preset: Preset): string {
  if (preset === '1d') return label;
  const [, mm, dd] = label.split('-');
  if (preset === '1y') {
    const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${m[Number(mm) - 1]} ${Number(dd)}`;
  }
  return `${Number(mm)}/${Number(dd)}`;
}

function fmtTooltipTitle(label: string, preset: Preset): string {
  if (preset === '1d') return label;  // label is already in server's configured timezone
  if (preset === '1y') return `Week of ${label}`;
  const d = new Date(label + 'T12:00:00Z');
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

const CALL_TYPE_LABELS: Record<string, string> = {
  chat: 'Chat',
  rules_lookup: 'Rules Lookup',
  history_archive: 'History Archive',
  character_parse: 'Character Parse',
  cron_parse: 'Cron Parse',
  auto_respond_score: 'Auto-Respond Score',
  session_note_synthesis: 'Session Note Synthesis',
};

const HEADER_SX = { fontWeight: 700, color: 'text.secondary', fontSize: '0.72rem', textTransform: 'uppercase' } as const;

/* ------------------------------------------------------------------ */
/* Stat card                                                           */
/* ------------------------------------------------------------------ */

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 160, flex: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5 }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" color="text.secondary">{sub}</Typography>
      )}
    </Paper>
  );
}

/* ------------------------------------------------------------------ */
/* Mini bar chart — pure CSS bars, no extra dependency                 */
/* ------------------------------------------------------------------ */

function UsageBarChart({ points, preset }: { points: ChartPointOut[]; preset: Preset }) {
  const maxTokens = Math.max(...points.map((p) => p.input_tokens + p.output_tokens), 1);

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, textTransform: 'uppercase' }}>
        {CHART_TITLE[preset]}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '2px',
          height: 80,
          borderBottom: '1px solid',
          borderColor: 'divider',
          pb: '2px',
        }}
      >
        {points.map((p, i) => {
          const total = p.input_tokens + p.output_tokens;
          const heightPct = total === 0 ? 2 : Math.max(4, (total / maxTokens) * 100);
          return (
            <Tooltip
              key={i}
              title={
                <Box sx={{ fontSize: '0.75rem' }}>
                  <Typography variant="caption" display="block" fontWeight={700}>{fmtTooltipTitle(p.label, preset)}</Typography>
                  <Typography variant="caption" display="block">{p.request_count} req · {fmtTokens(total)} tok</Typography>
                  {p.estimated_cost_usd != null && (
                    <Typography variant="caption" display="block">≈{fmtCost(p.estimated_cost_usd)}</Typography>
                  )}
                </Box>
              }
            >
              <Box
                sx={{
                  flex: 1,
                  minWidth: 4,
                  height: `${heightPct}%`,
                  bgcolor: total === 0 ? 'action.disabled' : 'primary.main',
                  borderRadius: '2px 2px 0 0',
                  opacity: total === 0 ? 0.3 : 0.85,
                  cursor: 'default',
                  transition: 'opacity 0.15s',
                  '&:hover': { opacity: 1 },
                }}
              />
            </Tooltip>
          );
        })}
      </Box>
      {points.length > 0 && (
        <Stack direction="row" justifyContent="space-between" sx={{ mt: 0.5 }}>
          <Typography variant="caption" color="text.disabled">{fmtAxisLabel(points[0].label, preset)}</Typography>
          <Typography variant="caption" color="text.disabled">{fmtAxisLabel(points[points.length - 1].label, preset)}</Typography>
        </Stack>
      )}
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/* Main section component                                              */
/* ------------------------------------------------------------------ */

export default function LLMUsageSection() {
  const [preset, setPreset] = useState<Preset>('1m');
  const [customStart, setCustomStart] = useState(monthStartStr());
  const [customEnd, setCustomEnd] = useState(todayStr());
  const { start, end } = summaryDates(preset, customStart, customEnd);

  const summaryQuery = useQuery<UsageSummaryOut>({
    queryKey: ['admin-usage-summary', start, end],
    queryFn: async () => {
      const res = await client.get<UsageSummaryOut>('/api/admin/usage/summary', {
        params: { start_date: start, end_date: end },
      });
      return res.data;
    },
    staleTime: 60_000,
  });

  const pointsQuery = useQuery<ChartPointOut[]>({
    queryKey: ['admin-usage-points', preset, preset === 'custom' ? start : null, preset === 'custom' ? end : null],
    queryFn: async () => {
      const params: Record<string, string> = { preset };
      if (preset === 'custom') { params.start_date = start; params.end_date = end; }
      const res = await client.get<ChartPointOut[]>('/api/admin/usage/points', { params });
      return res.data;
    },
    staleTime: 60_000,
  });

  const s = summaryQuery.data;

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <Typography variant="h6" fontWeight={700}>
          LLM Usage &amp; Costs
        </Typography>
        <Tooltip title="All costs are estimates based on published Anthropic pricing. Actual charges may differ.">
          <Chip label="Estimated" size="small" variant="outlined" color="warning" sx={{ fontSize: '0.65rem', height: 18 }} />
        </Tooltip>
        {(summaryQuery.isFetching || pointsQuery.isFetching) && <CircularProgress size={14} />}
      </Stack>

      {/* ── Preset toggle + optional custom date pickers ── */}
      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
        <ToggleButtonGroup
          value={preset}
          exclusive
          size="small"
          onChange={(_, v) => { if (v) setPreset(v as Preset); }}
        >
          {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => (
            <ToggleButton key={p} value={p} sx={{ px: 2, fontSize: '0.78rem', textTransform: 'none' }}>
              {PRESET_LABELS[p]}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        {preset === 'custom' && (
          <>
            <TextField
              label="From"
              type="date"
              size="small"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ width: 160 }}
            />
            <TextField
              label="To"
              type="date"
              size="small"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ width: 160 }}
            />
          </>
        )}
      </Stack>

      {/* ── Summary stat cards ── */}
      {s && (
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
          <StatCard label="Requests" value={s.total_requests.toLocaleString()} />
          <StatCard
            label="Input Tokens"
            value={fmtTokens(s.total_input_tokens)}
            sub={s.total_input_tokens.toLocaleString() + ' total'}
          />
          <StatCard
            label="Output Tokens"
            value={fmtTokens(s.total_output_tokens)}
            sub={s.total_output_tokens.toLocaleString() + ' total'}
          />
          <StatCard
            label="Est. Cost"
            value={fmtCost(s.total_estimated_cost_usd)}
            sub={s.cost_is_partial ? 'Partial — some models unpriced' : 'All models priced'}
          />
        </Stack>
      )}

      {summaryQuery.isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {summaryQuery.isError && (
        <Typography color="error" sx={{ mb: 2 }}>Failed to load usage data.</Typography>
      )}

      {/* ── Bar chart ── */}
      {pointsQuery.data && pointsQuery.data.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <UsageBarChart points={pointsQuery.data} preset={preset} />
        </Box>
      )}

      {/* ── By-model breakdown ── */}
      {s && s.by_model.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            By Model
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  {['Model', 'Requests', 'Input Tokens', 'Output Tokens', 'Est. Cost'].map((h) => (
                    <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {s.by_model.map((row) => (
                  <TableRow key={row.model} hover>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{row.model}</TableCell>
                    <TableCell>{row.request_count.toLocaleString()}</TableCell>
                    <TableCell>{fmtTokens(row.input_tokens)}</TableCell>
                    <TableCell>{fmtTokens(row.output_tokens)}</TableCell>
                    <TableCell>
                      {row.estimated_cost_usd != null
                        ? fmtCost(row.estimated_cost_usd)
                        : <Typography variant="caption" color="text.disabled">Unknown model</Typography>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ── By-call-type breakdown ── */}
      {s && s.by_call_type.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            By Feature
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  {['Feature', 'Model', 'Requests', 'Input Tokens', 'Output Tokens', 'Est. Cost'].map((h) => (
                    <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {s.by_call_type.map((row, i) => (
                  <TableRow key={`${row.call_type}-${row.model}-${i}`} hover>
                    <TableCell>
                      <Typography variant="body2">{CALL_TYPE_LABELS[row.call_type] ?? row.call_type}</Typography>
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{row.model}</TableCell>
                    <TableCell>{row.request_count.toLocaleString()}</TableCell>
                    <TableCell>{fmtTokens(row.input_tokens)}</TableCell>
                    <TableCell>{fmtTokens(row.output_tokens)}</TableCell>
                    <TableCell>
                      {row.estimated_cost_usd != null
                        ? fmtCost(row.estimated_cost_usd)
                        : <Typography variant="caption" color="text.disabled">—</Typography>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {s && s.by_model.length === 0 && !summaryQuery.isLoading && (
        <Typography color="text.secondary" variant="body2">
          No usage recorded for this period.
        </Typography>
      )}
    </Box>
  );
}
