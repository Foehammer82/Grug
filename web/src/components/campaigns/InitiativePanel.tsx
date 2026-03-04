import { useEffect, useState } from 'react';
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import type { Character, CombatTrackerDepth, Combatant, Encounter, MonsterSearchResult, SavingThrowResult } from '../../types';

interface InitiativePanelProps {
  guildId: string;
  campaignId: number;
  isGm: boolean;
  depth: CombatTrackerDepth;
  currentUserId: string;
}

const STATUS_COLORS: Record<string, string> = {
  preparing: 'warning.main',
  active: 'primary.main',
  ended: 'text.disabled',
};

const ABILITIES = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

export default function InitiativePanel({ guildId, campaignId, isGm, depth, currentUserId }: InitiativePanelProps) {
  const qc = useQueryClient();
  const canManage = isGm;
  const showHp = depth !== 'basic';
  const showFull = depth === 'full';

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['encounter-active', guildId, campaignId] });

  // --- Active encounter query ---
  const { data: encounter, isLoading } = useQuery<Encounter | null>({
    queryKey: ['encounter-active', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Encounter | null>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/active`,
      );
      return res.data;
    },
    refetchInterval: 3000,
  });

  // --- Create encounter ---
  const [newEncounterName, setNewEncounterName] = useState('');
  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await client.post<Encounter>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters`,
        { name },
      );
      return res.data;
    },
    onSuccess: () => {
      invalidate();
      setNewEncounterName('');
    },
  });

  // --- Encounter list (for auto-naming new encounters) ---
  const { data: encounterList = [] } = useQuery<Encounter[]>({
    queryKey: ['encounters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Encounter[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters`,
      );
      return res.data;
    },
    staleTime: 30_000,
    enabled: isGm,
  });
  const suggestedEncounterName = `Encounter ${encounterList.length + 1}`;

  // --- Rename encounter / combatant ---
  const [editingEncounterName, setEditingEncounterName] = useState(false);
  const [encounterNameInput, setEncounterNameInput] = useState('');

  const renameEncounterMutation = useMutation({
    mutationFn: async (name: string) => {
      if (!encounter) return;
      await client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}`,
        { name },
      );
    },
    onSuccess: invalidate,
  });

  const renameCombatantMutation = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      if (!encounter) return;
      await client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${id}`,
        { name },
      );
    },
    onSuccess: invalidate,
  });

  // --- Campaign characters (for player self-join) ---
  const { data: campaignCharacters = [] } = useQuery<Character[]>({
    queryKey: ['campaign-characters', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<Character[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/characters`,
      );
      return res.data;
    },
    staleTime: 30_000,
  });

  // My characters that aren't already in the encounter
  const myCharacters = campaignCharacters.filter(
    (ch) => ch.owner_discord_user_id === currentUserId,
  );

  // --- Add combatant (GM free-form) ---
  const [combatantName, setCombatantName] = useState('');
  const [combatantMod, setCombatantMod] = useState('');
  const [combatantEnemy, setCombatantEnemy] = useState(false);
  const [combatantHp, setCombatantHp] = useState('');
  const [combatantAc, setCombatantAc] = useState('');

  // --- Monster search (GM) ---
  const [monsterQuery, setMonsterQuery] = useState('');
  const [debouncedMonsterQuery, setDebouncedMonsterQuery] = useState('');
  useEffect(() => {
    if (!monsterQuery.trim()) {
      setDebouncedMonsterQuery('');
      return;
    }
    const t = setTimeout(() => setDebouncedMonsterQuery(monsterQuery.trim()), 400);
    return () => clearTimeout(t);
  }, [monsterQuery]);

  const { data: monsterResults = [], isFetching: monstersLoading } = useQuery<MonsterSearchResult[]>({
    queryKey: ['monster-search', debouncedMonsterQuery],
    queryFn: async () => {
      if (!debouncedMonsterQuery) return [];
      const res = await client.get<MonsterSearchResult[]>('/api/monsters/search', {
        params: { q: debouncedMonsterQuery, limit: 8 },
      });
      return res.data;
    },
    enabled: debouncedMonsterQuery.length >= 2,
    staleTime: 60_000,
  });

  const addCombatantMutation = useMutation({
    mutationFn: async (payload: {
      name: string;
      initiative_modifier: number;
      is_enemy: boolean;
      character_id?: number;
      max_hp?: number;
      armor_class?: number;
    } | undefined) => {
      if (!encounter) return;
      // Auto-generate a name if the GM left the name field blank
      const enemyCount = encounter.combatants.filter((c) => c.is_enemy && c.is_active).length;
      const allyCount = encounter.combatants.filter((c) => !c.is_enemy && c.is_active).length;
      const autoName = combatantEnemy ? `Enemy ${enemyCount + 1}` : `Ally ${allyCount + 1}`;
      const body = payload ?? {
        name: combatantName.trim() || autoName,
        initiative_modifier: combatantMod ? parseInt(combatantMod, 10) : 0,
        is_enemy: combatantEnemy,
        ...(combatantHp ? { max_hp: parseInt(combatantHp, 10) } : {}),
        ...(combatantAc ? { armor_class: parseInt(combatantAc, 10) } : {}),
      };
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants`,
        body,
      );
    },
    onSuccess: () => {
      invalidate();
      setCombatantName('');
      setCombatantMod('');
      setCombatantEnemy(false);
      setCombatantHp('');
      setCombatantAc('');
    },
  });

  // --- Remove combatant ---
  const removeCombatantMutation = useMutation({
    mutationFn: async (combatantId: number) => {
      if (!encounter) return;
      await client.delete(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${combatantId}`,
      );
    },
    onSuccess: invalidate,
  });

  // --- Roll initiative (start encounter) ---
  const rollMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/start`,
      );
    },
    onSuccess: invalidate,
  });

  // --- Advance turn ---
  const advanceMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/advance`,
      );
    },
    onSuccess: invalidate,
  });

  // --- End encounter ---
  const endMutation = useMutation({
    mutationFn: async () => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/end`,
      );
    },
    onSuccess: invalidate,
  });

  // --- Damage ---
  const damageMutation = useMutation({
    mutationFn: async (args: { ids: number[]; amount: number; damage_type?: string }) => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/damage`,
        { combatant_ids: args.ids, amount: args.amount, damage_type: args.damage_type },
      );
    },
    onSuccess: invalidate,
  });

  // --- Heal ---
  const healMutation = useMutation({
    mutationFn: async (args: { ids: number[]; amount: number }) => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/heal`,
        { combatant_ids: args.ids, amount: args.amount },
      );
    },
    onSuccess: invalidate,
  });

  // --- Condition ---
  const conditionMutation = useMutation({
    mutationFn: async (args: { combatantId: number; condition: string; remove: boolean }) => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${args.combatantId}/condition`,
        { condition: args.condition, remove: args.remove },
      );
    },
    onSuccess: invalidate,
  });

  // --- Death save ---
  const deathSaveMutation = useMutation({
    mutationFn: async (combatantId: number) => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${combatantId}/death-save`,
      );
    },
    onSuccess: invalidate,
  });

  // --- Concentration ---
  const concentrationMutation = useMutation({
    mutationFn: async (args: { combatantId: number; spell: string | null }) => {
      if (!encounter) return;
      await client.post(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${args.combatantId}/concentration`,
        { spell: args.spell },
      );
    },
    onSuccess: invalidate,
  });

  // --- Set initiative roll (manual) ---
  const setInitiativeMutation = useMutation({
    mutationFn: async (args: { combatantId: number; roll: number }) => {
      if (!encounter) return;
      await client.patch(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/combatants/${args.combatantId}/initiative`,
        { initiative_roll: args.roll },
      );
    },
    onSuccess: invalidate,
  });

  // --- Saving throw ---
  const [saveResults, setSaveResults] = useState<SavingThrowResult[] | null>(null);
  const saveMutation = useMutation({
    mutationFn: async (args: { ids: number[]; ability: string; dc: number }) => {
      if (!encounter) return [];
      const res = await client.post<SavingThrowResult[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/encounters/${encounter.id}/saving-throw`,
        { combatant_ids: args.ids, ability: args.ability, dc: args.dc },
      );
      return res.data;
    },
    onSuccess: (data) => {
      invalidate();
      setSaveResults(data ?? null);
    },
  });

  // --- Damage/Heal dialog state ---
  const [dhDialog, setDhDialog] = useState<{
    type: 'damage' | 'heal';
    combatantId: number;
    name: string;
  } | null>(null);
  const [dhAmount, setDhAmount] = useState('');
  const [dhDamageType, setDhDamageType] = useState('');

  // --- Save dialog state ---
  const [saveDialog, setSaveDialog] = useState(false);
  const [saveAbility, setSaveAbility] = useState('DEX');
  const [saveDc, setSaveDc] = useState('');
  const [saveTargetIds, setSaveTargetIds] = useState<number[]>([]);

  // --- Condition dialog state ---
  const [condDialog, setCondDialog] = useState<{
    combatantId: number;
    name: string;
  } | null>(null);
  const [condName, setCondName] = useState('');

  // --- Concentration dialog state ---
  const [concDialog, setConcDialog] = useState<{
    combatantId: number;
    name: string;
    current: string | null;
  } | null>(null);
  const [concSpell, setConcSpell] = useState('');

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  // ── No active encounter — show create form ──────────────────────
  if (!encounter) {
    return (
      <Box>
        {canManage ? (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              No active encounter. Create one to get started with initiative tracking.
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>
              💡 After creating, add combatants (PCs and monsters), then click <strong>Roll Initiative</strong> to begin.
              Players can also join from their own dashboard during setup.
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                size="small"
                label="Encounter name"
                value={newEncounterName}
                onChange={(e) => setNewEncounterName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    createMutation.mutate(newEncounterName.trim() || suggestedEncounterName);
                  }
                }}
                placeholder={suggestedEncounterName}
                sx={{ width: 220 }}
              />
              <Button
                variant="contained"
                size="small"
                startIcon={<PlayArrowIcon />}
                disabled={createMutation.isPending}
                onClick={() => createMutation.mutate(newEncounterName.trim() || suggestedEncounterName)}
              >
                {createMutation.isPending ? 'Creating…' : 'Start Encounter'}
              </Button>
            </Stack>
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No active encounter. When the GM starts one, you'll be able to join with your character
            from here or via <code>/initiative add</code> in Discord.
          </Typography>
        )}
      </Box>
    );
  }

  // ── Active encounter view ───────────────────────────────────────
  const activeCombatants = encounter.combatants.filter((c) => c.is_active);
  const isPreparing = encounter.status === 'preparing';
  const isActive = encounter.status === 'active';

  return (
    <Box>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        {editingEncounterName && canManage ? (
          <TextField
            size="small"
            autoFocus
            value={encounterNameInput}
            onChange={(e) => setEncounterNameInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && encounterNameInput.trim()) {
                renameEncounterMutation.mutate(encounterNameInput.trim());
                setEditingEncounterName(false);
              } else if (e.key === 'Escape') {
                setEditingEncounterName(false);
              }
            }}
            onBlur={() => {
              if (encounterNameInput.trim()) renameEncounterMutation.mutate(encounterNameInput.trim());
              setEditingEncounterName(false);
            }}
            sx={{ width: 200 }}
            slotProps={{ htmlInput: { sx: { py: 0.25, px: 0.5, fontSize: '0.925rem', fontWeight: 600 } } }}
          />
        ) : (
          <Tooltip title={canManage ? 'Click to rename' : ''} placement="top">
            <Typography
              variant="subtitle1"
              fontWeight={600}
              onClick={() => {
                if (canManage) {
                  setEncounterNameInput(encounter.name);
                  setEditingEncounterName(true);
                }
              }}
              sx={canManage ? { cursor: 'pointer', '&:hover': { color: 'primary.main' } } : {}}
            >
              ⚔️ {encounter.name}
            </Typography>
          </Tooltip>
        )}
        <Chip
          label={encounter.status.charAt(0).toUpperCase() + encounter.status.slice(1)}
          size="small"
          sx={{
            height: 20,
            fontSize: '0.7rem',
            color: STATUS_COLORS[encounter.status],
            borderColor: STATUS_COLORS[encounter.status],
          }}
          variant="outlined"
        />
        {isActive && (
          <Typography variant="caption" color="text.secondary">
            Round {encounter.round_number}
          </Typography>
        )}
        <Box sx={{ flex: 1 }} />
        {/* GM action buttons */}
        {canManage && isPreparing && activeCombatants.length > 0 && (
          <Button
            variant="contained"
            size="small"
            color="success"
            startIcon={<PlayArrowIcon />}
            disabled={rollMutation.isPending}
            onClick={() => rollMutation.mutate()}
          >
            {rollMutation.isPending ? 'Rolling…' : 'Roll Initiative'}
          </Button>
        )}
        {canManage && isActive && (
          <>
            <Button
              variant="contained"
              size="small"
              startIcon={<NavigateNextIcon />}
              disabled={advanceMutation.isPending}
              onClick={() => advanceMutation.mutate()}
            >
              Next Turn
            </Button>
            {showHp && (
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setSaveTargetIds(activeCombatants.map((c) => c.id));
                  setSaveDialog(true);
                }}
              >
                Group Save
              </Button>
            )}
          </>
        )}
        {canManage && (isPreparing || isActive) && (
          <Button
            variant="outlined"
            size="small"
            color="error"
            startIcon={<StopIcon />}
            disabled={endMutation.isPending}
            onClick={() => endMutation.mutate()}
          >
            End
          </Button>
        )}
      </Stack>

      {/* Combatant list */}
      {activeCombatants.length === 0 ? (
        <Box sx={{ py: 1 }}>
          <Typography variant="body2" color="text.secondary">
            No combatants yet.
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {canManage
              ? '💡 Add PCs and monsters below. Players can also join from their own dashboard. Once everyone\'s in, hit Roll Initiative to begin!'
              : '💡 Click your character below to join the encounter. The GM will roll initiative for everyone when ready.'}
          </Typography>
        </Box>
      ) : (
        <Stack spacing={0.25}>
          {activeCombatants.map((c, idx) => (
            <CombatantRow
              key={c.id}
              combatant={c}
              isCurrentTurn={isActive && idx === encounter.current_turn_index}
              canManage={canManage}
              showHp={showHp}
              showFull={showFull}
              canEditRoll={
                canManage
                  ? isPreparing || isActive
                  : isPreparing && c.character_id != null && myCharacters.some((ch) => ch.id === c.character_id)
              }
              canEditName={canManage}
              onRename={(name) => renameCombatantMutation.mutate({ id: c.id, name })}
              onSetInitiative={(roll) =>
                setInitiativeMutation.mutate({ combatantId: c.id, roll })
              }
              onRemove={() => removeCombatantMutation.mutate(c.id)}
              onDamage={() => setDhDialog({ type: 'damage', combatantId: c.id, name: c.name })}
              onHeal={() => setDhDialog({ type: 'heal', combatantId: c.id, name: c.name })}
              onCondition={() => setCondDialog({ combatantId: c.id, name: c.name })}
              onRemoveCondition={(cond) =>
                conditionMutation.mutate({ combatantId: c.id, condition: cond, remove: true })
              }
              onDeathSave={() => deathSaveMutation.mutate(c.id)}
              onConcentration={() => {
                setConcDialog({
                  combatantId: c.id,
                  name: c.name,
                  current: c.concentration_spell,
                });
                setConcSpell(c.concentration_spell ?? '');
              }}
            />
          ))}
        </Stack>
      )}

      {/* Preparing-phase hint for GM */}
      {canManage && isPreparing && activeCombatants.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          💡 When everyone is added, click <strong>Roll Initiative</strong> above. Combatants with a manual roll keep their value; Grug rolls for the rest.
          You can also click any roll value to override it.
        </Typography>
      )}

      {/* GM: quick-add campaign characters */}
      {canManage && (isPreparing || isActive) && (() => {
        const alreadyInEncounter = new Set(
          encounter.combatants.filter((c) => c.character_id != null).map((c) => c.character_id),
        );
        const availablePCs = campaignCharacters.filter((ch) => !alreadyInEncounter.has(ch.id));
        if (availablePCs.length === 0) return null;
        return (
          <>
            <Divider sx={{ my: 1.5 }} />
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
              Quick-add campaign characters (stats pulled from character sheets):
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {availablePCs.map((ch) => {
                const initMod = ch.structured_data?.initiative ?? 0;
                const hp = ch.structured_data?.hp?.max ?? undefined;
                const ac = ch.structured_data?.armor_class ?? undefined;
                const subtitle = [
                  initMod !== 0 ? `Init ${initMod >= 0 ? '+' : ''}${initMod}` : null,
                  hp != null ? `HP ${hp}` : null,
                  ac != null ? `AC ${ac}` : null,
                ].filter(Boolean).join(' \u00b7 ');

                return (
                  <Tooltip key={ch.id} title={subtitle || 'No sheet data'} placement="top">
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<AddIcon />}
                      disabled={addCombatantMutation.isPending}
                      onClick={() =>
                        addCombatantMutation.mutate({
                          name: ch.name,
                          initiative_modifier: initMod,
                          is_enemy: false,
                          character_id: ch.id,
                          ...(hp != null ? { max_hp: hp } : {}),
                          ...(ac != null ? { armor_class: ac } : {}),
                        })
                      }
                    >
                      {ch.name}
                    </Button>
                  </Tooltip>
                );
              })}
            </Stack>
          </>
        );
      })()}

      {/* GM: free-form add combatant form */}
      {canManage && (isPreparing || isActive) && (
        <>
          <Divider sx={{ my: 1.5 }} />

          {/* Monster search autocomplete */}
          <Autocomplete
            size="small"
            freeSolo
            options={monsterResults}
            loading={monstersLoading}
            inputValue={monsterQuery}
            onInputChange={(_, v) => setMonsterQuery(v)}
            getOptionLabel={(opt) => typeof opt === 'string' ? opt : opt.name}
            filterOptions={(x) => x}
            isOptionEqualToValue={(a, b) => a.name === b.name && a.source === b.source}
            onChange={(_, val) => {
              if (val && typeof val !== 'string') {
                setCombatantName(val.name);
                setCombatantMod(val.initiative_modifier != null ? String(val.initiative_modifier) : '');
                setCombatantHp(val.hp != null ? String(val.hp) : '');
                setCombatantAc(val.ac != null ? String(val.ac) : '');
                setCombatantEnemy(true);
                setMonsterQuery('');
              }
            }}
            renderOption={(props, opt) => (
              <Box component="li" {...props} key={`${opt.source}-${opt.name}`}>
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="body2">{opt.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {[
                      opt.cr,
                      opt.size,
                      opt.type,
                      opt.hp != null ? `HP ${opt.hp}` : null,
                      opt.ac != null ? `AC ${opt.ac}` : null,
                      opt.initiative_modifier != null ? `Init ${opt.initiative_modifier >= 0 ? '+' : ''}${opt.initiative_modifier}` : null,
                    ].filter(Boolean).join(' · ')}
                    {' — '}
                    {opt.source === 'srd_5e' ? '5e SRD' : opt.source === 'aon_pf2e' ? 'PF2e (AoN)' : opt.source}
                  </Typography>
                </Box>
              </Box>
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                label="🔍 Search monsters"
                placeholder="e.g. Goblin, Owlbear, Adult Red Dragon"
                helperText="Select a monster to auto-fill stats below, or type freely to add a custom combatant."
                slotProps={{
                  input: {
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {monstersLoading ? <CircularProgress color="inherit" size={16} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  },
                }}
              />
            )}
            sx={{ mb: 1.5, maxWidth: 500 }}
          />

          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            Add combatants by name. Players can also join from their own dashboard.
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="Name"
              value={combatantName}
              onChange={(e) => setCombatantName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && combatantName.trim()) {
                  addCombatantMutation.mutate(undefined);
                }
              }}
              placeholder="Goblin 1"
              sx={{ width: 150 }}
            />
            <Tooltip title="Initiative modifier — usually the creature's DEX modifier" placement="top">
              <TextField
                size="small"
                label="Init mod"
                type="number"
                value={combatantMod}
                onChange={(e) => setCombatantMod(e.target.value)}
                sx={{ width: 80 }}
                placeholder="+3"
              />
            </Tooltip>
            {showHp && (
              <>
                <Tooltip title="Max hit points" placement="top">
                  <TextField
                    size="small"
                    label="HP"
                    type="number"
                    value={combatantHp}
                    onChange={(e) => setCombatantHp(e.target.value)}
                    sx={{ width: 70 }}
                    placeholder="45"
                  />
                </Tooltip>
                <Tooltip title="Armor class" placement="top">
                  <TextField
                    size="small"
                    label="AC"
                    type="number"
                    value={combatantAc}
                    onChange={(e) => setCombatantAc(e.target.value)}
                    sx={{ width: 60 }}
                    placeholder="15"
                  />
                </Tooltip>
              </>
            )}
            <Tooltip title={combatantEnemy ? 'Click to switch to ally' : 'Click to switch to enemy/monster'}>
              <Chip
                label={combatantEnemy ? '👹 Enemy' : '🛡️ Ally'}
                size="small"
                variant={combatantEnemy ? 'filled' : 'outlined'}
                color={combatantEnemy ? 'error' : 'default'}
                onClick={() => setCombatantEnemy(!combatantEnemy)}
                sx={{ cursor: 'pointer', height: 28 }}
              />
            </Tooltip>
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              disabled={!combatantName.trim() || addCombatantMutation.isPending}
              onClick={() => addCombatantMutation.mutate(undefined)}
            >
              Add
            </Button>
          </Stack>
        </>
      )}

      {/* Player: character-based join buttons */}
      {!canManage && isPreparing && (() => {
        const alreadyInEncounter = new Set(
          encounter.combatants.filter((c) => c.character_id != null).map((c) => c.character_id),
        );
        const available = myCharacters.filter((ch) => !alreadyInEncounter.has(ch.id));
        const allJoined = myCharacters.length > 0 && available.length === 0;

        if (myCharacters.length === 0) {
          return (
            <>
              <Divider sx={{ my: 1.5 }} />
              <Typography variant="body2" color="text.secondary">
                You don't have a character in this campaign yet. Ask the GM to add one for you,
                or use <code>/initiative add</code> in Discord.
              </Typography>
            </>
          );
        }

        if (allJoined) {
          return (
            <>
              <Divider sx={{ my: 1.5 }} />
              <Typography variant="body2" color="text.secondary">
                ✅ {myCharacters.length === 1 ? 'Your character is' : 'All your characters are'} in the encounter.
                Click the roll value (or "—") to enter a manual roll from physical dice — otherwise Grug rolls for you.
              </Typography>
            </>
          );
        }

        return (
          <>
            <Divider sx={{ my: 1.5 }} />
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
              🛡️ Click a character to join the encounter. Stats are pulled from your character sheet.
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {available.map((ch) => {
                const initMod = ch.structured_data?.initiative ?? 0;
                const hp = ch.structured_data?.hp?.max ?? undefined;
                const ac = ch.structured_data?.armor_class ?? undefined;
                const subtitle = [
                  initMod !== 0 ? `Init ${initMod >= 0 ? '+' : ''}${initMod}` : null,
                  hp != null ? `HP ${hp}` : null,
                  ac != null ? `AC ${ac}` : null,
                ].filter(Boolean).join(' · ');

                return (
                  <Tooltip key={ch.id} title={subtitle || 'No sheet data — will join with +0 modifier'} placement="top">
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<AddIcon />}
                      disabled={addCombatantMutation.isPending}
                      onClick={() =>
                        addCombatantMutation.mutate({
                          name: ch.name,
                          initiative_modifier: initMod,
                          is_enemy: false,
                          character_id: ch.id,
                          ...(hp != null ? { max_hp: hp } : {}),
                          ...(ac != null ? { armor_class: ac } : {}),
                        })
                      }
                    >
                      {ch.name}
                    </Button>
                  </Tooltip>
                );
              })}
            </Stack>
          </>
        );
      })()}

      {/* Player hint when encounter is active */}
      {!canManage && isActive && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Combat is underway! Ask the GM to add you if you need to join mid-combat.
        </Typography>
      )}

      {/* ── Damage / Heal dialog ─────────────────────────────────── */}
      <Dialog
        open={!!dhDialog}
        onClose={() => {
          setDhDialog(null);
          setDhAmount('');
          setDhDamageType('');
        }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          {dhDialog?.type === 'damage' ? '💥 Damage' : '💚 Heal'} — {dhDialog?.name}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="Amount"
              type="number"
              size="small"
              value={dhAmount}
              onChange={(e) => setDhAmount(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && dhAmount && dhDialog) {
                  const amt = parseInt(dhAmount, 10);
                  if (amt > 0) {
                    if (dhDialog.type === 'damage') {
                      damageMutation.mutate({
                        ids: [dhDialog.combatantId],
                        amount: amt,
                        damage_type: dhDamageType || undefined,
                      });
                    } else {
                      healMutation.mutate({ ids: [dhDialog.combatantId], amount: amt });
                    }
                    setDhDialog(null);
                    setDhAmount('');
                    setDhDamageType('');
                  }
                }
              }}
            />
            {dhDialog?.type === 'damage' && (
              <TextField
                label="Damage type (optional)"
                size="small"
                value={dhDamageType}
                onChange={(e) => setDhDamageType(e.target.value)}
                placeholder="fire, slashing, etc."
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setDhDialog(null); setDhAmount(''); setDhDamageType(''); }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color={dhDialog?.type === 'damage' ? 'error' : 'success'}
            disabled={!dhAmount || parseInt(dhAmount, 10) <= 0}
            onClick={() => {
              if (!dhDialog) return;
              const amt = parseInt(dhAmount, 10);
              if (dhDialog.type === 'damage') {
                damageMutation.mutate({
                  ids: [dhDialog.combatantId],
                  amount: amt,
                  damage_type: dhDamageType || undefined,
                });
              } else {
                healMutation.mutate({ ids: [dhDialog.combatantId], amount: amt });
              }
              setDhDialog(null);
              setDhAmount('');
              setDhDamageType('');
            }}
          >
            {dhDialog?.type === 'damage' ? 'Deal Damage' : 'Heal'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Group Saving Throw dialog ────────────────────────────── */}
      <Dialog
        open={saveDialog}
        onClose={() => { setSaveDialog(false); setSaveResults(null); }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>🎲 Group Saving Throw</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={1}>
              {ABILITIES.map((ab) => (
                <Chip
                  key={ab}
                  label={ab}
                  size="small"
                  variant={saveAbility === ab ? 'filled' : 'outlined'}
                  color={saveAbility === ab ? 'primary' : 'default'}
                  onClick={() => setSaveAbility(ab)}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Stack>
            <TextField
              label="DC"
              type="number"
              size="small"
              value={saveDc}
              onChange={(e) => setSaveDc(e.target.value)}
              sx={{ width: 100 }}
            />
            {saveResults && (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Results:</Typography>
                {saveResults.map((r) => (
                  <Typography key={r.combatant_id} variant="body2">
                    {r.passed ? '✅' : '❌'} {r.combatant_name}: {r.roll}
                    {r.modifier >= 0 ? '+' : ''}{r.modifier} = {r.total} vs DC {r.dc}
                  </Typography>
                ))}
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setSaveDialog(false); setSaveResults(null); }}>Close</Button>
          <Button
            variant="contained"
            disabled={!saveDc || saveMutation.isPending}
            onClick={() => {
              saveMutation.mutate({
                ids: saveTargetIds,
                ability: saveAbility,
                dc: parseInt(saveDc, 10),
              });
            }}
          >
            {saveMutation.isPending ? 'Rolling…' : 'Roll Saves'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Add Condition dialog ─────────────────────────────────── */}
      <Dialog
        open={!!condDialog}
        onClose={() => { setCondDialog(null); setCondName(''); }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>⚡ Add Condition — {condDialog?.name}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label="Condition name"
            size="small"
            fullWidth
            value={condName}
            onChange={(e) => setCondName(e.target.value)}
            placeholder="Prone, Frightened, etc."
            sx={{ mt: 1 }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && condName.trim() && condDialog) {
                conditionMutation.mutate({
                  combatantId: condDialog.combatantId,
                  condition: condName.trim(),
                  remove: false,
                });
                setCondDialog(null);
                setCondName('');
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setCondDialog(null); setCondName(''); }}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!condName.trim()}
            onClick={() => {
              if (!condDialog) return;
              conditionMutation.mutate({
                combatantId: condDialog.combatantId,
                condition: condName.trim(),
                remove: false,
              });
              setCondDialog(null);
              setCondName('');
            }}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Concentration dialog ─────────────────────────────────── */}
      <Dialog
        open={!!concDialog}
        onClose={() => setConcDialog(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>🔮 Concentration — {concDialog?.name}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label="Spell name (blank to clear)"
            size="small"
            fullWidth
            value={concSpell}
            onChange={(e) => setConcSpell(e.target.value)}
            sx={{ mt: 1 }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && concDialog) {
                concentrationMutation.mutate({
                  combatantId: concDialog.combatantId,
                  spell: concSpell.trim() || null,
                });
                setConcDialog(null);
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConcDialog(null)}>Cancel</Button>
          {concDialog?.current && (
            <Button
              color="warning"
              onClick={() => {
                if (!concDialog) return;
                concentrationMutation.mutate({ combatantId: concDialog.combatantId, spell: null });
                setConcDialog(null);
              }}
            >
              Clear
            </Button>
          )}
          <Button
            variant="contained"
            onClick={() => {
              if (!concDialog) return;
              concentrationMutation.mutate({
                combatantId: concDialog.combatantId,
                spell: concSpell.trim() || null,
              });
              setConcDialog(null);
            }}
          >
            Set
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

// ── HP bar color helper ────────────────────────────────────────────

function hpColor(current: number, max: number): string {
  const pct = max > 0 ? current / max : 0;
  if (pct > 0.5) return 'success.main';
  if (pct > 0.25) return 'warning.main';
  return 'error.main';
}

/** A single row in the combatant list. */
function CombatantRow({
  combatant: c,
  isCurrentTurn,
  canManage,
  showHp,
  showFull,
  canEditRoll,
  canEditName,
  onRename,
  onSetInitiative,
  onRemove,
  onDamage,
  onHeal,
  onCondition,
  onRemoveCondition,
  onDeathSave,
  onConcentration,
}: {
  combatant: Combatant;
  isCurrentTurn: boolean;
  canManage: boolean;
  showHp: boolean;
  showFull: boolean;
  canEditRoll: boolean;
  canEditName: boolean;
  onRename: (name: string) => void;
  onSetInitiative: (roll: number) => void;
  onRemove: () => void;
  onDamage: () => void;
  onHeal: () => void;
  onCondition: () => void;
  onRemoveCondition: (cond: string) => void;
  onDeathSave: () => void;
  onConcentration: () => void;
}) {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [editingRoll, setEditingRoll] = useState(false);
  const [rollInput, setRollInput] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState('');

  const hasHp = c.max_hp != null && c.current_hp != null;
  const isDown = hasHp && c.current_hp === 0;

  return (
    <Box
      sx={{
        px: 1,
        py: 0.5,
        borderRadius: 0.5,
        bgcolor: isCurrentTurn ? 'action.selected' : 'transparent',
        border: isCurrentTurn ? '1px solid' : '1px solid transparent',
        borderColor: isCurrentTurn ? 'primary.main' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
        transition: 'all 0.15s',
      }}
    >
      {/* Main row */}
      <Stack direction="row" alignItems="center" spacing={1}>
        {/* Turn marker */}
        <Typography
          variant="body2"
          sx={{
            width: 20,
            fontWeight: 700,
            color: isCurrentTurn ? 'primary.main' : 'transparent',
          }}
        >
          ▶
        </Typography>

        {/* Initiative roll — click to edit when allowed */}
        {editingRoll ? (
          <TextField
            size="small"
            type="number"
            autoFocus
            value={rollInput}
            onChange={(e) => setRollInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && rollInput) {
                onSetInitiative(parseInt(rollInput, 10));
                setEditingRoll(false);
              } else if (e.key === 'Escape') {
                setEditingRoll(false);
              }
            }}
            onBlur={() => {
              if (rollInput) {
                onSetInitiative(parseInt(rollInput, 10));
              }
              setEditingRoll(false);
            }}
            sx={{ width: 48 }}
            slotProps={{ htmlInput: { sx: { py: 0.25, px: 0.5, textAlign: 'right', fontSize: '0.875rem' } } }}
          />
        ) : (
          <Tooltip
            title={canEditRoll ? 'Click to set initiative roll (for physical dice)' : ''}
            placement="top"
          >
            <Typography
              variant="body2"
              fontWeight={700}
              onClick={() => {
                if (canEditRoll) {
                  setRollInput(c.initiative_roll != null ? String(c.initiative_roll) : '');
                  setEditingRoll(true);
                }
              }}
              sx={{
                minWidth: 32,
                textAlign: 'right',
                color: c.initiative_roll != null ? 'text.primary' : 'text.disabled',
                ...(canEditRoll && {
                  cursor: 'pointer',
                  '&:hover': { color: 'primary.main', textDecoration: 'underline' },
                }),
              }}
            >
              {c.initiative_roll ?? '—'}
            </Typography>
          </Tooltip>
        )}

        {/* Name */}
        {editingName ? (
          <TextField
            size="small"
            autoFocus
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && nameInput.trim()) {
                onRename(nameInput.trim());
                setEditingName(false);
              } else if (e.key === 'Escape') {
                setEditingName(false);
              }
            }}
            onBlur={() => {
              if (nameInput.trim()) onRename(nameInput.trim());
              setEditingName(false);
            }}
            sx={{ width: 120 }}
            slotProps={{ htmlInput: { sx: { py: 0.25, px: 0.5, fontSize: '0.875rem' } } }}
          />
        ) : (
          <Tooltip title={canEditName ? 'Click to rename' : ''} placement="top">
            <Typography
              variant="body2"
              fontWeight={500}
              noWrap
              onClick={() => { if (canEditName) { setNameInput(c.name); setEditingName(true); } }}
              sx={{ minWidth: 90, ...(canEditName && { cursor: 'pointer', '&:hover': { color: 'primary.main' } }) }}
            >
              {c.name}
            </Typography>
          </Tooltip>
        )}

        {/* Enemy badge */}
        {c.is_enemy && (
          <Chip
            label="Enemy"
            size="small"
            color="error"
            variant="outlined"
            sx={{ height: 18, fontSize: '0.6rem' }}
          />
        )}

        {/* AC badge */}
        {showHp && c.armor_class != null && (
          <Tooltip title="Armor Class">
            <Chip
              label={`AC ${c.armor_class}`}
              size="small"
              variant="outlined"
              sx={{ height: 18, fontSize: '0.6rem' }}
            />
          </Tooltip>
        )}

        {/* HP bar */}
        {showHp && hasHp && (
          <Box sx={{ flex: 1, maxWidth: 140, minWidth: 80 }}>
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <LinearProgress
                variant="determinate"
                value={c.max_hp! > 0 ? (c.current_hp! / c.max_hp!) * 100 : 0}
                sx={{
                  flex: 1,
                  height: 8,
                  borderRadius: 1,
                  bgcolor: 'action.disabledBackground',
                  '& .MuiLinearProgress-bar': {
                    bgcolor: hpColor(c.current_hp!, c.max_hp!),
                  },
                }}
              />
              <Typography variant="caption" sx={{ minWidth: 50, textAlign: 'right' }}>
                {c.current_hp}{c.temp_hp ? `+${c.temp_hp}` : ''}/{c.max_hp}
              </Typography>
            </Stack>
          </Box>
        )}

        {/* Spacer when no HP */}
        {showHp && !hasHp && <Box sx={{ flex: 1 }} />}
        {!showHp && <Box sx={{ flex: 1 }} />}

        {/* Concentration indicator */}
        {showFull && c.concentration_spell && (
          <Tooltip title={`Concentrating on ${c.concentration_spell}`}>
            <Chip
              label={`🔮 ${c.concentration_spell}`}
              size="small"
              variant="outlined"
              color="secondary"
              sx={{ height: 18, fontSize: '0.6rem' }}
            />
          </Tooltip>
        )}

        {/* Init modifier */}
        {c.initiative_modifier !== 0 && (
          <Typography variant="caption" color="text.secondary">
            ({c.initiative_modifier > 0 ? '+' : ''}{c.initiative_modifier})
          </Typography>
        )}

        {/* GM actions menu */}
        {canManage && (
          <>
            <IconButton
              size="small"
              onClick={(e) => setMenuAnchor(e.currentTarget)}
              sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}
            >
              <MoreVertIcon sx={{ fontSize: 16 }} />
            </IconButton>
            <Menu
              anchorEl={menuAnchor}
              open={!!menuAnchor}
              onClose={() => setMenuAnchor(null)}
              slotProps={{ paper: { sx: { minWidth: 140 } } }}
            >
              {showHp && hasHp && (
                <MenuItem onClick={() => { setMenuAnchor(null); onDamage(); }}>
                  💥 Damage
                </MenuItem>
              )}
              {showHp && hasHp && (
                <MenuItem onClick={() => { setMenuAnchor(null); onHeal(); }}>
                  💚 Heal
                </MenuItem>
              )}
              {showHp && (
                <MenuItem onClick={() => { setMenuAnchor(null); onCondition(); }}>
                  ⚡ Condition
                </MenuItem>
              )}
              {showFull && (
                <MenuItem onClick={() => { setMenuAnchor(null); onConcentration(); }}>
                  🔮 Concentration
                </MenuItem>
              )}
              {showFull && isDown && (
                <MenuItem onClick={() => { setMenuAnchor(null); onDeathSave(); }}>
                  💀 Death Save
                </MenuItem>
              )}
              <Divider />
              <MenuItem
                onClick={() => { setMenuAnchor(null); onRemove(); }}
                sx={{ color: 'error.main' }}
              >
                Remove
              </MenuItem>
            </Menu>
          </>
        )}
      </Stack>

      {/* Conditions row */}
      {showHp && c.conditions && c.conditions.length > 0 && (
        <Stack direction="row" spacing={0.5} sx={{ ml: '52px', mt: 0.25 }} flexWrap="wrap" useFlexGap>
          {c.conditions.map((cond) => (
            <Chip
              key={cond}
              label={cond}
              size="small"
              color="warning"
              variant="outlined"
              onDelete={canManage ? () => onRemoveCondition(cond) : undefined}
              sx={{ height: 18, fontSize: '0.6rem' }}
            />
          ))}
        </Stack>
      )}

      {/* Death save indicators */}
      {showFull && isDown && (c.death_save_successes > 0 || c.death_save_failures > 0) && (
        <Stack direction="row" spacing={1} sx={{ ml: '52px', mt: 0.25 }}>
          <Typography variant="caption" color="success.main">
            ✅ {'●'.repeat(c.death_save_successes)}{'○'.repeat(3 - c.death_save_successes)}
          </Typography>
          <Typography variant="caption" color="error.main">
            ❌ {'●'.repeat(c.death_save_failures)}{'○'.repeat(3 - c.death_save_failures)}
          </Typography>
        </Stack>
      )}
    </Box>
  );
}
