/**
 * Manager page — admin-only view for managing instruction overrides and
 * viewing manager agent reviews.
 *
 * Two sections:
 * 1. Instruction Overrides — custom instructions that supplement Grug's prompt
 * 2. Manager Reviews — periodic review reports from the manager agent
 */

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import type { InstructionOverride, ManagerReview } from '../types';

// ─────────────────────────────────────────────────────────────────────────────
// Instruction Overrides Section
// ─────────────────────────────────────────────────────────────────────────────

function InstructionOverridesSection({ guildId }: { guildId: string }) {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newReason, setNewReason] = useState('');

  const { data: overrides, isLoading } = useQuery<InstructionOverride[]>({
    queryKey: ['instructions', guildId],
    queryFn: async () =>
      (await client.get<InstructionOverride[]>(`/api/guilds/${guildId}/instructions`)).data,
    enabled: !!guildId,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/instructions`, {
        content: newContent,
        reason: newReason || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['instructions', guildId] });
      setDialogOpen(false);
      setNewContent('');
      setNewReason('');
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, patch }: { id: number; patch: Record<string, unknown> }) => {
      await client.patch(`/api/guilds/${guildId}/instructions/${id}`, patch);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['instructions', guildId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/instructions/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['instructions', guildId] }),
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  const active = overrides?.filter((o) => o.status === 'active') ?? [];
  const pending = overrides?.filter((o) => o.status === 'pending') ?? [];
  const rejected = overrides?.filter((o) => o.status === 'rejected') ?? [];

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h6">Instruction Overrides</Typography>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
        >
          Add Instruction
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Custom instructions that supplement Grug's core prompt for this server.
        Active instructions are injected into every Grug response.
      </Typography>

      {active.length === 0 && pending.length === 0 && rejected.length === 0 && (
        <Typography color="text.secondary" sx={{ py: 2 }}>
          No instruction overrides configured. Grug uses the default system prompt.
        </Typography>
      )}

      {pending.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="warning.main" sx={{ mb: 1 }}>
            Pending Recommendations ({pending.length})
          </Typography>
          {pending.map((o) => (
            <OverrideCard
              key={o.id}
              override={o}
              onApply={() => updateMutation.mutate({ id: o.id, patch: { status: 'active' } })}
              onReject={() => updateMutation.mutate({ id: o.id, patch: { status: 'rejected' } })}
              onDelete={() => deleteMutation.mutate(o.id)}
            />
          ))}
        </Box>
      )}

      {active.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="success.main" sx={{ mb: 1 }}>
            Active ({active.length})
          </Typography>
          {active.map((o) => (
            <OverrideCard
              key={o.id}
              override={o}
              onDelete={() => deleteMutation.mutate(o.id)}
            />
          ))}
        </Box>
      )}

      {rejected.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.disabled" sx={{ mb: 1 }}>
            Rejected ({rejected.length})
          </Typography>
          {rejected.map((o) => (
            <OverrideCard
              key={o.id}
              override={o}
              onApply={() => updateMutation.mutate({ id: o.id, patch: { status: 'active' } })}
              onDelete={() => deleteMutation.mutate(o.id)}
            />
          ))}
        </Box>
      )}

      {/* Add instruction dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Custom Instruction</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This instruction will be injected into Grug's system prompt for this server.
            Write it as a clear directive.
          </Typography>
          <TextField
            label="Instruction"
            multiline
            rows={4}
            fullWidth
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Reason (optional)"
            fullWidth
            value={newReason}
            onChange={(e) => setNewReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => createMutation.mutate()}
            disabled={!newContent.trim() || createMutation.isPending}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function OverrideCard({
  override,
  onApply,
  onReject,
  onDelete,
}: {
  override: InstructionOverride;
  onApply?: () => void;
  onReject?: () => void;
  onDelete?: () => void;
}) {
  const statusColor = {
    active: 'success' as const,
    pending: 'warning' as const,
    rejected: 'default' as const,
  }[override.status];

  return (
    <Box
      sx={{
        p: 2,
        mb: 1,
        borderRadius: 1,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Stack direction="row" alignItems="flex-start" spacing={1}>
        <Box sx={{ flex: 1 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
            <Chip size="small" label={override.status} color={statusColor} />
            <Chip size="small" label={override.source} variant="outlined" />
          </Stack>
          <Typography
            variant="body2"
            sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.85rem' }}
          >
            {override.content}
          </Typography>
          {override.reason && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Reason: {override.reason}
            </Typography>
          )}
        </Box>
        <Stack direction="row" spacing={0.5}>
          {onApply && override.status !== 'active' && (
            <Tooltip title="Apply">
              <IconButton size="small" color="success" onClick={onApply}>
                <CheckCircleIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {onReject && override.status === 'pending' && (
            <Tooltip title="Reject">
              <IconButton size="small" color="warning" onClick={onReject}>
                <ThumbDownIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {onDelete && (
            <Tooltip title="Delete">
              <IconButton size="small" color="error" onClick={onDelete}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Manager Reviews Section
// ─────────────────────────────────────────────────────────────────────────────

function ManagerReviewsSection({ guildId }: { guildId: string }) {
  const qc = useQueryClient();

  const { data: reviews, isLoading } = useQuery<ManagerReview[]>({
    queryKey: ['manager-reviews', guildId],
    queryFn: async () =>
      (await client.get<ManagerReview[]>(`/api/guilds/${guildId}/manager/reviews`)).data,
    enabled: !!guildId,
    refetchInterval: 10_000,
  });

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/manager/reviews`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['manager-reviews', guildId] }),
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  const hasRunning = reviews?.some((r) => r.status === 'running' || r.status === 'pending');

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h6">Manager Reviews</Typography>
        <Button
          size="small"
          startIcon={<PlayArrowIcon />}
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending || hasRunning}
        >
          {hasRunning ? 'Review in progress…' : 'Run Review'}
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        The manager agent periodically reviews Grug's conversations and produces
        reports with observations and recommendations.
      </Typography>

      {(!reviews || reviews.length === 0) && (
        <Typography color="text.secondary" sx={{ py: 2 }}>
          No reviews yet. Click "Run Review" to trigger one, or configure periodic
          reviews via the MANAGER_REVIEW_ENABLED and MANAGER_REVIEW_CRON environment variables.
        </Typography>
      )}

      {reviews?.map((review) => (
        <ReviewCard key={review.id} review={review} />
      ))}
    </Box>
  );
}

