import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Avatar,
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
  FormLabel,
  IconButton,
  Menu,
  MenuItem,
  Paper,
  Skeleton,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PersonIcon from '@mui/icons-material/Person';
import TableRestaurantIcon from '@mui/icons-material/TableRestaurant';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SyncIcon from '@mui/icons-material/Sync';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import type { Campaign, Character, CharacterSheet, DiscordChannel, GuildMember } from '../types';

// Suggested systems shown in the autocomplete dropdown — users may still type
// any free-form value for unsupported systems.
const SYSTEM_OPTIONS = ['pf2e', 'dnd5e'];
const SYSTEM_LABELS: Record<string, string> = {
  pf2e: 'Pathfinder 2E',
  dnd5e: 'D&D 5e',
};

const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

const SHEET_ACCEPTED = '.txt,.md,.rst,.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp';
const MAX_SHEET_MB = 20;

// ── Guild member cell ─────────────────────────────────────────────────────

function GuildMemberCell({ guildId, userId, displayName }: { guildId: string; userId: string | null; displayName?: string | null }) {
  const { data, isLoading, isError } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => {
      const res = await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
    enabled: !!userId,
  });

  // No Discord owner — show display name or "Unassigned"
  if (!userId) {
    if (displayName) {
      return (
        <Chip label={displayName} size="small" variant="outlined" />
      );
    }
    return (
      <Typography variant="caption" color="text.disabled" sx={{ fontStyle: 'italic' }}>
        Unassigned
      </Typography>
    );
  }

  if (isLoading) {
    return (
      <Stack direction="row" alignItems="center" spacing={0.75}>
        <Skeleton variant="circular" width={22} height={22} />
        <Skeleton width={65} height={13} />
      </Stack>
    );
  }

  if (isError || !data) {
    return (
      <Typography variant="caption" sx={{ fontFamily: 'monospace' }} color="text.disabled">
        {userId}
      </Typography>
    );
  }

  return (
    <Tooltip title={`@${data.username} · ${userId}`} placement="top">
      <Stack direction="row" alignItems="center" spacing={0.75} sx={{ cursor: 'default' }}>
        <Avatar
          src={data.avatar_url ?? undefined}
          alt={data.display_name}
          sx={{ width: 22, height: 22, fontSize: '0.65rem' }}
        >
          {data.display_name[0].toUpperCase()}
        </Avatar>
        <Typography variant="caption" fontWeight={500} noWrap>
          {data.display_name}
        </Typography>
      </Stack>
    </Tooltip>
  );
}

// ── Character stat card ───────────────────────────────────────────────────

function CharacterStatCard({ sheet }: { sheet: CharacterSheet }) {
  const headline = [
    sheet.level != null && `Level ${sheet.level}`,
    sheet.class_and_subclass,
    sheet.race_or_ancestry,
  ]
    .filter(Boolean)
    .join(' · ');

  const hasAbilities =
    sheet.ability_scores != null &&
    ABILITY_KEYS.some((k) => sheet.ability_scores![k] != null);

  const hasStats =
    sheet.armor_class != null || sheet.hp?.max != null || sheet.speed != null;

  return (
    <Box
      sx={{
        mt: 0.75,
        p: 1.5,
        bgcolor: 'background.default',
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {headline && (
        <Typography variant="caption" color="text.secondary" display="block" mb={0.75}>
          {headline}
        </Typography>
      )}
      {hasStats && (
        <Stack direction="row" spacing={2} mb={hasAbilities ? 1 : 0} flexWrap="wrap">
          {sheet.armor_class != null && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>AC</Typography>
              <Typography variant="body2" fontWeight={700}>{sheet.armor_class}</Typography>
            </Box>
          )}
          {sheet.hp?.max != null && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>HP</Typography>
              <Typography variant="body2" fontWeight={700}>{sheet.hp.max}</Typography>
            </Box>
          )}
          {sheet.speed && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>Speed</Typography>
              <Typography variant="body2" fontWeight={700}>{sheet.speed}</Typography>
            </Box>
          )}
          {sheet.proficiency_bonus != null && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>Prof</Typography>
              <Typography variant="body2" fontWeight={700}>+{sheet.proficiency_bonus}</Typography>
            </Box>
          )}
        </Stack>
      )}
      {hasAbilities && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap">
          {ABILITY_KEYS.map((k) => {
            const val = sheet.ability_scores![k];
            if (val == null) return null;
            const mod = Math.floor((val - 10) / 2);
            return (
              <Box
                key={k}
                sx={{
                  textAlign: 'center',
                  minWidth: 38,
                  py: 0.5,
                  px: 0.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                }}
              >
                <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.2}>
                  {k}
                </Typography>
                <Typography variant="body2" fontWeight={700} lineHeight={1.3}>{val}</Typography>
                <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
                  {mod >= 0 ? `+${mod}` : mod}
                </Typography>
              </Box>
            );
          })}
        </Stack>
      )}
    </Box>
  );
}

