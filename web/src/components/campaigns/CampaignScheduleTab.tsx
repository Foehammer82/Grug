import { useState } from 'react';
import {
  Avatar,
  Box,
  Button,
  ButtonGroup,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import CancelIcon from '@mui/icons-material/Cancel';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import RepeatIcon from '@mui/icons-material/Repeat';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import RRuleBuilder from '../RRuleBuilder';
import type { CalendarEvent, EventRSVP, GuildMember, RSVPStatus } from '../../types';

interface CampaignScheduleTabProps {
  guildId: string;
  campaignId: number;
  campaignName: string;
  isAdmin: boolean;
  currentUserId: string;
  timezone: string;
}

const RSVP_CONFIG: Record<RSVPStatus, { label: string; color: 'success' | 'warning' | 'error'; icon: typeof CheckCircleIcon }> = {
  attending: { label: 'Attending', color: 'success', icon: CheckCircleIcon },
  maybe: { label: 'Maybe', color: 'warning', icon: HelpOutlineIcon },
  declined: { label: 'Declined', color: 'error', icon: CancelIcon },
};

/** Display a guild member's avatar + name inline. */
function MemberBadge({ guildId, userId }: { guildId: string; userId: string }) {
  const { data, isLoading } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => (await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`)).data,
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (isLoading) return <Skeleton variant="circular" width={20} height={20} />;

  const name = data?.display_name ?? userId;
  const avatar = data?.avatar_url ?? undefined;

  return (
    <Tooltip title={name} placement="top">
      <Avatar src={avatar} sx={{ width: 22, height: 22, fontSize: '0.6rem', bgcolor: 'primary.main' }}>
        {name[0]?.toUpperCase()}
      </Avatar>
    </Tooltip>
  );
}

/** A single event card showing date, details, and RSVP controls. */
function SessionEventCard({
  event,
  guildId,
  currentUserId,
  timezone,
}: {
  event: CalendarEvent;
  guildId: string;
  currentUserId: string;
  timezone: string;
}) {
  const qc = useQueryClient();

  // Fetch RSVPs for this event
  const { data: rsvps, isLoading: rsvpsLoading } = useQuery<EventRSVP[]>({
    queryKey: ['event-rsvps', guildId, event.id],
    queryFn: async () => (await client.get<EventRSVP[]>(`/api/guilds/${guildId}/events/${event.id}/rsvps`)).data,
    staleTime: 30_000,
  });

  const rsvpMutation = useMutation({
    mutationFn: async (status: RSVPStatus) => {
      await client.put(`/api/guilds/${guildId}/events/${event.id}/rsvp`, { status });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['event-rsvps', guildId, event.id] });
    },
  });

  const removeRsvpMutation = useMutation({
    mutationFn: async () => {
      await client.delete(`/api/guilds/${guildId}/events/${event.id}/rsvp`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['event-rsvps', guildId, event.id] });
    },
  });

  const myRsvp = rsvps?.find((r) => r.discord_user_id === currentUserId);
  const attending = rsvps?.filter((r) => r.status === 'attending') ?? [];
  const maybe = rsvps?.filter((r) => r.status === 'maybe') ?? [];
  const declined = rsvps?.filter((r) => r.status === 'declined') ?? [];

  // Format the event date nicely
  const startDate = new Date(event.start_time);
  const dateStr = startDate.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    timeZone: timezone || undefined,
  });
  const timeStr = startDate.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: timezone || undefined,
  });

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 2,
        '&:hover': { borderColor: 'primary.main', transition: 'border-color 0.2s' },
      }}
    >
      <Stack direction="row" alignItems="flex-start" spacing={2}>
        {/* Date block */}
        <Box
          sx={{
            textAlign: 'center',
            minWidth: 56,
            p: 1,
            borderRadius: 1,
            bgcolor: 'action.hover',
            flexShrink: 0,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.6rem' }}>
            {startDate.toLocaleDateString(undefined, { month: 'short', timeZone: timezone || undefined })}
          </Typography>
          <Typography variant="h5" fontWeight={700} lineHeight={1.1}>
            {startDate.toLocaleDateString(undefined, { day: 'numeric', timeZone: timezone || undefined })}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
            {startDate.toLocaleDateString(undefined, { weekday: 'short', timeZone: timezone || undefined })}
          </Typography>
        </Box>

        {/* Details */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" fontWeight={600} noWrap>
            {event.title}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.25 }}>
            <CalendarTodayIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
            <Typography variant="caption" color="text.secondary">
              {dateStr} at {timeStr}
            </Typography>
            {event.rrule && (
              <Tooltip title={`Recurring: ${event.rrule}`}>
                <RepeatIcon sx={{ fontSize: 12, color: 'info.main' }} />
              </Tooltip>
            )}
          </Stack>
          {event.location && (
            <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
              <LocationOnIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                {event.location}
              </Typography>
            </Stack>
          )}
          {event.description && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontSize: '0.8rem' }}>
              {event.description}
            </Typography>
          )}

          {/* RSVP summary */}
          {!rsvpsLoading && rsvps && rsvps.length > 0 && (
            <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
              {attending.length > 0 && (
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
                  <Typography variant="caption" color="success.main" fontWeight={600}>
                    {attending.length}
                  </Typography>
                  <Stack direction="row" spacing={-0.5}>
                    {attending.slice(0, 5).map((r) => (
                      <MemberBadge key={r.discord_user_id} guildId={guildId} userId={r.discord_user_id} />
                    ))}
                    {attending.length > 5 && (
                      <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                        +{attending.length - 5}
                      </Typography>
                    )}
                  </Stack>
                </Stack>
              )}
              {maybe.length > 0 && (
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <HelpOutlineIcon sx={{ fontSize: 14, color: 'warning.main' }} />
                  <Typography variant="caption" color="warning.main" fontWeight={600}>
                    {maybe.length}
                  </Typography>
                </Stack>
              )}
              {declined.length > 0 && (
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <CancelIcon sx={{ fontSize: 14, color: 'error.main' }} />
                  <Typography variant="caption" color="error.main" fontWeight={600}>
                    {declined.length}
                  </Typography>
                </Stack>
              )}
            </Stack>
          )}
        </Box>

        {/* RSVP buttons */}
        <Box sx={{ flexShrink: 0 }}>
          <ButtonGroup size="small" variant="outlined" disabled={rsvpMutation.isPending}>
            {(Object.entries(RSVP_CONFIG) as [RSVPStatus, typeof RSVP_CONFIG.attending][]).map(([status, cfg]) => {
              const Icon = cfg.icon;
              const isSelected = myRsvp?.status === status;
              return (
                <Button
                  key={status}
                  color={cfg.color}
                  variant={isSelected ? 'contained' : 'outlined'}
                  onClick={() => {
                    if (isSelected) {
                      removeRsvpMutation.mutate();
                    } else {
                      rsvpMutation.mutate(status);
                    }
                  }}
                  sx={{ minWidth: 0, px: 1, fontSize: '0.65rem' }}
                  startIcon={<Icon sx={{ fontSize: '14px !important' }} />}
                >
                  {cfg.label}
                </Button>
              );
            })}
          </ButtonGroup>
        </Box>
      </Stack>
    </Box>
  );
}

export default function CampaignScheduleTab({
  guildId,
  campaignId,
  campaignName,
  isAdmin,
  currentUserId,
  timezone,
}: CampaignScheduleTabProps) {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [newType, setNewType] = useState<'once' | 'recurring'>('once');
  const [newDate, setNewDate] = useState('');
  const [newTime, setNewTime] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newRrule, setNewRrule] = useState('');
  const [newDescription, setNewDescription] = useState('');

  // Fetch events for this campaign
  const { data: events, isLoading } = useQuery<CalendarEvent[]>({
    queryKey: ['campaign-events', guildId, campaignId],
    queryFn: async () => {
      const now = new Date().toISOString();
      const end = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString();
      const res = await client.get<CalendarEvent[]>(`/api/guilds/${guildId}/events`, {
        params: { start: now, end },
      });
      // Filter to only this campaign's events
      return res.data.filter((e) => e.campaign_id === campaignId);
    },
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const startTime = new Date(`${newDate}T${newTime || '00:00'}`).toISOString();
      await client.post(`/api/guilds/${guildId}/events`, {
        title: `${campaignName} — Session`,
        start_time: startTime,
        location: newLocation || null,
        rrule: newType === 'recurring' ? (newRrule || null) : null,
        description: newDescription || null,
        campaign_id: campaignId,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-events', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      setCreateOpen(false);
      setNewType('once');
      setNewDate('');
      setNewTime('');
      setNewLocation('');
      setNewRrule('');
      setNewDescription('');
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  const upcoming = events ?? [];

  return (
    <Box>
      {/* Header with create button */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          {upcoming.length === 0
            ? 'No upcoming sessions scheduled.'
            : `${upcoming.length} upcoming session${upcoming.length !== 1 ? 's' : ''}`}
        </Typography>
        {isAdmin && (
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
            sx={{ textTransform: 'none', fontSize: '0.75rem' }}
          >
            Schedule Session
          </Button>
        )}
      </Stack>

      {/* Event list */}
      <Stack spacing={1.5}>
        {upcoming.map((ev) => (
          <SessionEventCard
            key={`${ev.id}-${ev.occurrence_start ?? ev.start_time}`}
            event={ev}
            guildId={guildId}
            currentUserId={currentUserId}
            timezone={timezone}
          />
        ))}
      </Stack>

      {/* Quick-create session dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ pb: 0.5 }}>Schedule Session</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl>
              <FormLabel>Session type</FormLabel>
              <RadioGroup
                row
                value={newType}
                onChange={(e) => setNewType(e.target.value as 'once' | 'recurring')}
              >
                <FormControlLabel value="once" control={<Radio size="small" />} label="One-off" />
                <FormControlLabel value="recurring" control={<Radio size="small" />} label="Recurring" />
              </RadioGroup>
            </FormControl>
            <Stack direction="row" spacing={1.5}>
              <TextField
                label="Date"
                type="date"
                size="small"
                fullWidth
                required
                autoFocus
                value={newDate}
                onChange={(e) => setNewDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="Time"
                type="time"
                size="small"
                fullWidth
                value={newTime}
                onChange={(e) => setNewTime(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>
            {newType === 'recurring' && (
              <RRuleBuilder
                guildId={guildId}
                value={newRrule}
                onChange={setNewRrule}
              />
            )}
            <TextField
              label="Location (optional)"
              size="small"
              fullWidth
              value={newLocation}
              onChange={(e) => setNewLocation(e.target.value)}
              placeholder="e.g. Voice Channel, Roll20, in person"
            />
            <TextField
              label="Description (optional)"
              size="small"
              fullWidth
              multiline
              minRows={2}
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            {createMutation.isError && (
              <Typography variant="caption" color="error">
                {(createMutation.error as Error)?.message ?? 'Failed to create event.'}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            size="small"
            variant="contained"
            disabled={!newDate || (newType === 'recurring' && !newRrule) || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
