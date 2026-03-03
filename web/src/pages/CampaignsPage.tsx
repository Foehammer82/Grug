import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
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
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import PersonIcon from '@mui/icons-material/Person';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import { TABLE_HEADER_SX } from '../types';
import type { Campaign, Character, DiscordChannel } from '../types';

const SYSTEM_OPTIONS = [
  'dnd5e',
  'pf2e',
  'coc7',
  'mothership',
  'blades-in-the-dark',
  'shadowdark',
  'shadowrun',
  'warhammer-fantasy',
  'unknown',
];

// ── Characters panel ──────────────────────────────────────────────────────

interface CharactersPanelProps {
  guildId: string;
  campaignId: number;
  open: boolean;
  isAdmin: boolean;
  colSpan: number;
}

function CharactersPanel({ guildId, campaignId, open, isAdmin, colSpan }: CharactersPanelProps) {
  const qc = useQueryClient();

  // Add form
  const [showAdd, setShowAdd] = useState(false);
  const [addName, setAddName] = useState('');
  const [addSystem, setAddSystem] = useState('');

  // Inline edit
  const [editCharId, setEditCharId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editSystem, setEditSystem] = useState('');

  // Delete confirm
  const [deleteCharId, setDeleteCharId] = useState<number | null>(null);

  const { data: characters = [], isLoading } = useQuery<Character[]>({
    queryKey: ['campaign-characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`
      );
      return res.data;
    },
    enabled: open && !!guildId,
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });

  const createMutation = useMutation({
    mutationFn: () =>
      client.post(`/api/guilds/${guildId}/campaigns/${campaignId}/characters`, {
        name: addName,
        system: addSystem || 'unknown',
      }),
    onSuccess: () => {
      invalidate();
      setAddName('');
      setAddSystem('');
      setShowAdd(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${editCharId}`,
        { name: editName, system: editSystem }
      ),
    onSuccess: () => {
      invalidate();
      setEditCharId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      client.delete(`/api/guilds/${guildId}/campaigns/${campaignId}/characters/${id}`),
    onSuccess: () => {
      invalidate();
      setDeleteCharId(null);
    },
  });

  function startEdit(ch: Character) {
    setEditCharId(ch.id);
    setEditName(ch.name);
    setEditSystem(ch.system);
    setDeleteCharId(null);
  }

  if (!open) return null;

  return (
    <TableRow>
      <TableCell colSpan={colSpan} sx={{ py: 0, bgcolor: 'action.hover', borderBottom: 0 }}>
        <Collapse in={open} unmountOnExit>
          <Box sx={{ py: 2, px: 3 }}>
            {/* Header row */}
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.5}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <PersonIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Characters
                </Typography>
              </Stack>
              {isAdmin && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => { setShowAdd((v) => !v); setEditCharId(null); }}
                >
                  {showAdd ? 'Cancel' : '+ Add Character'}
                </Button>
              )}
            </Stack>

            {/* Add form */}
            <Collapse in={showAdd} unmountOnExit>
              <Paper
                variant="outlined"
                component="form"
                sx={{ p: 2, mb: 2 }}
                onSubmit={(e: React.FormEvent) => { e.preventDefault(); createMutation.mutate(); }}
              >
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                  <TextField
                    label="Name"
                    size="small"
                    required
                    value={addName}
                    onChange={(e) => setAddName(e.target.value)}
                    sx={{ minWidth: 180 }}
                  />
                  <Autocomplete
                    size="small"
                    freeSolo
                    options={SYSTEM_OPTIONS}
                    value={addSystem}
                    onInputChange={(_, v) => setAddSystem(v)}
                    sx={{ minWidth: 160 }}
                    renderInput={(params) => (
                      <TextField {...params} label="System" placeholder="e.g. pf2e" />
                    )}
                  />
                  <Button
                    type="submit"
                    variant="contained"
                    size="small"
                    disabled={createMutation.isPending}
                  >
                    Add
                  </Button>
                </Stack>
              </Paper>
            </Collapse>

            {/* Character list */}
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            ) : characters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No characters linked to this campaign yet.
                {isAdmin && ' Use "+ Add Character" to create one.'}
              </Typography>
            ) : (
              <Stack divider={<Divider />} spacing={0}>
                {characters.map((ch) => (
                  <Box
                    key={ch.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      py: 0.75,
                      flexWrap: 'wrap',
                    }}
                  >
                    {editCharId === ch.id ? (
                      <>
                        <TextField
                          size="small"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          sx={{ minWidth: 160 }}
                        />
                        <Autocomplete
                          size="small"
                          freeSolo
                          options={SYSTEM_OPTIONS}
                          value={editSystem}
                          onInputChange={(_, v) => setEditSystem(v)}
                          sx={{ minWidth: 140 }}
                          renderInput={(params) => <TextField {...params} label="System" />}
                        />
                        <Button
                          size="small"
                          variant="contained"
                          disabled={updateMutation.isPending}
                          onClick={() => updateMutation.mutate()}
                        >
                          Save
                        </Button>
                        <Button size="small" onClick={() => setEditCharId(null)}>
                          Cancel
                        </Button>
                      </>
                    ) : deleteCharId === ch.id ? (
                      <>
                        <Typography variant="body2" sx={{ flex: 1 }}>
                          <strong>{ch.name}</strong>
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Delete?
                        </Typography>
                        <Button
                          size="small"
                          color="error"
                          variant="contained"
                          disabled={deleteMutation.isPending}
                          onClick={() => deleteMutation.mutate(ch.id)}
                        >
                          Yes
                        </Button>
                        <Button size="small" onClick={() => setDeleteCharId(null)}>
                          No
                        </Button>
                      </>
                    ) : (
                      <>
                        <Typography variant="body2" fontWeight={500} sx={{ flex: 1 }}>
                          {ch.name}
                        </Typography>
                        {ch.system && ch.system !== 'unknown' && (
                          <Chip label={ch.system} size="small" variant="outlined" />
                        )}
                        {isAdmin && (
                          <Stack direction="row" spacing={0.5}>
                            <Button size="small" onClick={() => startEdit(ch)}>
                              Edit
                            </Button>
                            <Button
                              size="small"
                              color="error"
                              onClick={() => { setDeleteCharId(ch.id); setEditCharId(null); }}
                            >
                              Delete
                            </Button>
                          </Stack>
                        )}
                      </>
                    )}
                  </Box>
                ))}
              </Stack>
            )}
          </Box>
        </Collapse>
      </TableCell>
    </TableRow>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function CampaignsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();
  const { isAdmin } = useGuildContext();

  // Create form state
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSystem, setNewSystem] = useState<string>('');
  const [newChannel, setNewChannel] = useState<DiscordChannel | null>(null);

  // Edit state — keeps track of which row is being edited
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editSystem, setEditSystem] = useState('');
  const [editChannel, setEditChannel] = useState<DiscordChannel | null>(null);
  const [editActive, setEditActive] = useState(true);

  // Expanded characters rows
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Delete confirmation
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: channels = [], isLoading: channelsLoading } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ['campaigns', guildId],
    queryFn: async () => {
      const res = await client.get<Campaign[]>(`/api/guilds/${guildId}/campaigns`);
      return res.data;
    },
    enabled: !!guildId,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/campaigns`, {
        name: newName,
        system: newSystem || 'unknown',
        channel_id: newChannel?.id ?? '',
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setNewName('');
      setNewSystem('');
      setNewChannel(null);
      setShowForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {};
      if (editName) payload.name = editName;
      if (editSystem) payload.system = editSystem;
      if (editChannel !== null) payload.channel_id = editChannel.id;
      payload.is_active = editActive;
      await client.patch(`/api/guilds/${guildId}/campaigns/${editId}`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/campaigns/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setDeleteId(null);
    },
  });

  // ── Helpers ───────────────────────────────────────────────────────────────

  function startEdit(c: Campaign) {
    setEditId(c.id);
    setEditName(c.name);
    setEditSystem(c.system);
    setEditChannel(channels.find((ch) => ch.id === c.channel_id) ?? null);
    setEditActive(c.is_active);
  }

  function cancelEdit() {
    setEditId(null);
    setEditName('');
    setEditSystem('');
    setEditChannel(null);
    setEditActive(true);
  }

  const channelName = (id: string): string => {
    const ch = channels.find((c) => c.id === id);
    return ch ? `#${ch.name}` : `#${id}`;
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 1000 }}>
      <Typography variant="body2" color="text.secondary">
        Campaigns tie a Discord channel to a game session. Grug uses the active campaign
        to track characters, documents, and context for that channel.
      </Typography>

      {/* Toolbar */}
      {isAdmin && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            size="small"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? 'Cancel' : '+ New Campaign'}
          </Button>
        </Box>
      )}

      {/* Create form */}
      <Collapse in={showForm} unmountOnExit>
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            New Campaign
          </Typography>
          <Stack
            component="form"
            spacing={2}
            onSubmit={(e: React.FormEvent) => {
              e.preventDefault();
              createMutation.mutate();
            }}
          >
            <TextField
              label="Name"
              size="small"
              required
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Autocomplete
              size="small"
              freeSolo
              options={SYSTEM_OPTIONS}
              value={newSystem}
              onInputChange={(_, v) => setNewSystem(v)}
              renderInput={(params) => (
                <TextField {...params} label="Game System" placeholder="e.g. dnd5e" />
              )}
            />
            <Autocomplete
              size="small"
              options={channels}
              loading={channelsLoading}
              value={newChannel}
              onChange={(_, ch) => setNewChannel(ch)}
              getOptionLabel={(ch) => `#${ch.name}`}
              filterOptions={(opts, { inputValue }) => {
                const q = inputValue.toLowerCase();
                return opts.filter(
                  (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q)
                );
              }}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              renderOption={(props, ch) => (
                <Box component="li" {...props} key={ch.id}>
                  <span>#{ch.name}</span>
                  <Typography
                    component="span"
                    variant="caption"
                    color="text.disabled"
                    sx={{ ml: 1 }}
                  >
                    {ch.id}
                  </Typography>
                </Box>
              )}
              renderInput={(params) => (
                <TextField {...params} label="Channel" required />
              )}
            />
            <Box>
              <Button
                type="submit"
                variant="contained"
                size="small"
                disabled={createMutation.isPending}
              >
                Create
              </Button>
            </Box>
          </Stack>
        </Paper>
      </Collapse>

      {/* Campaigns table */}
      {campaigns.length === 0 ? (
        <Typography color="text.secondary">No campaigns yet.</Typography>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary">
            Click a row to view and manage its characters.
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={TABLE_HEADER_SX}>Name</TableCell>
                  <TableCell sx={TABLE_HEADER_SX}>System</TableCell>
                  <TableCell sx={TABLE_HEADER_SX}>Channel</TableCell>
                  <TableCell sx={TABLE_HEADER_SX}>Status</TableCell>
                  {isAdmin && <TableCell sx={TABLE_HEADER_SX} align="right">Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {campaigns.map((c) => (
                  <>
                    {/* Main data row — clicking it toggles the characters panel */}
                    <TableRow
                      key={`row-${c.id}`}
                      hover={editId !== c.id}
                      onClick={() => {
                        if (editId !== c.id && deleteId !== c.id) {
                          setExpandedId((v) => (v === c.id ? null : c.id));
                        }
                      }}
                      sx={{
                        cursor: editId === c.id || deleteId === c.id ? 'default' : 'pointer',
                        '& > td': { verticalAlign: 'middle' },
                        ...(expandedId === c.id && {
                          bgcolor: 'action.selected',
                        }),
                      }}
                    >
                      {/* Name cell — shows expand chevron inline */}
                      <TableCell>
                        {editId === c.id ? (
                          <TextField
                            size="small"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            sx={{ minWidth: 150 }}
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <Stack direction="row" alignItems="center" spacing={0.5}>
                            {expandedId === c.id ? (
                              <ExpandLessIcon fontSize="small" sx={{ color: 'text.secondary', flexShrink: 0 }} />
                            ) : (
                              <ExpandMoreIcon fontSize="small" sx={{ color: 'text.disabled', flexShrink: 0 }} />
                            )}
                            <Typography variant="body2" fontWeight={600}>
                              {c.name}
                            </Typography>
                          </Stack>
                        )}
                      </TableCell>

                      {/* System cell — inline edit */}
                      <TableCell>
                        {editId === c.id ? (
                          <Autocomplete
                            size="small"
                            freeSolo
                            options={SYSTEM_OPTIONS}
                            value={editSystem}
                            onInputChange={(_, v) => setEditSystem(v)}
                            sx={{ minWidth: 150 }}
                            renderInput={(params) => (
                              <TextField {...params} label="System" onClick={(e) => e.stopPropagation()} />
                            )}
                          />
                        ) : (
                          <Typography variant="body2">{c.system}</Typography>
                        )}
                      </TableCell>

                      {/* Channel cell — inline edit */}
                      <TableCell>
                        {editId === c.id ? (
                          <Autocomplete
                            size="small"
                            options={channels}
                            loading={channelsLoading}
                            value={editChannel}
                            onChange={(_, ch) => setEditChannel(ch)}
                            getOptionLabel={(ch) => `#${ch.name}`}
                            isOptionEqualToValue={(a, b) => a.id === b.id}
                            filterOptions={(opts, { inputValue }) => {
                              const q = inputValue.toLowerCase();
                              return opts.filter(
                                (ch) =>
                                  ch.name.toLowerCase().includes(q) || ch.id.includes(q)
                              );
                            }}
                            renderOption={(props, ch) => (
                              <Box component="li" {...props} key={ch.id}>
                                <span>#{ch.name}</span>
                                <Typography
                                  component="span"
                                  variant="caption"
                                  color="text.disabled"
                                  sx={{ ml: 1 }}
                                >
                                  {ch.id}
                                </Typography>
                              </Box>
                            )}
                            sx={{ minWidth: 180 }}
                            renderInput={(params) => (
                              <TextField {...params} label="Channel" onClick={(e) => e.stopPropagation()} />
                            )}
                          />
                        ) : (
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            {channelName(c.channel_id)}
                          </Typography>
                        )}
                      </TableCell>

                      {/* Status cell — active toggle when editing */}
                      <TableCell>
                        {editId === c.id ? (
                          <Chip
                            label={editActive ? 'Active' : 'Inactive'}
                            size="small"
                            color={editActive ? 'success' : 'default'}
                            onClick={(e) => { e.stopPropagation(); setEditActive((v) => !v); }}
                            sx={{ cursor: 'pointer' }}
                          />
                        ) : (
                          <Chip
                            label={c.is_active ? 'Active' : 'Inactive'}
                            size="small"
                            color={c.is_active ? 'success' : 'default'}
                          />
                        )}
                      </TableCell>

                      {/* Actions */}
                      {isAdmin && (
                        <TableCell
                          align="right"
                          sx={{ whiteSpace: 'nowrap', py: 0.5 }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {editId === c.id ? (
                            <Stack direction="row" spacing={1} justifyContent="flex-end">
                              <Button
                                size="small"
                                variant="contained"
                                disabled={updateMutation.isPending}
                                onClick={() => updateMutation.mutate()}
                              >
                                Save
                              </Button>
                              <Button size="small" onClick={cancelEdit}>
                                Cancel
                              </Button>
                            </Stack>
                          ) : deleteId === c.id ? (
                            <Stack direction="row" spacing={1} justifyContent="flex-end">
                              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                                Delete?
                              </Typography>
                              <Button
                                size="small"
                                color="error"
                                variant="contained"
                                disabled={deleteMutation.isPending}
                                onClick={() => deleteMutation.mutate(c.id)}
                              >
                                Yes
                              </Button>
                              <Button size="small" onClick={() => setDeleteId(null)}>
                                No
                              </Button>
                            </Stack>
                          ) : (
                            <Stack direction="row" spacing={1} justifyContent="flex-end">
                              <Button size="small" onClick={() => startEdit(c)}>
                                Edit
                              </Button>
                              <Button
                                size="small"
                                color="error"
                                onClick={() => setDeleteId(c.id)}
                              >
                                Delete
                              </Button>
                            </Stack>
                          )}
                        </TableCell>
                      )}
                    </TableRow>

                    {/* Characters panel */}
                    <CharactersPanel
                      key={`chars-${c.id}`}
                      guildId={guildId!}
                      campaignId={c.id}
                      open={expandedId === c.id}
                      isAdmin={isAdmin}
                      colSpan={isAdmin ? 5 : 4}
                    />
                  </>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Stack>
  );
}
