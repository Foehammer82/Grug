import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import type { Combatant, Encounter } from '../../types';

interface InitiativePanelProps {
  guildId: string;
  campaignId: number;
  isGm: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  preparing: 'warning.main',
  active: 'primary.main',
  ended: 'text.disabled',
};

export default function InitiativePanel({ guildId, campaignId, isGm }: InitiativePanelProps) {
  const qc = useQueryClient();
  const canManage = isGm;

  // --- Active encounter query ---
  const { data: encounter, isLoading } = useQuery<Encounter | null>({
    queryKey: ['encounter-active', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Encounter | null>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/active`,
      );
      return res.data;
    },
    refetchInterval: 3000,
  });

  // --- Create encounter ---
  const [newEncounterName, setNewEncounterName] = useState('');
  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await client.post<Encounter>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters`,
        { name },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
      setNewEncounterName('');
    },
  });

  // --- Add combatant ---
  const [combatantName, setCombatantName] = useState('');
  const [combatantMod, setCombatantMod] = useState('');
  const [combatantEnemy, setCombatantEnemy] = useState(false);
  const addCombatantMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      const res = await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants`,
        {
          name: combatantName,
          initiative_modifier: combatantMod ? parseInt(combatantMod, 10) : 0,
          is_enemy: combatantEnemy,
        },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
      setCombatantName('');
      setCombatantMod('');
      setCombatantEnemy(false);
    },
  });

  // --- Remove combatant ---
  const removeCombatantMutation = useMutation({
    mutationFn: async (combatantId: number) => {
      if (!encounter) return;
      await client.delete(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${combatantId}`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
    },
  });

  // --- Roll initiative (start encounter) ---
  const rollMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/start`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
    },
  });

  // --- Advance turn ---
  const advanceMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/advance`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
    },
  });

  // --- End encounter ---
  const endMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/end`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  // ── No active encounter — show create form ──────────────────────
  if (!encounter) {
    return (
      <Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          No active encounter. {canManage ? 'Start one below!' : 'The GM can start one from Discord or the dashboard.'}
        </Typography>
        {canManage && (
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              size="small"
              label="Encounter name"
              value={newEncounterName}
              onChange={(e) => setNewEncounterName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newEncounterName.trim()) {
                  createMutation.mutate(newEncounterName.trim());
                }
              }}
              placeholder="Goblin Ambush"
              sx={{ width: 220 }}
            />
            <Button
              variant="contained"
              size="small"
              startIcon={<PlayArrowIcon />}
              disabled={!newEncounterName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate(newEncounterName.trim())}
            >
              {createMutation.isPending ? 'Creating…' : 'Start Encounter'}
            </Button>
          </Stack>
        )}
      </Box>
    );
  }

  // ── Active encounter view ───────────────────────────────────────
  const activeCombatants = encounter.combatants.filter((c) => c.is_active);
  const isPreparing = encounter.status === 'preparing';
  const isActive = encounter.status === 'active';

  return (
    <Box>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <Typography variant="subtitle1" fontWeight={600}>
          ⚔️ {encounter.name}
        </Typography>
        <Chip
          label={encounter.status.charAt(0).toUpperCase() + encounter.status.slice(1)}
          size="small"
          sx={{
            height: 20,
            fontSize: '0.7rem',
            color: STATUS_COLORS[encounter.status],
            borderColor: STATUS_COLORS[encounter.status],
          }}
          variant="outlined"
        />
        {isActive && (
          <Typography variant="caption" color="text.secondary">
            Round {encounter.round_number}
          </Typography>
        )}
        <Box sx={{ flex: 1 }} />
        {/* Action buttons */}
        {canManage && isPreparing && activeCombatants.length > 0 && (
          <Button
            variant="contained"
            size="small"
            color="success"
            startIcon={<PlayArrowIcon />}
            disabled={rollMutation.isPending}
            onClick={() => rollMutation.mutate()}
          >
            {rollMutation.isPending ? 'Rolling…' : 'Roll Initiative'}
          </Button>
        )}
        {canManage && isActive && (
          <Button
            variant="contained"
            size="small"
            startIcon={<NavigateNextIcon />}
            disabled={advanceMutation.isPending}
            onClick={() => advanceMutation.mutate()}
          >
            Next Turn
          </Button>
        )}
        {canManage && (isPreparing || isActive) && (
          <Button
            variant="outlined"
            size="small"
            color="error"
            startIcon={<StopIcon />}
            disabled={endMutation.isPending}
            onClick={() => endMutation.mutate()}
          >
            End
          </Button>
        )}
      </Stack>

      {/* Combatant list */}
      {activeCombatants.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          No combatants yet. Add some below!
        </Typography>
      ) : (
        <Stack spacing={0.25}>
          {activeCombatants.map((c, idx) => (
            <CombatantRow
              key={c.id}
              combatant={c}
              isCurrentTurn={isActive && idx === encounter.current_turn_index}
              canManage={canManage}
              onRemove={() => removeCombatantMutation.mutate(c.id)}
            />
          ))}
        </Stack>
      )}

      {/* Add combatant form */}
      {canManage && (isPreparing || isActive) && (
        <>
          <Divider sx={{ my: 1.5 }} />
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="Name"
              value={combatantName}
              onChange={(e) => setCombatantName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && combatantName.trim()) {
                  addCombatantMutation.mutate();
                }
              }}
              placeholder="Goblin 1"
              sx={{ width: 150 }}
            />
            <TextField
              size="small"
              label="Init mod"
              type="number"
              value={combatantMod}
              onChange={(e) => setCombatantMod(e.target.value)}
              sx={{ width: 80 }}
              placeholder="+3"
            />
            <Tooltip title={combatantEnemy ? 'Enemy/monster' : 'PC/ally'}>
              <Chip
                label={combatantEnemy ? '👹 Enemy' : '🛡️ Ally'}
                size="small"
                variant={combatantEnemy ? 'filled' : 'outlined'}
                color={combatantEnemy ? 'error' : 'default'}
                onClick={() => setCombatantEnemy(!combatantEnemy)}
                sx={{ cursor: 'pointer', height: 28 }}
              />
            </Tooltip>
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              disabled={!combatantName.trim() || addCombatantMutation.isPending}
              onClick={() => addCombatantMutation.mutate()}
            >
              Add
            </Button>
          </Stack>
        </>
      )}
    </Box>
  );
}

/** A single row in the combatant list. */
function CombatantRow({
  combatant,
  isCurrentTurn,
  canManage,
  onRemove,
}: {
  combatant: Combatant;
  isCurrentTurn: boolean;
  canManage: boolean;
  onRemove: () => void;
}) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1}
      sx={{
        px: 1,
        py: 0.5,
        borderRadius: 0.5,
        bgcolor: isCurrentTurn ? 'action.selected' : 'transparent',
        border: isCurrentTurn ? '1px solid' : '1px solid transparent',
        borderColor: isCurrentTurn ? 'primary.main' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
        transition: 'all 0.15s',
      }}
    >
      {/* Turn marker */}
      <Typography
        variant="body2"
        sx={{
          width: 20,
          fontWeight: 700,
          color: isCurrentTurn ? 'primary.main' : 'transparent',
        }}
      >
        ▶
      </Typography>

      {/* Initiative roll */}
      <Typography
        variant="body2"
        fontWeight={700}
        sx={{
          minWidth: 32,
          textAlign: 'right',
          color: combatant.initiative_roll != null ? 'text.primary' : 'text.disabled',
        }}
      >
        {combatant.initiative_roll ?? '—'}
      </Typography>

      {/* Name */}
      <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
        {combatant.name}
      </Typography>

      {/* Enemy badge */}
      {combatant.is_enemy && (
        <Chip
          label="Enemy"
          size="small"
          color="error"
          variant="outlined"
          sx={{ height: 18, fontSize: '0.6rem' }}
        />
      )}

      {/* Modifier */}
      {combatant.initiative_modifier !== 0 && (
        <Typography variant="caption" color="text.secondary">
          ({combatant.initiative_modifier > 0 ? '+' : ''}{combatant.initiative_modifier})
        </Typography>
      )}

      {/* Remove button */}
      {canManage && (
        <Tooltip title="Remove from encounter">
          <IconButton size="small" onClick={onRemove} sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}>
            <RemoveCircleOutlineIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      )}
    </Stack>
  );
}
