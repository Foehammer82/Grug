import { useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
  Divider,
  IconButton,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ABILITY_KEYS, abilityMod } from '../../constants/character';
import type { CharacterSheet } from '../../types';

// ── PF2e proficiency helpers ───────────────────────────────────────────────

const PROF_LABELS = ['Untrained', 'Trained', 'Expert', 'Master', 'Legendary'] as const;
const PROF_ABBR = ['U', 'T', 'E', 'M', 'L'] as const;
const PROF_COLORS: Array<
  'default' | 'info' | 'primary' | 'warning' | 'success'
> = ['default', 'info', 'primary', 'warning', 'success'];

function profLabel(rank: unknown): string {
  if (typeof rank === 'number' && rank >= 0 && rank < PROF_LABELS.length) {
    return PROF_LABELS[rank];
  }
  return String(rank ?? '—');
}

function profAbbr(rank: unknown): string {
  if (typeof rank === 'number' && rank >= 0 && rank < PROF_ABBR.length) {
    return PROF_ABBR[rank];
  }
  return '—';
}

function profColor(rank: unknown): 'default' | 'info' | 'primary' | 'warning' | 'success' {
  if (typeof rank === 'number' && rank >= 0 && rank < PROF_COLORS.length) {
    return PROF_COLORS[rank];
  }
  return 'default';
}

// PF2e standard skills and their key abilities (for display grouping)
const PF2E_SKILLS: Array<{ key: string; label: string }> = [
  { key: 'acrobatics', label: 'Acrobatics' },
  { key: 'arcana', label: 'Arcana' },
  { key: 'athletics', label: 'Athletics' },
  { key: 'crafting', label: 'Crafting' },
  { key: 'deception', label: 'Deception' },
  { key: 'diplomacy', label: 'Diplomacy' },
  { key: 'intimidation', label: 'Intimidation' },
  { key: 'medicine', label: 'Medicine' },
  { key: 'nature', label: 'Nature' },
  { key: 'occultism', label: 'Occultism' },
  { key: 'performance', label: 'Performance' },
  { key: 'religion', label: 'Religion' },
  { key: 'society', label: 'Society' },
  { key: 'stealth', label: 'Stealth' },
  { key: 'survival', label: 'Survival' },
  { key: 'thievery', label: 'Thievery' },
];

// ── Main component ─────────────────────────────────────────────────────────

