/**
 * 404 Not Found — Roll for your fate, adventurer.
 *
 * A d20 minigame. Click the die to roll. Grug will tell you your fate.
 */
import { Box, Button, Chip, Typography } from '@mui/material';
import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

// ── Outcome table ────────────────────────────────────────────────────────────

interface Outcome {
  label: string;
  color: 'error' | 'warning' | 'default' | 'info' | 'success';
  text: string;
  subtext: string;
}

function getOutcome(roll: number): Outcome {
  if (roll === 1) {
    return {
      label: 'CRITICAL FAIL',
      color: 'error',
      text: 'Grug also lost once. End up in marsh for six days.',
      subtext: 'The page you seek does not exist in this plane. Or any plane.',
    };
  }
  if (roll <= 4) {
    return {
      label: 'Very Bad',
      color: 'error',
      text: 'Grug check map. Map also missing. This very bad.',
      subtext: 'Rough roll. Page not here. Try not rolling a 3 next time.',
    };
  }
  if (roll <= 8) {
    return {
      label: 'Bad',
      color: 'warning',
      text: 'Grug shrug. Page go somewhere. Grug go somewhere too.',
      subtext: 'Below average. Much like this 404.',
    };
  }
  if (roll <= 11) {
    return {
      label: 'Mediocre',
      color: 'default',
      text: 'Ehh. Not great, not terrible. Page still missing though.',
      subtext: 'Average roll for an average situation.',
    };
  }
  if (roll <= 15) {
    return {
      label: 'Decent',
      color: 'info',
      text: 'Solid roll! Page still dead, but Grug salute your skill.',
      subtext: 'You clearly have proficiency in something. Just not navigation.',
    };
  }
  if (roll <= 19) {
    return {
      label: 'Great',
      color: 'info',
      text: 'Strong! Grug impressed. Page not impressed. Page gone.',
      subtext: 'High roller, wrong room. The dashboard is thataway →',
    };
  }
  // roll === 20
  return {
    label: '⚔ NATURAL 20',
    color: 'success',
    text: 'CRITICAL SUCCESS! Grug believe in you, adventurer!',
    subtext:
      'You have rolled with advantage and defeated the 404. Now go home.',
  };
}

// ── D20 face (SVG polygon) ───────────────────────────────────────────────────

const D20_POINTS = '75,5 145,40 145,110 75,145 5,110 5,40';

interface DieProps {
  value: number | null;
  rolling: boolean;
}

