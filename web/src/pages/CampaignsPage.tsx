import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Paper,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import TableRestaurantIcon from '@mui/icons-material/TableRestaurant';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import { SYSTEM_OPTIONS, SYSTEM_LABELS } from '../constants/character';
import CampaignCard from '../components/campaigns/CampaignCard';
import type { Campaign, DiscordChannel, GuildMember } from '../types';

// ── Main page ─────────────────────────────────────────────────────────────

export default function CampaignsPage() {
  const { data: me } = useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();
  const { isAdmin } = useGuildContext();
  const currentUserId = me?.id ?? '';

  // Create form state
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSystem, setNewSystem] = useState<string>('');
  const [newChannel, setNewChannel] = useState<DiscordChannel | null>(null);

  // Edit campaign dialog state
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editSystem, setEditSystem] = useState('');
  const [editChannel, setEditChannel] = useState<DiscordChannel | null>(null);
  const [editActive, setEditActive] = useState(true);
  const [editGmMember, setEditGmMember] = useState<GuildMember | null>(null);

  // Create GM state
  const [newGmMember, setNewGmMember] = useState<GuildMember | null>(null);

  // Create banking state
  const [newPlayerBankingEnabled, setNewPlayerBankingEnabled] = useState(false);

  // Edit banking state
  const [editPlayerBankingEnabled, setEditPlayerBankingEnabled] = useState(false);

  // Delete confirmation
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // Snackbar shown after soft-delete, allows undo
  const [undoSnackbar, setUndoSnackbar] = useState<{ id: number; name: string } | null>(null);

  // Permanently-delete confirmation
  const [permanentDeleteId, setPermanentDeleteId] = useState<number | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: channels = [], isLoading: channelsLoading } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const { data: guildMembers = [], isLoading: membersLoading } = useQuery<GuildMember[]>({
    queryKey: ['guild-members', guildId],
    queryFn: async () => {
      const res = await client.get<GuildMember[]>(`/api/guilds/${guildId}/members`);
      return res.data;
    },
    enabled: !!guildId && isAdmin,
  });

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ['campaigns', guildId],
    queryFn: async () => {
      const res = await client.get<Campaign[]>(
        `/api/guilds/${guildId}/campaigns?include_deleted=true`,
      );
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
        channel_id: newChannel?.id ?? null,
        gm_discord_user_id: newGmMember?.discord_user_id ?? null,
        banking_enabled: true,
        player_banking_enabled: newPlayerBankingEnabled,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setNewName('');
      setNewSystem('');
      setNewChannel(null);
      setNewGmMember(null);
      setNewPlayerBankingEnabled(false);
      setShowForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      await client.patch(`/api/guilds/${guildId}/campaigns/${editId}`, {
        name: editName,
        system: editSystem,
        channel_id: editChannel?.id ?? null,
        is_active: editActive,
        gm_discord_user_id: editGmMember?.discord_user_id ?? null,
        banking_enabled: true,
        player_banking_enabled: editPlayerBankingEnabled,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      cancelEdit();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/campaigns/${id}`);
    },
    onSuccess: (_, id) => {
      const c = campaigns.find((x) => x.id === id);
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setDeleteId(null);
      if (c) setUndoSnackbar({ id, name: c.name });
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (id: number) =>
      client.post(`/api/guilds/${guildId}/campaigns/${id}/restore`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setUndoSnackbar(null);
    },
  });

  const permanentDeleteMutation = useMutation({
    mutationFn: (id: number) =>
      client.delete(`/api/guilds/${guildId}/campaigns/${id}/permanent`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setPermanentDeleteId(null);
    },
  });

  // ── Helpers ───────────────────────────────────────────────────────────────

  function startEdit(c: Campaign) {
    setEditId(c.id);
    setEditName(c.name);
    setEditSystem(c.system);
    setEditChannel(channels.find((ch) => ch.id === c.channel_id) ?? null);
    setEditActive(c.is_active);
    setEditGmMember(guildMembers.find((m) => m.discord_user_id === c.gm_discord_user_id) ?? null);
    setEditPlayerBankingEnabled(c.player_banking_enabled);
  }

  function cancelEdit() {
    setEditId(null);
    setEditName('');
    setEditSystem('');
    setEditChannel(null);
    setEditActive(true);
    setEditGmMember(null);
    setEditPlayerBankingEnabled(false);
  }

  const activeCampaigns = campaigns.filter((c) => !c.deleted_at);
  const deletedCampaigns = campaigns.filter((c) => !!c.deleted_at);

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
              getOptionLabel={(opt) => SYSTEM_LABELS[opt] ?? opt}
              renderInput={(params) => (
                <TextField {...params} label="Game System" placeholder="e.g. Pathfinder 2E" />
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
                  (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q),
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
                <TextField {...params} label="Channel" />
              )}
            />
            <Autocomplete
              size="small"
              fullWidth
              options={guildMembers}
              loading={membersLoading}
              value={newGmMember}
              onChange={(_, m) => setNewGmMember(m)}
              getOptionLabel={(m) => m.display_name}
              isOptionEqualToValue={(a, b) => a.discord_user_id === b.discord_user_id}
              filterOptions={(opts, { inputValue }) => {
                const q = inputValue.toLowerCase();
                return opts.filter(
                  (m) =>
                    m.display_name.toLowerCase().includes(q) ||
                    m.username.toLowerCase().includes(q),
                );
              }}
              renderInput={(params) => (
                <TextField {...params} label="Game Master (optional)" />
              )}
            />
            {/* Banking */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Banking
              </Typography>
              <Stack spacing={0.5} sx={{ pl: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={newPlayerBankingEnabled}
                      onChange={(e) => setNewPlayerBankingEnabled(e.target.checked)}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2">Allow player transactions</Typography>
                      <Typography variant="caption" color="text.secondary">Players can add/remove gold from their own wallet and deposit to or withdraw from the party pool</Typography>
                    </Box>
                  }
                />
              </Stack>
            </Box>
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

      {/* Campaign list */}
      {activeCampaigns.length === 0 && deletedCampaigns.length === 0 ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            py: 8,
            gap: 1.5,
            color: 'text.disabled',
          }}
        >
          <TableRestaurantIcon sx={{ fontSize: 48, opacity: 0.4 }} />
          <Typography variant="h6" color="text.disabled">
            No campaigns yet
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center">
            {isAdmin
              ? 'Create your first campaign with the "+ New Campaign" button above.'
              : 'No campaigns have been created for this server yet.'}
          </Typography>
        </Box>
      ) : (
        <Stack spacing={2}>
          {activeCampaigns.map((c) => (
            <CampaignCard
              key={c.id}
              campaign={c}
              channels={channels}
              isAdmin={isAdmin}
              currentUserId={currentUserId}
              allCampaigns={activeCampaigns}
              onEdit={startEdit}
              onDelete={(camp) => setDeleteId(camp.id)}
            />
          ))}
        </Stack>
      )}

      {/* Deleted campaigns section — admin only */}
      {isAdmin && deletedCampaigns.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Divider sx={{ mb: 1.5 }} />
          <Typography variant="caption" color="text.disabled" sx={{ mb: 1, display: 'block' }}>
            {deletedCampaigns.length} deleted{' '}
            {deletedCampaigns.length === 1 ? 'campaign' : 'campaigns'}
          </Typography>
          <Stack spacing={0.5}>
            {deletedCampaigns.map((c) => (
              <Box
                key={c.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  px: 2,
                  py: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  opacity: 0.55,
                }}
              >
                <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                  {c.name}
                </Typography>
                <Typography variant="caption" color="text.disabled" noWrap>
                  {c.deleted_at
                    ? `Deleted ${new Date(c.deleted_at).toLocaleDateString()}`
                    : ''}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={restoreMutation.isPending}
                  onClick={() => restoreMutation.mutate(c.id)}
                >
                  Restore
                </Button>
                <Button
                  size="small"
                  color="error"
                  onClick={() => setPermanentDeleteId(c.id)}
                >
                  Delete permanently
                </Button>
              </Box>
            ))}
          </Stack>
        </Box>
      )}

      {/* Edit campaign dialog */}
      <Dialog open={editId !== null} onClose={cancelEdit} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Campaign</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              size="small"
              required
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              fullWidth
            />
            <Autocomplete
              size="small"
              freeSolo
              options={SYSTEM_OPTIONS}
              value={editSystem}
              onInputChange={(_, v) => setEditSystem(v)}
              getOptionLabel={(opt) => SYSTEM_LABELS[opt] ?? opt}
              renderInput={(params) => (
                <TextField {...params} label="Game System" />
              )}
            />
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
                  (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q),
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
              renderInput={(params) => (
                <TextField {...params} label="Channel" />
              )}
            />
            <Box>
              <Chip
                label={editActive ? 'Active' : 'Inactive'}
                size="small"
                color={editActive ? 'success' : 'default'}
                onClick={() => setEditActive((v) => !v)}
                sx={{ cursor: 'pointer' }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                Click to toggle
              </Typography>
            </Box>
            <Autocomplete
              size="small"
              fullWidth
              options={guildMembers}
              loading={membersLoading}
              value={editGmMember}
              onChange={(_, m) => setEditGmMember(m)}
              getOptionLabel={(m) => m.display_name}
              isOptionEqualToValue={(a, b) => a.discord_user_id === b.discord_user_id}
              filterOptions={(opts, { inputValue }) => {
                const q = inputValue.toLowerCase();
                return opts.filter(
                  (m) =>
                    m.display_name.toLowerCase().includes(q) ||
                    m.username.toLowerCase().includes(q),
                );
              }}
              renderInput={(params) => (
                <TextField {...params} label="Game Master (optional)" />
              )}
            />
            {/* Banking */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Banking
              </Typography>
              <Stack spacing={0.5} sx={{ pl: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={editPlayerBankingEnabled}
                      onChange={(e) => setEditPlayerBankingEnabled(e.target.checked)}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2">Allow player transactions</Typography>
                      <Typography variant="caption" color="text.secondary">Players can add/remove gold from their own wallet and deposit to or withdraw from the party pool</Typography>
                    </Box>
                  }
                />
              </Stack>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={cancelEdit}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            disabled={updateMutation.isPending || !editName.trim()}
            onClick={() => updateMutation.mutate()}
          >
            {updateMutation.isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete campaign dialog */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Campaign</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Move{' '}
            <strong>{campaigns.find((c) => c.id === deleteId)?.name ?? 'this campaign'}</strong>{' '}
            to the deleted list? You can restore it afterwards, or permanently delete it later.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setDeleteId(null)}>
            Cancel
          </Button>
          <Button
            size="small"
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (deleteId !== null) deleteMutation.mutate(deleteId);
            }}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Permanent delete confirmation */}
      <Dialog
        open={permanentDeleteId !== null}
        onClose={() => setPermanentDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Permanently Delete Campaign</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Permanently delete{' '}
            <strong>
              {campaigns.find((c) => c.id === permanentDeleteId)?.name ?? 'this campaign'}
            </strong>
            ? This will also remove all associated characters and{' '}
            <strong>cannot be undone</strong>.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setPermanentDeleteId(null)}>
            Cancel
          </Button>
          <Button
            size="small"
            color="error"
            variant="contained"
            disabled={permanentDeleteMutation.isPending}
            onClick={() => {
              if (permanentDeleteId !== null) permanentDeleteMutation.mutate(permanentDeleteId);
            }}
          >
            {permanentDeleteMutation.isPending ? 'Deleting…' : 'Delete permanently'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Undo snackbar — shown after soft-delete */}
      <Snackbar
        open={undoSnackbar !== null}
        autoHideDuration={8000}
        onClose={() => setUndoSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity="info"
          action={
            <Button
              size="small"
              color="inherit"
              onClick={() => {
                if (undoSnackbar) restoreMutation.mutate(undoSnackbar.id);
              }}
            >
              Undo
            </Button>
          }
          sx={{ width: '100%' }}
        >
          Campaign &ldquo;{undoSnackbar?.name}&rdquo; deleted.
        </Alert>
      </Snackbar>
    </Stack>
  );
}
