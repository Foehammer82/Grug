import { useEffect, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CasinoIcon from '@mui/icons-material/Casino';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import type { Character, DiceRoll, DiceRollType } from '../../types';
import { ROLL_TYPE_LABELS } from '../../types';

interface DiceTabProps {
  guildId: string;
  campaignId: number;
  isGm: boolean;
  currentUserId: string;
  allowManualDiceRecording?: boolean;
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

const HISTORY_PREVIEW_COUNT = 5;

export default function DiceTab({ guildId, campaignId, isGm, currentUserId, allowManualDiceRecording = false }: DiceTabProps) {
  const qc = useQueryClient();

  // --- Roller state ---
  const [dicePool, setDicePool] = useState<Record<number, number>>({});
  const [modifier, setModifier] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [customExpr, setCustomExpr] = useState('');
  const [lastResult, setLastResult] = useState<DiceRoll | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedCharId, setSelectedCharId] = useState<number | null>(null);

  // --- Characters in this campaign owned by the current user ---
  const { data: allCharacters = [] } = useQuery<Character[]>({
    queryKey: ['characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
      );
      return res.data;
    },
    staleTime: 60_000,
  });
  const myCharacters = allCharacters.filter(
    (ch) => ch.owner_discord_user_id === currentUserId,
  );

  // Auto-select: pick the first character when characters load.
  useEffect(() => {
    if (myCharacters.length > 0 && selectedCharId === null) {
      setSelectedCharId(myCharacters[0].id);
    }
  }, [myCharacters.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedChar = myCharacters.find((ch) => ch.id === selectedCharId) ?? myCharacters[0] ?? null;

  // --- Manual roll state ---
  const [manualOpen, setManualOpen] = useState(false);
  const [manualExpr, setManualExpr] = useState('');
  const [manualTotal, setManualTotal] = useState('');
  const [manualType, setManualType] = useState<DiceRollType>('general');
  const [manualNote, setManualNote] = useState('');
  const [manualPrivate, setManualPrivate] = useState(false);

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
    mutationFn: async (payload: { expression: string; is_private: boolean; roll_type?: string; character_name?: string }) => {
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
    const charName = selectedChar?.name;
    const expr = customExpr.trim();
    if (expr) {
      rollMutation.mutate({ expression: expr, is_private: isPrivate, character_name: charName });
      return;
    }
    // Build expression from dice pool
    const parts = Object.entries(dicePool)
      .filter(([, cnt]) => cnt > 0)
      .sort(([a], [b]) => Number(b) - Number(a))
      .map(([sides, cnt]) => `${cnt}d${sides}`);
    if (parts.length === 0) return;
    const mod = modifier.trim();
    if (mod) {
      parts.push(mod.startsWith('+') || mod.startsWith('-') ? mod : `+${mod}`);
    }
    rollMutation.mutate({ expression: parts.join('+'), is_private: isPrivate, character_name: charName });
  };

  // --- Record manual roll mutation ---
  const recordMutation = useMutation({
    mutationFn: async (payload: {
      expression: string;
      total: number;
      roll_type: string;
      is_private: boolean;
      context_note?: string;
      character_name?: string;
    }) => {
      const res = await client.post<DiceRoll>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/dice/record`,
        payload,
      );
      return res.data;
    },
    onSuccess: (data) => {
      setLastResult(data);
      qc.invalidateQueries({ queryKey: ['dice-history', guildId, campaignId] });
      setManualExpr('');
      setManualTotal('');
      setManualType('general');
      setManualNote('');
      setManualPrivate(false);
      setManualOpen(false);
    },
  });

  const handleRecordManual = () => {
    const total = parseInt(manualTotal, 10);
    if (isNaN(total)) return;
    recordMutation.mutate({
      expression: manualExpr.trim() || `manual`,
      total,
      roll_type: manualType,
      is_private: manualPrivate,
      character_name: selectedChar?.name,
      ...(manualNote.trim() ? { context_note: manualNote.trim() } : {}),
    });
  };

  const handleReset = () => {
    setDicePool({});
    setModifier('');
    setIsPrivate(false);
    setCustomExpr('');
  };

  const previewHistory = history?.slice(0, HISTORY_PREVIEW_COUNT) ?? [];

  return (
    <Box>
      {/* ── Dice Roller ─────────────────────────────── */}
      <Stack spacing={1.5}>
        {/* Die selector buttons */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
            Add dice:
          </Typography>
          {DICE_OPTIONS.map((d) => {
            const count = dicePool[d.sides] ?? 0;
            const active = count > 0;
            return (
              <Badge
                key={d.sides}
                badgeContent={count || null}
                sx={{
                  '& .MuiBadge-badge': {
                    bgcolor: d.color,
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: '0.65rem',
                  },
                }}
              >
                <Button
                  variant={active ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => {
                    setDicePool((prev) => ({ ...prev, [d.sides]: (prev[d.sides] ?? 0) + 1 }));
                    setCustomExpr('');
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setDicePool((prev) => {
                      const curr = prev[d.sides] ?? 0;
                      if (curr <= 1) {
                        const next = { ...prev };
                        delete next[d.sides];
                        return next;
                      }
                      return { ...prev, [d.sides]: curr - 1 };
                    });
                  }}
                  sx={{
                    minWidth: { xs: 52, sm: 48 },
                    minHeight: { xs: 44, sm: 36 },
                    fontSize: { xs: '0.85rem', sm: '0.75rem' },
                    fontWeight: 700,
                    borderColor: d.color,
                    color: active ? '#fff' : d.color,
                    bgcolor: active ? d.color : 'transparent',
                    '&:hover': { bgcolor: d.color, color: '#fff' },
                  }}
                >
                  {d.label}
                </Button>
              </Badge>
            );
          })}
          <Typography variant="caption" color="text.disabled" sx={{ ml: 0.5, display: { xs: 'none', sm: 'inline' } }}>
            (right-click to remove one)
          </Typography>
        </Stack>

        {/* Active pool chips */}
        {Object.keys(dicePool).length > 0 && (
          <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="caption" color="text.secondary">Rolling:</Typography>
            {Object.entries(dicePool)
              .sort(([a], [b]) => Number(b) - Number(a))
              .map(([sides, count]) => (
                <Chip
                  key={sides}
                  label={`${count}d${sides}`}
                  size="small"
                  onDelete={() =>
                    setDicePool((prev) => {
                      const next = { ...prev };
                      delete next[Number(sides)];
                      return next;
                    })
                  }
                  sx={{
                    height: 22,
                    fontSize: '0.75rem',
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    bgcolor: DICE_OPTIONS.find((d) => d.sides === Number(sides))?.color + '33',
                    borderColor: DICE_OPTIONS.find((d) => d.sides === Number(sides))?.color + '88',
                    border: '1px solid',
                    color: DICE_OPTIONS.find((d) => d.sides === Number(sides))?.color,
                  }}
                />
              ))}
          </Stack>
        )}

        {/* Character selector — shown when user has >1 character in this campaign */}
        {myCharacters.length > 1 && (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="text.secondary">Rolling as:</Typography>
            <Select
              size="small"
              value={selectedCharId ?? ''}
              onChange={(e) => setSelectedCharId(Number(e.target.value))}
              sx={{ minWidth: 160, height: 32, fontSize: '0.8rem' }}
            >
              {myCharacters.map((ch) => (
                <MenuItem key={ch.id} value={ch.id}>{ch.name}</MenuItem>
              ))}
            </Select>
          </Stack>
        )}
        {myCharacters.length === 1 && (
          <Typography variant="caption" color="text.secondary">
            Rolling as <strong>{myCharacters[0].name}</strong>
          </Typography>
        )}

        {/* Controls row */}
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
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
              sx={{ minWidth: 40, minHeight: 40 }}
            >
              {isPrivate ? <LockIcon fontSize="small" /> : <LockOpenIcon fontSize="small" />}
            </IconButton>
          </Tooltip>

          <Button
            variant="contained"
            size="medium"
            startIcon={<CasinoIcon />}
            onClick={handleRoll}
            disabled={rollMutation.isPending || (Object.keys(dicePool).length === 0 && !customExpr.trim())}
            sx={{ minHeight: { xs: 44, sm: 36 }, minWidth: { xs: 100, sm: 'auto' } }}
          >
            {rollMutation.isPending ? 'Rolling…' : 'Roll'}
          </Button>

          <Tooltip title="Reset to defaults">
            <IconButton size="small" onClick={handleReset} sx={{ minWidth: 40, minHeight: 40 }}>
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

      {/* ── Manual Roll Recording ───────────────────── */}      {allowManualDiceRecording && (      <Box sx={{ mt: 1 }}>
        <Button
          size="small"
          variant="text"
          startIcon={<EditIcon />}
          onClick={() => setManualOpen(!manualOpen)}
          sx={{ textTransform: 'none', color: 'text.secondary' }}
        >
          {manualOpen ? 'Hide' : 'Record a physical roll'}
        </Button>
        <Collapse in={manualOpen}>
          <Box sx={{ mt: 1, p: 1.5, borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              Rolled physical dice? Record the result here so it shows up in the campaign log.
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <TextField
                size="small"
                label="What you rolled"
                value={manualExpr}
                onChange={(e) => setManualExpr(e.target.value)}
                placeholder="1d20+5"
                sx={{ width: 130 }}
              />
              <TextField
                size="small"
                label="Total *"
                type="number"
                value={manualTotal}
                onChange={(e) => setManualTotal(e.target.value)}
                placeholder="18"
                sx={{ width: 80 }}
                required
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && manualTotal.trim()) handleRecordManual();
                }}
              />
              <Select
                size="small"
                value={manualType}
                onChange={(e) => setManualType(e.target.value as DiceRollType)}
                sx={{ minWidth: 120, height: 40 }}
              >
                {Object.entries(ROLL_TYPE_LABELS).map(([value, label]) => (
                  <MenuItem key={value} value={value}>{label}</MenuItem>
                ))}
              </Select>
              <TextField
                size="small"
                label="Note"
                value={manualNote}
                onChange={(e) => setManualNote(e.target.value)}
                placeholder="STR save vs DC 15"
                sx={{ width: 160 }}
              />
              <Tooltip title={manualPrivate ? 'Private — only you and GM see this' : 'Public — everyone sees this'}>
                <IconButton
                  size="small"
                  onClick={() => setManualPrivate(!manualPrivate)}
                  color={manualPrivate ? 'warning' : 'default'}
                >
                  {manualPrivate ? <LockIcon fontSize="small" /> : <LockOpenIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
              <Button
                variant="outlined"
                size="small"
                onClick={handleRecordManual}
                disabled={!manualTotal.trim() || recordMutation.isPending}
              >
                {recordMutation.isPending ? 'Saving…' : 'Record'}
              </Button>
            </Stack>
            {recordMutation.isError && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {(recordMutation.error as Error)?.message ?? 'Failed to record roll'}
              </Typography>
            )}
          </Box>
        </Collapse>
      </Box>
      )}

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

/** Match the first NdN die in an expression to a DICE_OPTIONS color. */
function getDieColor(expression: string): string | undefined {
  const match = expression.match(/d(\d+)/i);
  if (!match) return undefined;
  const sides = parseInt(match[1], 10);
  return DICE_OPTIONS.find((d) => d.sides === sides)?.color;
}

/** A single row in the roll history list. */
function RollHistoryRow({ roll, currentUserId }: { roll: DiceRoll; currentUserId: string }) {
  const isOwn = roll.roller_discord_user_id === currentUserId;
  const exprColor = getDieColor(roll.expression);

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

      <Box sx={{ minWidth: 80, maxWidth: 140, flexShrink: 0 }}>
        <Typography variant="body2" fontWeight={500} noWrap>
          {roll.roller_display_name}
        </Typography>
        {roll.character_name && (
          <Typography variant="caption" color="text.disabled" noWrap sx={{ display: 'block', lineHeight: 1.1 }}>
            as {roll.character_name}
          </Typography>
        )}
      </Box>

      <Chip
        label={ROLL_TYPE_LABELS[roll.roll_type] ?? roll.roll_type}
        size="small"
        variant="outlined"
        sx={{ height: 18, fontSize: '0.6rem', flexShrink: 0 }}
      />

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Chip
          label={roll.expression}
          size="small"
          sx={{
            height: 22,
            fontSize: '0.72rem',
            fontWeight: 700,
            fontFamily: 'monospace',
            bgcolor: exprColor ? `${exprColor}22` : 'action.hover',
            color: exprColor ?? 'text.secondary',
            border: '1px solid',
            borderColor: exprColor ? `${exprColor}66` : 'divider',
          }}
        />
      </Box>

      <Typography variant="body2" fontWeight={700} sx={{ minWidth: 36, textAlign: 'right' }}>
        {roll.total}
      </Typography>

      {roll.individual_rolls?.[0]?.manual && (
        <Tooltip title="Manually recorded roll">
          <Chip
            label="✋"
            size="small"
            sx={{ height: 18, fontSize: '0.65rem', px: 0.3, minWidth: 'auto' }}
          />
        </Tooltip>
      )}

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
