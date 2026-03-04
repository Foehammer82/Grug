import { Avatar, Autocomplete, Box, Stack, TextField, Typography } from '@mui/material';
import type { GuildMember } from '../../types';

/** Sentinel used to represent "Unassigned" in the owner picker. */
export const UNASSIGNED_MEMBER: GuildMember = {
  discord_user_id: '',
  display_name: 'Unassigned',
  username: '',
  avatar_url: null,
};

/** Derive the owner API payload fields from the Autocomplete selection. */
export function resolveOwnerPayload(owner: GuildMember | string) {
  if (typeof owner === 'object') {
    if (!owner.discord_user_id) return { owner_discord_user_id: null, owner_display_name: null };
    return { owner_discord_user_id: owner.discord_user_id, owner_display_name: null };
  }
  const trimmed = owner.trim();
  return { owner_discord_user_id: null, owner_display_name: trimmed || null };
}

interface OwnerAutocompleteProps {
  guildMembers: GuildMember[];
  loading: boolean;
  value: GuildMember | string;
  onChange: (v: GuildMember | string) => void;
}

/** Autocomplete for picking a character owner — a guild member, a free-text name, or Unassigned. */
export default function OwnerAutocomplete({ guildMembers, loading, value, onChange }: OwnerAutocompleteProps) {
  return (
    <Autocomplete
      freeSolo
      size="small"
      fullWidth
      loading={loading}
      options={[UNASSIGNED_MEMBER, ...guildMembers]}
      value={value}
      onChange={(_, val) => onChange((val ?? UNASSIGNED_MEMBER) as GuildMember | string)}
      getOptionLabel={(opt) => (typeof opt === 'string' ? opt : opt.display_name)}
      isOptionEqualToValue={(opt, val) =>
        typeof val === 'string'
          ? opt.display_name === val
          : opt.discord_user_id === (val as GuildMember).discord_user_id
      }
      filterOptions={(opts, { inputValue }) => {
        if (!inputValue) return opts;
        const q = inputValue.toLowerCase();
        return opts.filter(
          (o) =>
            o.display_name.toLowerCase().includes(q) ||
            o.username.toLowerCase().includes(q),
        );
      }}
      renderOption={(props, opt) => (
        <Box component="li" {...props} key={opt.discord_user_id || '__unassigned__'}>
          {opt.discord_user_id ? (
            <Stack direction="row" alignItems="center" spacing={1}>
              <Avatar
                src={opt.avatar_url ?? undefined}
                sx={{ width: 24, height: 24, fontSize: '0.7rem' }}
              >
                {opt.display_name[0]?.toUpperCase()}
              </Avatar>
              <Box>
                <Typography variant="body2" lineHeight={1.3}>{opt.display_name}</Typography>
                <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
                  @{opt.username}
                </Typography>
              </Box>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
              Unassigned
            </Typography>
          )}
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Owner"
          placeholder="Search members or type a name…"
          helperText="Pick a server member, type a custom name, or choose Unassigned"
        />
      )}
    />
  );
}
