import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import client from '../../api/client';
import type { Character } from '../../types';

interface GoldManageDialogProps {
  open: boolean;
  onClose: () => void;
  guildId: string;
  campaignId: number;
  character: Character;
  /** True if the current user is an admin or the campaign GM. */
  isAdminOrGm: boolean;
  /** True if the campaign allows players to manage their own wallets. */
  playerBankingEnabled: boolean;
  partyGold: number;
}

/**
 * Dialog for managing a character's gold wallet.
 *
 * - Admin / GM: can directly add or remove any amount (Adjust tab) + transfer to/from party pool.
 * - Players: can always spend (deduct) their own gold and transfer to/from the party pool.
 *   `playerBankingEnabled` only gates positive self-adjustments (adding gold from nowhere),
 *   which are enforced on the backend and do not appear as a separate UI tab.
 */
export default function GoldManageDialog({
  open,
  onClose,
  guildId,
  campaignId,
  character,
  isAdminOrGm,
  playerBankingEnabled,
  partyGold,
}: GoldManageDialogProps) {
  const qc = useQueryClient();

  // ── Tab state ─────────────────────────────────────────────────────────
  // Players can always spend (deduct) their own gold and transfer to/from the party pool.
  // player_banking_enabled only gates positive self-adjustments (adding gold from nowhere),
  // which is enforced on the backend — no separate tab needed here.
  const canSpend = !isAdminOrGm;
  const canTransfer = true;
  // Admins/GMs see Adjust + Transfer; players always see Spend + Transfer
  const useTabs = true;
  type TabKey = 'adjust' | 'spend' | 'transfer';
  const defaultTab: TabKey = isAdminOrGm ? 'adjust' : 'spend';
  const [tab, setTab] = useState<TabKey>(defaultTab);

  // ── Adjust state (GM / admin) ─────────────────────────────────────────
  const [adjustDirection, setAdjustDirection] = useState<'add' | 'remove'>('add');
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');

  // ── Wallet state (players — direction determines sign sent to API) ─────
  // 'add' only available when playerBankingEnabled; otherwise locked to 'spend'.
  const [walletDirection, setWalletDirection] = useState<'add' | 'spend'>('spend');
  const [spendAmount, setSpendAmount] = useState('');
  const [spendReason, setSpendReason] = useState('');

  // ── Transfer state ────────────────────────────────────────────────────
  const [transferAmount, setTransferAmount] = useState('');
  const [transferDirection, setTransferDirection] = useState<'to_party' | 'from_party'>('to_party');
  const [transferReason, setTransferReason] = useState('');

  function resetAndClose() {
    setAdjustDirection('add');
    setAdjustAmount('');
    setAdjustReason('');
    setWalletDirection('spend');
    setSpendAmount('');
    setSpendReason('');
    setTransferAmount('');
    setTransferDirection('to_party');
    setTransferReason('');
    setTab(defaultTab);
    onClose();
  }

  // ── Mutations ─────────────────────────────────────────────────────────
  const adjustMutation = useMutation({
    mutationFn: async () => {
      const signed = adjustDirection === 'add' ? adjustAmountNum : -adjustAmountNum;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/gold/characters/${character.id}`,
        { amount: signed, reason: adjustReason || null },
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
      resetAndClose();
    },
  });

  // Player wallet mutation — direction determines sign.
  const spendMutation = useMutation({
    mutationFn: async () => {
      const signed = walletDirection === 'add' ? spendAmountNum : -spendAmountNum;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/gold/characters/${character.id}`,
        { amount: signed, reason: spendReason || null },
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
      resetAndClose();
    },
  });

  const transferMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/campaigns/${campaignId}/gold/transfer`, {
        from_character_id: transferDirection === 'to_party' ? character.id : null,
        to_character_id: transferDirection === 'from_party' ? character.id : null,
        amount: parseFloat(transferAmount),
        reason: transferReason || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-characters', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      resetAndClose();
    },
  });

  const currentGold = (character.gold ?? 0).toLocaleString(undefined, { maximumFractionDigits: 4 });
  const adjustAmountNum = parseFloat(adjustAmount);
  const spendAmountNum = parseFloat(spendAmount);
  const transferAmountNum = parseFloat(transferAmount);

  const fmtGp = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 4 }) + ' gp';

  // ── GM / Admin: Adjust panel ──────────────────────────────────────────
  const adjustPanel = (
    <Stack spacing={1.5}>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={adjustDirection}
        onChange={(_, v) => v && setAdjustDirection(v)}
        fullWidth
      >
        <ToggleButton
          value="add"
          sx={{ gap: 0.5, '&.Mui-selected': { color: 'success.main', borderColor: 'success.main', bgcolor: 'success.main' + '1A' } }}
        >
          <AddCircleOutlineIcon fontSize="small" /> Add
        </ToggleButton>
        <ToggleButton
          value="remove"
          sx={{ gap: 0.5, '&.Mui-selected': { color: 'error.main', borderColor: 'error.main', bgcolor: 'error.main' + '1A' } }}
        >
          <RemoveCircleOutlineIcon fontSize="small" /> Remove
        </ToggleButton>
      </ToggleButtonGroup>
      <TextField
        label="Amount (gp)"
        size="small"
        type="number"
        value={adjustAmount}
        onChange={(e) => setAdjustAmount(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && adjustAmount && !isNaN(adjustAmountNum) && adjustAmountNum > 0 && !adjustMutation.isPending)
            adjustMutation.mutate();
        }}
        helperText={adjustDirection === 'add' ? 'Will be credited to the wallet' : 'Will be deducted from the wallet'}
        inputProps={{ min: 0 }}
        fullWidth
        autoFocus={tab === 'adjust'}
      />
      <TextField
        label="Reason (optional)"
        size="small"
        value={adjustReason}
        onChange={(e) => setAdjustReason(e.target.value)}
        fullWidth
      />
      {adjustMutation.isError && (
        <Typography variant="caption" color="error">
          {(adjustMutation.error as Error)?.message ?? 'Failed to adjust gold.'}
        </Typography>
      )}
      <Button
        variant="contained"
        size="small"
        color={adjustDirection === 'add' ? 'success' : 'error'}
        disabled={!adjustAmount || isNaN(adjustAmountNum) || adjustAmountNum <= 0 || adjustMutation.isPending}
        onClick={() => adjustMutation.mutate()}
      >
        {adjustMutation.isPending
          ? (adjustDirection === 'add' ? 'Adding…' : 'Removing…')
          : (adjustDirection === 'add'
              ? `Add${adjustAmountNum > 0 ? ' ' + fmtGp(adjustAmountNum) : ''}`
              : `Remove${adjustAmountNum > 0 ? ' ' + fmtGp(adjustAmountNum) : ''}`)}
      </Button>
    </Stack>
  );

  // ── Player: Wallet panel ──────────────────────────────────────────────
  const spendPanel = (
    <Stack spacing={1.5}>
      {playerBankingEnabled && (
        <ToggleButtonGroup
          exclusive
          size="small"
          value={walletDirection}
          onChange={(_, v) => v && setWalletDirection(v)}
          fullWidth
        >
          <ToggleButton
            value="add"
            sx={{ gap: 0.5, '&.Mui-selected': { color: 'success.main', borderColor: 'success.main', bgcolor: 'success.main' + '1A' } }}
          >
            <AddCircleOutlineIcon fontSize="small" /> Receive
          </ToggleButton>
          <ToggleButton
            value="spend"
            sx={{ gap: 0.5, '&.Mui-selected': { color: 'warning.main', borderColor: 'warning.main', bgcolor: 'warning.main' + '1A' } }}
          >
            <RemoveCircleOutlineIcon fontSize="small" /> Spend
          </ToggleButton>
        </ToggleButtonGroup>
      )}
      <TextField
        label="Amount (gp)"
        size="small"
        type="number"
        value={spendAmount}
        onChange={(e) => setSpendAmount(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && spendAmount && !isNaN(spendAmountNum) && spendAmountNum > 0 && !spendMutation.isPending)
            spendMutation.mutate();
        }}
        helperText={walletDirection === 'add' ? 'Will be credited to your wallet' : 'Will be deducted from your wallet'}
        inputProps={{ min: 0 }}
        fullWidth
        autoFocus={tab === 'spend'}
      />
      <TextField
        label="Reason (optional)"
        size="small"
        value={spendReason}
        onChange={(e) => setSpendReason(e.target.value)}
        placeholder={walletDirection === 'add' ? 'e.g. Reward from the blacksmith' : 'e.g. Bought rations at the market'}
        fullWidth
      />
      {spendMutation.isError && (
        <Typography variant="caption" color="error">
          {(spendMutation.error as Error)?.message ?? 'Failed to update gold.'}
        </Typography>
      )}
      <Button
        variant="contained"
        size="small"
        color={walletDirection === 'add' ? 'success' : 'warning'}
        disabled={!spendAmount || isNaN(spendAmountNum) || spendAmountNum <= 0 || spendMutation.isPending}
        onClick={() => spendMutation.mutate()}
      >
        {spendMutation.isPending
          ? (walletDirection === 'add' ? 'Adding…' : 'Spending…')
          : (walletDirection === 'add'
              ? `Receive${spendAmountNum > 0 ? ' ' + fmtGp(spendAmountNum) : ''}`
              : `Spend${spendAmountNum > 0 ? ' ' + fmtGp(spendAmountNum) : ''}`)}
      </Button>
    </Stack>
  );

  const transferPanel = (
    <Stack spacing={1.5}>
      <Typography variant="caption" color="text.secondary">
        Party pool: <strong>{partyGold.toLocaleString(undefined, { maximumFractionDigits: 4 })} gp</strong>
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={transferDirection}
        onChange={(_, v) => v && setTransferDirection(v)}
        fullWidth
      >
        <ToggleButton value="to_party">↑ Deposit to pool</ToggleButton>
        <ToggleButton value="from_party">↓ Withdraw from pool</ToggleButton>
      </ToggleButtonGroup>
      <TextField
        label="Amount"
        size="small"
        type="number"
        value={transferAmount}
        onChange={(e) => setTransferAmount(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && transferAmount && !isNaN(transferAmountNum) && transferAmountNum > 0 && !transferMutation.isPending)
            transferMutation.mutate();
        }}
        helperText="Must be a positive amount"
        inputProps={{ min: 0 }}
        fullWidth
        autoFocus={tab === 'transfer'}
      />
      <TextField
        label="Reason (optional)"
        size="small"
        value={transferReason}
        onChange={(e) => setTransferReason(e.target.value)}
        fullWidth
      />
      {transferMutation.isError && (
        <Typography variant="caption" color="error">
          {(transferMutation.error as Error)?.message ?? 'Failed to transfer gold.'}
        </Typography>
      )}
      <Button
        variant="outlined"
        size="small"
        disabled={
          !transferAmount ||
          isNaN(transferAmountNum) ||
          transferAmountNum <= 0 ||
          transferMutation.isPending
        }
        onClick={() => transferMutation.mutate()}
      >
        {transferMutation.isPending ? 'Transferring…' : 'Transfer'}
      </Button>
    </Stack>
  );

  return (
    <Dialog open={open} onClose={resetAndClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        {character.name}&rsquo;s Gold
        <Typography variant="body2" color="text.secondary" component="div">
          Current balance: <strong>{currentGold} gp</strong>
        </Typography>
      </DialogTitle>

      {useTabs && (
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v as TabKey)}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          {isAdminOrGm && <Tab label="Adjust" value="adjust" />}
          {canSpend && <Tab label={playerBankingEnabled ? 'Wallet' : 'Spend'} value="spend" />}
          <Tab label="Transfer" value="transfer" />
        </Tabs>
      )}

      <DialogContent>
        <Box sx={{ mt: 1 }}>
          {tab === 'adjust' && isAdminOrGm && adjustPanel}
          {tab === 'spend' && canSpend && spendPanel}
          {tab === 'transfer' && transferPanel}
        </Box>
      </DialogContent>

      <DialogActions>
        <Button size="small" onClick={resetAndClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
