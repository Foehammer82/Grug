import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface GuildConfig {
  guild_id: number;
  prefix: string;
  timezone: string;
  announce_channel_id: number | null;
}

export default function GuildConfigPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: config, isLoading } = useQuery<GuildConfig>({
    queryKey: ['config', guildId],
    queryFn: async () => {
      const res = await client.get<GuildConfig>(`/api/guilds/${guildId}/config`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const [timezone, setTimezone] = useState('');
  const [channelId, setChannelId] = useState('');

  const mutation = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {};
      if (timezone) body.timezone = timezone;
      if (channelId) body.announce_channel_id = parseInt(channelId);
      await client.patch(`/api/guilds/${guildId}/config`, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config', guildId] });
      setTimezone('');
      setChannelId('');
    },
  });

  return (
    <>
      <NavBar />
      <main style={{ padding: '2rem', maxWidth: 600 }}>
        <h2>Guild Configuration</h2>
        {isLoading && <p>Loading…</p>}
        {config && (
          <table style={{ borderCollapse: 'collapse', width: '100%', marginBottom: '2rem' }}>
            <tbody>
              {[
                ['Guild ID', config.guild_id],
                ['Prefix', config.prefix],
                ['Timezone', config.timezone],
                ['Announce Channel', config.announce_channel_id ?? '—'],
              ].map(([k, v]) => (
                <tr key={String(k)}>
                  <td style={{ padding: '0.5rem', fontWeight: 600, width: 180 }}>{k}</td>
                  <td style={{ padding: '0.5rem' }}>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <h3>Update Config</h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
        >
          <label>
            Timezone
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder={config?.timezone ?? 'UTC'}
              style={{ display: 'block', width: '100%', padding: '0.5rem', marginTop: 4 }}
            />
          </label>
          <label>
            Announce Channel ID
            <input
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              placeholder={config?.announce_channel_id?.toString() ?? 'Channel ID'}
              style={{ display: 'block', width: '100%', padding: '0.5rem', marginTop: 4 }}
            />
          </label>
          <button
            type="submit"
            disabled={mutation.isPending}
            style={{ padding: '0.6rem 1.5rem', background: '#5865F2', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', alignSelf: 'flex-start' }}
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
          {mutation.isSuccess && <p style={{ color: 'green' }}>Saved!</p>}
          {mutation.isError && <p style={{ color: 'red' }}>Error saving.</p>}
        </form>
      </main>
    </>
  );
}
