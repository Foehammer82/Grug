import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn'
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import client from '../../api/client';
import GuildMemberCell from './GuildMemberCell';
import CharacterDialog from './CharacterDialog';
import GoldManageDialog from './GoldManageDialog';
import type { Campaign, Character } from '../../types';

// ── CopyablePathbuilderChip ────────────────────────────────────────────────

function CopyablePathbuilderChip({ pathbuilderId }: { pathbuilderId: number }) {
  const [copied, setCopied] = useState(false);
  const [hovered, setHovered] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(String(pathbuilderId)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <Tooltip title={copied ? 'Copied!' : `ID: ${pathbuilderId}`} placement="top">
      <Chip
        label="Pathbuilder"
        size="small"
        color={copied ? 'success' : 'secondary'}
        variant="outlined"
        onClick={handleCopy}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        deleteIcon={<ContentCopyIcon sx={{ fontSize: '0.75rem !important' }} />}
        onDelete={hovered ? handleCopy : undefined}
        sx={{
          height: 20,
          fontSize: '0.65rem',
          cursor: 'pointer',
          transition: 'width 0.15s ease',
        }}
      />
    </Tooltip>
  );
}

interface CharacterTableProps {
  guildId: string;
  campaignId: number;
  campaignSystem: string;
  isAdmin: boolean;
  isGm: boolean;
  currentUserId: string;
  allCampaigns: Campaign[];
  bankingEnabled?: boolean;
  playerBankingEnabled?: boolean;
  partyGold?: number;
}

