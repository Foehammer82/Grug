import { useState } from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CasinoIcon from '@mui/icons-material/Casino';
import CloseIcon from '@mui/icons-material/Close';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import type { DiceRoll } from '../../types';
import { ROLL_TYPE_LABELS } from '../../types';

interface DiceTabProps {
  guildId: string;
  campaignId: number;
  isGm: boolean;
  currentUserId: string;
}

const DICE_OPTIONS = [
  { sides: 4, label: 'd4', color: '#e57373' },
  { sides: 6, label: 'd6', color: '#f06292' },
  { sides: 8, label: 'd8', color: '#ba68c8' },
  { sides: 10, label: 'd10', color: '#9575cd' },
  { sides: 12, label: 'd12', color: '#7986cb' },
  { sides: 20, label: 'd20', color: '#64b5f6' },
  { sides: 100, label: 'd100', color: '#4dd0e1' },
] as const;

/** Format a relative timestamp like "2m ago", "1h ago". */
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const DEFAULT_QUANTITY = 1;
const DEFAULT_DIE = 20;
const HISTORY_PREVIEW_COUNT = 5;

export default function DiceTab({ guildId, campaignId, isGm, currentUserId }: DiceTabProps) {
  const qc = useQueryClient();

  // --- Roller state ---
  const [quantity, setQuantity] = useState(DEFAULT_QUANTITY);
  const [selectedDie, setSelectedDie] = useState(DEFAULT_DIE);
  const [modifier, setModifier] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [customExpr, setCustomExpr] = useState('');
  const [lastResult, setLastResult] = useState<DiceRoll | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  // --- History ---
  const { data: history, isLoading: historyLoading } = useQuery<DiceRoll[]>({
    queryKey: ['dice-history', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<DiceRoll[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/dice/history`,
        { params: { limit: 50 } },
      );
      return res.data;
    },
    refetchInterval: 5000,
  });

  // --- Roll mutation ---
  const rollMutation = useMutation({
    mutationFn: async (payload: { expression: string; is_private: boolean; roll_type?: string }) => {
      const res = await client.post<DiceRoll>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/dice/roll`,
        payload,
      );
      return res.data;
    },
    onSuccess: (data) => {
      setLastResult(data);
      qc.invalidateQueries({ queryKey: ['dice-history', guildId, campaignId] });
    },
  });

  const handleRoll = () => {
    const expr = customExpr.trim();
    if (expr) {
      rollMutation.mutate({ expression: expr, is_private: isPrivate });
      return;
    }
    // Build expression from buttons
    const mod = modifier.trim();
    let expression = `${quantity}d${selectedDie}`;
    if (mod) {
      // Allow "+5", "-2", or just "5" (treated as +5)
      if (mod.startsWith('+') || mod.startsWith('-')) {
        expression += mod;
      } else {
        expression += `+${mod}`;
      }
    }
    rollMutation.mutate({ expression, is_private: isPrivate });
  };

  const handleQuickRoll = (sides: number) => {
    const mod = modifier.trim();
    let expression = `${quantity}d${sides}`;
    if (mod) {
      if (mod.startsWith('+') || mod.startsWith('-')) {
        expression += mod;
      } else {
        expression += `+${mod}`;
      }
    }
    rollMutation.mutate({ expression, is_private: isPrivate });
  };

  const handleReset = () => {
    setQuantity(DEFAULT_QUANTITY);
    setSelectedDie(DEFAULT_DIE);
    setModifier('');
    setIsPrivate(false);
    setCustomExpr('');
  };

  const previewHistory = history?.slice(0, HISTORY_PREVIEW_COUNT) ?? [];

  return (
    <Box>
      {/* ── Dice Roller ─────────────────────────────── */}
      <Stack spacing={1.5}>
        {/* Quick-roll dice buttons */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
            Quick roll:
          </Typography>
          {DICE_OPTIONS.map((d) => (
            <Button
              key={d.sides}
              variant={selectedDie === d.sides ? 'contained' : 'outlined'}
              size="small"
              onClick={() => {
                setSelectedDie(d.sides);
                setCustomExpr('');
                handleQuickRoll(d.sides);
              }}
              sx={{
                minWidth: 48,
                fontSize: '0.75rem',
                fontWeight: 700,
                borderColor: d.color,
                color: selectedDie === d.sides ? '#fff' : d.color,
                bgcolor: selectedDie === d.sides ? d.color : 'transparent',
                '&:hover': { bgcolor: d.color, color: '#fff' },
              }}
            >
              {d.label}
            </Button>
          ))}
        </Stack>

        {/* Controls row */}
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <ButtonGroup size="small" variant="outlined">
            <Button onClick={() => setQuantity((q) => Math.max(1, q - 1))} disabled={quantity <= 1}>
              −
            </Button>
            <Button disabled sx={{ minWidth: 36, fontWeight: 700 }}>
              {quantity}
            </Button>
            <Button onClick={() => setQuantity((q) => Math.min(20, q + 1))} disabled={quantity >= 20}>
              +
            </Button>
          </ButtonGroup>

          <TextField
            size="small"
            label="Modifier"
            value={modifier}
            onChange={(e) => setModifier(e.target.value)}
            sx={{ width: 90 }}
            placeholder="+5"
          />

          <Typography variant="caption" color="text.secondary" sx={{ mx: 0.5 }}>
            or
          </Typography>

          <TextField
            size="small"
            label="Custom expression"
            value={customExpr}
            onChange={(e) => setCustomExpr(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleRoll();
            }}
            placeholder="2d6+1d4+3"
            sx={{ width: 180 }}
          />

          <Tooltip title={isPrivate ? 'Private — only you and GM see this' : 'Public — everyone sees this'}>
            <IconButton
              size="small"
              onClick={() => setIsPrivate(!isPrivate)}
              color={isPrivate ? 'warning' : 'default'}
            >
              {isPrivate ? <LockIcon fontSize="small" /> : <LockOpenIcon fontSize="small" />}
            </IconButton>
          </Tooltip>

          <Button
            variant="contained"
            size="small"
            startIcon={<CasinoIcon />}
            onClick={handleRoll}
            disabled={rollMutation.isPending}
          >
            {rollMutation.isPending ? 'Rolling…' : 'Roll'}
          </Button>

          <Tooltip title="Reset to defaults">
            <IconButton size="small" onClick={handleReset}>
              <RestartAltIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Last result */}
        {lastResult && (
          <Box
            sx={{
              p: 1.5,
              borderRadius: 1,
              bgcolor: 'action.hover',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Stack direction="row" alignItems="center" spacing={1}>
              <CasinoIcon sx={{ fontSize: 18, color: 'primary.main' }} />
              <Typography variant="body2" fontWeight={600}>
                {lastResult.expression}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                →
              </Typography>
              <Typography variant="h6" fontWeight={700} color="primary.main">
                {lastResult.total}
              </Typography>
              {lastResult.is_private && (
                <Chip label="Private" size="small" color="warning" sx={{ height: 18, fontSize: '0.65rem' }} />
              )}
            </Stack>
            {/* Show individual dice */}
            <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
              {lastResult.individual_rolls.map((group, idx) =>
                group.rolls ? (
                  <Chip
                    key={idx}
                    label={`${group.expression}: [${group.kept?.join(', ')}]`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                ) : (
                  <Chip
                    key={idx}
                    label={`${group.sign === -1 ? '-' : '+'}${group.constant}`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                ),
              )}
            </Stack>
          </Box>
        )}

        {rollMutation.isError && (
          <Typography variant="caption" color="error">
            {(rollMutation.error as Error)?.message ?? 'Roll failed'}
          </Typography>
        )}
      </Stack>

      {/* ── Roll History ────────────────────────────── */}
      <Divider sx={{ my: 2 }} />
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 0.5 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Recent Rolls {isGm ? '(all rolls)' : '(your rolls + public)'}
        </Typography>
        {(history?.length ?? 0) > HISTORY_PREVIEW_COUNT && (
          <Button size="small" onClick={() => setHistoryOpen(true)}>
            View All ({history!.length})
          </Button>
        )}
      </Stack>

      {historyLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      ) : !history?.length ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          No rolls yet. Use the roller above or type /roll in Discord!
        </Typography>
      ) : (
        <Stack spacing={0.5}>
          {previewHistory.map((r) => (
            <RollHistoryRow key={r.id} roll={r} currentUserId={currentUserId} />
          ))}
        </Stack>
      )}

      {/* ── Full History Dialog ──────────────────────── */}
      <Dialog
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">Roll History</Typography>
          <IconButton size="small" onClick={() => setHistoryOpen(false)}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers>
          {!history?.length ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
              No rolls yet.
            </Typography>
          ) : (
            <Stack spacing={0.5} sx={{ maxHeight: 480, overflowY: 'auto' }}>
              {history.map((r) => (
                <RollHistoryRow key={r.id} roll={r} currentUserId={currentUserId} />
              ))}
            </Stack>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

/** A single row in the roll history list. */
function RollHistoryRow({ roll, currentUserId }: { roll: DiceRoll; currentUserId: string }) {
  const isOwn = roll.roller_discord_user_id === currentUserId;

  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1}
      sx={{
        px: 1,
        py: 0.5,
        borderRadius: 0.5,
        bgcolor: isOwn ? 'action.selected' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Typography variant="caption" color="text.disabled" sx={{ minWidth: 52, flexShrink: 0 }}>
        {timeAgo(roll.created_at)}
      </Typography>

      <Typography variant="body2" fontWeight={500} noWrap sx={{ minWidth: 80, maxWidth: 120 }}>
        {roll.character_name ?? roll.roller_display_name}
      </Typography>

      <Chip
        label={ROLL_TYPE_LABELS[roll.roll_type] ?? roll.roll_type}
        size="small"
        variant="outlined"
        sx={{ height: 18, fontSize: '0.6rem', flexShrink: 0 }}
      />

      <Typography variant="body2" color="text.secondary" noWrap sx={{ flex: 1 }}>
        {roll.expression}
      </Typography>

      <Typography variant="body2" fontWeight={700} sx={{ minWidth: 36, textAlign: 'right' }}>
        {roll.total}
      </Typography>

      {roll.is_private && (
        <Tooltip title="Private roll">
          <LockIcon sx={{ fontSize: 14, color: 'warning.main' }} />
        </Tooltip>
      )}

      {roll.context_note && (
        <Tooltip title={roll.context_note}>
          <Typography variant="caption" color="text.disabled" noWrap sx={{ maxWidth: 120 }}>
            {roll.context_note}
          </Typography>
        </Tooltip>
      )}
    </Stack>
  );
}
