import {
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useGuildContext } from '../hooks/useGuildContext';
import { useAuth } from '../hooks/useAuth';
import type { AvailabilityPoll, PollOption, PollVote } from '../types';

/* ------------------------------------------------------------------ */
/* AvailabilityPollsPanel — list + create polls for an event          */
/* ------------------------------------------------------------------ */

interface Props {
  eventId?: number;
}

export default function AvailabilityPollsPanel({ eventId }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const { isAdmin } = useGuildContext();
  const qc = useQueryClient();

  const [createOpen, setCreateOpen] = useState(false);
  const [viewPoll, setViewPoll] = useState<AvailabilityPoll | null>(null);

  const { data: polls, isLoading } = useQuery<AvailabilityPoll[]>({
    queryKey: ['polls', guildId],
    queryFn: async () => {
      const res = await client.get<AvailabilityPoll[]>(`/api/guilds/${guildId}/polls`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const filteredPolls = eventId
    ? polls?.filter((p) => p.event_id === eventId)
    : polls;

  const deleteMutation = useMutation({
    mutationFn: async (pollId: number) => {
      await client.delete(`/api/guilds/${guildId}/polls/${pollId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['polls', guildId] }),
  });

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2">Availability Polls</Typography>
        {isAdmin && (
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            New Poll
          </Button>
        )}
      </Box>

      {isLoading ? (
        <CircularProgress size={16} />
      ) : filteredPolls && filteredPolls.length > 0 ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {filteredPolls.map((poll) => {
            const totalVotes = poll.votes.length;
            const winner = poll.winner_option_id != null
              ? poll.options.find((o) => o.id === poll.winner_option_id)
              : null;
            return (
              <Box
                key={poll.id}
                sx={{
                  p: 1.5,
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 0.5,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Typography variant="body2" fontWeight={600}>
                    {poll.title}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Button size="small" onClick={() => setViewPoll(poll)}>
                      View
                    </Button>
                    {isAdmin && (
                      <IconButton
                        size="small"
                        onClick={() => deleteMutation.mutate(poll.id)}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {poll.options.length} option{poll.options.length !== 1 ? 's' : ''} · {totalVotes} vote{totalVotes !== 1 ? 's' : ''}
                  {poll.closes_at ? ` · Closes ${new Date(poll.closes_at).toLocaleDateString()}` : ''}
                </Typography>
                {winner && (
                  <Chip
                    icon={<EmojiEventsIcon />}
                    label={`Winner: ${winner.label}`}
                    size="small"
                    color="success"
                    sx={{ alignSelf: 'flex-start' }}
                  />
                )}
              </Box>
            );
          })}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No availability polls yet.
          {isAdmin && ' Create one to let members vote on a time.'}
        </Typography>
      )}

      {createOpen && (
        <CreatePollModal
          eventId={eventId}
          open={createOpen}
          onClose={() => setCreateOpen(false)}
        />
      )}

      {viewPoll && (
        <PollDetailModal
          poll={viewPoll}
          open={!!viewPoll}
          onClose={() => setViewPoll(null)}
        />
      )}
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/* Create Poll Modal                                                   */
/* ------------------------------------------------------------------ */

interface CreatePollModalProps {
  eventId?: number;
  open: boolean;
  onClose: () => void;
}

function CreatePollModal({ eventId, open, onClose }: CreatePollModalProps) {
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const [title, setTitle] = useState('');
  const [options, setOptions] = useState<{ label: string; start_time: string; end_time: string }[]>([
    { label: '', start_time: '', end_time: '' },
  ]);

  const addOption = () =>
    setOptions((prev) => [...prev, { label: '', start_time: '', end_time: '' }]);

  const removeOption = (i: number) =>
    setOptions((prev) => prev.filter((_, idx) => idx !== i));

  const updateOption = (i: number, field: string, value: string) =>
    setOptions((prev) => prev.map((o, idx) => (idx === i ? { ...o, [field]: value } : o)));

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        title,
        event_id: eventId ?? null,
        options: options.map((o, i) => ({
          id: i + 1,
          label: o.label || `Option ${i + 1}`,
          start_time: o.start_time ? new Date(o.start_time).toISOString() : null,
          end_time: o.end_time ? new Date(o.end_time).toISOString() : null,
        })),
      };
      await client.post(`/api/guilds/${guildId}/polls`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['polls', guildId] });
      onClose();
    },
  });

  const isValid = title.trim().length > 0 && options.some((o) => o.label.trim());

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New Availability Poll</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
        <TextField
          label="Poll Title"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          fullWidth
          size="small"
          autoFocus
        />

        <Typography variant="subtitle2">Options</Typography>
        {options.map((opt, i) => (
          <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <TextField
              label={`Option ${i + 1}`}
              value={opt.label}
              onChange={(e) => updateOption(i, 'label', e.target.value)}
              size="small"
              sx={{ flex: 2 }}
              placeholder="e.g. Saturday 7pm"
            />
            <TextField
              label="Start"
              type="datetime-local"
              value={opt.start_time}
              onChange={(e) => updateOption(i, 'start_time', e.target.value)}
              size="small"
              sx={{ flex: 2 }}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="End"
              type="datetime-local"
              value={opt.end_time}
              onChange={(e) => updateOption(i, 'end_time', e.target.value)}
              size="small"
              sx={{ flex: 2 }}
              InputLabelProps={{ shrink: true }}
            />
            {options.length > 1 && (
              <IconButton size="small" onClick={() => removeOption(i)} sx={{ mt: 0.5 }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        ))}
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={addOption}
          sx={{ alignSelf: 'flex-start' }}
        >
          Add Option
        </Button>

        {createMutation.isError && (
          <Typography color="error" variant="body2">
            Failed to create poll. Please try again.
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!isValid || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          {createMutation.isPending ? 'Creating…' : 'Create Poll'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Poll Detail / Voting Modal                                          */
/* ------------------------------------------------------------------ */

interface PollDetailModalProps {
  poll: AvailabilityPoll;
  open: boolean;
  onClose: () => void;
}

function PollDetailModal({ poll, open, onClose }: PollDetailModalProps) {
  const { guildId } = useParams<{ guildId: string }>();
  const { isAdmin } = useGuildContext();
  const authQuery = useAuth();
  const currentUserId = authQuery.data?.id ?? null;
  const qc = useQueryClient();

  // Reload full poll with votes
  const { data: fullPoll, isLoading } = useQuery<AvailabilityPoll>({
    queryKey: ['poll', guildId, poll.id],
    queryFn: async () => {
      const res = await client.get<AvailabilityPoll>(`/api/guilds/${guildId}/polls/${poll.id}`);
      return res.data;
    },
    enabled: !!guildId && open,
  });

  const activePoll = fullPoll ?? poll;

  const myVote: PollVote | null =
    activePoll.votes.find((v) => v.discord_user_id === currentUserId) ?? null;
  const [selectedIds, setSelectedIds] = useState<number[]>(myVote?.option_ids ?? []);

  const voteMutation = useMutation({
    mutationFn: async () => {
      await client.put(`/api/guilds/${guildId}/polls/${poll.id}/vote`, {
        option_ids: selectedIds,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['poll', guildId, poll.id] });
      qc.invalidateQueries({ queryKey: ['polls', guildId] });
    },
  });

  const pickWinnerMutation = useMutation({
    mutationFn: async (optionId: number) => {
      await client.patch(`/api/guilds/${guildId}/polls/${poll.id}`, {
        winner_option_id: optionId,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['poll', guildId, poll.id] });
      qc.invalidateQueries({ queryKey: ['polls', guildId] });
    },
  });

  const toggleOption = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  if (isLoading) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogContent>
          <CircularProgress />
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{activePoll.title}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
        {activePoll.winner_option_id != null && (
          <Chip
            icon={<EmojiEventsIcon />}
            label={`Winner: ${activePoll.options.find((o) => o.id === activePoll.winner_option_id)?.label ?? 'Unknown'}`}
            color="success"
            sx={{ alignSelf: 'flex-start' }}
          />
        )}

        <Typography variant="body2" color="text.secondary">
          Select all times that work for you:
        </Typography>

        {(activePoll.options as PollOption[]).map((opt) => {
          const votesForOption = activePoll.votes.filter((v) =>
            v.option_ids.includes(opt.id)
          ).length;
          const isWinner = activePoll.winner_option_id === opt.id;

          return (
            <Box
              key={opt.id}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                p: 1,
                borderRadius: 1,
                bgcolor: isWinner ? 'success.light' : 'action.hover',
                border: isWinner ? '2px solid' : '1px solid',
                borderColor: isWinner ? 'success.main' : 'divider',
              }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selectedIds.includes(opt.id)}
                    onChange={() => toggleOption(opt.id)}
                    size="small"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2" fontWeight={isWinner ? 700 : 400}>
                      {isWinner && '🏆 '}{opt.label}
                    </Typography>
                    {opt.start_time && (
                      <Typography variant="caption" color="text.secondary">
                        {new Date(opt.start_time).toLocaleString()}
                        {opt.end_time ? ` – ${new Date(opt.end_time).toLocaleTimeString()}` : ''}
                      </Typography>
                    )}
                  </Box>
                }
              />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip label={`${votesForOption} vote${votesForOption !== 1 ? 's' : ''}`} size="small" />
                {isAdmin && activePoll.winner_option_id == null && (
                  <Tooltip title="Pick this as the winner">
                    <IconButton
                      size="small"
                      onClick={() => pickWinnerMutation.mutate(opt.id)}
                      disabled={pickWinnerMutation.isPending}
                    >
                      <EmojiEventsIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Box>
          );
        })}

        <Divider />
        <Typography variant="caption" color="text.secondary">
          {activePoll.votes.length} member{activePoll.votes.length !== 1 ? 's' : ''} voted
          {activePoll.closes_at ? ` · Closes ${new Date(activePoll.closes_at).toLocaleDateString()}` : ''}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button
          variant="contained"
          onClick={() => voteMutation.mutate()}
          disabled={voteMutation.isPending}
        >
          {myVote ? 'Update Vote' : 'Submit Vote'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
