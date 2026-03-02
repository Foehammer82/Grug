/**
 * GuildAvatar — renders a guild's Discord icon, or a Discord-style initials
 * placeholder when the guild has no icon set.
 *
 * Initials are derived from the first letter of each whitespace-separated word
 * (up to 4 characters, matching Discord's behaviour). The background colour is
 * deterministically chosen from a palette using the guild ID so it stays stable
 * across renders and page loads.
 */

interface GuildAvatarProps {
  guildId: string;
  name: string;
  icon: string | null;
  size?: number;
  /** When true, removes the built-in border-radius so a parent can control shape (e.g. sidebar morph). */
  square?: boolean;
}

// Discord-inspired palette — vibrant enough to read white text on.
const PALETTE = [
  '#5865F2', // blurple
  '#57F287', // green
  '#FEE75C', // yellow  — darker text needed, skipped
  '#EB459E', // fuchsia
  '#ED4245', // red
  '#3BA55C', // dark green
  '#FAA61A', // orange
  '#9C84EC', // purple
  '#2D7D46', // forest green
  '#1ABC9C', // teal
  '#E91E63', // pink
  '#FF5722', // deep orange
];

function pickColour(guildId: string): string {
  // Simple djb2-style hash over the guild ID string.
  let hash = 5381;
  for (let i = 0; i < guildId.length; i++) {
    hash = (hash * 33) ^ guildId.charCodeAt(i);
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase())
    .slice(0, 4)
    .join('');
}

export default function GuildAvatar({ guildId, name, icon, size = 48, square = false }: GuildAvatarProps) {
  if (icon) {
    return (
      <img
        src={`https://cdn.discordapp.com/icons/${guildId}/${icon}.png?size=64`}
        alt={name}
        style={{ width: size, height: size, borderRadius: square ? 0 : '50%', flexShrink: 0 }}
      />
    );
  }

  const initials = getInitials(name);
  const bg = pickColour(guildId);
  // Scale font size so it always fits: roughly 38% of the circle diameter.
  const fontSize = Math.round(size * (initials.length > 2 ? 0.28 : 0.36));

  return (
    <div
      aria-label={name}
      style={{
        width: size,
        height: size,
        borderRadius: square ? 0 : '50%',
        background: bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      <span
        style={{
          color: '#fff',
          fontWeight: 700,
          fontSize,
          letterSpacing: initials.length > 2 ? '-0.5px' : undefined,
          lineHeight: 1,
        }}
      >
        {initials}
      </span>
    </div>
  );
}