function ReviewCard({ review }: { review: ManagerReview }) {
  const [expanded, setExpanded] = useState(false);

  const statusColor = {
    pending: 'default' as const,
    running: 'info' as const,
    completed: 'success' as const,
    failed: 'error' as const,
  }[review.status];

  const severityIcon: Record<string, string> = {
    info: 'ℹ️',
    minor: '⚠️',
    major: '🔶',
    critical: '🔴',
  };

  return (
    <Box
      sx={{
        p: 2,
        mb: 1.5,
        borderRadius: 1,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        cursor: review.summary ? 'pointer' : 'default',
      }}
      onClick={() => review.summary && setExpanded(!expanded)}
    >
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <Chip size="small" label={review.status} color={statusColor} />
        <Typography variant="caption" color="text.secondary">
          {review.created_at && new Date(review.created_at).toLocaleString()}
        </Typography>
        {review.messages_reviewed > 0 && (
          <Typography variant="caption" color="text.secondary">
            {review.messages_reviewed} messages, {review.feedback_reviewed} feedback
          </Typography>
        )}
      </Stack>

      {review.status === 'running' && (
        <Stack direction="row" alignItems="center" spacing={1}>
          <CircularProgress size={16} />
          <Typography variant="body2">Review in progress…</Typography>
        </Stack>
      )}

      {review.summary && (
        <Typography variant="body2" sx={{ mb: 1 }}>
          {review.summary}
        </Typography>
      )}

      {review.error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {review.error}
        </Alert>
      )}

      {expanded && review.observations && review.observations.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Observations</Typography>
          {review.observations.map((obs, i) => (
            <Typography key={i} variant="body2" sx={{ mb: 0.5 }}>
              {severityIcon[obs.severity] ?? 'ℹ️'} [{obs.category}] {obs.detail}
            </Typography>
          ))}
        </Box>
      )}

      {expanded && review.recommendations && review.recommendations.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Recommendations</Typography>
          {review.recommendations.map((rec, i) => (
            <Box key={i} sx={{ mb: 1, pl: 1, borderLeft: 2, borderColor: 'primary.main' }}>
              <Typography variant="body2">
                <strong>{rec.action}:</strong> {rec.reason}
              </Typography>
              <Typography
                variant="body2"
                sx={{ fontFamily: 'monospace', fontSize: '0.85rem', mt: 0.5 }}
              >
                {rec.content}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ManagerPage() {
  const { guildId } = useParams<{ guildId: string }>();

  if (!guildId) return null;

  return (
    <Box>
      <InstructionOverridesSection guildId={guildId} />
      <Divider sx={{ my: 4 }} />
      <ManagerReviewsSection guildId={guildId} />
    </Box>
  );
}
