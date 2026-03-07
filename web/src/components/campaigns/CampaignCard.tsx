import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Skeleton, Stack, Tab, Tabs, TextField, Tooltip, Typography } from '@mui/material';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import BoltIcon from '@mui/icons-material/Bolt';
import CasinoIcon from '@mui/icons-material/Casino';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import EventIcon from '@mui/icons-material/Event';
import FolderIcon from '@mui/icons-material/Folder';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PeopleIcon from '@mui/icons-material/People';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import TuneIcon from '@mui/icons-material/Tune';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import { SYSTEM_LABELS } from '../../constants/character';
import CharacterTable from './CharacterTable';
import CampaignDocumentsTab from './CampaignDocumentsTab';
import CampaignScheduleTab from './CampaignScheduleTab';
import DiceTab from './DiceTab';
import GoldLedgerDialog from './GoldLedgerDialog';
import InitiativePanel from './InitiativePanel';
import PassiveCheckPanel from './PassiveCheckPanel';
import SessionNotesTab from './SessionNotesTab';
import type { Campaign, DiscordChannel, GuildMember } from '../../types';

interface CampaignCardProps {
  campaign: Campaign;
  channels: DiscordChannel[];
  isAdmin: boolean;
  currentUserId: string;
  allCampaigns: Campaign[];
  timezone: string;
  onEdit: (c: Campaign) => void;
  onDelete: (c: Campaign) => void;
  /** When true, hides the "open in own page" icon button (used on the detail page itself). */
  hideOpenInPage?: boolean;
}

