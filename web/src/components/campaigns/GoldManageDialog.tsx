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
 * - Admin / GM: can directly add or remove any amount from the wallet.
 * - Admin / GM / player (when playerBankingEnabled): can transfer between the wallet and the party pool.
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
  const canTransfer = isAdminOrGm || playerBankingEnabled;
  const useTabs = isAdminOrGm && canTransfer;
  const [tab, setTab] = useState<'adjust' | 'transfer'>(isAdminOrGm ? 'adjust' : 'transfer');

  // ── Adjust state ──────────────────────────────────────────────────────
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');

  // ── Transfer state ────────────────────────────────────────────────────
  const [transferAmount, setTransferAmount] = useState('');
  const [transferDirection, setTransferDirection] = useState<'to_party' | 'from_party'>('to_party');
  const [transferReason, setTransferReason] = useState('');

  function resetAndClose() {
    setAdjustAmount('');
    setAdjustReason('');
    setTransferAmount('');
    setTransferDirection('to_party');
    setTransferReason('');
    setTab(isAdminOrGm ? 'adjust' : 'transfer');
    onClose();
  }

  // ── Mutations ─────────────────────────────────────────────────────────
  const adjustMutation = useMutation({
    mutationFn: async () => {
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/gold/characters/${character.id}`,
        { amount: parseFloat(adjustAmount), reason: adjustReason || null },
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
  const transferAmountNum = parseFloat(transferAmount);

  const adjustPanel = (
    <Stack spacing={1.5}>
      <TextField
        label="Amount"
        size="small"
        type="number"
        value={adjustAmount}
        onChange={(e) => setAdjustAmount(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && adjustAmount && !isNaN(adjustAmountNum) && !adjustMutation.isPending)
            adjustMutation.mutate();
        }}
        helperText="Use a negative number to remove gold"
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
        disabled={!adjustAmount || isNaN(adjustAmountNum) || adjustMutation.isPending}
        onClick={() => adjustMutation.mutate()}
      >
        {adjustMutation.isPending ? 'Adjusting…' : 'Adjust'}
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
          onChange={(_, v) => setTab(v)}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Adjust" value="adjust" />
          <Tab label="Transfer" value="transfer" />
        </Tabs>
      )}

      <DialogContent>
        <Box sx={{ mt: 1 }}>
          {(!useTabs || tab === 'adjust') && isAdminOrGm && adjustPanel}
          {(!useTabs || tab === 'transfer') && canTransfer && transferPanel}
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
