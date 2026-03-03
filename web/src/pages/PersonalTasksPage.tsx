import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormLabel,
  Paper,
  Radio,
  RadioGroup,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import PollingIndicator from '../components/PollingIndicator';
import { TABLE_HEADER_SX } from '../types';
import { cronToHuman } from '../utils';
import type { ScheduledTask } from '../types';



const EMPTY_FORM = {
  type: 'once' as 'once' | 'recurring',
  name: '',
  prompt: '',
  fire_at: '',
  cron_expression: '',
  schedule_text: '',
};

export default function PersonalTasksPage() {
  useAuth();
  const qc = useQueryClient();

  const POLL_MS = 15_000;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const { data: tasks, isLoading, dataUpdatedAt } = useQuery<ScheduledTask[]>({
    queryKey: ['personal', 'tasks'],
    queryFn: async () => {
      const res = await client.get<ScheduledTask[]>('/api/personal/tasks');
      return res.data;
    },
    refetchInterval: POLL_MS,
  });

  const cronFromTextMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await client.post<{ cron_expression: string }>(
        '/api/personal/tasks/cron-from-text',
        { text },
      );
      return res.data.cron_expression;
    },
    onSuccess: (cron) => setForm((f) => ({ ...f, cron_expression: cron })),
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        type: form.type,
        prompt: form.prompt,
        name: form.name || null,
      };
      if (form.type === 'once') {
        payload.fire_at = form.fire_at ? new Date(form.fire_at).toISOString() : null;
      } else {
        payload.cron_expression = form.cron_expression || null;
      }
      await client.post('/api/personal/tasks', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['personal', 'tasks'] });
      setDialogOpen(false);
      setForm(EMPTY_FORM);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      await client.patch(`/api/personal/tasks/${id}`, { enabled });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personal', 'tasks'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/personal/tasks/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personal', 'tasks'] }),
  });

  const isFormValid =
    form.prompt.trim().length > 0 &&
    (form.type === 'once' ? !!form.fire_at : !!form.cron_expression.trim());

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

      {/* ── Scheduled Tasks ───────────────────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Scheduled tasks Grug was asked to set up during your DMs — one-off reminders
          and recurring automated prompts.
          Ask Grug: "remind me to update my spell slots in 10 minutes" or
          "every Monday morning, remind me to update my character sheet".
        </Typography>
        <PollingIndicator intervalMs={POLL_MS} dataUpdatedAt={dataUpdatedAt} />
      </Box>

      <Box>
        <Button variant="contained" size="small" onClick={() => setDialogOpen(true)}>
          New Task
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !tasks || tasks.length === 0 ? (
        <Typography color="text.secondary">No personal scheduled tasks.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Type', 'Name / Prompt', 'Schedule', 'Enabled', 'Status', 'Next Run', 'Actions'].map((h) => (
                  <TableCell key={h} sx={TABLE_HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tasks.map((t) => (
                <TableRow key={t.id} hover>
                  <TableCell>
                    <Chip
                      label={t.type === 'once' ? 'Once' : 'Recurring'}
                      size="small"
                      color={t.type === 'once' ? 'info' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {t.name ?? t.prompt.slice(0, 60)}
                  </TableCell>
                  <TableCell>
                    {t.type === 'once' ? (
                      <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                        {t.fire_at ? new Date(t.fire_at).toLocaleString() : '—'}
                      </Typography>
                    ) : (() => {
                      const human = cronToHuman(t.cron_expression);
                      return (
                        <Box>
                          {human ? (
                            <Typography variant="body2">{human}</Typography>
                          ) : null}
                          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                            {t.cron_expression ?? '—'}
                          </Typography>
                        </Box>
                      );
                    })()}
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={t.enabled}
                      onChange={() => toggleMutation.mutate({ id: t.id, enabled: !t.enabled })}
                    />
                  </TableCell>
                  <TableCell>
                    {t.type === 'once' ? (
                      <Chip
                        label="Pending"
                        size="small"
                        color="primary"
                        variant="filled"
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {t.last_run ? new Date(t.last_run).toLocaleString() : '—'}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    <Typography variant="body2" color="text.secondary">
                      {t.next_run ? new Date(t.next_run).toLocaleString() : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      onClick={() => deleteMutation.mutate(t.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ── Create task dialog ── */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Scheduled Task</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <FormControl>
            <FormLabel>Task type</FormLabel>
            <RadioGroup
              row
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as 'once' | 'recurring' }))}
            >
              <FormControlLabel value="once" control={<Radio size="small" />} label="One-off" />
              <FormControlLabel value="recurring" control={<Radio size="small" />} label="Recurring" />
            </RadioGroup>
          </FormControl>

          <TextField
            label="Prompt"
            required
            multiline
            minRows={3}
            value={form.prompt}
            onChange={(e) => setForm((f) => ({ ...f, prompt: e.target.value }))}
            helperText="The message Grug will send or act on when the task fires."
          />

          <TextField
            label="Name (optional)"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            helperText="Short label shown in the task list. Defaults to the prompt text."
          />

          {form.type === 'once' ? (
            <TextField
              label="Fire at"
              type="datetime-local"
              required
              value={form.fire_at}
              onChange={(e) => setForm((f) => ({ ...f, fire_at: e.target.value }))}
              InputLabelProps={{ shrink: true }}
              helperText="Date and time when the task should fire (local time)."
            />
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <TextField
                  label="Describe the schedule"
                  placeholder='e.g. "every Monday at 9am UTC"'
                  fullWidth
                  size="small"
                  value={form.schedule_text}
                  onChange={(e) => setForm((f) => ({ ...f, schedule_text: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && form.schedule_text.trim()) {
                      e.preventDefault();
                      cronFromTextMutation.mutate(form.schedule_text.trim());
                    }
                  }}
                  disabled={cronFromTextMutation.isPending}
                />
                <Button
                  variant="outlined"
                  size="small"
                  sx={{ whiteSpace: 'nowrap', flexShrink: 0, height: 40 }}
                  disabled={!form.schedule_text.trim() || cronFromTextMutation.isPending}
                  onClick={() => cronFromTextMutation.mutate(form.schedule_text.trim())}
                >
                  {cronFromTextMutation.isPending ? 'Converting…' : 'Convert'}
                </Button>
              </Box>
              {cronFromTextMutation.isError && (
                <Typography variant="caption" color="error">
                  Could not convert — try rephrasing or enter the cron manually.
                </Typography>
              )}
              <TextField
                label="Cron expression"
                required
                value={form.cron_expression}
                onChange={(e) => setForm((f) => ({ ...f, cron_expression: e.target.value }))}
                helperText={
                  cronToHuman(form.cron_expression)
                  ?? '5-field UTC cron — e.g. "0 9 * * 1" = every Monday at 09:00 UTC.'
                }
                inputProps={{ style: { fontFamily: 'monospace' } }}
              />
            </Box>
          )}

          {createMutation.isError && (
            <Typography color="error" variant="body2">
              Failed to create task. Check your inputs and try again.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setDialogOpen(false); setForm(EMPTY_FORM); }}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!isFormValid || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
