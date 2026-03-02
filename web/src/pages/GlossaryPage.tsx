import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface GlossaryTerm {
  id: number;
  guild_id: number;
  channel_id: number | null;
  term: string;
  definition: string;
  ai_generated: boolean;
  originally_ai_generated: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
}

interface HistoryEntry {
  id: number;
  term_id: number;
  guild_id: number;
  old_term: string;
  old_definition: string;
  old_ai_generated: boolean;
  changed_by: number;
  changed_at: string;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

function SourceChip({ term }: { term: GlossaryTerm }) {
  if (term.ai_generated) return <Chip label="🤖 AI" size="small" color="secondary" />;
  if (term.originally_ai_generated) return <Chip label="🤖→👤 Edited" size="small" color="warning" />;
  return <Chip label="👤 Human" size="small" color="success" />;
}

export default function GlossaryPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const [filterChannel, setFilterChannel] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [newTerm, setNewTerm] = useState('');
  const [newDef, setNewDef] = useState('');
  const [newChannel, setNewChannel] = useState<string>('');
  const [editId, setEditId] = useState<number | null>(null);
  const [editTerm, setEditTerm] = useState('');
  const [editDef, setEditDef] = useState('');
  const [historyTermId, setHistoryTermId] = useState<number | null>(null);

  const { data: channels = [] } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const channelName = (id: number | null): string => {
    if (!id) return 'Server-wide';
    const ch = channels.find((c) => c.id === String(id));
    return ch ? `#${ch.name}` : `#${id}`;
  };

  const queryParams = filterChannel ? `?channel_id=${filterChannel}` : '';
  const { data: terms = [], isLoading } = useQuery<GlossaryTerm[]>({
    queryKey: ['glossary', guildId, filterChannel],
    queryFn: async () => {
      const res = await client.get<GlossaryTerm[]>(`/api/guilds/${guildId}/glossary${queryParams}`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const { data: history = [] } = useQuery<HistoryEntry[]>({
    queryKey: ['glossary-history', guildId, historyTermId],
    queryFn: async () => {
      const res = await client.get<HistoryEntry[]>(
        `/api/guilds/${guildId}/glossary/${historyTermId}/history`
      );
      return res.data;
    },
    enabled: !!historyTermId,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/glossary`, {
        term: newTerm,
        definition: newDef,
        channel_id: newChannel ? parseInt(newChannel) : null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['glossary', guildId] });
      setNewTerm('');
      setNewDef('');
      setNewChannel('');
      setShowForm(false);
    },
  });

  const editMutation = useMutation({
    mutationFn: async () => {
      await client.patch(`/api/guilds/${guildId}/glossary/${editId}`, {
        term: editTerm || undefined,
        definition: editDef || undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['glossary', guildId] });
      setEditId(null);
      setEditTerm('');
      setEditDef('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/glossary/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary', guildId] }),
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 900 }}>
      {/* Section header */}
      <Typography variant="body2" color="text.secondary">
        Server-specific terms and definitions Grug knows about. Grug automatically adds
        entries when he encounters new lore or rulings in chat. You can also add terms
        manually and override anything Grug has written.
      </Typography>

      {/* Toolbar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="channel-filter-label">Filter by channel</InputLabel>
          <Select
            labelId="channel-filter-label"
            value={filterChannel}
            label="Filter by channel"
            onChange={(e) => setFilterChannel(e.target.value)}
          >
            <MenuItem value="">All scopes</MenuItem>
            {channels.map((c) => (
              <MenuItem key={c.id} value={c.id}>#{c.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" size="small" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : '+ Add Term'}
        </Button>
      </Box>

      {/* Add term form */}
      <Collapse in={showForm} unmountOnExit>
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>New Term</Typography>
          <Stack
            component="form"
            spacing={2}
            onSubmit={(e: React.FormEvent) => {
              e.preventDefault();
              createMutation.mutate();
            }}
          >
            <TextField
              label="Term"
              size="small"
              required
              value={newTerm}
              onChange={(e) => setNewTerm(e.target.value)}
            />
            <TextField
              label="Definition"
              size="small"
              required
              multiline
              minRows={3}
              value={newDef}
              onChange={(e) => setNewDef(e.target.value)}
            />
            <FormControl size="small">
              <InputLabel id="new-channel-label">Channel scope</InputLabel>
              <Select
                labelId="new-channel-label"
                value={newChannel}
                label="Channel scope"
                onChange={(e) => setNewChannel(e.target.value)}
              >
                <MenuItem value="">Server-wide</MenuItem>
                {channels.map((c) => (
                  <MenuItem key={c.id} value={c.id}>#{c.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Button type="submit" variant="contained" size="small" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Saving…' : 'Save'}
              </Button>
              {createMutation.isError && (
                <Typography color="error" variant="caption">Error saving term.</Typography>
              )}
            </Box>
          </Stack>
        </Paper>
      </Collapse>

      {/* Term list */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {!isLoading && terms.length === 0 && (
        <Typography color="text.secondary">No glossary terms yet.</Typography>
      )}

      {terms.map((t) => (
        <Paper key={t.id} variant="outlined" sx={{ p: 2 }}>
          {editId === t.id ? (
            <Stack
              component="form"
              spacing={2}
              onSubmit={(e: React.FormEvent) => {
                e.preventDefault();
                editMutation.mutate();
              }}
            >
              <TextField
                label="Term"
                size="small"
                value={editTerm}
                onChange={(e) => setEditTerm(e.target.value)}
                placeholder={t.term}
              />
              <TextField
                label="Definition"
                size="small"
                multiline
                minRows={2}
                value={editDef}
                onChange={(e) => setEditDef(e.target.value)}
                placeholder={t.definition}
              />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button type="submit" variant="contained" size="small" disabled={editMutation.isPending}>
                  Save
                </Button>
                <Button variant="outlined" size="small" onClick={() => setEditId(null)}>
                  Cancel
                </Button>
              </Box>
            </Stack>
          ) : (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 0.5 }}>
                <Typography fontWeight={600}>{t.term}</Typography>
                <Typography variant="caption" color="text.secondary">{channelName(t.channel_id)}</Typography>
                <SourceChip term={t} />
              </Box>
              <Typography variant="body2" sx={{ mb: 1.5 }}>{t.definition}</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    setEditId(t.id);
                    setEditTerm(t.term);
                    setEditDef(t.definition);
                  }}
                >
                  Edit
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => setHistoryTermId(historyTermId === t.id ? null : t.id)}
                >
                  {historyTermId === t.id ? 'Hide History' : 'History'}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  onClick={() => {
                    if (window.confirm(`Delete "${t.term}"?`)) deleteMutation.mutate(t.id);
                  }}
                >
                  Delete
                </Button>
              </Box>

              {/* Inline history panel */}
              <Collapse in={historyTermId === t.id} unmountOnExit>
                <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    Change history
                  </Typography>
                  {history.length === 0 && (
                    <Typography variant="body2" color="text.secondary">No history yet.</Typography>
                  )}
                  {history.map((h) => (
                    <Box key={h.id}>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="body2">
                        <strong>Was:</strong> {h.old_term} — {h.old_definition}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(h.changed_at).toLocaleString()} · changed by{' '}
                        {h.changed_by === 0 ? '🤖 AI' : `user ${h.changed_by}`}
                        {h.old_ai_generated && ' · was AI-generated'}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Collapse>
            </>
          )}
        </Paper>
      ))}
    </Stack>
  );
}