// ── Owner autocomplete ───────────────────────────────────────────────────

interface OwnerAutocompleteProps {
  guildMembers: GuildMember[];
  loading: boolean;
  value: GuildMember | string;
  onChange: (v: GuildMember | string) => void;
}

function OwnerAutocomplete({ guildMembers, loading, value, onChange }: OwnerAutocompleteProps) {
  return (
    <Autocomplete
      freeSolo
      size="small"
      fullWidth
      loading={loading}
      options={[UNASSIGNED_MEMBER, ...guildMembers]}
      value={value}
      onChange={(_, val) => onChange((val ?? UNASSIGNED_MEMBER) as GuildMember | string)}
      getOptionLabel={(opt) => (typeof opt === 'string' ? opt : opt.display_name)}
      isOptionEqualToValue={(opt, val) =>
        typeof val === 'string'
          ? opt.display_name === val
          : opt.discord_user_id === (val as GuildMember).discord_user_id
      }
      filterOptions={(opts, { inputValue }) => {
        if (!inputValue) return opts;
        const q = inputValue.toLowerCase();
        return opts.filter(
          (o) =>
            o.display_name.toLowerCase().includes(q) ||
            o.username.toLowerCase().includes(q)
        );
      }}
      renderOption={(props, opt) => (
        <Box component="li" {...props} key={opt.discord_user_id || '__unassigned__'}>
          {opt.discord_user_id ? (
            <Stack direction="row" alignItems="center" spacing={1}>
              <Avatar
                src={opt.avatar_url ?? undefined}
                sx={{ width: 24, height: 24, fontSize: '0.7rem' }}
              >
                {opt.display_name[0]?.toUpperCase()}
              </Avatar>
              <Box>
                <Typography variant="body2" lineHeight={1.3}>{opt.display_name}</Typography>
                <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
                  @{opt.username}
                </Typography>
              </Box>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
              Unassigned
            </Typography>
          )}
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Owner"
          placeholder="Search members or type a name…"
          helperText="Pick a server member, type a custom name, or choose Unassigned"
        />
      )}
    />
  );
}

// ── Characters panel ──────────────────────────────────────────────────────

interface CharactersPanelProps {
  guildId: string;
  campaignId: number;
  campaignSystem: string;
  isAdmin: boolean;
  currentUserId: string;
  /** All active campaigns in the guild — used to populate the transfer/copy dialog. */
  allCampaigns: Campaign[];
}

// Sentinel GuildMember used to represent the "Unassigned" option in the owner picker.
const UNASSIGNED_MEMBER: GuildMember = {
  discord_user_id: '',
  display_name: 'Unassigned',
  username: '',
  avatar_url: null,
};

/** Derive the owner API payload fields from the Autocomplete selection. */
function resolveOwnerPayload(owner: GuildMember | string) {
  if (typeof owner === 'object') {
    if (!owner.discord_user_id) return { owner_discord_user_id: null, owner_display_name: null };
    return { owner_discord_user_id: owner.discord_user_id, owner_display_name: null };
  }
  const trimmed = owner.trim();
  return { owner_discord_user_id: null, owner_display_name: trimmed || null };
}