function D20Face({ value, rolling }: DieProps) {
  return (
    <Box
      component="svg"
      viewBox="0 0 150 150"
      sx={{
        width: 160,
        height: 160,
        filter: rolling ? 'none' : 'drop-shadow(0 4px 12px rgba(0,0,0,0.4))',
        animation: rolling ? 'grugRoll 0.6s ease-in-out' : 'none',
        '@keyframes grugRoll': {
          '0%':   { transform: 'rotate(0deg) scale(1)' },
          '20%':  { transform: 'rotate(-25deg) scale(0.85)' },
          '50%':  { transform: 'rotate(180deg) scale(1.15)' },
          '80%':  { transform: 'rotate(340deg) scale(0.9)' },
          '100%': { transform: 'rotate(360deg) scale(1)' },
        },
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {/* Shadow polygon */}
      <polygon
        points={D20_POINTS}
        fill="rgba(0,0,0,0.25)"
        transform="translate(4,6)"
      />
      {/* Main body */}
      <polygon
        points={D20_POINTS}
        fill="url(#dieGrad)"
        stroke="rgba(255,255,255,0.25)"
        strokeWidth="2"
      />
      {/* Inner bevelled polygon */}
      <polygon
        points="75,22 130,50 130,100 75,128 20,100 20,50"
        fill="none"
        stroke="rgba(255,255,255,0.12)"
        strokeWidth="1"
      />
      {/* Gradient */}
      <defs>
        <linearGradient id="dieGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
      </defs>
      {/* Number */}
      {value !== null && (
        <text
          x="75"
          y="85"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="white"
          fontSize={value >= 10 ? '36' : '42'}
          fontWeight="bold"
          fontFamily="monospace"
          style={{ letterSpacing: '-1px' }}
        >
          {value}
        </text>
      )}
      {value === null && (
        <text
          x="75"
          y="85"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="rgba(255,255,255,0.5)"
          fontSize="32"
          fontFamily="monospace"
        >
          d20
        </text>
      )}
    </Box>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function NotFoundPage() {
  const navigate = useNavigate();
  const [roll, setRoll] = useState<number | null>(null);
  const [rolling, setRolling] = useState(false);
  const rollCount = useRef(0);

  const doRoll = useCallback(() => {
    if (rolling) return;
    setRolling(true);
    rollCount.current += 1;
    const thisRoll = rollCount.current;

    // Tick through random values during animation then settle on final
    let ticks = 0;
    const maxTicks = 10;
    const final = Math.floor(Math.random() * 20) + 1;

    const ticker = setInterval(() => {
      ticks += 1;
      setRoll(Math.floor(Math.random() * 20) + 1);
      if (ticks >= maxTicks) {
        clearInterval(ticker);
        setRoll(final);
        if (rollCount.current === thisRoll) setRolling(false);
      }
    }, 55);
  }, [rolling]);

  const outcome = roll !== null ? getOutcome(roll) : null;
  const isNat20 = roll === 20;
  const isNat1  = roll === 1;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 3,
        px: 2,
        // subtle vignette
        background: (theme) =>
          theme.palette.mode === 'dark'
            ? 'radial-gradient(ellipse at center, #1a1f2e 0%, #0d1117 70%)'
            : 'radial-gradient(ellipse at center, #f0f4ff 0%, #ffffff 70%)',
      }}
    >
      {/* ── Big 404 ──────────────────────────────────────────── */}
      <Typography
        variant="h1"
        fontWeight={900}
        sx={{
          fontSize: { xs: '6rem', sm: '9rem' },
          lineHeight: 1,
          letterSpacing: '-0.04em',
          color: isNat20 ? 'success.main' : isNat1 ? 'error.main' : 'primary.main',
          transition: 'color 0.4s',
          textShadow: isNat20
            ? '0 0 40px rgba(34,197,94,0.4)'
            : isNat1
            ? '0 0 40px rgba(239,68,68,0.4)'
            : 'none',
        }}
      >
        404
      </Typography>

      <Typography variant="h5" fontWeight={600} textAlign="center">
        Grug not find this page.
      </Typography>

      <Typography variant="body2" color="text.secondary" textAlign="center" maxWidth={400}>
        Perhaps it was slain. Perhaps it never existed. Perhaps the rogue stole it.
        <br />
        <strong>Roll the d20</strong> to determine your fate.
      </Typography>

      {/* ── Die ─────────────────────────────────────────────── */}
      <Box
        onClick={doRoll}
        sx={{ mt: 1, mb: 1, transition: 'transform 0.15s', '&:hover': { transform: 'scale(1.06)' } }}
      >
        <D20Face value={roll} rolling={rolling} />
      </Box>

      <Typography variant="caption" color="text.disabled">
        {roll === null ? 'Click the die to roll' : 'Click again to re-roll'}
      </Typography>

      {/* ── Outcome ─────────────────────────────────────────── */}
      {outcome && !rolling && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1.5,
            mt: 1,
            p: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: isNat20 ? 'success.main' : isNat1 ? 'error.main' : 'divider',
            maxWidth: 440,
            width: '100%',
            bgcolor: 'background.paper',
            boxShadow: isNat20 ? '0 0 24px rgba(34,197,94,0.2)' : 'none',
            transition: 'all 0.3s',
          }}
        >
          <Chip label={outcome.label} color={outcome.color} size="small" />
          <Typography
            variant="h6"
            fontWeight={700}
            textAlign="center"
            color={isNat20 ? 'success.main' : isNat1 ? 'error.main' : 'text.primary'}
          >
            "{outcome.text}"
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center">
            {outcome.subtext}
          </Typography>
        </Box>
      )}

      {/* ── Actions ─────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', justifyContent: 'center', mt: 1 }}>
        <Button variant="contained" onClick={() => navigate('/dashboard')}>
          Return to safety
        </Button>
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Go back
        </Button>
      </Box>
    </Box>
  );
}