export default function CharacterTable({
  guildId,
  campaignId,
  campaignSystem,
  isAdmin,
  isGm,
  currentUserId,
  allCampaigns,
  bankingEnabled = false,
  playerBankingEnabled = false,
  partyGold = 0,
}: CharacterTableProps) {
  const qc = useQueryClient();

  // ── Data ──────────────────────────────────────────────────────────────
  const { data: characters = [], isLoading } = useQuery<Character[]>({
    queryKey: ['campaign-characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
      );
      return res.data;
    },
    enabled: !!guildId,
  });

  // ── Selection state (batch ops) ───────────────────────────────────────
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === characters.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(characters.map((c) => c.id)));
    }
  }

  // ── Batch delete mutation ─────────────────────────────────────────────
  const batchDeleteMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(
        ids.map((id) =>
          client.delete(`/api/guilds/${guildId}/campaigns/${campaignId}/characters/${id}`),
        ),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      setSelected(new Set());
      setDeleteConfirmOpen(false);
    },
  });

  // ── Character dialog state ────────────────────────────────────────────
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [dialogChar, setDialogChar] = useState<Character | null>(null);
  const [dialogTab, setDialogTab] = useState(0);

  // ── Gold manage dialog state ──────────────────────────────────────────
  const [goldChar, setGoldChar] = useState<Character | null>(null);

  function openCreate() {
    setDialogMode('create');
    setDialogChar(null);
    setDialogTab(0);
    setDialogOpen(true);
  }

  function openCharacter(ch: Character, tab = 0) {
    setDialogMode('edit');
    setDialogChar(ch);
    setDialogTab(tab);
    setDialogOpen(true);
  }

  // Only GMs/admins (or owners of at least one selected character) can batch-delete
  const canBatchDelete =
    isGm ||
    [...selected].every((id) => {
      const ch = characters.find((c) => c.id === id);
      return ch?.owner_discord_user_id === currentUserId;
    });

  const selectedNames = characters
    .filter((c) => selected.has(c.id))
    .map((c) => c.name);

  // ── Loading state ─────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <>
      {/* Batch toolbar — visible when rows are selected */}
      {selected.size > 0 && canBatchDelete && (
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {selected.size} selected
          </Typography>
          <Button
            size="small"
            color="error"
            variant="outlined"
            onClick={() => setDeleteConfirmOpen(true)}
          >
            Delete selected
          </Button>
        </Stack>
      )}

      {characters.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          No characters yet.
        </Typography>
      ) : (
        <Table size="small" sx={{ '& td, & th': { borderColor: 'divider' } }}>
          <TableHead>
            <TableRow>
              {(isGm || characters.some((c) => c.owner_discord_user_id === currentUserId)) && (
                <TableCell padding="checkbox" sx={{ width: 42 }}>
                  <Checkbox
                    size="small"
                    indeterminate={selected.size > 0 && selected.size < characters.length}
                    checked={selected.size === characters.length && characters.length > 0}
                    onChange={toggleAll}
                  />
                </TableCell>
              )}
              <TableCell>Name</TableCell>
              <TableCell sx={{ width: 100 }}>Source</TableCell>
              <TableCell sx={{ width: 140 }}>Owner</TableCell>
              {bankingEnabled && <TableCell sx={{ width: 90 }}>Gold</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {characters.map((ch) => {
              const canEdit = isGm || ch.owner_discord_user_id === currentUserId;
              return (
                <TableRow
                  key={ch.id}
                  hover
                  sx={{ cursor: 'pointer', '&:last-child td': { borderBottom: 0 } }}
                  onClick={() => openCharacter(ch, canEdit ? 0 : 1)}
                >
                  {(isGm || characters.some((c) => c.owner_discord_user_id === currentUserId)) && (
                    <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                      {canEdit && (
                        <Checkbox
                          size="small"
                          checked={selected.has(ch.id)}
                          onChange={() => toggleOne(ch.id)}
                        />
                      )}
                    </TableCell>
                  )}
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {ch.name}
                    </Typography>
                    {ch.structured_data && (
                      <Typography variant="caption" color="text.secondary">
                        {[
                          ch.structured_data.level != null && `Lvl ${ch.structured_data.level}`,
                          ch.structured_data.class_and_subclass,
                          ch.structured_data.race_or_ancestry,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {ch.pathbuilder_id != null ? (
                      <CopyablePathbuilderChip pathbuilderId={ch.pathbuilder_id} />
                    ) : ch.file_path ? (
                      <Chip label="Sheet" size="small" color="info" variant="outlined" sx={{ height: 20, fontSize: '0.65rem' }} />
                    ) : null}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <GuildMemberCell
                      guildId={guildId}
                      userId={ch.owner_discord_user_id}
                      displayName={ch.owner_display_name}
                    />
                  </TableCell>
                  {bankingEnabled && (() => {
                    const isAdminOrGm = isGm;
                    const isOwner = ch.owner_discord_user_id === currentUserId;
                    const canSee = isAdminOrGm || isOwner;
                    const canManage = isAdminOrGm || (isOwner && playerBankingEnabled);
                    return (
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {canSee ? (
                          <Tooltip
                            title={canManage ? 'Manage gold' : ''}
                            placement="top"
                          >
                            <Chip
                              size="small"
                              variant="outlined"
                              icon={
                                <MonetizationOnIcon
                                  sx={{ fontSize: '13px !important', color: 'warning.main !important' }}
                                />
                              }
                              label={
                                `${(ch.gold ?? 0).toLocaleString(undefined, { maximumFractionDigits: 4 })} gp`
                              }
                              onClick={canManage ? () => setGoldChar(ch) : undefined}
                              sx={{
                                height: 20,
                                fontSize: '0.7rem',
                                fontVariantNumeric: 'tabular-nums',
                                color: 'warning.main',
                                borderColor: 'warning.main',
                                cursor: canManage ? 'pointer' : 'default',
                              }}
                            />
                          </Tooltip>
                        ) : (
                          <Typography variant="body2" color="text.disabled">&mdash;</Typography>
                        )}
                      </TableCell>
                    );
                  })()}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {/* Add character button */}
      <Box sx={{ mt: 1 }}>
        <Button size="small" variant="outlined" onClick={openCreate}>
          + Add Character
        </Button>
      </Box>

      {/* Character create/edit dialog */}
      <CharacterDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        mode={dialogMode}
        character={dialogChar}
        guildId={guildId}
        campaignId={campaignId}
        campaignSystem={campaignSystem}
        isAdmin={isAdmin}
        isGm={isGm}
        currentUserId={currentUserId}
        allCampaigns={allCampaigns}
        initialTab={dialogTab}
      />

      {/* Gold manage dialog */}
      {goldChar && (
        <GoldManageDialog
          open={goldChar !== null}
          onClose={() => setGoldChar(null)}
          guildId={guildId}
          campaignId={campaignId}
          character={goldChar}
          isAdminOrGm={isGm}
          playerBankingEnabled={playerBankingEnabled}
          partyGold={partyGold}
        />
      )}

      {/* Batch delete confirmation */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete {selected.size} {selected.size === 1 ? 'Character' : 'Characters'}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>
            This will permanently delete the following {selected.size === 1 ? 'character' : 'characters'}:
          </Typography>
          <Stack spacing={0.25}>
            {selectedNames.map((n) => (
              <Typography key={n} variant="body2" fontWeight={500}>
                • {n}
              </Typography>
            ))}
          </Stack>
          <Typography variant="body2" color="error" sx={{ mt: 1.5 }}>
            This cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
          <Button
            size="small"
            color="error"
            variant="contained"
            disabled={batchDeleteMutation.isPending}
            onClick={() => batchDeleteMutation.mutate([...selected])}
          >
            {batchDeleteMutation.isPending ? 'Deleting…' : `Delete ${selected.size}`}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
