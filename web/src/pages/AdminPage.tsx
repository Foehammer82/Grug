import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
  Autocomplete,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Link,
  Skeleton,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DnsIcon from '@mui/icons-material/Dns';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import LockIcon from '@mui/icons-material/Lock';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import SupervisorAccountIcon from '@mui/icons-material/SupervisorAccount';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import LLMUsageSection from '../components/LLMUsageSection';
import GuildAvatar from '../components/GuildAvatar';
import { useNavigate } from 'react-router-dom';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface GrugUser {
  discord_user_id: string;
  can_invite: boolean;
  is_super_admin: boolean;
  is_env_super_admin: boolean;
  created_at: string;
}

interface AdminGuild {
  guild_id: string;
  name: string;
  icon: string | null;
  member_count: number | null;
  total_campaigns: number;
  active_campaigns: number;
  total_messages: number;
  joined_at: string;
}

interface DiscordUser {
  discord_user_id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  profile_url: string;
}

interface DiscordMember {
  discord_user_id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
}

/* ------------------------------------------------------------------ */
/* Discord user cell — resolves ID to avatar + name + profile link     */
/* ------------------------------------------------------------------ */

function DiscordUserCell({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery<DiscordUser>({
    queryKey: ['discord-user', id],
    queryFn: async () => {
      const res = await client.get<DiscordUser>(`/api/discord/users/${id}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (isLoading) {
    return (
      <Stack direction="row" alignItems="center" spacing={1}>
        <Skeleton variant="circular" width={28} height={28} />
        <Box>
          <Skeleton width={90} height={14} />
          <Skeleton width={130} height={12} sx={{ mt: 0.3 }} />
        </Box>
      </Stack>
    );
  }

  if (isError || !data) {
    return <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{id}</Typography>;
  }

  return (
    <Stack direction="row" alignItems="center" spacing={1}>
      <Avatar
        src={data.avatar_url ?? undefined}
        alt={data.username}
        sx={{ width: 28, height: 28, fontSize: '0.75rem' }}
      >
        {data.username[0].toUpperCase()}
      </Avatar>
      <Box>
        <Link
          href={data.profile_url}
          target="_blank"
          rel="noopener noreferrer"
          variant="body2"
          underline="hover"
          color="text.primary"
          fontWeight={500}
        >
          {data.display_name}
        </Link>
        <Typography variant="caption" color="text.secondary" display="block">
          @{data.username} · {id}
        </Typography>
      </Box>
    </Stack>
  );
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
  const navigate = useNavigate();
  const [addOpen, setAddOpen] = useState(false);
  const [tab, setTab] = useState(0);
  const [newUserId, setNewUserId] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedMember, setSelectedMember] = useState<DiscordMember | null>(null);
  const [leaveGuildId, setLeaveGuildId] = useState<string | null>(null);
  const [leaveGuildName, setLeaveGuildName] = useState<string>('');

  /* ---- Debounce search input 400 ms ---- */
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchInput), 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  /* ---- Reset dialog state on close ---- */
  const handleClose = () => {
    setAddOpen(false);
    setNewUserId('');
    setSearchInput('');
    setDebouncedSearch('');
    setSelectedMember(null);
  };

  /* ---- Data ---- */
  const { data: users, isLoading } = useQuery<GrugUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const res = await client.get<GrugUser[]>('/api/admin/users');
      return res.data;
    },
    enabled: !!me?.is_super_admin,
  });

  /* ---- Member search ---- */
  const { data: searchResults, isFetching: searchFetching } = useQuery<DiscordMember[]>({
    queryKey: ['member-search', debouncedSearch],
    queryFn: async () => {
      if (!debouncedSearch.trim()) return [];
      const res = await client.get<DiscordMember[]>('/api/admin/users/search', {
        params: { q: debouncedSearch.trim() },
      });
      return res.data;
    },
    enabled: !!me?.is_super_admin && debouncedSearch.trim().length > 0,
    staleTime: 30_000,
  });

  /* ---- Toggle can_invite ---- */
  const toggleMutation = useMutation({
    mutationFn: async ({ id, canInvite }: { id: string; canInvite: boolean }) => {
      await client.patch(`/api/admin/users/${id}`, { can_invite: canInvite });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  /* ---- Toggle is_super_admin ---- */
  const toggleSuperAdminMutation = useMutation({
    mutationFn: async ({ id, isSuperAdmin }: { id: string; isSuperAdmin: boolean }) => {
      await client.patch(`/api/admin/users/${id}`, { is_super_admin: isSuperAdmin });
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
      const id = (selectedMember?.discord_user_id ?? newUserId).trim();
      await client.patch(`/api/admin/users/${id}`, { can_invite: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      handleClose();
    },
  });

  /* ---- Impersonate user ---- */
  const impersonateMutation = useMutation({
    mutationFn: async (id: string) => {
      await client.post(`/api/admin/impersonate/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries();
      navigate('/dashboard');
    },
  });

  /* ---- Admin guilds list ---- */
  const { data: adminGuilds, isLoading: guildsLoading } = useQuery<AdminGuild[]>({
    queryKey: ['admin-guilds'],
    queryFn: async () => {
      const res = await client.get<AdminGuild[]>('/api/admin/guilds');
      return res.data;
    },
    enabled: !!me?.is_super_admin && tab === 2,
  });

  /* ---- Leave guild ---- */
  const leaveGuildMutation = useMutation({
    mutationFn: async (guildId: string) => {
      await client.delete(`/api/admin/guilds/${guildId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-guilds'] });
      setLeaveGuildId(null);
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
    <Box sx={{ p: { xs: 2, sm: 4 }, maxWidth: 900, mx: 'auto' }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        Admin
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v as number)}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="User Management" />
        <Tab label="LLM Usage & Costs" />
        <Tab label="Servers" icon={<DnsIcon fontSize="small" />} iconPosition="start" />
      </Tabs>

      {/* ── Tab 0: User Management ── */}
      {tab === 0 && (
        <>
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" spacing={1} sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Manage Discord users and their privileges. Super-admin can be granted here or set via
              the <code>GRUG_SUPER_ADMIN_IDS</code> environment variable (env-locked).
            </Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<PersonAddIcon />}
              onClick={() => setAddOpen(true)}
              sx={{ flexShrink: 0, alignSelf: { xs: 'flex-end', sm: 'center' } }}
            >
              Add User
            </Button>
          </Stack>

          {!users || users.length === 0 ? (
        <Typography color="text.secondary">No managed users yet.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {['User', 'Super Admin', 'Can Invite', 'Added', ''].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.discord_user_id} hover>
                  <TableCell sx={{ minWidth: 220 }}>
                    <DiscordUserCell id={u.discord_user_id} />
                  </TableCell>
                  <TableCell>
                    {u.is_env_super_admin ? (
                      <Tooltip title="Set via GRUG_SUPER_ADMIN_IDS env var — cannot be changed here">
                        <Stack direction="row" alignItems="center" spacing={0.5}>
                          <Switch size="small" checked disabled />
                          <LockIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                        </Stack>
                      </Tooltip>
                    ) : (
                      <Switch
                        size="small"
                        checked={u.is_super_admin}
                        onChange={(_, checked) =>
                          toggleSuperAdminMutation.mutate({ id: u.discord_user_id, isSuperAdmin: checked })
                        }
                        disabled={toggleSuperAdminMutation.isPending}
                      />
                    )}
                    {u.is_env_super_admin && (
                      <Chip label="Env" color="warning" size="small" sx={{ ml: 0.5, height: 16, fontSize: '0.65rem' }} />
                    )}
                  </TableCell>
                  <TableCell>
                    {u.is_super_admin ? (
                      <Tooltip title="Super admins can always invite">
                        <Typography variant="caption" color="text.disabled">—</Typography>
                      </Tooltip>
                    ) : (
                      <Switch
                        size="small"
                        checked={u.can_invite}
                        onChange={(_, checked) =>
                          toggleMutation.mutate({ id: u.discord_user_id, canInvite: checked })
                        }
                        disabled={toggleMutation.isPending}
                      />
                    )}
                  </TableCell>
                  <TableCell>{new Date(u.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {u.discord_user_id !== me?.id && (
                        <Tooltip title="Impersonate user">
                          <IconButton
                            size="small"
                            onClick={() => impersonateMutation.mutate(u.discord_user_id)}
                            disabled={impersonateMutation.isPending}
                          >
                            <SupervisorAccountIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                      {!u.is_env_super_admin && (
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
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ── Add User dialog ── */}
      <Dialog open={addOpen} onClose={handleClose} maxWidth="xs" fullWidth>
        <DialogTitle>Add User</DialogTitle>
        <DialogContent>
          <Autocomplete<DiscordMember, false, false, true>
            freeSolo
            fullWidth
            options={searchResults ?? []}
            loading={searchFetching}
            inputValue={searchInput}
            value={selectedMember}
            onInputChange={(_, value, reason) => {
              setSearchInput(value);
              if (reason === 'input') {
                // Typed freely — clear selection and treat as manual ID
                setSelectedMember(null);
                setNewUserId(value);
              }
            }}
            onChange={(_, value) => {
              if (value && typeof value === 'object') {
                setSelectedMember(value);
                setNewUserId(value.discord_user_id);
                setSearchInput(`${value.display_name} (${value.username})`);
              } else if (typeof value === 'string') {
                setSelectedMember(null);
                setNewUserId(value);
              } else {
                setSelectedMember(null);
                setNewUserId('');
              }
            }}
            getOptionLabel={(opt) =>
              typeof opt === 'string' ? opt : `${opt.display_name} (${opt.username})`
            }
            isOptionEqualToValue={(a, b) =>
              typeof a !== 'string' && typeof b !== 'string'
                ? a.discord_user_id === b.discord_user_id
                : false
            }
            filterOptions={(opts) => opts}
            renderOption={(props, opt) => (
              typeof opt === 'string' ? (
                <Box component="li" {...props} key={opt}>{opt}</Box>
              ) : (
                <Box component="li" {...props} key={opt.discord_user_id}
                  sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}
                >
                  <Avatar
                    src={opt.avatar_url ?? undefined}
                    alt={opt.username}
                    sx={{ width: 28, height: 28, fontSize: '0.75rem' }}
                  >
                    {opt.username[0].toUpperCase()}
                  </Avatar>
                  <Box>
                    <Typography variant="body2">{opt.display_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      @{opt.username} · {opt.discord_user_id}
                    </Typography>
                  </Box>
                </Box>
              )
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                autoFocus
                label="Search by name or paste User ID"
                placeholder="e.g. Gandalf or 123456789012345678"
                sx={{ mt: 1 }}
                helperText={
                  selectedMember
                    ? `ID: ${selectedMember.discord_user_id} — will be granted can-invite`
                    : 'Search for a member across joined servers, or paste a Discord snowflake ID directly.'
                }
                slotProps={{
                  input: {
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {searchFetching ? <CircularProgress size={16} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  },
                }}
              />
            )}
            sx={{ mt: 1 }}
            noOptionsText={
              debouncedSearch.trim().length > 0
                ? 'No members found — you can still paste a snowflake ID directly'
                : 'Start typing to search'
            }
          />
          {addMutation.isError && (
            <Typography color="error" variant="body2" sx={{ mt: 1 }}>
              Failed to add user — check the ID and try again.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => addMutation.mutate()}
            disabled={!newUserId.trim() || addMutation.isPending}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>
        </>
      )}

      {/* ── Tab 1: LLM Usage & Costs ── */}
      {tab === 1 && <LLMUsageSection />}

      {/* ── Tab 2: Servers ── */}
      {tab === 2 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            All Discord servers Grug has joined. Super-admins can remove Grug from any server.
          </Typography>

          {guildsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
              <CircularProgress />
            </Box>
          ) : !adminGuilds || adminGuilds.length === 0 ? (
            <Typography color="text.secondary">No servers found.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {['Server', 'Members', 'Campaigns', 'Active', 'Messages', 'Joined', 'Actions'].map((h) => (
                      <TableCell key={h} sx={HEADER_SX}>{h !== 'Actions' ? h : ''}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {adminGuilds.map((g) => (
                    <TableRow key={g.guild_id} hover>
                      <TableCell sx={{ minWidth: 220 }}>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <GuildAvatar guildId={g.guild_id} name={g.name} icon={g.icon} size={28} />
                          <Box>
                            <Typography variant="body2" fontWeight={500}>{g.name}</Typography>
                            <Typography variant="caption" color="text.secondary">{g.guild_id}</Typography>
                          </Box>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        {g.member_count != null ? g.member_count.toLocaleString() : '—'}
                      </TableCell>
                      <TableCell>{g.total_campaigns}</TableCell>
                      <TableCell>
                        <Chip
                          label={g.active_campaigns}
                          size="small"
                          color={g.active_campaigns > 0 ? 'success' : 'default'}
                          variant="outlined"
                          sx={{ height: 18, fontSize: '0.7rem' }}
                        />
                      </TableCell>
                      <TableCell>{g.total_messages.toLocaleString()}</TableCell>
                      <TableCell>{new Date(g.joined_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <Tooltip title="Remove Grug from this server">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => {
                              setLeaveGuildId(g.guild_id);
                              setLeaveGuildName(g.name);
                            }}
                          >
                            <ExitToAppIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Leave guild confirmation dialog */}
          <Dialog
            open={leaveGuildId !== null}
            onClose={() => setLeaveGuildId(null)}
            maxWidth="xs"
            fullWidth
          >
            <DialogTitle>Leave Server?</DialogTitle>
            <DialogContent>
              <Typography>
                Remove Grug from <strong>{leaveGuildName}</strong>? The bot will leave the server
                and all guild configuration will be deleted. This cannot be undone without re-inviting.
              </Typography>
              {leaveGuildMutation.isError && (
                <Typography color="error" variant="body2" sx={{ mt: 1 }}>
                  Failed to leave server — please try again.
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setLeaveGuildId(null)}>Cancel</Button>
              <Button
                variant="contained"
                color="error"
                onClick={() => leaveGuildId && leaveGuildMutation.mutate(leaveGuildId)}
                disabled={leaveGuildMutation.isPending}
              >
                Leave Server
              </Button>
            </DialogActions>
          </Dialog>
        </>
      )}
    </Box>
  );
}
