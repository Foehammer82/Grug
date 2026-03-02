import { useEffect, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';

interface Props {
  /** How often the query refetches, in milliseconds. Must match refetchInterval. */
  intervalMs: number;
  /** Pass `dataUpdatedAt` from useQuery so the countdown resets after each fetch. */
  dataUpdatedAt: number;
}

/**
 * Subtle corner indicator — a tiny circular progress ring and a muted countdown.
 * Meant to be placed in a flex row alongside a page title.
 */
export default function PollingIndicator({ intervalMs, dataUpdatedAt }: Props) {
  const [remaining, setRemaining] = useState(intervalMs);

  useEffect(() => {
    setRemaining(intervalMs);
  }, [dataUpdatedAt, intervalMs]);

  useEffect(() => {
    const tick = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1_000));
    }, 1_000);
    return () => clearInterval(tick);
  }, [dataUpdatedAt, intervalMs]);

  const seconds = Math.ceil(remaining / 1_000);
  const progress = ((intervalMs - remaining) / intervalMs) * 100;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, opacity: 0.7, '&:hover': { opacity: 1 }, transition: 'opacity 0.2s' }}>
      <Box sx={{ position: 'relative', width: 14, height: 14 }}>
        {/* Track */}
        <CircularProgress
          variant="determinate"
          value={100}
          size={14}
          thickness={3}
          sx={{ color: 'divider', position: 'absolute', top: 0, left: 0 }}
        />
        {/* Fill */}
        <CircularProgress
          variant="determinate"
          value={progress}
          size={14}
          thickness={3}
          sx={{ color: 'text.secondary', position: 'absolute', top: 0, left: 0 }}
        />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
        Refreshing in {seconds}s
      </Typography>
    </Box>
  );
}
