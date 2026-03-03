/**
 * CalendarSubscribePanel
 *
 * Shows the guild's iCal feed URL with one-click copy and deep-link buttons
 * for Google Calendar, Apple Calendar / iCal, and Microsoft Outlook.
 *
 * Admins also get a "Regenerate token" button that rotates the secret URL
 * segment (invalidating any existing subscriptions).
 */
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  InputAdornment,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { getEnv } from '../env';
import { useGuildContext } from '../hooks/useGuildContext';

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Return the base URL for the Grug API (same as the axios client uses). */
function apiBase(): string {
  return getEnv('VITE_API_URL') ?? '';
}

/**
 * Build all subscription-relevant URLs from the feed URL.
 *
 * @param feedUrl  The full https:// iCal feed URL.
 */
function buildSubscribeUrls(feedUrl: string) {
  // webcal:// substitution is handled natively by most desktop calendar apps
  // (Apple Calendar, Thunderbird, Fantastical…).  Clicking a webcal:// link
  // prompts the OS to open the default calendar application.
  const webcalUrl = feedUrl.replace(/^https?:\/\//, 'webcal://');

  // Google Calendar: "Other calendars → From URL" (newer settings page)
  const googleUrl = `https://calendar.google.com/calendar/u/0/r/settings/addbyurl?url=${encodeURIComponent(feedUrl)}`;

  // Outlook (web / Microsoft 365): "Add calendar → Subscribe from web"
  const outlookUrl = `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(feedUrl)}&name=Grug+Events`;

  return { webcalUrl, googleUrl, outlookUrl };
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

interface Props {
  /** If true the panel renders inline without the outer section heading. */
  compact?: boolean;
}

export default function CalendarSubscribePanel({ compact = false }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const { isAdmin } = useGuildContext();
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  /* ---- Fetch (or lazily create) the calendar token ---- */
  const { data, isLoading, isError } = useQuery<{ token: string }>({
    queryKey: ['calendar-token', guildId],
    queryFn: async () => {
      const res = await client.get<{ token: string }>(
        `/api/guilds/${guildId}/calendar-token`
      );
      return res.data;
    },
    enabled: !!guildId,
  });

  /* ---- Regenerate token (admin only) ---- */
  const regenMutation = useMutation({
    mutationFn: async () => {
      const res = await client.post<{ token: string }>(
        `/api/guilds/${guildId}/calendar-token/regenerate`
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-token', guildId] });
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Loading calendar link…
        </Typography>
      </Box>
    );
  }

  if (isError || !data) {
    return (
      <Alert severity="warning" sx={{ mt: 1 }}>
        Could not load calendar feed URL.
      </Alert>
    );
  }

  const feedUrl = `${apiBase()}/api/guilds/${guildId}/events/ical?token=${data.token}`;
  const { webcalUrl, googleUrl, outlookUrl } = buildSubscribeUrls(feedUrl);

  function handleCopy() {
    navigator.clipboard.writeText(feedUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {!compact && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CalendarMonthIcon fontSize="small" color="action" />
          <Typography variant="subtitle2">Subscribe to Calendar</Typography>
        </Box>
      )}

      <Typography variant="body2" color="text.secondary">
        Add this guild's events to Google Calendar, Apple Calendar, Outlook, or
        any app that supports iCal / CalDAV subscriptions. The calendar updates
        automatically — you only need to add it once.
      </Typography>

      {/* Feed URL display + copy */}
      <TextField
        size="small"
        fullWidth
        value={feedUrl}
        InputProps={{
          readOnly: true,
          sx: { fontFamily: 'monospace', fontSize: 'caption.fontSize' },
          endAdornment: (
            <InputAdornment position="end">
              <Tooltip title={copied ? 'Copied!' : 'Copy URL'}>
                <IconButton size="small" onClick={handleCopy} edge="end">
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </InputAdornment>
          ),
        }}
        label="iCal Feed URL"
      />

      {/* Subscribe buttons */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Button
          variant="outlined"
          size="small"
          href={googleUrl}
          target="_blank"
          rel="noopener noreferrer"
          sx={{ textTransform: 'none' }}
        >
          + Google Calendar
        </Button>

        <Button
          variant="outlined"
          size="small"
          href={webcalUrl}
          sx={{ textTransform: 'none' }}
        >
          + Apple Calendar / iCal
        </Button>

        <Button
          variant="outlined"
          size="small"
          href={outlookUrl}
          target="_blank"
          rel="noopener noreferrer"
          sx={{ textTransform: 'none' }}
        >
          + Outlook
        </Button>
      </Box>

      <Typography variant="caption" color="text.secondary">
        The URL contains a secret token. Share it only with people you trust.
        {isAdmin && ' Use "Regenerate token" if the URL is ever compromised.'}
      </Typography>

      {/* Admin: regenerate token */}
      {isAdmin && (
        <Box>
          <Button
            size="small"
            color="warning"
            variant="text"
            startIcon={<RefreshIcon />}
            onClick={() => setConfirmOpen(true)}
            disabled={regenMutation.isPending}
            sx={{ textTransform: 'none' }}
          >
            Regenerate token
          </Button>
          {regenMutation.isSuccess && (
            <Typography variant="caption" color="warning.main" sx={{ ml: 1 }}>
              Token regenerated — existing subscriptions must be updated.
            </Typography>
          )}
        </Box>
      )}

      {/* Confirmation dialog */}
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>Regenerate calendar token?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will invalidate the current iCal feed URL. Anyone subscribed
            with the old URL will stop receiving updates until they re-subscribe
            with the new one. This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)} autoFocus>
            Cancel
          </Button>
          <Button
            color="warning"
            variant="contained"
            onClick={() => {
              setConfirmOpen(false);
              regenMutation.mutate();
            }}
          >
            Regenerate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
