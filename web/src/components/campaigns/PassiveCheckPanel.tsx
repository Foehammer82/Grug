import { useState } from 'react';
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useMutation } from '@tanstack/react-query';
import client from '../../api/client';

/** Skill options — union of D&D 5e and PF2e skills for the autocomplete. */
const SKILL_OPTIONS = [
  { key: 'perception', label: 'Perception' },
  { key: 'acrobatics', label: 'Acrobatics' },
  { key: 'animal_handling', label: 'Animal Handling' },
  { key: 'arcana', label: 'Arcana' },
  { key: 'athletics', label: 'Athletics' },
  { key: 'crafting', label: 'Crafting' },
  { key: 'deception', label: 'Deception' },
  { key: 'diplomacy', label: 'Diplomacy' },
  { key: 'history', label: 'History' },
  { key: 'insight', label: 'Insight' },
  { key: 'intimidation', label: 'Intimidation' },
  { key: 'investigation', label: 'Investigation' },
  { key: 'medicine', label: 'Medicine' },
  { key: 'nature', label: 'Nature' },
  { key: 'occultism', label: 'Occultism' },
  { key: 'performance', label: 'Performance' },
  { key: 'persuasion', label: 'Persuasion' },
  { key: 'religion', label: 'Religion' },
  { key: 'sleight_of_hand', label: 'Sleight of Hand' },
  { key: 'society', label: 'Society' },
  { key: 'stealth', label: 'Stealth' },
  { key: 'survival', label: 'Survival' },
  { key: 'thievery', label: 'Thievery' },
];

interface PassiveResult {
  name: string;
  owner_discord_user_id: string | null;
  score: number | null;
  pass: boolean | null;
}

interface PassiveCheckPanelProps {
  guildId: string;
  campaignId: number;
}

/**
 * GM-only panel for checking the party's passive skill scores.
 *
 * Lets the GM pick a skill (default: Perception) and optionally enter a DC,
 * then shows each character's passive score with pass/fail results.
 */
export default function PassiveCheckPanel({ guildId, campaignId }: PassiveCheckPanelProps) {
  const [skill, setSkill] = useState(SKILL_OPTIONS[0]);
  const [dcInput, setDcInput] = useState('');

  const checkMutation = useMutation<PassiveResult[], Error, { skill: string; dc: number | null }>({
    mutationFn: async ({ skill: sk, dc }) => {
      const body: Record<string, unknown> = { skill: sk };
      if (dc != null) body.dc = dc;
      const res = await client.post<PassiveResult[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/passives`,
        body,
      );
      return res.data;
    },
  });

  const dc = dcInput.trim() !== '' && !isNaN(Number(dcInput)) ? Number(dcInput) : null;

  const handleCheck = () => {
    checkMutation.mutate({ skill: skill.key, dc });
  };

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'flex-start' }}>
        <Autocomplete
          size="small"
          options={SKILL_OPTIONS}
          value={skill}
          onChange={(_, v) => { if (v) setSkill(v); }}
          getOptionLabel={(o) => o.label}
          isOptionEqualToValue={(a, b) => a.key === b.key}
          disableClearable
          sx={{ minWidth: 180 }}
          renderInput={(params) => <TextField {...params} label="Skill" />}
        />
        <TextField
          size="small"
          label="DC (optional)"
          type="number"
          value={dcInput}
          onChange={(e) => setDcInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleCheck(); }}
          sx={{ width: 120 }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={checkMutation.isPending ? <CircularProgress size={14} color="inherit" /> : <VisibilityIcon />}
          disabled={checkMutation.isPending}
          onClick={handleCheck}
          sx={{ minWidth: 90, height: 40 }}
        >
          Check
        </Button>
      </Stack>

      {checkMutation.isError && (
        <Typography variant="caption" color="error" sx={{ mt: 1, display: 'block' }}>
          {(checkMutation.error as Error)?.message ?? 'Failed to check passives.'}
        </Typography>
      )}

      {checkMutation.data && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Passive {skill.label}{dc != null ? ` vs DC ${dc}` : ''}
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Character</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, py: 0.5 }}>Score</TableCell>
                {dc != null && (
                  <TableCell align="center" sx={{ fontWeight: 600, py: 0.5 }}>Result</TableCell>
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {checkMutation.data.map((r) => (
                <TableRow key={r.name}>
                  <TableCell sx={{ py: 0.5 }}>{r.name}</TableCell>
                  <TableCell align="right" sx={{ py: 0.5 }}>
                    {r.score != null ? (
                      <Typography variant="body2" fontWeight={600}>{r.score}</Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">—</Typography>
                    )}
                  </TableCell>
                  {dc != null && (
                    <TableCell align="center" sx={{ py: 0.5 }}>
                      {r.pass === true && <Chip label="Pass" size="small" color="success" sx={{ height: 20, fontSize: '0.7rem' }} />}
                      {r.pass === false && <Chip label="Fail" size="small" color="error" sx={{ height: 20, fontSize: '0.7rem' }} />}
                      {r.pass == null && <Typography variant="body2" color="text.disabled">—</Typography>}
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {checkMutation.data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={dc != null ? 3 : 2}>
                    <Typography variant="body2" color="text.secondary">No characters in this campaign.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Box>
      )}
    </Box>
  );
}
