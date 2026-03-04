import { useEffect, useState } from 'react';
import {
  Autocomplete,
  Avatar,
  Box,
  Button,
  ButtonGroup,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Skeleton,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import EventIcon from '@mui/icons-material/Event';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import CancelIcon from '@mui/icons-material/Cancel';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import RepeatIcon from '@mui/icons-material/Repeat';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import RRuleBuilder from '../RRuleBuilder';
import type { CalendarEvent, DiscordChannel, EventRSVP, GuildMember, RSVPStatus } from '../../types';

/* ──────────────────────────────────────────────────────────────────── */

interface CampaignScheduleTabProps {
  guildId: string;
  campaignId: number;
  campaignName: string;
  /** From Campaign.schedule_mode — passed so the dialog can toggle it. */
  scheduleMode: 'fixed' | 'poll';
  isAdmin: boolean;
  currentUserId: string;
  timezone: string;
  channels: DiscordChannel[];
  campaignChannelId: string | null;
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

/**
 * A unique cache key for a specific occurrence.
 * Recurring events all share the same `event.id`, so we include
 * `occurrence_start` to prevent RSVP state from bleeding between
 * different occurrences of the same series.
 */
function occurrenceKey(event: CalendarEvent) {
  return event.occurrence_start ?? event.start_time;
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

  // Per-occurrence cache key so RSVPs don't bleed between occurrences
  const rsvpKey = ['event-rsvps', guildId, event.id, occurrenceKey(event)];

  const { data: rsvps, isLoading: rsvpsLoading } = useQuery<EventRSVP[]>({
    queryKey: rsvpKey,
    queryFn: async () => (await client.get<EventRSVP[]>(`/api/guilds/${guildId}/events/${event.id}/rsvps`)).data,
    staleTime: 30_000,
  });

  const rsvpMutation = useMutation({
    mutationFn: async (status: RSVPStatus) => {
      await client.put(`/api/guilds/${guildId}/events/${event.id}/rsvp`, { status });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rsvpKey });
    },
  });

  const removeRsvpMutation = useMutation({
    mutationFn: async () => {
      await client.delete(`/api/guilds/${guildId}/events/${event.id}/rsvp`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rsvpKey });
    },
  });

  const myRsvp = rsvps?.find((r) => r.discord_user_id === currentUserId);
  const attending = rsvps?.filter((r) => r.status === 'attending') ?? [];
  const maybe = rsvps?.filter((r) => r.status === 'maybe') ?? [];
  const declined = rsvps?.filter((r) => r.status === 'declined') ?? [];

  // Use occurrence_start when available (recurring expansions) so the correct date shows
  const startDate = new Date(event.occurrence_start ?? event.start_time);
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

/** Form state shared by create and edit dialog. */
interface ScheduleForm {
  scheduleMode: 'fixed' | 'poll';
  type: 'once' | 'recurring';
  date: string;
  time: string;
  location: string;
  description: string;
  rrule: string;
  channelId: string | null;
  reminderTime: string;
  reminderDays: number[];
  pollAdvanceDays: number;
}

const EMPTY_FORM: ScheduleForm = {
  scheduleMode: 'fixed',
  type: 'recurring',
  date: '',
  time: '',
  location: '',
  description: '',
  rrule: '',
  channelId: null,
  reminderTime: '18:00',
  reminderDays: [1],
  pollAdvanceDays: 7,
};

/** Max number of reminder slots allowed. */
const MAX_REMINDER_DAYS = 5;

