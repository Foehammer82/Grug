import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  FormLabel,
  IconButton,
  Link,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import client from '../../api/client';
import { fetchPathbuilderClientSide } from '../../utils/pathbuilder';
import { SHEET_ACCEPTED, MAX_SHEET_MB } from '../../constants/character';
import OwnerAutocomplete, { UNASSIGNED_MEMBER, resolveOwnerPayload } from './OwnerAutocomplete';
import CharacterStatCard from './CharacterStatCard';
import type { Campaign, Character, GuildMember } from '../../types';

// ── Types ──────────────────────────────────────────────────────────────────

type DialogMode = 'create' | 'edit';

interface CharacterDialogProps {
  open: boolean;
  onClose: () => void;
  /** 'create' shows only the Details tab; 'edit' shows all three tabs. */
  mode: DialogMode;
  /** The character being edited (required when mode='edit'). */
  character?: Character | null;
  guildId: string;
  campaignId: number;
  campaignSystem: string;
  isAdmin: boolean;
  isGm: boolean;
  currentUserId: string;
  /** All active campaigns — for the move/copy actions on the Details tab. */
  allCampaigns: Campaign[];
  /** Called AFTER a successful create/update/delete to refresh parent data. */
  onSuccess?: () => void;
  /** Initial tab index (0=Details, 1=Sheet, 2=Notes). */
  initialTab?: number;
}

// ── Component ──────────────────────────────────────────────────────────────

