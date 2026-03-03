import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
  IconButton,
  Menu,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PersonIcon from '@mui/icons-material/Person';
import TableRestaurantIcon from '@mui/icons-material/TableRestaurant';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import type { Campaign, Character, CharacterSheet, DiscordChannel, GuildMember } from '../types';

// Suggested systems shown in the autocomplete dropdown — users may still type
// any free-form value for unsupported systems.
const SYSTEM_OPTIONS = ['dnd5e', 'pf2e'];

const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

const SHEET_ACCEPTED = '.txt,.md,.rst,.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp';
const MAX_SHEET_MB = 20;

// ── Guild member cell ─────────────────────────────────────────────────────

function GuildMemberCell({ guildId, userId }: { guildId: string; userId: string }) {
  const { data, isLoading, isError } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => {
      const res = await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

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

// ── Characters panel ──────────────────────────────────────────────────────

interface CharactersPanelProps {
  guildId: string;
  campaignId: number;
  campaignSystem: string;
  isAdmin: boolean;
}

function CharactersPanel({ guildId, campaignId, campaignSystem, isAdmin }: CharactersPanelProps) {
  const qc = useQueryClient();

  // Add form
  const [showAdd, setShowAdd] = useState(false);
  const [addName, setAddName] = useState('');
  const [addFile, setAddFile] = useState<File | null>(null);
  const addFileRef = useRef<HTMLInputElement>(null);

  // Inline edit
  const [editCharId, setEditCharId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  // Delete confirm
  const [deleteCharId, setDeleteCharId] = useState<number | null>(null);

  // Upload sheet dialog
  const [uploadCharId, setUploadCharId] = useState<number | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 3-dot action menu for character rows
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [menuCharId, setMenuCharId] = useState<number | null>(null);

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

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await client.post<Character>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
        { name: addName, system: campaignSystem }
      );
      if (addFile) {
        try {
          const form = new FormData();
          form.append('file', addFile);
          await client.post(
            `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${res.data.id}/upload`,
            form,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          );
        } catch {
          // Character was created — upload failure is non-fatal
        }
      }
    },
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setAddName('');
      setAddFile(null);
      if (addFileRef.current) addFileRef.current.value = '';
      setShowAdd(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${editCharId}`,
        { name: editName }
      ),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setEditCharId(null);
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

  const uploadMutation = useMutation({
    mutationFn: async ({ charId, file }: { charId: number; file: File }) => {
      const form = new FormData();
      form.append('file', file);
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}/upload`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
    },
    onSuccess: () => {
      invalidate();
      closeUploadDialog();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Upload failed. Please try again.';
      setUploadError(msg);
    },
  });

  function startEdit(ch: Character) {
    setEditCharId(ch.id);
    setEditName(ch.name);
    setDeleteCharId(null);
  }

  function openUploadDialog(charId: number) {
    setUploadCharId(charId);
    setUploadFile(null);
    setUploadError(null);
  }

  function openMenu(e: React.MouseEvent<HTMLElement>, charId: number) {
    e.stopPropagation();
    setMenuAnchorEl(e.currentTarget);
    setMenuCharId(charId);
  }

  function closeMenu() {
    setMenuAnchorEl(null);
    setMenuCharId(null);
  }

  function closeUploadDialog() {
    setUploadCharId(null);
    setUploadFile(null);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setUploadError(null);
    if (!file) { setUploadFile(null); return; }
    if (file.size / (1024 * 1024) > MAX_SHEET_MB) {
      setUploadError(`File exceeds ${MAX_SHEET_MB} MB limit.`);
      setUploadFile(null);
      return;
    }
    setUploadFile(file);
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
                <Stack spacing={1.5}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <TextField
                      label="Name"
                      size="small"
                      required
                      value={addName}
                      onChange={(e) => setAddName(e.target.value)}
                      sx={{ minWidth: 180 }}
                    />
                    <Button
                      type="submit"
                      variant="contained"
                      size="small"
                      disabled={createMutation.isPending || !addName.trim()}
                    >
                      {createMutation.isPending ? 'Adding…' : 'Add'}
                    </Button>
                  </Stack>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Button
                      variant="outlined"
                      component="label"
                      size="small"
                      disabled={createMutation.isPending}
                    >
                      {addFile ? addFile.name : 'Attach sheet… (optional)'}
                      <input
                        ref={addFileRef}
                        type="file"
                        accept={SHEET_ACCEPTED}
                        hidden
                        onChange={(e) => {
                          const f = e.target.files?.[0] ?? null;
                          if (f && f.size / (1024 * 1024) > MAX_SHEET_MB) {
                            alert(`File exceeds ${MAX_SHEET_MB} MB limit.`);
                            return;
                          }
                          setAddFile(f);
                        }}
                      />
                    </Button>
                    {addFile && (
                      <Button
                        size="small"
                        onClick={() => {
                          setAddFile(null);
                          if (addFileRef.current) addFileRef.current.value = '';
                        }}
                      >
                        Clear
                      </Button>
                    )}
                  </Stack>
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
                    <Box key={ch.id} sx={{ py: 1 }}>
                    {editCharId === ch.id ? (
                      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
                        <TextField
                          size="small"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          sx={{ minWidth: 160 }}
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
                      </Stack>
                    ) : deleteCharId === ch.id ? (
                      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
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
                      </Stack>                    ) : (
                      <>
                        <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                          <Typography variant="body2" fontWeight={500} sx={{ flex: 1 }}>
                            {ch.name}
                          </Typography>
                          {ch.file_path && (
                            <Tooltip title="Character sheet on file">
                              <Chip label="Sheet" size="small" color="info" variant="outlined" />
                            </Tooltip>
                          )}
                          <GuildMemberCell guildId={guildId} userId={ch.owner_discord_user_id} />
                          {isAdmin && (
                            <IconButton size="small" onClick={(e) => openMenu(e, ch.id)}>
                              <MoreVertIcon fontSize="small" />
                            </IconButton>
                          )}
                        </Stack>
                        {ch.structured_data && (
                          <CharacterStatCard sheet={ch.structured_data} />
                        )}
                      </>
                    )}
                  </Box>
                ))}
              </Stack>
            )}
      </Box>

      {/* Character actions menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={menuAnchorEl !== null}
        onClose={closeMenu}
        slotProps={{ paper: { elevation: 2 } }}
      >
        <MenuItem
          dense
          onClick={() => {
            const ch = characters.find((c) => c.id === menuCharId);
            if (ch) startEdit(ch);
            closeMenu();
          }}
        >
          Edit name
        </MenuItem>
        <MenuItem
          dense
          onClick={() => {
            if (menuCharId !== null) openUploadDialog(menuCharId);
            closeMenu();
          }}
        >
          Upload sheet
        </MenuItem>
        <Divider />
        <MenuItem
          dense
          sx={{ color: 'error.main' }}
          onClick={() => {
            setDeleteCharId(menuCharId);
            closeMenu();
          }}
        >
          Delete
        </MenuItem>
      </Menu>

      {/* Upload sheet dialog */}
      <Dialog
        open={uploadCharId !== null}
        onClose={closeUploadDialog}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Upload Character Sheet</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Upload a PDF, image, or text file. Grug will parse it and extract
              stats automatically.
            </Typography>
            <Button
              variant="outlined"
              component="label"
              size="small"
              sx={{ alignSelf: 'flex-start' }}
            >
              {uploadFile ? uploadFile.name : 'Choose file…'}
              <input
                ref={fileInputRef}
                type="file"
                accept={SHEET_ACCEPTED}
                hidden
                onChange={handleFileChange}
              />
            </Button>
            {uploadError && (
              <Typography variant="caption" color="error">
                {uploadError}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={closeUploadDialog}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            disabled={!uploadFile || uploadMutation.isPending}
            onClick={() => {
              if (uploadCharId !== null && uploadFile) {
                uploadMutation.mutate({ charId: uploadCharId, file: uploadFile });
              }
            }}
          >
            {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
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

  // Campaign 3-dot menu
  const [campaignMenuAnchor, setCampaignMenuAnchor] = useState<null | HTMLElement>(null);
  const [campaignMenuId, setCampaignMenuId] = useState<number | null>(null);

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
      cancelEdit();
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

  function openCampaignMenu(e: React.MouseEvent<HTMLElement>, id: number) {
    e.stopPropagation();
    setCampaignMenuAnchor(e.currentTarget);
    setCampaignMenuId(id);
  }

  function closeCampaignMenu() {
    setCampaignMenuAnchor(null);
    setCampaignMenuId(null);
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

      {/* Campaign list */}
      {campaigns.length === 0 ? (
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
          {campaigns.map((c) => (
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
                    label={c.system}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ fontFamily: 'monospace', color: 'text.secondary', flexShrink: 0 }}
                    noWrap
                  >
                    {channelName(c.channel_id)}
                  </Typography>
                  <Chip
                    label={c.is_active ? 'Active' : 'Inactive'}
                    size="small"
                    color={c.is_active ? 'success' : 'default'}
                    sx={{ flexShrink: 0 }}
                  />
                  {isAdmin && (
                    <IconButton
                      size="small"
                      onClick={(e) => openCampaignMenu(e, c.id)}
                      sx={{ flexShrink: 0 }}
                    >
                      <MoreVertIcon fontSize="small" />
                    </IconButton>
                  )}
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 1.5, pb: 2, px: 3 }}>
                <CharactersPanel
                  guildId={guildId!}
                  campaignId={c.id}
                  campaignSystem={c.system}
                  isAdmin={isAdmin}
                />
              </AccordionDetails>
            </Accordion>
          ))}
        </Stack>
      )}

      {/* Campaign 3-dot menu */}
      <Menu
        anchorEl={campaignMenuAnchor}
        open={campaignMenuAnchor !== null}
        onClose={closeCampaignMenu}
        slotProps={{ paper: { elevation: 2 } }}
      >
        <MenuItem
          dense
          onClick={() => {
            const c = campaigns.find((x) => x.id === campaignMenuId);
            if (c) startEdit(c);
            closeCampaignMenu();
          }}
        >
          Edit
        </MenuItem>
        <Divider />
        <MenuItem
          dense
          sx={{ color: 'error.main' }}
          onClick={() => {
            setDeleteId(campaignMenuId);
            closeCampaignMenu();
          }}
        >
          Delete
        </MenuItem>
      </Menu>

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
            Are you sure you want to delete{' '}
            <strong>{campaigns.find((c) => c.id === deleteId)?.name ?? 'this campaign'}</strong>?
            This will also remove all associated characters.
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
    </Stack>
  );
}