export default function CampaignScheduleTab({
  guildId,
  campaignId,
  campaignName,
  scheduleMode,
  isAdmin,
  currentUserId,
  timezone,
  channels,
  campaignChannelId,
}: CampaignScheduleTabProps) {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<ScheduleForm>({ ...EMPTY_FORM, scheduleMode });
  const [confirmDelete, setConfirmDelete] = useState(false);

  // 2-year window catches all upcoming occurrences and confirms if a schedule exists
  const { data: events, isLoading } = useQuery<CalendarEvent[]>({
    queryKey: ['campaign-events', guildId, campaignId],
    queryFn: async () => {
      const now = new Date().toISOString();
      const end = new Date(Date.now() + 2 * 365 * 24 * 60 * 60 * 1000).toISOString();
      const res = await client.get<CalendarEvent[]>(`/api/guilds/${guildId}/events`, {
        params: { start: now, end },
      });
      return res.data.filter((e) => e.campaign_id === campaignId);
    },
    staleTime: 30_000,
  });

  // Show only the next 2 sessions to avoid cluttering the card
  const upcoming = (events ?? []).slice(0, 2);

  // The base event is the first result — all occurrences share the same event.id
  const baseEvent = events && events.length > 0 ? events[0] : null;
  const hasSchedule = baseEvent !== null;

  /** Pre-fill form from existing event when opening the edit dialog. */
  function openDialog() {
    if (!baseEvent) {
      setForm({ ...EMPTY_FORM, scheduleMode, channelId: campaignChannelId ?? null });
    } else {
      const start = new Date(baseEvent.start_time);
      const localDate = start.toLocaleDateString('en-CA'); // YYYY-MM-DD
      const localTime = start.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }); // HH:MM
      setForm({
        scheduleMode,
        type: baseEvent.rrule ? 'recurring' : 'once',
        date: localDate,
        time: localTime,
        location: baseEvent.location ?? '',
        description: baseEvent.description ?? '',
        rrule: baseEvent.rrule ?? '',
        channelId: baseEvent.channel_id ?? campaignChannelId ?? null,
        reminderTime: baseEvent.reminder_time ?? '18:00',
        reminderDays: baseEvent.reminder_days ?? [1],
        pollAdvanceDays: baseEvent.poll_advance_days ?? 7,
      });
    }
    setConfirmDelete(false);
    setDialogOpen(true);
  }

  // Keep scheduleMode in sync if the campaign prop changes externally
  useEffect(() => {
    setForm((f) => ({ ...f, scheduleMode }));
  }, [scheduleMode]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const startTime = new Date(`${form.date}T${form.time || '00:00'}`).toISOString();
      const payload = {
        title: `${campaignName} — Session`,
        start_time: startTime,
        location: form.location || null,
        rrule: form.type === 'recurring' ? form.rrule || null : null,
        description: form.description || null,
        channel_id: form.channelId || null,
        reminder_days: form.reminderDays.length > 0 ? form.reminderDays : [1],
        reminder_time: form.reminderTime || '18:00',
        poll_advance_days: form.scheduleMode === 'poll' ? form.pollAdvanceDays : null,
        campaign_id: campaignId,
      };

      if (hasSchedule && baseEvent) {
        await client.patch(`/api/guilds/${guildId}/events/${baseEvent.id}`, payload);
      } else {
        await client.post(`/api/guilds/${guildId}/events`, payload);
      }

      // Sync schedule_mode on campaign if it changed
      if (form.scheduleMode !== scheduleMode) {
        await client.patch(`/api/guilds/${guildId}/campaigns/${campaignId}`, {
          schedule_mode: form.scheduleMode,
        });
        qc.invalidateQueries({ queryKey: ['campaigns', guildId] });
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-events', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      setDialogOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!baseEvent) return;
      await client.delete(`/api/guilds/${guildId}/events/${baseEvent.id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-events', guildId, campaignId] });
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      setConfirmDelete(false);
    },
  });

  const isFormValid = !!form.date && (form.type === 'once' || !!form.rrule);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          {upcoming.length === 0
            ? hasSchedule
              ? 'No upcoming sessions in schedule.'
              : 'No schedule set up yet.'
            : `Next ${upcoming.length} upcoming session${upcoming.length !== 1 ? 's' : ''}`}
        </Typography>

        {isAdmin && (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Button
              size="small"
              startIcon={hasSchedule ? <EditIcon /> : <EventIcon />}
              onClick={openDialog}
              sx={{ textTransform: 'none', fontSize: '0.75rem' }}
            >
              {hasSchedule ? 'Edit Schedule' : 'Set Up Schedule'}
            </Button>
            {hasSchedule && !confirmDelete && (
              <Tooltip title="Delete schedule">
                <IconButton
                  size="small"
                  color="error"
                  onClick={() => setConfirmDelete(true)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            {hasSchedule && confirmDelete && (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <Button
                  size="small"
                  color="error"
                  variant="contained"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate()}
                  sx={{ textTransform: 'none', fontSize: '0.7rem' }}
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Confirm Delete'}
                </Button>
                <Button
                  size="small"
                  onClick={() => setConfirmDelete(false)}
                  sx={{ textTransform: 'none', fontSize: '0.7rem' }}
                >
                  Cancel
                </Button>
              </Stack>
            )}
          </Stack>
        )}
      </Stack>

      {/* Next 2 upcoming sessions */}
      <Stack spacing={1.5}>
        {upcoming.map((ev) => (
          <SessionEventCard
            key={`${ev.id}-${occurrenceKey(ev)}`}
            event={ev}
            guildId={guildId}
            currentUserId={currentUserId}
            timezone={timezone}
          />
        ))}
      </Stack>

      {/* Create / edit schedule dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ pb: 0.5 }}>
          {hasSchedule ? 'Edit Campaign Schedule' : 'Set Up Campaign Schedule'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {/* Scheduling mode */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Scheduling mode
              </Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={form.scheduleMode}
                onChange={(_, v) => { if (v) setForm((f) => ({ ...f, scheduleMode: v })); }}
              >
                <ToggleButton value="fixed">
                  <Tooltip title="Sessions happen on a fixed recurring schedule">
                    <span>Fixed schedule</span>
                  </Tooltip>
                </ToggleButton>
                <ToggleButton value="poll">
                  <Tooltip title="Poll players for availability before each session">
                    <span>Poll players</span>
                  </Tooltip>
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Session type */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Session type
              </Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={form.type}
                onChange={(_, v) => { if (v) setForm((f) => ({ ...f, type: v })); }}
              >
                <ToggleButton value="recurring">Recurring</ToggleButton>
                <ToggleButton value="once">One-off</ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Date & time */}
            <Stack direction="row" spacing={1.5}>
              <TextField
                label={form.type === 'recurring' ? 'First session date' : 'Date'}
                type="date"
                size="small"
                fullWidth
                required
                autoFocus
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="Time"
                type="time"
                size="small"
                fullWidth
                value={form.time}
                onChange={(e) => setForm((f) => ({ ...f, time: e.target.value }))}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>

            {form.type === 'recurring' && (
              <RRuleBuilder
                guildId={guildId}
                value={form.rrule}
                onChange={(v) => setForm((f) => ({ ...f, rrule: v }))}
              />
            )}

            <TextField
              label="Location (optional)"
              size="small"
              fullWidth
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="e.g. Voice Channel, Roll20, in person"
            />
            <TextField
              label="Description (optional)"
              size="small"
              fullWidth
              multiline
              minRows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />

            <Divider />

            {/* Announcement channel */}
            <Autocomplete
              size="small"
              fullWidth
              options={channels}
              value={channels.find((c) => c.id === form.channelId) ?? null}
              onChange={(_, ch) => setForm((f) => ({ ...f, channelId: ch?.id ?? null }))}
              getOptionLabel={(ch) => `#${ch.name}`}
              filterOptions={(opts, { inputValue }) => {
                const q = inputValue.toLowerCase();
                return opts.filter((ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q));
              }}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              renderOption={(props, ch) => (
                <Box component="li" {...props} key={ch.id}>
                  <span>#{ch.name}</span>
                  <Typography component="span" variant="caption" color="text.disabled" sx={{ ml: 1 }}>
                    {ch.id}
                  </Typography>
                </Box>
              )}
              renderInput={(params) => (
                <TextField {...params} label="Announcement Channel (optional)" helperText="Where Grug posts session reminders" />
              )}
            />

            {/* Reminder time */}
            <TextField
              label="Reminder time of day"
              type="time"
              size="small"
              fullWidth
              value={form.reminderTime}
              onChange={(e) => setForm((f) => ({ ...f, reminderTime: e.target.value }))}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={`Reminders fire at this time in the server timezone (${timezone || 'UTC'})`}
            />

            {/* Reminder days */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Reminders (days before session)
              </Typography>
              <Stack spacing={1}>
                {form.reminderDays.map((d, idx) => (
                  <Stack key={idx} direction="row" spacing={1} alignItems="center">
                    <TextField
                      size="small"
                      type="number"
                      value={d}
                      onChange={(e) => {
                        const val = Math.max(0, parseInt(e.target.value) || 0);
                        setForm((f) => {
                          const next = [...f.reminderDays];
                          next[idx] = val;
                          return { ...f, reminderDays: next };
                        });
                      }}
                      slotProps={{ htmlInput: { min: 0, max: 90 } }}
                      sx={{ width: 100 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      day{d !== 1 ? 's' : ''} before
                    </Typography>
                    {form.reminderDays.length > 1 && (
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() =>
                          setForm((f) => ({
                            ...f,
                            reminderDays: f.reminderDays.filter((_, i) => i !== idx),
                          }))
                        }
                      >
                        <RemoveCircleOutlineIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Stack>
                ))}
                {form.reminderDays.length < MAX_REMINDER_DAYS && (
                  <Button
                    size="small"
                    startIcon={<AddIcon />}
                    onClick={() =>
                      setForm((f) => ({ ...f, reminderDays: [...f.reminderDays, 1] }))
                    }
                    sx={{ textTransform: 'none', alignSelf: 'flex-start', fontSize: '0.75rem' }}
                  >
                    Add reminder
                  </Button>
                )}
              </Stack>
            </Box>

            {/* Poll advance days (only in poll mode) */}
            {form.scheduleMode === 'poll' && (
              <TextField
                label="Poll advance (days)"
                type="number"
                size="small"
                fullWidth
                value={form.pollAdvanceDays}
                onChange={(e) =>
                  setForm((f) => ({ ...f, pollAdvanceDays: Math.max(1, parseInt(e.target.value) || 1) }))
                }
                slotProps={{ htmlInput: { min: 1, max: 90 } }}
                helperText="How many days before the session to open the availability poll"
              />
            )}

            {saveMutation.isError && (
              <Typography variant="caption" color="error">
                {(saveMutation.error as Error)?.message ?? 'Failed to save schedule.'}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            size="small"
            variant="contained"
            disabled={!isFormValid || saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? 'Saving…' : hasSchedule ? 'Save Changes' : 'Create Schedule'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