/** Comprehensive character sheet view for the dialog Sheet tab. */
export default function CharacterStatCard({ sheet }: { sheet: CharacterSheet }) {
  const isPf2e = sheet._source === 'pathbuilder' || sheet.system === 'pf2e';
  const profs = sheet.proficiencies ?? {};

  // ── Headline ─────────────────────────────────────────────────────────

  const headline = [
    sheet.level != null && `Level ${sheet.level}`,
    sheet.class_and_subclass,
    sheet.dual_class && `/ ${sheet.dual_class}`,
    sheet.race_or_ancestry,
    sheet.heritage && `(${sheet.heritage})`,
  ]
    .filter(Boolean)
    .join(' ');

  const infoLine = [
    sheet.background && `Background: ${sheet.background}`,
    sheet.alignment && `Alignment: ${sheet.alignment}`,
    sheet.deity && `Deity: ${sheet.deity}`,
    sheet.size && `Size: ${sheet.size}`,
  ].filter(Boolean);

  // ── Ability scores ───────────────────────────────────────────────────

  const hasAbilities =
    sheet.ability_scores != null &&
    ABILITY_KEYS.some((k) => sheet.ability_scores![k] != null);

  // ── Saving throws ───────────────────────────────────────────────────

  const saves = sheet.saving_throws;
  const hasSaves =
    saves != null &&
    (saves.fortitude != null || saves.reflex != null || saves.will != null);

  // ── Skills ───────────────────────────────────────────────────────────

  const hasSkills =
    isPf2e && PF2E_SKILLS.some((s) => profs[s.key] != null && profs[s.key]! > 0);
  const loreSkills = sheet.lore_skills ?? [];

  // ── Combat ───────────────────────────────────────────────────────────

  const attacks = sheet.attacks ?? [];
  const armorList = sheet.armor ?? [];
  const classDC = profs.classDC;

  // ── Spells ───────────────────────────────────────────────────────────

  const spells = sheet.spells ?? [];

  // ── Features / feats ─────────────────────────────────────────────────

  const features = (sheet.features_and_traits ?? []).map(String);

  // ── Inventory ────────────────────────────────────────────────────────

  const inventory = (sheet.inventory ?? []).map(String);
  const currency = sheet.currency;
  const hasCurrency = currency && Object.values(currency).some((v) => v > 0);

  // ── Languages ────────────────────────────────────────────────────────

  const languages = sheet.languages ?? [];

  // ── Weapon / Armor proficiencies ─────────────────────────────────────

  const weaponProfs = ['unarmed', 'simple', 'martial', 'advanced']
    .filter((k) => profs[k] != null && profs[k]! > 0)
    .map((k) => ({ key: k, label: k.charAt(0).toUpperCase() + k.slice(1), rank: profs[k]! }));

  const armorProfs = ['unarmored', 'light', 'medium', 'heavy']
    .filter((k) => profs[k] != null && profs[k]! > 0)
    .map((k) => ({ key: k, label: k.charAt(0).toUpperCase() + k.slice(1), rank: profs[k]! }));

  // ────────────────────────────────────────────────────────────────────

  return (
    <Box sx={{ mt: 0.5 }}>
      {/* ── Header ──────────────────────────────────────────── */}
      {headline && (
        <Typography variant="subtitle2" fontWeight={700} gutterBottom>
          {headline}
        </Typography>
      )}
      {infoLine.length > 0 && (
        <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ mb: 1 }}>
          {infoLine.map((info) => (
            <Typography key={info} variant="caption" color="text.secondary">
              {info}
            </Typography>
          ))}
        </Stack>
      )}

      {/* ── Combat Stats Row ────────────────────────────────── */}
      <Box
        sx={{
          display: 'flex',
          gap: 1.5,
          flexWrap: 'wrap',
          justifyContent: 'center',
          py: 1.5,
          px: 1,
          bgcolor: 'background.default',
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'divider',
          mb: 1.5,
        }}
      >
        {sheet.armor_class != null && (
          <StatBox label="AC" value={String(sheet.armor_class)} />
        )}
        {sheet.hp?.max != null && (
          <StatBox label="HP" value={String(sheet.hp.max)} />
        )}
        {sheet.speed && <StatBox label="Speed" value={sheet.speed} />}
        {sheet.perception != null && isPf2e && (
          <StatBox label="Perception" value={profLabel(sheet.perception)} color={profColor(sheet.perception)} />
        )}
        {classDC != null && isPf2e && (
          <StatBox label="Class DC" value={profLabel(classDC)} color={profColor(classDC)} />
        )}
        {sheet.proficiency_bonus != null && !isPf2e && (
          <StatBox label="Prof" value={`+${sheet.proficiency_bonus}`} />
        )}
      </Box>

      {/* ── Ability Scores ──────────────────────────────────── */}
      {hasAbilities && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap" justifyContent="center" sx={{ mb: 1.5 }}>
          {ABILITY_KEYS.map((k) => {
            const val = sheet.ability_scores![k];
            if (val == null) return null;
            return (
              <Box
                key={k}
                sx={{
                  textAlign: 'center',
                  minWidth: 44,
                  py: 0.5,
                  px: 0.75,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                }}
              >
                <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.2}>
                  {k}
                </Typography>
                <Typography variant="body2" fontWeight={700} lineHeight={1.3}>
                  {val}
                </Typography>
                <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
                  {abilityMod(val)}
                </Typography>
              </Box>
            );
          })}
        </Stack>
      )}

      {/* ── Saving Throws ───────────────────────────────────── */}
      {hasSaves && (
        <SectionBlock title="Saving Throws">
          <Stack direction="row" spacing={2} flexWrap="wrap" justifyContent="center">
            {(['fortitude', 'reflex', 'will'] as const).map((save) => {
              const val = saves![save];
              if (val == null) return null;
              return (
                <Box key={save} sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.disabled" display="block" textTransform="capitalize">
                    {save}
                  </Typography>
                  <Chip
                    label={isPf2e ? profLabel(val) : String(val)}
                    size="small"
                    color={isPf2e ? profColor(val) : 'default'}
                    variant="outlined"
                  />
                </Box>
              );
            })}
          </Stack>
        </SectionBlock>
      )}

      {/* ── Skills ──────────────────────────────────────────── */}
      {(hasSkills || loreSkills.length > 0) && (
        <CollapsibleSection title="Skills" defaultOpen={false}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
              gap: 0.25,
            }}
          >
            {PF2E_SKILLS.map((s) => {
              const rank = profs[s.key];
              if (rank == null) return null;
              return (
                <SkillRow key={s.key} label={s.label} rank={rank} trained={rank > 0} />
              );
            })}
            {loreSkills.map((lore, i) => (
              <SkillRow key={`lore-${i}`} label={`${lore.name} Lore`} rank={lore.rank} trained={lore.rank > 0} />
            ))}
          </Box>
        </CollapsibleSection>
      )}

      {/* ── Strikes / Attacks ───────────────────────────────── */}
      {attacks.length > 0 && (
        <CollapsibleSection title="Strikes" defaultOpen>
          <Stack spacing={1} divider={<Divider />}>
            {attacks.map((atk, i) => {
              const name = String(atk.name || atk.display || `Attack ${i + 1}`);
              const die = atk.die ? String(atk.die) : null;
              const dmgType = atk.damage_type ? String(atk.damage_type) : null;
              const pot = typeof atk.pot === 'number' && atk.pot > 0 ? atk.pot : null;
              const striking = typeof atk.str === 'number' && atk.str > 0 ? atk.str : null;
              const runes =
                Array.isArray(atk.runes) ? (atk.runes as string[]).filter(Boolean) : [];

              return (
                <Box key={i}>
                  <Typography variant="body2" fontWeight={600}>
                    {name}
                    {pot ? ` (+${pot})` : ''}
                  </Typography>
                  <Stack direction="row" spacing={1.5} flexWrap="wrap">
                    {die && (
                      <Typography variant="caption" color="text.secondary">
                        {die}
                        {dmgType ? ` ${dmgType}` : ''}
                      </Typography>
                    )}
                    {striking && (
                      <Typography variant="caption" color="text.secondary">
                        +{striking} striking
                      </Typography>
                    )}
                    {runes.length > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        {runes.join(', ')}
                      </Typography>
                    )}
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        </CollapsibleSection>
      )}

      {/* ── Armor ───────────────────────────────────────────── */}
      {armorList.length > 0 && (
        <CollapsibleSection title="Armor" defaultOpen={false}>
          <Stack spacing={0.75} divider={<Divider />}>
            {armorList.map((arm, i) => {
              const name = String(arm.display || arm.name || `Armor ${i + 1}`);
              const worn = arm.worn ? ' (worn)' : '';
              const pot = typeof arm.pot === 'number' && arm.pot > 0 ? arm.pot : null;
              const res = typeof arm.res === 'number' && arm.res > 0 ? arm.res : null;
              const runes =
                Array.isArray(arm.runes) ? (arm.runes as string[]).filter(Boolean) : [];

              return (
                <Box key={i}>
                  <Typography variant="body2" fontWeight={600}>
                    {name}{worn}
                  </Typography>
                  <Stack direction="row" spacing={1.5} flexWrap="wrap">
                    {pot && (
                      <Typography variant="caption" color="text.secondary">
                        +{pot} potency
                      </Typography>
                    )}
                    {res && (
                      <Typography variant="caption" color="text.secondary">
                        +{res} resilient
                      </Typography>
                    )}
                    {runes.length > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        {runes.join(', ')}
                      </Typography>
                    )}
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        </CollapsibleSection>
      )}

      {/* ── Weapon & Armor Proficiencies ────────────────────── */}
      {(weaponProfs.length > 0 || armorProfs.length > 0) && (
        <CollapsibleSection title="Weapon & Armor Proficiencies" defaultOpen={false}>
          {weaponProfs.length > 0 && (
            <Box mb={armorProfs.length > 0 ? 1 : 0}>
              <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" mb={0.5}>
                Weapons
              </Typography>
              <Stack direction="row" spacing={0.75} flexWrap="wrap">
                {weaponProfs.map((p) => (
                  <Chip
                    key={p.key}
                    label={`${p.label}: ${profAbbr(p.rank)}`}
                    size="small"
                    color={profColor(p.rank)}
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Box>
          )}
          {armorProfs.length > 0 && (
            <Box>
              <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" mb={0.5}>
                Armor
              </Typography>
              <Stack direction="row" spacing={0.75} flexWrap="wrap">
                {armorProfs.map((p) => (
                  <Chip
                    key={p.key}
                    label={`${p.label}: ${profAbbr(p.rank)}`}
                    size="small"
                    color={profColor(p.rank)}
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Box>
          )}
        </CollapsibleSection>
      )}

      {/* ── Spells ──────────────────────────────────────────── */}
      {spells.length > 0 && (
        <CollapsibleSection title="Spells" defaultOpen>
          {spells.map((caster, ci) => (
            <Box key={ci} sx={ci > 0 ? { mt: 2 } : undefined}>
              <Stack direction="row" spacing={1} alignItems="center" mb={0.75}>
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
                      <Box key={li} sx={{ mb: 0.75 }}>
                        <Typography variant="caption" fontWeight={600} color="text.secondary">
                          {lvl.level === 0 ? 'Cantrips' : `Rank ${lvl.level}`}
                          {Array.isArray(caster.per_day) &&
                          typeof (caster.per_day as number[])[lvl.level] === 'number'
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
        </CollapsibleSection>
      )}

      {/* ── Features & Feats ────────────────────────────────── */}
      {features.length > 0 && (
        <CollapsibleSection title="Features & Feats" defaultOpen={false}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {features.map((feat, i) => (
              <Chip key={i} label={feat} size="small" variant="outlined" />
            ))}
          </Stack>
        </CollapsibleSection>
      )}

      {/* ── Inventory & Wealth ──────────────────────────────── */}
      {(inventory.length > 0 || hasCurrency) && (
        <CollapsibleSection title="Inventory & Wealth" defaultOpen={false}>
          {inventory.length > 0 && (
            <Stack spacing={0.15}>
              {inventory.map((item, i) => (
                <Typography key={i} variant="body2">
                  • {item}
                </Typography>
              ))}
            </Stack>
          )}
          {hasCurrency && (
            <Box
              sx={{
                mt: inventory.length > 0 ? 1.5 : 0,
                pt: inventory.length > 0 ? 1 : 0,
                borderTop: inventory.length > 0 ? '1px solid' : 'none',
                borderColor: 'divider',
              }}
            >
              <Typography variant="caption" fontWeight={600} color="text.secondary">
                Wealth
              </Typography>
              <Stack direction="row" spacing={2} mt={0.5}>
                {currency!.pp != null && currency!.pp > 0 && (
                  <CurrencyChip label="PP" value={currency!.pp} />
                )}
                {currency!.gp != null && currency!.gp > 0 && (
                  <CurrencyChip label="GP" value={currency!.gp} />
                )}
                {currency!.sp != null && currency!.sp > 0 && (
                  <CurrencyChip label="SP" value={currency!.sp} />
                )}
                {currency!.cp != null && currency!.cp > 0 && (
                  <CurrencyChip label="CP" value={currency!.cp} />
                )}
              </Stack>
            </Box>
          )}
        </CollapsibleSection>
      )}

      {/* ── Languages ───────────────────────────────────────── */}
      {languages.length > 0 && (
        <SectionBlock title="Languages">
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {languages.map((lang, i) => (
              <Chip key={i} label={lang} size="small" variant="outlined" />
            ))}
          </Stack>
        </SectionBlock>
      )}
    </Box>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

/** Big stat number (AC, HP, Speed, etc.). */
function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: 'default' | 'info' | 'primary' | 'warning' | 'success';
}) {
  return (
    <Box sx={{ textAlign: 'center', minWidth: 52 }}>
      <Typography variant="caption" color="text.disabled" display="block" lineHeight={1.4}>
        {label}
      </Typography>
      {color && color !== 'default' ? (
        <Chip label={value} size="small" color={color} variant="outlined" />
      ) : (
        <Typography variant="h6" fontWeight={700} lineHeight={1.3}>
          {value}
        </Typography>
      )}
    </Box>
  );
}

/** A non-collapsible labeled section. */
function SectionBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box
      sx={{
        mb: 1.5,
        p: 1.25,
        bgcolor: 'background.default',
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography
        variant="overline"
        color="text.secondary"
        display="block"
        lineHeight={1.6}
        sx={{ mb: 0.5 }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

/** A collapsible section with toggle arrow. */
function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Box
      sx={{
        mb: 1,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
      }}
    >
      <Box
        onClick={() => setOpen((v) => !v)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.25,
          py: 0.75,
          cursor: 'pointer',
          bgcolor: 'action.hover',
          '&:hover': { bgcolor: 'action.selected' },
          userSelect: 'none',
        }}
      >
        <Typography variant="overline" color="text.secondary" lineHeight={1.6}>
          {title}
        </Typography>
        <IconButton
          size="small"
          sx={{
            p: 0.25,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={open}>
        <Box sx={{ px: 1.25, py: 1 }}>{children}</Box>
      </Collapse>
    </Box>
  );
}

/** Single skill row with proficiency indicator. */
function SkillRow({
  label,
  rank,
  trained,
}: {
  label: string;
  rank: number;
  trained: boolean;
}) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      justifyContent="space-between"
      sx={{
        py: 0.25,
        px: 0.5,
        opacity: trained ? 1 : 0.5,
      }}
    >
      <Typography variant="body2" noWrap sx={{ flex: 1 }}>
        {label}
      </Typography>
      <Chip
        label={profAbbr(rank)}
        size="small"
        color={profColor(rank)}
        variant={trained ? 'filled' : 'outlined'}
        sx={{ minWidth: 28, '& .MuiChip-label': { px: 0.75 } }}
      />
    </Stack>
  );
}

/** Compact currency indicator. */
function CurrencyChip({ label, value }: { label: string; value: number }) {
  return (
    <Box sx={{ textAlign: 'center' }}>
      <Typography variant="body2" fontWeight={700}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.disabled">
        {label}
      </Typography>
    </Box>
  );
}
