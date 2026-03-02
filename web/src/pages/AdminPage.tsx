import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface GrugUser {
  discord_user_id: string;
  can_invite: boolean;
  is_super_admin: boolean;
  created_at: string;
}

/* ------------------------------------------------------------------ */
/* Header style matching guild pages                                   */
/* ------------------------------------------------------------------ */

const HEADER_SX = {
  fontWeight: 700,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.06em',
  color: 'text.secondary',
};

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function AdminPage() {
  const { data: me } = useAuth();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [newUserId, setNewUserId] = useState('');

  /* ---- Data ---- */
  const { data: users, isLoading } = useQuery<GrugUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const res = await client.get<GrugUser[]>('/api/admin/users');
      return res.data;
    },
    enabled: !!me?.is_super_admin,
  });

  /* ---- Toggle can_invite ---- */
  const toggleMutation = useMutation({
    mutationFn: async ({ id, canInvite }: { id: string; canInvite: boolean }) => {
      await client.patch(`/api/admin/users/${id}`, { can_invite: canInvite });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  /* ---- Delete user ---- */
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/api/admin/users/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  /* ---- Add user (upsert via PATCH) ---- */
  const addMutation = useMutation({
    mutationFn: async () => {
      await client.patch(`/api/admin/users/${newUserId.trim()}`, { can_invite: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setNewUserId('');
      setAddOpen(false);
    },
  });

  if (!me?.is_super_admin) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
        <Typography color="error">Access denied — super-admin only.</Typography>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          Admin — User Management
        </Typography>
        <Button
          variant="contained"
          size="small"
          startIcon={<PersonAddIcon />}
          onClick={() => setAddOpen(true)}
        >
          Add User
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Manage which Discord users can invite Grug to new servers. Super-admins are configured via
        the <code>GRUG_SUPER_ADMIN_IDS</code> environment variable.
      </Typography>

      {!users || users.length === 0 ? (
        <Typography color="text.secondary">No managed users yet.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Discord User ID', 'Status', 'Can Invite', 'Added', ''].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.discord_user_id} hover>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{u.discord_user_id}</TableCell>
                  <TableCell>
                    {u.is_super_admin ? (
                      <Chip label="Super-Admin" color="warning" size="small" />
                    ) : (
                      <Chip label="User" size="small" variant="outlined" />
                    )}
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={u.can_invite}
                      onChange={(_, checked) =>
                        toggleMutation.mutate({ id: u.discord_user_id, canInvite: checked })
                      }
                      disabled={toggleMutation.isPending}
                    />
                  </TableCell>
                  <TableCell>{new Date(u.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    {!u.is_super_admin && (
                      <Tooltip title="Remove user">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => deleteMutation.mutate(u.discord_user_id)}
                          disabled={deleteMutation.isPending}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ── Add User dialog ── */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Add User</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Discord User ID"
            placeholder="e.g. 123456789012345678"
            value={newUserId}
            onChange={(e) => setNewUserId(e.target.value)}
            sx={{ mt: 1 }}
            helperText="The user's Discord snowflake ID. They will be granted the can-invite permission."
          />
          {addMutation.isError && (
            <Typography color="error" variant="body2" sx={{ mt: 1 }}>
              Failed to add user — check the ID and try again.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => addMutation.mutate()}
            disabled={!newUserId.trim() || addMutation.isPending}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
