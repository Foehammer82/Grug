import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import client from '../api/client';

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

interface DailyUsagePointOut {
  date: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
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

function thirtyDaysAgoStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 29);
  return d.toISOString().slice(0, 10);
}

const CALL_TYPE_LABELS: Record<string, string> = {
  chat: 'Chat',
  rules_lookup: 'Rules Lookup',
  history_archive: 'History Archive',
  character_parse: 'Character Parse',
  cron_parse: 'Cron Parse',
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

function DailyBarChart({ points }: { points: DailyUsagePointOut[] }) {
  const maxTokens = Math.max(...points.map((p) => p.input_tokens + p.output_tokens), 1);

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600, textTransform: 'uppercase' }}>
        Daily Token Usage (last 30 days)
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
        {points.map((p) => {
          const total = p.input_tokens + p.output_tokens;
          const heightPct = total === 0 ? 2 : Math.max(4, (total / maxTokens) * 100);
          return (
            <Tooltip
              key={p.date}
              title={
                <Box sx={{ fontSize: '0.75rem' }}>
                  <Typography variant="caption" display="block" fontWeight={700}>{p.date}</Typography>
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
      <Stack direction="row" justifyContent="space-between" sx={{ mt: 0.5 }}>
        <Typography variant="caption" color="text.disabled">{points[0]?.date}</Typography>
        <Typography variant="caption" color="text.disabled">{points[points.length - 1]?.date}</Typography>
      </Stack>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/* Main section component                                              */
/* ------------------------------------------------------------------ */

export default function LLMUsageSection() {
  const [startDate, setStartDate] = useState(monthStartStr());
  const [endDate, setEndDate] = useState(todayStr());
  const [dailyStart] = useState(thirtyDaysAgoStr());

  const summaryQuery = useQuery<UsageSummaryOut>({
    queryKey: ['admin-usage-summary', startDate, endDate],
    queryFn: async () => {
      const res = await client.get<UsageSummaryOut>('/api/admin/usage/summary', {
        params: { start_date: startDate, end_date: endDate },
      });
      return res.data;
    },
    staleTime: 60_000,
  });

  const dailyQuery = useQuery<DailyUsagePointOut[]>({
    queryKey: ['admin-usage-daily', dailyStart, todayStr()],
    queryFn: async () => {
      const res = await client.get<DailyUsagePointOut[]>('/api/admin/usage/daily', {
        params: { start_date: dailyStart, end_date: todayStr() },
      });
      return res.data;
    },
    staleTime: 60_000,
  });

  const s = summaryQuery.data;

  return (
    <Box>
      <Divider sx={{ my: 4 }} />
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <Typography variant="h6" fontWeight={700}>
          LLM Usage &amp; Costs
        </Typography>
        <Tooltip title="All costs are estimates based on published Anthropic pricing. Actual charges may differ.">
          <Chip label="Estimated" size="small" variant="outlined" color="warning" sx={{ fontSize: '0.65rem', height: 18 }} />
        </Tooltip>
      </Stack>

      {/* ── Date range controls ── */}
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
        <TextField
          label="From"
          type="date"
          size="small"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 160 }}
        />
        <TextField
          label="To"
          type="date"
          size="small"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 160 }}
        />
        {summaryQuery.isFetching && <CircularProgress size={16} />}
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

      {/* ── Daily bar chart ── */}
      {dailyQuery.data && dailyQuery.data.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <DailyBarChart points={dailyQuery.data} />
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
