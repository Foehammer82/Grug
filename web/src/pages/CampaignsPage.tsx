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
  IconButton,
  List,
  ListItem,
  ListItemText,
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
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
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

// ── Characters sub-row ────────────────────────────────────────────────────

interface CharactersRowProps {
  guildId: string;
  campaignId: number;
  open: boolean;
}

function CharactersRow({ guildId, campaignId, open }: CharactersRowProps) {
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

  if (!open) return null;

  return (
    <TableRow>
      <TableCell colSpan={6} sx={{ py: 0, bgcolor: 'action.hover' }}>
        <Collapse in={open} unmountOnExit>
          <Box sx={{ py: 2, px: 3 }}>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            ) : characters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No characters linked to this campaign yet.
              </Typography>
            ) : (
              <List dense disablePadding>
                {characters.map((ch) => (
                  <ListItem key={ch.id} disablePadding sx={{ py: 0.25 }}>
                    <ListItemText
                      primary={ch.name}
                      secondary={ch.system !== 'unknown' ? ch.system : undefined}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
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
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 40 }} />
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
                  {/* Main data row */}
                  <TableRow
                    key={`row-${c.id}`}
                    sx={{ '& > td': { verticalAlign: 'middle' } }}
                  >
                    {/* Expand characters toggle */}
                    <TableCell sx={{ py: 0 }}>
                      <Tooltip
                        title={expandedId === c.id ? 'Hide characters' : 'Show characters'}
                        placement="right"
                      >
                        <IconButton
                          size="small"
                          onClick={() => setExpandedId((v) => (v === c.id ? null : c.id))}
                        >
                          {expandedId === c.id ? (
                            <ExpandLessIcon fontSize="small" />
                          ) : (
                            <ExpandMoreIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>

                    {/* Name cell — inline edit */}
                    <TableCell>
                      {editId === c.id ? (
                        <TextField
                          size="small"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          sx={{ minWidth: 150 }}
                        />
                      ) : (
                        <Typography variant="body2" fontWeight={600}>
                          {c.name}
                        </Typography>
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
                            <TextField {...params} label="System" />
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
                            <TextField {...params} label="Channel" />
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
                          onClick={() => setEditActive((v) => !v)}
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
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap', py: 0.5 }}>
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
                            <Button
                              size="small"
                              onClick={() => startEdit(c)}
                            >
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

                  {/* Characters sub-row */}
                  <CharactersRow
                    key={`chars-${c.id}`}
                    guildId={guildId!}
                    campaignId={c.id}
                    open={expandedId === c.id}
                  />
                </>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}
