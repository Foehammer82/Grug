import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SyncIcon from '@mui/icons-material/Sync';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Character } from '../types';

const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

const SYSTEM_LABELS: Record<string, string> = {
  pf2e: 'Pathfinder 2E',
  dnd5e: 'D&D 5e',
  unknown: 'Unknown',
};

/** PF2e proficiency rank labels (0 = untrained, 1 = trained, ...). */
const PROF_RANKS = ['Untrained', 'Trained', 'Expert', 'Master', 'Legendary'] as const;

function profLabel(rank: unknown): string {
  if (typeof rank === 'number' && rank >= 0 && rank < PROF_RANKS.length) {
    return PROF_RANKS[rank];
  }
  return String(rank ?? '—');
}

function profColor(rank: unknown): 'default' | 'info' | 'primary' | 'warning' | 'success' | 'error' {
  if (typeof rank !== 'number') return 'default';
  if (rank <= 0) return 'default';
  if (rank === 1) return 'info';
  if (rank === 2) return 'primary';
  if (rank === 3) return 'warning';
  return 'success'; // Legendary
}

function abilityMod(score: number | null | undefined): string {
  if (score == null) return '—';
  const mod = Math.floor((score - 10) / 2);
  return mod >= 0 ? `+${mod}` : String(mod);
}

