import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import type { ScheduledTask } from '../types';
import { cronToHuman } from '../utils';

export type { ScheduledTask } from '../types';

interface Props {
  task: ScheduledTask;
  open: boolean;
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function TaskDetailModal({ task, open, onClose }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      await client.patch(`/api/guilds/${guildId}/tasks/${task.id}`, { enabled });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', guildId] });
      qc.invalidateQueries({ queryKey: ['events', guildId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await client.delete(`/api/guilds/${guildId}/tasks/${task.id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', guildId] });
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      onClose();
    },
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          Scheduled Task
          <Chip
            label={task.type === 'once' ? 'One-off' : 'Recurring'}
            size="small"
            color={task.type === 'once' ? 'info' : 'default'}
            variant="outlined"
          />
        </Box>
        <Button
          size="small"
          color="error"
          variant="outlined"
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
        >
          Delete
        </Button>
      </DialogTitle>

      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
        <TextField
          label="Name"
          defaultValue={task.name ?? ''}
          InputProps={{ readOnly: true }}
          fullWidth
          size="small"
        />

        <TextField
          label="Prompt"
          defaultValue={task.prompt}
          InputProps={{ readOnly: true }}
          fullWidth
          multiline
          minRows={2}
          size="small"
        />

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Enabled
          </Typography>
          <Switch
            checked={task.enabled}
            onChange={() => toggleMutation.mutate(!task.enabled)}
            size="small"
          />
        </Box>

        {task.type === 'once' && (
          <TextField
            label="Fire at"
            defaultValue={task.fire_at ? new Date(task.fire_at).toLocaleString() : '—'}
            InputProps={{ readOnly: true }}
            fullWidth
            size="small"
          />
        )}

        {task.type === 'recurring' && (
          <TextField
            label="Cron expression"
            defaultValue={task.cron_expression ?? '—'}
            InputProps={{ readOnly: true }}
            fullWidth
            size="small"
            inputProps={{ style: { fontFamily: 'monospace' } }}
            helperText={cronToHuman(task.cron_expression) ?? undefined}
          />
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Next run"
            defaultValue={task.next_run ? new Date(task.next_run).toLocaleString() : '—'}
            InputProps={{ readOnly: true }}
            fullWidth
            size="small"
          />
          <TextField
            label="Last run"
            defaultValue={task.last_run ? new Date(task.last_run).toLocaleString() : '—'}
            InputProps={{ readOnly: true }}
            fullWidth
            size="small"
          />
        </Box>

        <Typography variant="caption" color="text.secondary">
          Created {new Date(task.created_at).toLocaleString()}
        </Typography>

        {(toggleMutation.isError || deleteMutation.isError) && (
          <Typography color="error" variant="body2">
            Something went wrong — please try again.
          </Typography>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