function CharactersPanel({ guildId, campaignId, campaignSystem, isAdmin, currentUserId, allCampaigns }: CharactersPanelProps) {
  const qc = useQueryClient();

  // ── Create dialog state ─────────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createOwner, setCreateOwner] = useState<GuildMember | string>(UNASSIGNED_MEMBER);
  const [createFile, setCreateFile] = useState<File | null>(null);
  const [createPathbuilderId, setCreatePathbuilderId] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const createFileRef = useRef<HTMLInputElement>(null);

  // ── Edit dialog state ───────────────────────────────────────────────────
  const [editChar, setEditChar] = useState<Character | null>(null);
  const [editName, setEditName] = useState('');
  const [editOwner, setEditOwner] = useState<GuildMember | string>(UNASSIGNED_MEMBER);
  const [editNotes, setEditNotes] = useState('');
  const [editNotesRevealed, setEditNotesRevealed] = useState(false);
  const [editFile, setEditFile] = useState<File | null>(null);
  const [editPathbuilderId, setEditPathbuilderId] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const editFileRef = useRef<HTMLInputElement>(null);

  // ── Delete confirm ──────────────────────────────────────────────────────
  const [deleteCharId, setDeleteCharId] = useState<number | null>(null);

  // ── Sheet detail modal ──────────────────────────────────────────────────
  const [sheetDetailChar, setSheetDetailChar] = useState<Character | null>(null);

  // ── Transfer / copy dialog ──────────────────────────────────────────────
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferOp, setTransferOp] = useState<'move' | 'copy'>('move');
  const [transferCharId, setTransferCharId] = useState<number | null>(null);
  const [transferTarget, setTransferTarget] = useState<Campaign | null>(null);
  const [transferMenuAnchor, setTransferMenuAnchor] = useState<null | HTMLElement>(null);
  const [transferMenuCharId, setTransferMenuCharId] = useState<number | null>(null);

  const otherCampaigns = allCampaigns.filter((c) => c.id !== campaignId);

  // Guild members list — for the owner assignment autocomplete (admin only).
  const { data: guildMembers = [], isLoading: guildMembersLoading } = useQuery<GuildMember[]>({
    queryKey: ['guild-members', guildId],
    queryFn: async () => {
      const res = await client.get<GuildMember[]>(`/api/guilds/${guildId}/members`);
      return res.data;
    },
    enabled: isAdmin && !!guildId,
    staleTime: 60_000,
  });

  const { data: characters = [], isLoading } = useQuery<Character[]>({
    queryKey: ['campaign-characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`
      );
      return res.data;
    },
    enabled: !!guildId,
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });

  // Auto-sync all Pathbuilder-linked characters when the panel first reveals them.
  const syncCampaignMutation = useMutation({
    mutationFn: () =>
      client.post(`/api/guilds/${guildId}/campaigns/${campaignId}/sync-pathbuilder`),
    onSuccess: () => { invalidate(); },
  });

  useEffect(() => {
    if (characters.length > 0 && characters.some((c) => c.pathbuilder_id != null)) {
      syncCampaignMutation.mutate();
    }
    // Only run when characters first load (not on every mutation-triggered refetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characters.length > 0]);

  // ── Create character mutation ───────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = { name: createName, system: campaignSystem };
      if (isAdmin) {
        Object.assign(payload, resolveOwnerPayload(createOwner));
      }
      const res = await client.post<Character>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
        payload
      );
      const charId = res.data.id;

      // Optional sheet attachment — file takes precedence if somehow both are set
      if (createFile) {
        const form = new FormData();
        form.append('file', createFile);
        await client.post(
          `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}/upload`,
          form,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
      } else if (createPathbuilderId.trim()) {
        const pbId = parseInt(createPathbuilderId, 10);
        if (!isNaN(pbId)) {
          await client.post(
            `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}/link-pathbuilder`,
            { pathbuilder_id: pbId }
          );
        }
      }
    },
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      closeCreateDialog();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to create character.';
      setCreateError(msg);
    },
  });

  // ── Update character mutation ───────────────────────────────────────────
  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!editChar) return;
      const payload: Record<string, unknown> = { name: editName };
      if (isAdmin) {
        Object.assign(payload, resolveOwnerPayload(editOwner));
      }
      // Notes
      payload.notes = editNotes || null;

      await client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${editChar.id}`,
        payload
      );

      // Handle sheet changes — file takes precedence; only re-link PB if the ID changed
      if (editFile) {
        const form = new FormData();
        form.append('file', editFile);
        await client.post(
          `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${editChar.id}/upload`,
          form,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
      } else if (
        editPathbuilderId.trim() &&
        editPathbuilderId !== editChar.pathbuilder_id?.toString()
      ) {
        const pbId = parseInt(editPathbuilderId, 10);
        if (!isNaN(pbId)) {
          await client.post(
            `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${editChar.id}/link-pathbuilder`,
            { pathbuilder_id: pbId }
          );
        }
      }
    },
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      closeEditDialog();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to save changes.';
      setEditError(msg);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      client.delete(`/api/guilds/${guildId}/campaigns/${campaignId}/characters/${id}`),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setDeleteCharId(null);
    },
  });

  const syncPathbuilderMutation = useMutation({
    mutationFn: (charId: number) =>
      client.post(`/api/guilds/${guildId}/characters/${charId}/sync-pathbuilder`),
    onSuccess: () => {
      invalidate();
    },
  });

  const moveMutation = useMutation({
    mutationFn: (targetId: number) =>
      client.patch(`/api/guilds/${guildId}/characters/${transferCharId}`, {
        campaign_id: targetId,
      }),
    onSuccess: (_, targetId) => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, targetId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      closeTransferDialog();
    },
  });

  const copyMutation = useMutation({
    mutationFn: (targetId: number) =>
      client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${transferCharId}/copy`,
        { target_campaign_id: targetId }
      ),
    onSuccess: (_, targetId) => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, targetId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      closeTransferDialog();
    },
  });

  // ── Helpers ─────────────────────────────────────────────────────────────

  function openCreateDialog() {
    setCreateOpen(true);
    setCreateName('');
    // Default owner to the current user if found in the loaded member list.
    const me = guildMembers.find((m) => m.discord_user_id === currentUserId)
      ?? { discord_user_id: currentUserId, display_name: 'Me', username: '', avatar_url: null };
    setCreateOwner(me);
    setCreateFile(null);
    setCreatePathbuilderId('');
    setCreateError(null);
    if (createFileRef.current) createFileRef.current.value = '';
  }

  function closeCreateDialog() {
    setCreateOpen(false);
    setCreateName('');
    setCreateFile(null);
    setCreateError(null);
    if (createFileRef.current) createFileRef.current.value = '';
  }

  function openEditDialog(ch: Character) {
    setEditChar(ch);
    setEditName(ch.name);
    setEditNotes(ch.notes ?? '');
    setEditFile(null);
    setEditPathbuilderId(ch.pathbuilder_id?.toString() ?? '');
    setEditError(null);
    if (editFileRef.current) editFileRef.current.value = '';

    const isOwner = ch.owner_discord_user_id === currentUserId;
    setEditNotesRevealed(isOwner || !ch.notes);
    if (ch.owner_discord_user_id) {
      const member = guildMembers.find((m) => m.discord_user_id === ch.owner_discord_user_id)
        ?? { discord_user_id: ch.owner_discord_user_id, display_name: ch.owner_discord_user_id, username: '', avatar_url: null };
      setEditOwner(member);
    } else if (ch.owner_display_name) {
      setEditOwner(ch.owner_display_name);
    } else {
      setEditOwner(UNASSIGNED_MEMBER);
    }
  }

  function closeEditDialog() {
    setEditChar(null);
    setEditError(null);
    if (editFileRef.current) editFileRef.current.value = '';
  }

  function openTransferMenu(e: React.MouseEvent<HTMLElement>, charId: number) {
    e.stopPropagation();
    setTransferMenuAnchor(e.currentTarget);
    setTransferMenuCharId(charId);
  }

  function closeTransferMenu() {
    setTransferMenuAnchor(null);
    setTransferMenuCharId(null);
  }

  function openTransferDialog(op: 'move' | 'copy', charId: number) {
    setTransferOp(op);
    setTransferCharId(charId);
    setTransferTarget(null);
    setTransferOpen(true);
  }

  function closeTransferDialog() {
    setTransferOpen(false);
    setTransferCharId(null);
    setTransferTarget(null);
  }

  /** Whether the current user can edit/delete a given character. */
  function canEditChar(ch: Character) {
    return isAdmin || ch.owner_discord_user_id === currentUserId;
  }

  return (
    <>
      <Box>
            {/* Header row */}
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.5}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <PersonIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Characters
                </Typography>
              </Stack>
              <Button size="small" variant="outlined" onClick={openCreateDialog}>
                + Add Character
              </Button>
            </Stack>

            <Divider sx={{ mb: 1.5 }} />

            {/* Character list */}
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            ) : characters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No characters linked to this campaign yet. Use &ldquo;+ Add Character&rdquo; to create one.
              </Typography>
            ) : (
              <Stack divider={<Divider />} spacing={0}>
                {characters.map((ch) => {
                  const editable = canEditChar(ch);
                  return (
                    <Box key={ch.id} sx={{ py: 1 }}>
                      <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                        <Typography variant="body2" fontWeight={500} sx={{ flex: 1 }}>
                          {ch.name}
                        </Typography>
                        {ch.pathbuilder_id != null && (
                          <Tooltip title={`Pathbuilder ID: ${ch.pathbuilder_id}${ch.structured_data ? ' — click to view' : ''}`}>
                            <Chip
                              label="Pathbuilder"
                              size="small"
                              color="secondary"
                              variant="outlined"
                              onClick={ch.structured_data ? () => setSheetDetailChar(ch) : undefined}
                              sx={ch.structured_data ? { cursor: 'pointer' } : undefined}
                            />
                          </Tooltip>
                        )}
                        {ch.file_path && !ch.pathbuilder_id && (
                          <Tooltip title={ch.structured_data ? 'Character sheet on file — click to view' : 'Character sheet on file'}>
                            <Chip
                              label="Sheet"
                              size="small"
                              color="info"
                              variant="outlined"
                              onClick={ch.structured_data ? () => setSheetDetailChar(ch) : undefined}
                              sx={ch.structured_data ? { cursor: 'pointer' } : undefined}
                            />
                          </Tooltip>
                        )}
                        <GuildMemberCell guildId={guildId} userId={ch.owner_discord_user_id} displayName={ch.owner_display_name} />
                        <Stack direction="row" spacing={0.25}>
                          {/* Sync — visible to owners + admins on Pathbuilder chars */}
                          {ch.pathbuilder_id != null && editable && (
                            <Tooltip title="Sync Pathbuilder">
                              <IconButton
                                size="small"
                                onClick={() => syncPathbuilderMutation.mutate(ch.id)}
                                disabled={syncPathbuilderMutation.isPending}
                              >
                                <SyncIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                          {/* Move / Copy — admin only */}
                          {isAdmin && otherCampaigns.length > 0 && (
                            <Tooltip title="Move / Copy">
                              <IconButton size="small" onClick={(e) => openTransferMenu(e, ch.id)}>
                                <CallSplitIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                          {/* Edit — owner or admin */}
                          {editable && (
                            <Tooltip title="Edit">
                              <IconButton size="small" onClick={() => openEditDialog(ch)}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                          {/* Delete — owner or admin */}
                          {editable && (
                            <Tooltip title="Delete">
                              <IconButton size="small" color="error" onClick={() => setDeleteCharId(ch.id)}>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Stack>
                      </Stack>
                    </Box>
                  );
                })}
              </Stack>
            )}
      </Box>

      {/* Transfer submenu (move / copy to another campaign) */}
      <Menu
        anchorEl={transferMenuAnchor}
        open={transferMenuAnchor !== null}
        onClose={closeTransferMenu}
        slotProps={{ paper: { elevation: 2 } }}
      >
        <MenuItem
          dense
          onClick={() => {
            if (transferMenuCharId !== null) openTransferDialog('move', transferMenuCharId);
            closeTransferMenu();
          }}
        >
          Move to campaign…
        </MenuItem>
        <MenuItem
          dense
          onClick={() => {
            if (transferMenuCharId !== null) openTransferDialog('copy', transferMenuCharId);
            closeTransferMenu();
          }}
        >
          Copy to campaign…
        </MenuItem>
      </Menu>

      {/* ── Create character dialog ──────────────────────────────────────── */}
      <Dialog open={createOpen} onClose={closeCreateDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Add Character</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="Name"
              size="small"
              fullWidth
              required
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
            />

            {/* Owner selection — admin only */}
            {isAdmin && (
              <OwnerAutocomplete
                guildMembers={guildMembers}
                loading={guildMembersLoading}
                value={createOwner}
                onChange={setCreateOwner}
              />
            )}

            {/* Sheet attachment — upload file OR link Pathbuilder; filling one clears the other */}
            <Box>
              <FormLabel component="legend" sx={{ display: 'block', mb: 1 }}>Character Sheet</FormLabel>
              <Stack spacing={1.5}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Button
                    variant="outlined"
                    component="label"
                    size="small"
                    startIcon={<CloudUploadIcon />}
                    color={createFile ? 'primary' : 'inherit'}
                  >
                    {createFile ? createFile.name : 'Upload file…'}
                    <input
                      ref={createFileRef}
                      type="file"
                      accept={SHEET_ACCEPTED}
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0] ?? null;
                        if (f && f.size / (1024 * 1024) > MAX_SHEET_MB) {
                          setCreateError(`File exceeds ${MAX_SHEET_MB} MB limit.`);
                          return;
                        }
                        setCreateFile(f);
                        setCreatePathbuilderId('');  // clear PB field
                        setCreateError(null);
                      }}
                    />
                  </Button>
                  {createFile && (
                    <Button size="small" onClick={() => {
                      setCreateFile(null);
                      if (createFileRef.current) createFileRef.current.value = '';
                    }}>Clear</Button>
                  )}
                </Stack>
                <TextField
                  label="Pathbuilder ID"
                  size="small"
                  type="number"
                  value={createPathbuilderId}
                  onChange={(e) => {
                    setCreatePathbuilderId(e.target.value);
                    if (e.target.value.trim()) {
                      setCreateFile(null);  // clear file selection
                      if (createFileRef.current) createFileRef.current.value = '';
                    }
                  }}
                  placeholder="Pathbuilder export URL number"
                  helperText="Filling one clears the other"
                  slotProps={{ htmlInput: { min: 1 } }}
                />
              </Stack>
            </Box>

            {createError && (
              <Typography variant="caption" color="error">{createError}</Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={closeCreateDialog}>Cancel</Button>
          <Button
            size="small"
            variant="contained"
            disabled={createMutation.isPending || !createName.trim()}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Edit character dialog ────────────────────────────────────────── */}
      <Dialog open={editChar !== null} onClose={closeEditDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Character</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="Name"
              size="small"
              fullWidth
              required
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />

            {/* Owner section — admin only */}
            {isAdmin && (
              <OwnerAutocomplete
                guildMembers={guildMembers}
                loading={guildMembersLoading}
                value={editOwner}
                onChange={setEditOwner}
              />
            )}

            {/* Sheet management — upload a new file OR change the Pathbuilder ID; filling one clears the other */}
            {editChar && (
              <Box>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                  <FormLabel component="legend">Character Sheet</FormLabel>
                  {!editFile && !editPathbuilderId && editChar.pathbuilder_id != null && (
                    <Chip label={`Pathbuilder #${editChar.pathbuilder_id}`} size="small" color="secondary" variant="outlined" />
                  )}
                  {!editFile && !editPathbuilderId && editChar.file_path && editChar.pathbuilder_id == null && (
                    <Chip label="Sheet on file" size="small" color="info" variant="outlined" />
                  )}
                </Stack>
                <Stack spacing={1.5}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Button
                      variant="outlined"
                      component="label"
                      size="small"
                      startIcon={<CloudUploadIcon />}
                      color={editFile ? 'primary' : 'inherit'}
                    >
                      {editFile ? editFile.name : 'Upload new file…'}
                      <input
                        ref={editFileRef}
                        type="file"
                        accept={SHEET_ACCEPTED}
                        hidden
                        onChange={(e) => {
                          const f = e.target.files?.[0] ?? null;
                          if (f && f.size / (1024 * 1024) > MAX_SHEET_MB) {
                            setEditError(`File exceeds ${MAX_SHEET_MB} MB limit.`);
                            return;
                          }
                          setEditFile(f);
                          setEditPathbuilderId('');  // clear PB field
                          setEditError(null);
                        }}
                      />
                    </Button>
                    {editFile && (
                      <Button size="small" onClick={() => {
                        setEditFile(null);
                        if (editFileRef.current) editFileRef.current.value = '';
                      }}>Clear</Button>
                    )}
                  </Stack>
                  <TextField
                    label="Pathbuilder ID"
                    size="small"
                    type="number"
                    value={editPathbuilderId}
                    onChange={(e) => {
                      setEditPathbuilderId(e.target.value);
                      if (e.target.value.trim()) {
                        setEditFile(null);  // clear file selection
                        if (editFileRef.current) editFileRef.current.value = '';
                      }
                    }}
                    placeholder="Pathbuilder export URL number"
                    helperText={editPathbuilderId && editPathbuilderId !== editChar.pathbuilder_id?.toString() ? 'Will re-link on save' : 'Filling one clears the other'}
                    slotProps={{ htmlInput: { min: 1 } }}
                  />
                </Stack>
              </Box>
            )}

            {/* Private notes section */}
            {editChar && (() => {
              const isOwner = editChar.owner_discord_user_id === currentUserId;
              const hasHiddenNotes = !isOwner && isAdmin && !!editChar.notes;
              return (
                <Box>
                  <FormLabel component="legend" sx={{ mb: 0.5 }}>
                    Private Notes
                    {hasHiddenNotes && !editNotesRevealed && (
                      <Tooltip title="This character has private notes. Click to reveal.">
                        <IconButton size="small" sx={{ ml: 0.5 }} onClick={() => setEditNotesRevealed(true)}>
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                    {hasHiddenNotes && editNotesRevealed && (
                      <Tooltip title="Hide notes">
                        <IconButton size="small" sx={{ ml: 0.5 }} onClick={() => setEditNotesRevealed(false)}>
                          <VisibilityOffIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </FormLabel>
                  {(isOwner || !hasHiddenNotes || editNotesRevealed) ? (
                    <TextField
                      multiline
                      minRows={2}
                      maxRows={6}
                      size="small"
                      fullWidth
                      placeholder="Only visible to the character owner (and admins who choose to look)."
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                    />
                  ) : (
                    <Typography variant="caption" color="text.disabled" sx={{ fontStyle: 'italic' }}>
                      Notes hidden — click the eye icon to reveal.
                    </Typography>
                  )}
                </Box>
              );
            })()}

            {editError && (
              <Typography variant="caption" color="error">{editError}</Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={closeEditDialog}>Cancel</Button>
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

      {/* ── Delete character dialog ──────────────────────────────────────── */}
      <Dialog open={deleteCharId !== null} onClose={() => setDeleteCharId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Character</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Delete{' '}
            <strong>{characters.find((c) => c.id === deleteCharId)?.name ?? 'this character'}</strong>
            ? This cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setDeleteCharId(null)}>Cancel</Button>
          <Button
            size="small"
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => { if (deleteCharId !== null) deleteMutation.mutate(deleteCharId); }}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Sheet detail modal (read-only stat card) ─────────────────────── */}
      <Dialog
        open={sheetDetailChar !== null}
        onClose={() => setSheetDetailChar(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          {sheetDetailChar?.name ?? 'Character Sheet'}
        </DialogTitle>
        <DialogContent>
          {sheetDetailChar?.structured_data ? (
            <CharacterStatCard sheet={sheetDetailChar.structured_data} />
          ) : (
            <Typography variant="body2" color="text.secondary">
              No parsed sheet data available.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setSheetDetailChar(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Move / Copy character to another campaign */}
      <Dialog open={transferOpen} onClose={closeTransferDialog} maxWidth="xs" fullWidth>
        <DialogTitle>
          {transferOp === 'move' ? 'Move Character' : 'Copy Character'} to Another Campaign
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {transferOp === 'move'
                ? 'The character will be unlinked from this campaign and linked to the selected one.'
                : 'A full copy of this character (including sheet data) will be added to the selected campaign.'}
            </Typography>
            <Autocomplete
              size="small"
              options={otherCampaigns}
              value={transferTarget}
              onChange={(_, c) => setTransferTarget(c)}
              getOptionLabel={(c) => c.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              renderInput={(params) => (
                <TextField {...params} label="Target Campaign" required />
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={closeTransferDialog}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            disabled={
              !transferTarget ||
              moveMutation.isPending ||
              copyMutation.isPending
            }
            onClick={() => {
              if (!transferTarget) return;
              if (transferOp === 'move') moveMutation.mutate(transferTarget.id);
              else copyMutation.mutate(transferTarget.id);
            }}
          >
            {moveMutation.isPending || copyMutation.isPending
              ? transferOp === 'move'
                ? 'Moving…'
                : 'Copying…'
              : transferOp === 'move'
              ? 'Move'
              : 'Copy'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

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

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ['campaigns', guildId],
    queryFn: async () => {
      const res = await client.get<Campaign[]>(
        `/api/guilds/${guildId}/campaigns?include_deleted=true`
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
  }

  function cancelEdit() {
    setEditId(null);
    setEditName('');
    setEditSystem('');
    setEditChannel(null);
    setEditActive(true);
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
              ? 'Create your first campaign with the “+ New Campaign” button above.'
              : 'No campaigns have been created for this server yet.'}
          </Typography>
        </Box>
      ) : (
        <Stack spacing={0.5}>
          {activeCampaigns.map((c) => (
            <Accordion
              key={c.id}
              expanded={expandedId === c.id}
              onChange={() => setExpandedId((v) => (v === c.id ? null : c.id))}
              variant="outlined"
              disableGutters
              sx={{
                '&:before': { display: 'none' },
                opacity: c.is_active ? 1 : 0.55,
                transition: 'opacity 0.15s',
              }}
            >
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                sx={{ minHeight: 48, '& .MuiAccordionSummary-content': { my: 0.75, alignItems: 'center' } }}
              >
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1.5}
                  sx={{ flex: 1, pr: 1, minWidth: 0 }}
                >
                  <Typography variant="body2" fontWeight={600} noWrap sx={{ flex: '0 1 auto' }}>
                    {c.name}
                  </Typography>
                  {c.character_count > 0 && (
                    <Chip
                      label={`${c.character_count} ${c.character_count === 1 ? 'character' : 'characters'}`}
                      size="small"
                      variant="outlined"
                      sx={{ height: 18, fontSize: '0.65rem', pointerEvents: 'none', flexShrink: 0 }}
                    />
                  )}
                  <Box sx={{ flex: 1 }} />
                  <Chip
                    label={SYSTEM_LABELS[c.system] ?? c.system}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
                  />
                  <Chip
                    label={`Channel: #${channels.find((ch) => ch.id === c.channel_id)?.name ?? c.channel_id}`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0, color: 'text.secondary' }}
                  />
                  <Chip
                    label={c.is_active ? 'Active' : 'Inactive'}
                    size="small"
                    color={c.is_active ? 'success' : 'default'}
                    sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
                  />
                  {isAdmin && (
                    <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
                      <Tooltip title="Edit campaign">
                        <IconButton
                          size="small"
                          onClick={(e) => { e.stopPropagation(); startEdit(c); }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete campaign">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={(e) => { e.stopPropagation(); setDeleteId(c.id); }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  )}
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 1.5, pb: 2, px: 3 }}>
                <CharactersPanel
                  guildId={guildId!}
                  campaignId={c.id}
                  campaignSystem={c.system}
                  isAdmin={isAdmin}
                  currentUserId={currentUserId}
                  allCampaigns={activeCampaigns}
                />
              </AccordionDetails>
            </Accordion>
          ))}
        </Stack>
      )}

      {/* Deleted campaigns section — admin only */}
      {isAdmin && deletedCampaigns.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Divider sx={{ mb: 1.5 }} />
          <Typography variant="caption" color="text.disabled" sx={{ mb: 1, display: 'block' }}>
            {deletedCampaigns.length} deleted {deletedCampaigns.length === 1 ? 'campaign' : 'campaigns'}
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
                  (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q)
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
      <Dialog open={permanentDeleteId !== null} onClose={() => setPermanentDeleteId(null)} maxWidth="xs" fullWidth>
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