/** A compact header Chip showing the campaign's Game Master. */
function GmChip({ guildId, userId }: { guildId: string; userId: string }) {
  const { data, isLoading } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => {
      const res = await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (isLoading) {
    return <Skeleton variant="rounded" width={80} height={20} />;
  }

  const label = data?.display_name ?? userId;
  const avatarSrc = data?.avatar_url ?? undefined;
  const initials = (data?.display_name ?? userId)[0]?.toUpperCase();

  return (
    <Tooltip title="Game Master" placement="top">
      <Chip
        size="small"
        variant="outlined"
        label={label}
        avatar={
          <Avatar src={avatarSrc} sx={{ bgcolor: 'primary.main', fontSize: '0.55rem' }}>
            {initials}
          </Avatar>
        }
        sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
      />
    </Tooltip>
  );
}

/** Renders a single campaign card with its header bar and always-visible character table. */
export default function CampaignCard({
  campaign,
  channels,
  isAdmin,
  currentUserId,
  allCampaigns,
  timezone,
  onEdit,
  onDelete,
  hideOpenInPage = false,
}: CampaignCardProps) {
  const c = campaign;
  const navigate = useNavigate();
  const channelName = channels.find((ch) => ch.id === c.channel_id)?.name;
  const isActualGm = c.gm_discord_user_id === currentUserId;

  // Admin GM-mode toggle — lets admins opt-in to GM controls per campaign
  // so they can play as a regular player by default without spoilers.
  const [gmModeEnabled, setGmModeEnabled] = useState(() =>
    localStorage.getItem(`gm-mode-${c.id}`) === 'true',
  );
  const isGm = isActualGm || (isAdmin && gmModeEnabled);
  const canManagePartyGold = isGm;

  const qc = useQueryClient();
  const [partyGoldOpen, setPartyGoldOpen] = useState(false);
  const [partyGoldAmount, setPartyGoldAmount] = useState('');
  const [partyGoldReason, setPartyGoldReason] = useState('');
  const [activeTab, setActiveTab] = useState<'characters' | 'notes' | 'documents' | 'schedule' | 'dice' | 'initiative'>('characters');
  const [ledgerOpen, setLedgerOpen] = useState(false);
  const [goldMenuAnchor, setGoldMenuAnchor] = useState<HTMLElement | null>(null);
  const [passiveCheckOpen, setPassiveCheckOpen] = useState(false);

  const adjustPartyGoldMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${c.guild_id}/campaigns/${c.id}/gold/party`, {
        amount: parseFloat(partyGoldAmount),
        reason: partyGoldReason || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns', c.guild_id] });
      setPartyGoldOpen(false);
      setPartyGoldAmount('');
      setPartyGoldReason('');
    },
  });

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        opacity: c.is_active ? 1 : 0.55,
        transition: 'opacity 0.15s',
      }}
    >
      {/* Campaign header bar */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{
          px: { xs: 1.5, sm: 2 },
          py: 1,
          bgcolor: 'action.hover',
          borderBottom: '1px solid',
          borderColor: 'divider',
          minHeight: 44,
          flexWrap: 'wrap',
          gap: 0.5,
        }}
      >
        <Typography variant="body2" fontWeight={600} noWrap sx={{ flex: '0 1 auto' }}>
          {c.name}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Game system" placement="top">
          <Chip
            label={SYSTEM_LABELS[c.system] ?? c.system}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
          />
        </Tooltip>
        {channelName && (
          <Tooltip title="Linked Discord channel" placement="top">
            <Chip
              label={`#${channelName}`}
              size="small"
              variant="outlined"
              sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0, opacity: 0.5, display: { xs: 'none', sm: 'inline-flex' } }}
            />
          </Tooltip>
        )}
        {c.gm_discord_user_id && (
          <GmChip guildId={c.guild_id} userId={c.gm_discord_user_id} />
        )}
        {c.banking_enabled && (
          <Tooltip
            title={`Party gold pool${c.player_banking_enabled ? ' · Players can transact' : ''}${canManagePartyGold ? ' · Click for options' : ' · Click to view ledger'}`}
            placement="top"
          >
            <Chip
              size="small"
              variant="outlined"
              icon={<MonetizationOnIcon sx={{ fontSize: '13px !important', color: 'warning.main !important' }} />}
              label={`${c.party_gold.toLocaleString(undefined, { maximumFractionDigits: 4 })} gp`}
              onClick={canManagePartyGold
                ? (e) => setGoldMenuAnchor(e.currentTarget)
                : () => setLedgerOpen(true)
              }
              sx={{
                height: 20,
                fontSize: '0.7rem',
                flexShrink: 0,
                color: 'warning.main',
                borderColor: 'warning.main',
                cursor: 'pointer',
              }}
            />
          </Tooltip>
        )}
        <Menu
          anchorEl={goldMenuAnchor}
          open={Boolean(goldMenuAnchor)}
          onClose={() => setGoldMenuAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem dense onClick={() => { setGoldMenuAnchor(null); setPartyGoldOpen(true); }}>
            <ListItemIcon><TuneIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Adjust party gold</ListItemText>
          </MenuItem>
          <MenuItem dense onClick={() => { setGoldMenuAnchor(null); setLedgerOpen(true); }}>
            <ListItemIcon><ReceiptLongIcon fontSize="small" /></ListItemIcon>
            <ListItemText>View ledger</ListItemText>
          </MenuItem>
        </Menu>
        <Tooltip title={c.is_active ? 'Campaign is active' : 'Campaign is inactive'} placement="top">
          <Chip
            label={c.is_active ? 'Active' : 'Inactive'}
            size="small"
            color={c.is_active ? 'success' : 'default'}
            sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
          />
        </Tooltip>
        {isAdmin && !isActualGm && (
          <Tooltip title={gmModeEnabled ? 'Disable GM mode' : 'Enable GM mode — show GM controls'} placement="top">
            <Chip
              label="GM Mode"
              size="small"
              icon={<AdminPanelSettingsIcon sx={{ fontSize: '13px !important' }} />}
              color={gmModeEnabled ? 'primary' : 'default'}
              variant={gmModeEnabled ? 'filled' : 'outlined'}
              onClick={() => {
                const next = !gmModeEnabled;
                setGmModeEnabled(next);
                localStorage.setItem(`gm-mode-${c.id}`, String(next));
              }}
              sx={{ height: 20, fontSize: '0.7rem', cursor: 'pointer', flexShrink: 0 }}
            />
          </Tooltip>
        )}
        {isGm && (
          <Tooltip title="Edit campaign">
            <IconButton size="small" onClick={() => onEdit(c)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {isAdmin && (
          <Tooltip title="Delete campaign">
            <IconButton size="small" color="error" onClick={() => onDelete(c)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {!hideOpenInPage && (
          <Tooltip title="Open campaign in own page">
            <IconButton
              size="small"
              onClick={() => navigate(`/guilds/${c.guild_id}/campaigns/${c.id}`)}
            >
              <OpenInNewIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {/* Tab bar */}
      <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', px: { xs: 1, sm: 2 } }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          textColor="inherit"
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          TabIndicatorProps={{ style: { height: 2 } }}
          sx={{ minHeight: 36 }}
        >
          <Tab
            value="characters"
            label="Characters"
            icon={<PeopleIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
          <Tab
            value="notes"
            label="Session Notes"
            icon={<MenuBookIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
          <Tab
            value="documents"
            label="Documents"
            icon={<FolderIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
          <Tab
            value="schedule"
            label="Schedule"
            icon={<EventIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
          <Tab
            value="dice"
            label="Dice"
            icon={<CasinoIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
          <Tab
            value="initiative"
            label="Initiative"
            icon={<BoltIcon sx={{ fontSize: 14 }} />}
            iconPosition="start"
            sx={{ minHeight: 36, py: 0, fontSize: '0.75rem', textTransform: 'none' }}
          />
        </Tabs>
      </Box>

      {/* Tab panels */}
      <Box sx={{ px: { xs: 1, sm: 2 }, py: 1.5 }}>
        {activeTab === 'characters' && (
          <>
            <CharacterTable
              guildId={c.guild_id}
              campaignId={c.id}
              campaignSystem={c.system}
              isAdmin={isAdmin}
              isGm={isGm}
              currentUserId={currentUserId}
              allCampaigns={allCampaigns}
              bankingEnabled={c.banking_enabled}
              playerBankingEnabled={c.player_banking_enabled}
              partyGold={c.party_gold}
            />
            {isGm && (
              <Box sx={{ mt: 2 }}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<VisibilityIcon />}
                  onClick={() => setPassiveCheckOpen((prev) => !prev)}
                  sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                >
                  {passiveCheckOpen ? 'Hide Passive Check' : 'Passive Check'}
                </Button>
                {passiveCheckOpen && (
                  <Box sx={{ mt: 1 }}>
                    <PassiveCheckPanel guildId={c.guild_id} campaignId={c.id} />
                  </Box>
                )}
              </Box>
            )}
          </>
        )}
        {activeTab === 'notes' && (
          <SessionNotesTab
            guildId={c.guild_id}
            campaignId={c.id}
            isAdmin={isAdmin}
            isGm={isGm}
            currentUserId={currentUserId}
          />
        )}
        {activeTab === 'documents' && (
          <CampaignDocumentsTab
            guildId={c.guild_id}
            campaignId={c.id}
            isGm={isGm}
            isAdmin={isAdmin}
          />
        )}
        {activeTab === 'schedule' && (
          <CampaignScheduleTab
            guildId={c.guild_id}
            campaignId={c.id}
            campaignName={c.name}
            scheduleMode={c.schedule_mode ?? 'fixed'}
            isGm={isGm}
            currentUserId={currentUserId}
            timezone={timezone}
            channels={channels}
            campaignChannelId={c.channel_id ?? null}
          />
        )}
        {activeTab === 'dice' && (
          <DiceTab
            guildId={c.guild_id}
            campaignId={c.id}
            isGm={isGm}
            currentUserId={currentUserId}
            allowManualDiceRecording={c.allow_manual_dice_recording ?? false}
          />
        )}
        {activeTab === 'initiative' && (
          <InitiativePanel
            guildId={c.guild_id}
            campaignId={c.id}
            isGm={isGm}
            depth={c.combat_tracker_depth ?? 'standard'}
            currentUserId={currentUserId}
          />
        )}
      </Box>

      {/* Party gold adjust dialog */}
      <Dialog open={partyGoldOpen} onClose={() => setPartyGoldOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ pb: 0.5 }}>
          Adjust Party Gold
          <Typography variant="body2" color="text.secondary" component="div">
            Current balance: <strong>{c.party_gold.toLocaleString(undefined, { maximumFractionDigits: 4 })} gp</strong>
          </Typography>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <TextField
              label="Amount"
              size="small"
              type="number"
              value={partyGoldAmount}
              onChange={(e) => setPartyGoldAmount(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && partyGoldAmount && !isNaN(parseFloat(partyGoldAmount)) && !adjustPartyGoldMutation.isPending)
                  adjustPartyGoldMutation.mutate();
              }}
              helperText="Use a negative number to remove gold"
              fullWidth
              autoFocus
            />
            <TextField
              label="Reason (optional)"
              size="small"
              value={partyGoldReason}
              onChange={(e) => setPartyGoldReason(e.target.value)}
              fullWidth
            />
            {adjustPartyGoldMutation.isError && (
              <Typography variant="caption" color="error">
                {(adjustPartyGoldMutation.error as Error)?.message ?? 'Failed to adjust gold.'}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setPartyGoldOpen(false)}>Cancel</Button>
          <Button
            size="small"
            variant="contained"
            disabled={
              !partyGoldAmount ||
              isNaN(parseFloat(partyGoldAmount)) ||
              adjustPartyGoldMutation.isPending
            }
            onClick={() => adjustPartyGoldMutation.mutate()}
          >
            {adjustPartyGoldMutation.isPending ? 'Adjusting…' : 'Adjust'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Gold ledger dialog */}
      <GoldLedgerDialog
        open={ledgerOpen}
        onClose={() => setLedgerOpen(false)}
        guildId={c.guild_id}
        campaignId={c.id}
        campaignName={c.name}
      />
    </Box>
  );
}