export default function CharacterDialog({
  open,
  onClose,
  mode,
  character,
  guildId,
  campaignId,
  campaignSystem,
  isAdmin,
  isGm,
  currentUserId,
  allCampaigns,
  onSuccess,
  initialTab = 0,
}: CharacterDialogProps) {
  const qc = useQueryClient();
  const isCreate = mode === 'create';
  const canEdit = isCreate || isGm || character?.owner_discord_user_id === currentUserId;

  // ── Tab state ─────────────────────────────────────────────────────────
  const [tab, setTab] = useState(isCreate ? 0 : initialTab);

  // Reset tab when dialog opens/closes or character changes
  useEffect(() => {
    if (open) setTab(isCreate ? 0 : initialTab);
  }, [open, isCreate, initialTab]);

  // ── Details form state ────────────────────────────────────────────────
  const [name, setName] = useState('');
  const [owner, setOwner] = useState<GuildMember | string>(UNASSIGNED_MEMBER);
  const [file, setFile] = useState<File | null>(null);
  const [pathbuilderId, setPathbuilderId] = useState('');
  const [pbIdCopied, setPbIdCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Notes state ───────────────────────────────────────────────────────
  const [notes, setNotes] = useState('');
  const [notesRevealed, setNotesRevealed] = useState(false);
  const notesInitRef = useRef('');

  // ── Transfer state ────────────────────────────────────────────────────
  const [transferOp, setTransferOp] = useState<'move' | 'copy' | null>(null);
  const [transferTarget, setTransferTarget] = useState<Campaign | null>(null);

  // Guild members — only fetched for admins
  const { data: guildMembers = [], isLoading: guildMembersLoading } = useQuery<GuildMember[]>({
    queryKey: ['guild-members', guildId],
    queryFn: async () => {
      const res = await client.get<GuildMember[]>(`/api/guilds/${guildId}/members`);
      return res.data;
    },
    enabled: isGm && !!guildId && open,
    staleTime: 60_000,
  });

  // Reset form when dialog opens
  useEffect(() => {
    if (!open) return;
    setError(null);
    setFile(null);
    setTransferOp(null);
    setTransferTarget(null);
    if (fileRef.current) fileRef.current.value = '';

    if (isCreate) {
      setName('');
      setPathbuilderId('');
      // Default owner to current user
      const me = guildMembers.find((m) => m.discord_user_id === currentUserId) ?? {
        discord_user_id: currentUserId,
        display_name: 'Me',
        username: '',
        avatar_url: null,
      };
      setOwner(me);
      setNotes('');
      notesInitRef.current = '';
      setNotesRevealed(true);
    } else if (character) {
      setName(character.name);
      setPathbuilderId(character.pathbuilder_id?.toString() ?? '');

      if (character.owner_discord_user_id) {
        const member =
          guildMembers.find((m) => m.discord_user_id === character.owner_discord_user_id) ?? {
            discord_user_id: character.owner_discord_user_id,
            display_name: character.owner_discord_user_id,
            username: '',
            avatar_url: null,
          };
        setOwner(member);
      } else if (character.owner_display_name) {
        setOwner(character.owner_display_name);
      } else {
        setOwner(UNASSIGNED_MEMBER);
      }

      const charNotes = character.notes ?? '';
      setNotes(charNotes);
      notesInitRef.current = charNotes;
      const isOwner = character.owner_discord_user_id === currentUserId;
      setNotesRevealed(isOwner || !character.notes);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, character?.id, isCreate]);

  const otherCampaigns = allCampaigns.filter((c) => c.id !== campaignId);

  // ── Invalidation helper ───────────────────────────────────────────────
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
    qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
    onSuccess?.();
  };

  // ── Create mutation ───────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = { name, system: campaignSystem };
      if (isGm) Object.assign(payload, resolveOwnerPayload(owner));

      // When importing from Pathbuilder the name will be overwritten by the
      // link step, so use a placeholder if the user left the field blank.
      if (!payload.name && pathbuilderId.trim()) {
        payload.name = 'Importing from Pathbuilder…';
      }

      const res = await client.post<Character>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
        payload,
      );
      const charId = res.data.id;

      if (file) {
        const form = new FormData();
        form.append('file', file);
        await client.post(
          `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}/upload`,
          form,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        );
      } else if (pathbuilderId.trim()) {
        const pbId = parseInt(pathbuilderId, 10);
        if (!isNaN(pbId)) {
          const pbData = await fetchPathbuilderClientSide(pbId);
          await client.post(
            `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}/link-pathbuilder`,
            { pathbuilder_id: pbId, pathbuilder_data: pbData },
          );
        }
      }
    },
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to create character.';
      setError(msg);
    },
  });

  // ── Update mutation ───────────────────────────────────────────────────
  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!character) return;
      const payload: Record<string, unknown> = { name };
      if (isGm) Object.assign(payload, resolveOwnerPayload(owner));

      await client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${character.id}`,
        payload,
      );

      if (file) {
        const form = new FormData();
        form.append('file', file);
        await client.post(
          `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${character.id}/upload`,
          form,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        );
      } else if (
        pathbuilderId.trim() &&
        pathbuilderId !== character.pathbuilder_id?.toString()
      ) {
        const pbId = parseInt(pathbuilderId, 10);
        if (!isNaN(pbId)) {
          const pbData = await fetchPathbuilderClientSide(pbId);
          await client.post(
            `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${character.id}/link-pathbuilder`,
            { pathbuilder_id: pbId, pathbuilder_data: pbData },
          );
        }
      }
    },
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to save changes.';
      setError(msg);
    },
  });

  // ── Notes auto-save ───────────────────────────────────────────────────
  const saveNotesMutation = useMutation({
    mutationFn: async ({ charId, charNotes }: { charId: number; charNotes: string | null }) =>
      client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${charId}`,
        { notes: charNotes },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
    },
  });

  useEffect(() => {
    if (!character || isCreate) return;
    if (notes === notesInitRef.current) return;
    const timer = setTimeout(() => {
      saveNotesMutation.mutate({ charId: character.id, charNotes: notes || null });
      notesInitRef.current = notes;
    }, 800);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes, character?.id]);

  // ── Move / Copy mutations ─────────────────────────────────────────────
  const moveMutation = useMutation({
    mutationFn: (targetId: number) =>
      client.patch(`/api/guilds/${guildId}/characters/${character!.id}`, {
        campaign_id: targetId,
      }),
    onSuccess: (_, targetId) => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, targetId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setTransferOp(null);
      setTransferTarget(null);
      onClose();
    },
  });

  const copyMutation = useMutation({
    mutationFn: (targetId: number) =>
      client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters/${character!.id}/copy`,
        { target_campaign_id: targetId },
      ),
    onSuccess: (_, targetId) => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, targetId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setTransferOp(null);
      setTransferTarget(null);
    },
  });

  // ── Delete mutation ───────────────────────────────────────────────────
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteMutation = useMutation({
    mutationFn: () =>
      client.delete(`/api/guilds/${guildId}/campaigns/${campaignId}/characters/${character!.id}`),
    onSuccess: () => {
      invalidate();
      setConfirmDelete(false);
      onClose();
    },
  });

  // ── Pending state ─────────────────────────────────────────────────────
  const isPending =
    createMutation.isPending ||
    updateMutation.isPending ||
    moveMutation.isPending ||
    copyMutation.isPending ||
    deleteMutation.isPending;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0 }}>
        {isCreate ? 'Add Character' : character?.name ?? 'Character'}
      </DialogTitle>

      {/* Tabs — only Details for create mode */}
      {!isCreate && (
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v as number)}
          sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Details" />
          <Tab label="Sheet" />
          <Tab label="Notes" />
        </Tabs>
      )}

      <DialogContent>
        {/* ── Tab 0: Details ─────────────────────────────────── */}
        {(isCreate || tab === 0) && (
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="Name"
              size="small"
              fullWidth
              required={!pathbuilderId.trim()}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!canEdit}
              placeholder={pathbuilderId.trim() ? 'Will be imported from Pathbuilder' : undefined}
            />

            {isGm && (
              <OwnerAutocomplete
                guildMembers={guildMembers}
                loading={guildMembersLoading}
                value={owner}
                onChange={setOwner}
              />
            )}

            {canEdit && (
              <Box>
                <FormLabel component="legend" sx={{ display: 'block', mb: 1 }}>
                  Character Sheet
                </FormLabel>
                <Stack spacing={1.5}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Button
                      variant="outlined"
                      component="label"
                      size="small"
                      startIcon={<CloudUploadIcon />}
                      color={file ? 'primary' : 'inherit'}
                    >
                      {file ? file.name : 'Upload file…'}
                      <input
                        ref={fileRef}
                        type="file"
                        accept={SHEET_ACCEPTED}
                        hidden
                        onChange={(e) => {
                          const f = e.target.files?.[0] ?? null;
                          if (f && f.size / (1024 * 1024) > MAX_SHEET_MB) {
                            setError(`File exceeds ${MAX_SHEET_MB} MB limit.`);
                            return;
                          }
                          setFile(f);
                          setPathbuilderId('');
                          setError(null);
                        }}
                      />
                    </Button>
                    {file && (
                      <Button
                        size="small"
                        onClick={() => {
                          setFile(null);
                          if (fileRef.current) fileRef.current.value = '';
                        }}
                      >
                        Clear
                      </Button>
                    )}
                  </Stack>
                  <TextField
                    label="Pathbuilder ID"
                    size="small"
                    type="number"
                    value={pathbuilderId}
                    onChange={(e) => {
                      setPathbuilderId(e.target.value);
                      if (e.target.value.trim()) {
                        setFile(null);
                        if (fileRef.current) fileRef.current.value = '';
                      }
                    }}
                    placeholder="e.g. 123456"
                    helperText="Filling one clears the other"
                    slotProps={{
                      htmlInput: { min: 1 },
                      input: pathbuilderId.trim()
                        ? {
                            endAdornment: (
                              <Tooltip title={pbIdCopied ? 'Copied!' : 'Copy ID'} placement="top">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    navigator.clipboard.writeText(pathbuilderId.trim()).then(() => {
                                      setPbIdCopied(true);
                                      setTimeout(() => setPbIdCopied(false), 1500);
                                    });
                                  }}
                                  edge="end"
                                >
                                  <ContentCopyIcon fontSize="inherit" />
                                </IconButton>
                              </Tooltip>
                            ),
                          }
                        : undefined,
                    }}
                  />
                  <Alert
                    severity="info"
                    sx={{ fontSize: '0.72rem', py: 0.25, '& .MuiAlert-message': { py: 0.5 } }}
                  >
                    <strong>How to import from Pathbuilder 2e:</strong>
                    <ol style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                      <li>
                        Build your character at{' '}
                        <Link href="https://pathbuilder2e.com" target="_blank" rel="noreferrer">
                          pathbuilder2e.com
                        </Link>
                      </li>
                      <li>Open the burger menu (☰) → <strong>Export JSON</strong></li>
                      <li>Copy the ID number from the export page and paste it above</li>
                      <li>
                        Or ask Grug in Discord:{' '}
                        <em>&ldquo;create my character from Pathbuilder ID 123456&rdquo;</em>
                      </li>
                    </ol>
                  </Alert>
                </Stack>
              </Box>
            )}

            {/* Move / Copy — admin only, edit mode only */}
            {!isCreate && isAdmin && otherCampaigns.length > 0 && (
              <Box>
                <FormLabel component="legend" sx={{ display: 'block', mb: 1 }}>
                  Transfer
                </FormLabel>
                <Stack direction="row" spacing={1} alignItems="center" mb={1}>
                  <Button
                    size="small"
                    variant={transferOp === 'move' ? 'contained' : 'outlined'}
                    onClick={() => setTransferOp(transferOp === 'move' ? null : 'move')}
                  >
                    Move to…
                  </Button>
                  <Button
                    size="small"
                    variant={transferOp === 'copy' ? 'contained' : 'outlined'}
                    onClick={() => setTransferOp(transferOp === 'copy' ? null : 'copy')}
                  >
                    Copy to…
                  </Button>
                </Stack>
                {transferOp && (
                  <Stack spacing={1.5}>
                    <Typography variant="body2" color="text.secondary">
                      {transferOp === 'move'
                        ? 'The character will be unlinked from this campaign and linked to the selected one.'
                        : 'A full copy of this character (including sheet data) will be added to the selected campaign.'}
                    </Typography>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Autocomplete
                        size="small"
                        sx={{ flex: 1 }}
                        options={otherCampaigns}
                        value={transferTarget}
                        onChange={(_, c) => setTransferTarget(c)}
                        getOptionLabel={(c) => c.name}
                        isOptionEqualToValue={(a, b) => a.id === b.id}
                        renderInput={(params) => (
                          <TextField {...params} label="Target Campaign" />
                        )}
                      />
                      <Button
                        size="small"
                        variant="contained"
                        disabled={!transferTarget || isPending}
                        onClick={() => {
                          if (!transferTarget) return;
                          if (transferOp === 'move') moveMutation.mutate(transferTarget.id);
                          else copyMutation.mutate(transferTarget.id);
                        }}
                      >
                        {isPending
                          ? transferOp === 'move' ? 'Moving…' : 'Copying…'
                          : transferOp === 'move' ? 'Move' : 'Copy'}
                      </Button>
                    </Stack>
                  </Stack>
                )}
              </Box>
            )}

            {error && (
              <Typography variant="caption" color="error">
                {error}
              </Typography>
            )}
          </Stack>
        )}

        {/* ── Tab 1: Sheet ──────────────────────────────────── */}
        {!isCreate && tab === 1 && (
          character?.structured_data ? (
            <CharacterStatCard sheet={character.structured_data} />
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
              No parsed sheet data available.
            </Typography>
          )
        )}

        {/* ── Tab 2: Notes ──────────────────────────────────── */}
        {!isCreate && tab === 2 && character && (() => {
          const isOwner = character.owner_discord_user_id === currentUserId;
          const hasHiddenNotes = !isOwner && isGm && !!character.notes;
          return (
            <Box sx={{ pt: 1 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Private — only visible to the owner and GMs.
                </Typography>
                {saveNotesMutation.isPending && <CircularProgress size={14} />}
              </Stack>
              {hasHiddenNotes && !notesRevealed ? (
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="caption" color="text.disabled" sx={{ fontStyle: 'italic' }}>
                    Notes hidden.
                  </Typography>
                  <Tooltip title="Reveal notes">
                    <IconButton size="small" onClick={() => setNotesRevealed(true)}>
                      <VisibilityIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              ) : (
                <>
                  <TextField
                    multiline
                    minRows={5}
                    maxRows={14}
                    size="small"
                    fullWidth
                    placeholder="Jot down anything about this character — backstory, session notes, secrets…"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={!isOwner && !isGm}
                  />
                  {hasHiddenNotes && notesRevealed && (
                    <Box sx={{ mt: 0.5 }}>
                      <Tooltip title="Hide notes">
                        <IconButton size="small" onClick={() => setNotesRevealed(false)}>
                          <VisibilityOffIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  )}
                </>
              )}
            </Box>
          );
        })()}
      </DialogContent>

      <DialogActions>
        {/* Delete — visible on Details tab for owners/admins in edit mode */}
        {!isCreate && tab === 0 && canEdit && (
          <Box sx={{ flex: 1, display: 'flex' }}>
            {confirmDelete ? (
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" color="error">Are you sure?</Typography>
                <Button
                  size="small"
                  color="error"
                  variant="contained"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate()}
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Yes, delete'}
                </Button>
                <Button size="small" onClick={() => setConfirmDelete(false)}>
                  No
                </Button>
              </Stack>
            ) : (
              <Button size="small" color="error" onClick={() => setConfirmDelete(true)}>
                Delete
              </Button>
            )}
          </Box>
        )}

        <Button size="small" onClick={onClose}>
          {isCreate ? 'Cancel' : 'Close'}
        </Button>

        {/* Save/Create button — only on Details tab */}
        {(isCreate || tab === 0) && canEdit && (
          <Button
            size="small"
            variant="contained"
            disabled={isPending || (!name.trim() && !pathbuilderId.trim())}
            onClick={() => {
              if (isCreate) createMutation.mutate();
              else updateMutation.mutate();
            }}
          >
            {isPending
              ? isCreate ? 'Creating…' : 'Saving…'
              : isCreate ? 'Create' : 'Save'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