export default function CharacterSheetPage() {
  useAuth();
  const { guildId, characterId } = useParams<{ guildId: string; characterId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: character, isLoading } = useQuery<Character>({
    queryKey: ['character', guildId, characterId],
    queryFn: async () => {
      const res = await client.get<Character>(`/api/guilds/${guildId}/characters/${characterId}`);
      return res.data;
    },
    enabled: !!guildId && !!characterId,
  });

  const syncMutation = useMutation({
    mutationFn: () =>
      client.post(`/api/guilds/${guildId}/characters/${characterId}/sync-pathbuilder`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', guildId, characterId] });
      qc.invalidateQueries({ queryKey: ['guild-characters', guildId] });
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!character) {
    return (
      <Typography color="text.secondary">Character not found.</Typography>
    );
  }

  const sd = character.structured_data as Record<string, unknown> | null;
  const isPathbuilder = sd?._source === 'pathbuilder';

  // Extract fields with fallback
  const charName = character.name;
  const level = sd?.level as number | null | undefined;
  const charClass = sd?.class_and_subclass as string | null | undefined;
  const dualClass = sd?.dual_class as string | null | undefined;
  const ancestry = sd?.race_or_ancestry as string | null | undefined;
  const heritage = sd?.heritage as string | null | undefined;
  const background = sd?.background as string | null | undefined;
  const alignment = sd?.alignment as string | null | undefined;
  const deity = sd?.deity as string | null | undefined;
  const size = sd?.size as string | null | undefined;
  const hp = sd?.hp as { current?: number | null; max?: number | null; temp?: number | null } | null | undefined;
  const ac = sd?.armor_class as number | null | undefined;
  const speed = sd?.speed as string | null | undefined;
  const perception = sd?.perception as number | null | undefined;
  const abilityScores = sd?.ability_scores as Record<string, number | null> | null | undefined;
  const savingThrows = sd?.saving_throws as Record<string, number | null> | null | undefined;
  const proficiencies = sd?.proficiencies as Record<string, number | null> | null | undefined;
  const attacks = sd?.attacks as Array<Record<string, unknown>> | null | undefined;
  const spells = sd?.spells as Array<Record<string, unknown>> | null | undefined;
  const features = sd?.features_and_traits as string[] | null | undefined;
  const inventory = sd?.inventory as string[] | null | undefined;
  const loreSkills = sd?.lore_skills as Array<{ name: string; rank: number }> | null | undefined;
  const armorList = sd?.armor as Array<Record<string, unknown>> | null | undefined;
  const currency = sd?.currency as Record<string, number> | null | undefined;
  const languages = sd?.languages as string[] | null | undefined;
  const notes = sd?.notes as string | null | undefined;

  const headline = [
    level != null && `Level ${level}`,
    charClass,
    dualClass && `/ ${dualClass}`,
    ancestry,
    heritage && `(${heritage})`,
  ].filter(Boolean).join(' ');

  return (
    <>
      {/* Back button + header */}
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <IconButton onClick={() => navigate(`/guilds/${guildId}/campaigns`)} size="small">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
          {charName}
        </Typography>
        <Chip
          label={SYSTEM_LABELS[character.system] ?? character.system}
          size="small"
          color={character.system === 'pf2e' ? 'error' : character.system === 'dnd5e' ? 'primary' : 'default'}
          variant="outlined"
        />
        {character.pathbuilder_id && (
          <Tooltip title="Sync from Pathbuilder">
            <IconButton
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              size="small"
            >
              <SyncIcon />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {headline && (
        <Typography variant="subtitle1" color="text.secondary" mb={0.5}>
          {headline}
        </Typography>
      )}

      {/* Secondary info line */}
      <Stack direction="row" spacing={2} flexWrap="wrap" mb={3}>
        {background && (
          <Typography variant="body2" color="text.secondary">
            <strong>Background:</strong> {background}
          </Typography>
        )}
        {alignment && (
          <Typography variant="body2" color="text.secondary">
            <strong>Alignment:</strong> {alignment}
          </Typography>
        )}
        {deity && (
          <Typography variant="body2" color="text.secondary">
            <strong>Deity:</strong> {deity}
          </Typography>
        )}
        {size && (
          <Typography variant="body2" color="text.secondary">
            <strong>Size:</strong> {size}
          </Typography>
        )}
      </Stack>

      {syncMutation.isError && (
        <Typography variant="caption" color="error" display="block" mb={2}>
          Sync failed:{' '}
          {(syncMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Unknown error'}
        </Typography>
      )}

      {/* ── Combat Stats ────────────────────────────────────── */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={4} flexWrap="wrap" justifyContent="center">
          {ac != null && (
            <StatBlock label="AC" value={String(ac)} />
          )}
          {hp?.max != null && (
            <StatBlock label="HP" value={String(hp.max)} />
          )}
          {speed && (
            <StatBlock label="Speed" value={speed} />
          )}
          {perception != null && (
            <StatBlock
              label="Perception"
              value={profLabel(perception)}
              chip
              chipColor={profColor(perception)}
            />
          )}
        </Stack>
      </Paper>

      {/* ── Ability Scores ──────────────────────────────────── */}
      {abilityScores && Object.values(abilityScores).some((v) => v != null) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="overline" color="text.secondary" display="block" mb={1}>
            Ability Scores
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="center">
            {ABILITY_KEYS.map((key) => {
              const val = abilityScores[key];
              if (val == null) return null;
              return (
                <Box
                  key={key}
                  sx={{
                    textAlign: 'center',
                    minWidth: 56,
                    py: 1,
                    px: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                  }}
                >
                  <Typography variant="caption" color="text.disabled" display="block">
                    {key}
                  </Typography>
                  <Typography variant="h6" fontWeight={700} lineHeight={1.3}>
                    {val}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {abilityMod(val)}
                  </Typography>
                </Box>
              );
            })}
          </Stack>
        </Paper>
      )}

      {/* ── Saving Throws (PF2e proficiency ranks) ──────── */}
      {savingThrows && Object.values(savingThrows).some((v) => v != null) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="overline" color="text.secondary" display="block" mb={1}>
            Saving Throws
          </Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" justifyContent="center">
            {Object.entries(savingThrows).map(([key, val]) => (
              val != null && (
                <Box key={key} sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.disabled" display="block" textTransform="capitalize">
                    {key}
                  </Typography>
                  <Chip
                    label={isPathbuilder ? profLabel(val) : String(val)}
                    size="small"
                    color={isPathbuilder ? profColor(val) : 'default'}
                    variant="outlined"
                  />
                </Box>
              )
            ))}
          </Stack>
        </Paper>
      )}

      {/* ── Proficiencies (PF2e) ────────────────────────── */}
      {isPathbuilder && proficiencies && (
        <SheetAccordion title="Proficiencies" defaultExpanded={false}>
          <Stack spacing={0.5}>
            {Object.entries(proficiencies)
              .filter(([key]) => !['fortitude', 'reflex', 'will', 'perception', 'classDC'].includes(key))
              .filter(([, val]) => val != null && (typeof val === 'number' ? val > 0 : true))
              .map(([key, val]) => (
                <Stack key={key} direction="row" alignItems="center" justifyContent="space-between">
                  <Typography variant="body2" textTransform="capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </Typography>
                  <Chip
                    label={profLabel(val)}
                    size="small"
                    color={profColor(val)}
                    variant="outlined"
                  />
                </Stack>
              ))
            }
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Lore Skills (PF2e) ──────────────────────────── */}
      {loreSkills && loreSkills.length > 0 && (
        <SheetAccordion title="Lore Skills" defaultExpanded={false}>
          <Stack spacing={0.5}>
            {loreSkills.map((lore, i) => (
              <Stack key={i} direction="row" alignItems="center" justifyContent="space-between">
                <Typography variant="body2">{lore.name} Lore</Typography>
                <Chip
                  label={profLabel(lore.rank)}
                  size="small"
                  color={profColor(lore.rank)}
                  variant="outlined"
                />
              </Stack>
            ))}
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Weapons / Attacks ───────────────────────────── */}
      {attacks && attacks.length > 0 && (
        <SheetAccordion title="Attacks" defaultExpanded>
          <Stack spacing={1} divider={<Divider />}>
            {attacks.map((atk, i) => (
              <Box key={i}>
                <Typography variant="body2" fontWeight={600}>
                  {String(atk.name || atk.display || `Attack ${i + 1}`)}
                </Typography>
                <Stack direction="row" spacing={2} flexWrap="wrap">
                  {Boolean(atk.die) && (
                    <Typography variant="caption" color="text.secondary">
                      Damage: {String(atk.die)}{atk.damage_type ? ` ${String(atk.damage_type)}` : ''}
                    </Typography>
                  )}
                  {typeof atk.pot === 'number' && atk.pot > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      +{String(atk.pot)} potency
                    </Typography>
                  )}
                  {typeof atk.str === 'number' && atk.str > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      +{String(atk.str)} striking
                    </Typography>
                  )}
                  {Array.isArray(atk.runes) && (atk.runes as string[]).length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      Runes: {(atk.runes as string[]).filter(Boolean).join(', ')}
                    </Typography>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Armor ───────────────────────────────────────── */}
      {armorList && armorList.length > 0 && (
        <SheetAccordion title="Armor" defaultExpanded={false}>
          <Stack spacing={1} divider={<Divider />}>
            {armorList.map((arm, i) => (
              <Box key={i}>
                <Typography variant="body2" fontWeight={600}>
                  {String(arm.display || arm.name || `Armor ${i + 1}`)}
                  {arm.worn ? ' (worn)' : ''}
                </Typography>
                <Stack direction="row" spacing={2} flexWrap="wrap">
                  {typeof arm.pot === 'number' && arm.pot > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      +{arm.pot} potency
                    </Typography>
                  )}
                  {typeof arm.res === 'number' && arm.res > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      +{arm.res} resilient
                    </Typography>
                  )}
                  {Array.isArray(arm.runes) && (arm.runes as string[]).length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      Runes: {(arm.runes as string[]).filter(Boolean).join(', ')}
                    </Typography>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Spells ──────────────────────────────────────── */}
      {spells && spells.length > 0 && (
        <SheetAccordion title="Spells" defaultExpanded>
          {spells.map((caster, ci) => (
            <Box key={ci} sx={ci > 0 ? { mt: 2 } : undefined}>
              <Stack direction="row" spacing={1} alignItems="center" mb={1}>
                {Boolean(caster.tradition) && (
                  <Chip label={String(caster.tradition)} size="small" variant="outlined" />
                )}
                {Boolean(caster.type) && (
                  <Typography variant="caption" color="text.secondary">
                    {String(caster.type)}
                  </Typography>
                )}
                {typeof caster.focus_points === 'number' && caster.focus_points > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    {'Focus: ' + String(caster.focus_points)}
                  </Typography>
                )}
              </Stack>
              {Array.isArray(caster.spells_by_level) &&
                (caster.spells_by_level as Array<{ level: number; spells: string[] }>).map(
                  (lvl, li) =>
                    lvl.spells?.length > 0 && (
                      <Box key={li} sx={{ mb: 1 }}>
                        <Typography variant="caption" fontWeight={600} color="text.secondary">
                          {lvl.level === 0 ? 'Cantrips' : `Level ${lvl.level}`}
                          {Array.isArray(caster.per_day) && typeof (caster.per_day as number[])[lvl.level] === 'number'
                            ? ` (${(caster.per_day as number[])[lvl.level]}/day)`
                            : ''}
                        </Typography>
                        <Stack direction="row" spacing={0.5} flexWrap="wrap" mt={0.25}>
                          {lvl.spells.map((spell, si) => (
                            <Chip key={si} label={spell} size="small" variant="outlined" />
                          ))}
                        </Stack>
                      </Box>
                    ),
                )}
            </Box>
          ))}
        </SheetAccordion>
      )}

      {/* ── Features & Traits / Feats ───────────────────── */}
      {features && features.length > 0 && (
        <SheetAccordion title="Features & Feats" defaultExpanded={false}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {features.map((feat, i) => (
              <Chip key={i} label={feat} size="small" variant="outlined" />
            ))}
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Inventory ───────────────────────────────────── */}
      {inventory && inventory.length > 0 && (
        <SheetAccordion title="Inventory" defaultExpanded={false}>
          <Stack spacing={0.25}>
            {inventory.map((item, i) => (
              <Typography key={i} variant="body2">
                • {item}
              </Typography>
            ))}
          </Stack>
          {currency && Object.values(currency).some((v) => v > 0) && (
            <Box sx={{ mt: 1.5, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                Currency:
              </Typography>
              <Stack direction="row" spacing={2} mt={0.5}>
                {currency.pp != null && currency.pp > 0 && (
                  <Typography variant="body2">{currency.pp} pp</Typography>
                )}
                {currency.gp != null && currency.gp > 0 && (
                  <Typography variant="body2">{currency.gp} gp</Typography>
                )}
                {currency.sp != null && currency.sp > 0 && (
                  <Typography variant="body2">{currency.sp} sp</Typography>
                )}
                {currency.cp != null && currency.cp > 0 && (
                  <Typography variant="body2">{currency.cp} cp</Typography>
                )}
              </Stack>
            </Box>
          )}
        </SheetAccordion>
      )}

      {/* ── Languages ───────────────────────────────────── */}
      {languages && languages.length > 0 && (
        <SheetAccordion title="Languages" defaultExpanded={false}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {languages.map((lang, i) => (
              <Chip key={i} label={lang} size="small" variant="outlined" />
            ))}
          </Stack>
        </SheetAccordion>
      )}

      {/* ── Notes ───────────────────────────────────────── */}
      {notes && (
        <SheetAccordion title="Notes" defaultExpanded={false}>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {notes}
          </Typography>
        </SheetAccordion>
      )}
    </>
  );
}


// ── Reusable components ──────────────────────────────────────────────────

function StatBlock({
  label,
  value,
  chip,
  chipColor,
}: {
  label: string;
  value: string;
  chip?: boolean;
  chipColor?: 'default' | 'info' | 'primary' | 'warning' | 'success' | 'error';
}) {
  return (
    <Box sx={{ textAlign: 'center', minWidth: 60 }}>
      <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>
        {label}
      </Typography>
      {chip ? (
        <Chip label={value} size="small" color={chipColor ?? 'default'} variant="outlined" />
      ) : (
        <Typography variant="h5" fontWeight={700}>{value}</Typography>
      )}
    </Box>
  );
}

function SheetAccordion({
  title,
  defaultExpanded = false,
  children,
}: {
  title: string;
  defaultExpanded?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      variant="outlined"
      disableGutters
      sx={{
        mb: 1,
        '&:before': { display: 'none' },
        '&.Mui-expanded': { mb: 1 },
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="subtitle2" fontWeight={600}>
          {title}
        </Typography>
      </AccordionSummary>
      <AccordionDetails>{children}</AccordionDetails>
    </Accordion>
  );
}
