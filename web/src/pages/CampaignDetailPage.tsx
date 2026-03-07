import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MenuItem from '@mui/material/MenuItem';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuilds } from '../hooks/useGuilds';
import { SYSTEM_OPTIONS, SYSTEM_LABELS } from '../constants/character';
import CampaignCard from '../components/campaigns/CampaignCard';
import type { Campaign, CombatTrackerDepth, DiscordChannel, GuildConfig, GuildMember } from '../types';

const DEPTH_OPTIONS: { value: CombatTrackerDepth; label: string; description: string }[] = [
  { value: 'basic', label: 'Basic', description: 'Initiative & turns only' },
  { value: 'standard', label: 'Standard', description: '+ HP, AC, conditions' },
  { value: 'full', label: 'Full', description: '+ damage log, death saves, concentration' },
];

export default function CampaignDetailPage() {
  const { data: me } = useAuth();
  const { guildId, campaignId } = useParams<{ guildId: string; campaignId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const currentUserId = me?.id ?? '';

  // Derive admin status and timezone directly (no GuildLayout outlet context needed)
  const { data: guilds } = useGuilds();
  const guild = guilds?.find((g) => g.id === guildId);
  const isAdmin = guild?.is_admin ?? false;

  const { data: guildConfig } = useQuery<GuildConfig>({
    queryKey: ['guild-config', guildId],
    queryFn: async () => {
      const res = await client.get<GuildConfig>(`/api/guilds/${guildId}/config`);
      return res.data;
    },
    enabled: !!guildId,
  });
  const timezone = guildConfig?.timezone ?? 'UTC';

  // Edit state
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editSystem, setEditSystem] = useState('');
  const [editChannel, setEditChannel] = useState<DiscordChannel | null>(null);
  const [editActive, setEditActive] = useState(true);
  const [editGmMember, setEditGmMember] = useState<GuildMember | null>(null);
  const [editPlayerBankingEnabled, setEditPlayerBankingEnabled] = useState(false);
  const [editCombatDepth, setEditCombatDepth] = useState<CombatTrackerDepth>('standard');
  const [editAllowManualDice, setEditAllowManualDice] = useState(false);

  // Delete state
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [undoSnackbar, setUndoSnackbar] = useState<{ id: number; name: string } | null>(null);

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

  const campaign = campaigns.find((c) => c.id === Number(campaignId));
  const activeCampaigns = campaigns.filter((c) => !c.deleted_at);

  // ── Mutations ─────────────────────────────────────────────────────────────

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
        combat_tracker_depth: editCombatDepth,
        allow_manual_dice_recording: editAllowManualDice,
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

  // ── Helpers ───────────────────────────────────────────────────────────────

  function startEdit(c: Campaign) {
    setEditId(c.id);
    setEditName(c.name);
    setEditSystem(c.system);
    setEditChannel(channels.find((ch) => ch.id === c.channel_id) ?? null);
    setEditActive(c.is_active);
    setEditGmMember(guildMembers.find((m) => m.discord_user_id === c.gm_discord_user_id) ?? null);
    setEditPlayerBankingEnabled(c.player_banking_enabled);
    setEditCombatDepth(c.combat_tracker_depth ?? 'standard');
    setEditAllowManualDice(c.allow_manual_dice_recording ?? false);
  }

  function cancelEdit() {
    setEditId(null);
    setEditName('');
    setEditSystem('');
    setEditChannel(null);
    setEditActive(true);
    setEditGmMember(null);
    setEditPlayerBankingEnabled(false);
    setEditCombatDepth('standard');
    setEditAllowManualDice(false);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!campaign) {
    return (
      <Box sx={{ py: 4 }}>
        <Typography variant="body1" color="text.secondary">
          Campaign not found.
        </Typography>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(`/guilds/${guildId}/campaigns`)}
          sx={{ mt: 2 }}
        >
          Back to campaigns
        </Button>
      </Box>
    );
  }

  return (
    <Stack spacing={2} sx={{ p: { xs: 2, sm: 4 } }}>
      {/* Back navigation */}
      <Box>
        <Tooltip title="Back to all campaigns">
          <IconButton
            size="small"
            onClick={() => navigate(`/guilds/${guildId}/campaigns`)}
            sx={{ mr: 1 }}
          >
            <ArrowBackIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Typography variant="caption" color="text.secondary">
          All campaigns
        </Typography>
      </Box>

      {/* Campaign card */}
      <CampaignCard
        campaign={campaign}
        channels={channels}
        isAdmin={isAdmin}
        currentUserId={currentUserId}
        allCampaigns={activeCampaigns}
        timezone={timezone}
        onEdit={startEdit}
        onDelete={(c) => setDeleteId(c.id)}
        hideOpenInPage
      />

      {/* Edit campaign dialog */}
      <Dialog open={editId !== null} onClose={cancelEdit} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Campaign</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label="Name"
                size="small"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                sx={{ flex: 1 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={editActive}
                    onChange={(e) => setEditActive(e.target.checked)}
                  />
                }
                label={editActive ? 'Active' : 'Inactive'}
                slotProps={{ typography: { variant: 'body2', fontWeight: 500 } }}
                sx={{ flexShrink: 0 }}
              />
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
              Inactive campaigns are hidden from players and Grug won&apos;t track context in their channel.
            </Typography>
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
                  <Typography component="span" variant="caption" color="text.disabled" sx={{ ml: 1 }}>
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
                      <Typography variant="caption" color="text.secondary">
                        Players can add/remove gold from their own wallet and deposit to or withdraw from the party pool
                      </Typography>
                    </Box>
                  }
                />
              </Stack>
            </Box>
            <TextField
              select
              size="small"
              label="Combat Tracker Depth"
              value={editCombatDepth}
              onChange={(e) => setEditCombatDepth(e.target.value as CombatTrackerDepth)}
              helperText={DEPTH_OPTIONS.find((d) => d.value === editCombatDepth)?.description}
            >
              {DEPTH_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={editAllowManualDice}
                  onChange={(e) => setEditAllowManualDice(e.target.checked)}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Allow manual dice recording</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Players can log physical dice rolls to the campaign roll history
                  </Typography>
                </Box>
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={cancelEdit}>Cancel</Button>
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
          <Button size="small" onClick={() => setDeleteId(null)}>Cancel</Button>
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

      {/* Undo snackbar — shown after soft-delete */}
      <Snackbar
        open={undoSnackbar !== null}
        autoHideDuration={8000}
        onClose={() => {
          setUndoSnackbar(null);
          navigate(`/guilds/${guildId}/campaigns`);
        }}
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
