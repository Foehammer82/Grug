import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import client from '../../api/client';
import GuildMemberCell from './GuildMemberCell';
import type { Character, GoldTransaction } from '../../types';

interface GoldLedgerDialogProps {
  open: boolean;
  onClose: () => void;
  guildId: string;
  campaignId: number;
  campaignName: string;
}

export default function GoldLedgerDialog({
  open,
  onClose,
  guildId,
  campaignId,
  campaignName,
}: GoldLedgerDialogProps) {
  const { data: transactions = [], isLoading: ledgerLoading, isError } = useQuery<GoldTransaction[]>({
    queryKey: ['gold-ledger', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<GoldTransaction[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/gold/ledger?limit=200`,
      );
      return res.data;
    },
    enabled: open,
    staleTime: 10_000,
  });

  // Reuse the cached character list so names resolve without an extra fetch.
  const { data: characters = [] } = useQuery<Character[]>({
    queryKey: ['campaign-characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  const charById = Object.fromEntries(characters.map((c) => [c.id, c.name]));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Gold Ledger — {campaignName}
        <Typography variant="body2" color="text.secondary" component="div">
          Most recent 200 transactions, newest first
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ p: 0 }}>
        {ledgerLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : isError ? (
          <Typography variant="body2" color="error" sx={{ p: 3 }}>
            Failed to load ledger.
          </Typography>
        ) : transactions.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 3 }}>
            No transactions recorded yet.
          </Typography>
        ) : (
          <Table size="small" stickyHeader sx={{ '& td, & th': { borderColor: 'divider' } }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 140 }}>Date</TableCell>
                <TableCell sx={{ width: 90, textAlign: 'right' }}>Amount</TableCell>
                <TableCell sx={{ width: 120 }}>Target</TableCell>
                <TableCell sx={{ width: 150 }}>Actor</TableCell>
                <TableCell>Reason</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {transactions.map((tx) => {
                const isPositive = tx.amount >= 0;
                return (
                  <TableRow key={tx.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                        {new Date(tx.created_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontVariantNumeric: 'tabular-nums',
                          fontWeight: 600,
                          color: isPositive ? 'success.main' : 'error.main',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {isPositive ? '+' : ''}
                        {tx.amount.toLocaleString(undefined, { maximumFractionDigits: 4 })} gp
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {tx.character_id != null ? (
                        <Chip
                          label={charById[tx.character_id] ?? `#${tx.character_id}`}
                          size="small"
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.65rem' }}
                        />
                      ) : (
                        <Chip
                          label="Party pool"
                          size="small"
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.65rem', color: 'warning.main', borderColor: 'warning.main' }}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <GuildMemberCell
                        guildId={guildId}
                        userId={tx.actor_discord_user_id}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color={tx.reason ? 'text.primary' : 'text.disabled'}>
                        {tx.reason ?? '—'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </DialogContent>

      <DialogActions>
        <Button size="small" onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
