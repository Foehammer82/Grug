import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface GlossaryTerm {
  id: number;
  guild_id: number;
  channel_id: number | null;
  term: string;
  definition: string;
  ai_generated: boolean;
  originally_ai_generated: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
}

interface HistoryEntry {
  id: number;
  term_id: number;
  guild_id: number;
  old_term: string;
  old_definition: string;
  old_ai_generated: boolean;
  changed_by: number;
  changed_at: string;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

function sourceBadge(term: GlossaryTerm): { label: string; color: string } {
  if (term.ai_generated) return { label: '🤖 AI', color: '#8B5CF6' };
  if (term.originally_ai_generated) return { label: '🤖→👤 AI-origin (edited)', color: '#D97706' };
  return { label: '👤 Human', color: '#059669' };
}

const btn: React.CSSProperties = {
  padding: '0.4rem 1rem',
  background: '#5865F2',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
};
const dangerBtn: React.CSSProperties = { ...btn, background: '#ed4245' };
const ghostBtn: React.CSSProperties = {
  ...btn,
  background: 'transparent',
  color: '#5865F2',
  border: '1px solid #5865F2',
};
const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '0.5rem',
  marginTop: 4,
  boxSizing: 'border-box',
};

export default function GlossaryPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const [filterChannel, setFilterChannel] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [newTerm, setNewTerm] = useState('');
  const [newDef, setNewDef] = useState('');
  const [newChannel, setNewChannel] = useState<string>('');
  const [editId, setEditId] = useState<number | null>(null);
  const [editTerm, setEditTerm] = useState('');
  const [editDef, setEditDef] = useState('');
  const [historyTermId, setHistoryTermId] = useState<number | null>(null);

  const { data: channels = [] } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const channelName = (id: number | null): string => {
    if (!id) return 'Server-wide';
    const ch = channels.find((c) => c.id === String(id));
    return ch ? `#${ch.name}` : `#${id}`;
  };

  const queryParams = filterChannel ? `?channel_id=${filterChannel}` : '';
  const { data: terms = [], isLoading } = useQuery<GlossaryTerm[]>({
    queryKey: ['glossary', guildId, filterChannel],
    queryFn: async () => {
      const res = await client.get<GlossaryTerm[]>(`/api/guilds/${guildId}/glossary${queryParams}`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const { data: history = [] } = useQuery<HistoryEntry[]>({
    queryKey: ['glossary-history', guildId, historyTermId],
    queryFn: async () => {
      const res = await client.get<HistoryEntry[]>(
        `/api/guilds/${guildId}/glossary/${historyTermId}/history`
      );
      return res.data;
    },
    enabled: !!historyTermId,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await client.post(`/api/guilds/${guildId}/glossary`, {
        term: newTerm,
        definition: newDef,
        channel_id: newChannel ? parseInt(newChannel) : null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['glossary', guildId] });
      setNewTerm('');
      setNewDef('');
      setNewChannel('');
      setShowForm(false);
    },
  });

  const editMutation = useMutation({
    mutationFn: async () => {
      await client.patch(`/api/guilds/${guildId}/glossary/${editId}`, {
        term: editTerm || undefined,
        definition: editDef || undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['glossary', guildId] });
      setEditId(null);
      setEditTerm('');
      setEditDef('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/glossary/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary', guildId] }),
  });

  return (
    <>
      <NavBar />
      <main style={{ padding: '2rem', maxWidth: 900 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0 }}>Glossary</h2>
          <button style={btn} onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Cancel' : '+ Add Term'}
          </button>
        </div>

        {/* Channel filter */}
        <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label htmlFor="channelFilter" style={{ fontWeight: 600 }}>
            Filter by channel:
          </label>
          <select
            id="channelFilter"
            value={filterChannel}
            onChange={(e) => setFilterChannel(e.target.value)}
            style={{ padding: '0.4rem' }}
          >
            <option value="">All scopes</option>
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                #{c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Add term form */}
        {showForm && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            style={{
              background: '#f6f6f6',
              padding: '1rem',
              borderRadius: 8,
              marginBottom: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            <h3 style={{ margin: 0 }}>New Term</h3>
            <label>
              Term
              <input
                required
                value={newTerm}
                onChange={(e) => setNewTerm(e.target.value)}
                style={inputStyle}
              />
            </label>
            <label>
              Definition
              <textarea
                required
                value={newDef}
                onChange={(e) => setNewDef(e.target.value)}
                style={{ ...inputStyle, minHeight: 80 }}
              />
            </label>
            <label>
              Channel scope (optional)
              <select
                value={newChannel}
                onChange={(e) => setNewChannel(e.target.value)}
                style={inputStyle}
              >
                <option value="">Server-wide</option>
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    #{c.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" style={btn} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Saving…' : 'Save'}
            </button>
            {createMutation.isError && <p style={{ color: 'red' }}>Error saving term.</p>}
          </form>
        )}

        {/* Term list */}
        {isLoading && <p>Loading…</p>}
        {!isLoading && terms.length === 0 && <p>No glossary terms yet.</p>}
        {terms.map((t) => {
          const badge = sourceBadge(t);
          return (
            <div
              key={t.id}
              style={{
                border: '1px solid #e0e0e0',
                borderRadius: 8,
                padding: '1rem',
                marginBottom: '0.75rem',
              }}
            >
              {editId === t.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    editMutation.mutate();
                  }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
                >
                  <input
                    value={editTerm}
                    onChange={(e) => setEditTerm(e.target.value)}
                    placeholder={t.term}
                    style={inputStyle}
                  />
                  <textarea
                    value={editDef}
                    onChange={(e) => setEditDef(e.target.value)}
                    placeholder={t.definition}
                    style={{ ...inputStyle, minHeight: 60 }}
                  />
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button type="submit" style={btn} disabled={editMutation.isPending}>
                      Save
                    </button>
                    <button type="button" style={ghostBtn} onClick={() => setEditId(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: '0.75rem',
                      flexWrap: 'wrap',
                    }}
                  >
                    <strong style={{ fontSize: '1.05rem' }}>{t.term}</strong>
                    <span style={{ fontSize: '0.8rem', color: '#777' }}>
                      {channelName(t.channel_id)}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: badge.color }}>{badge.label}</span>
                  </div>
                  <p style={{ margin: '0.4rem 0 0.75rem' }}>{t.definition}</p>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      style={ghostBtn}
                      onClick={() => {
                        setEditId(t.id);
                        setEditTerm(t.term);
                        setEditDef(t.definition);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      style={ghostBtn}
                      onClick={() =>
                        setHistoryTermId(historyTermId === t.id ? null : t.id)
                      }
                    >
                      {historyTermId === t.id ? 'Hide History' : 'History'}
                    </button>
                    <button
                      style={dangerBtn}
                      onClick={() => {
                        if (window.confirm(`Delete "${t.term}"?`)) deleteMutation.mutate(t.id);
                      }}
                    >
                      Delete
                    </button>
                  </div>

                  {/* Inline history panel */}
                  {historyTermId === t.id && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        background: '#f9f9f9',
                        borderRadius: 6,
                        padding: '0.75rem',
                      }}
                    >
                      <strong>Change history</strong>
                      {history.length === 0 && (
                        <p style={{ margin: '0.5rem 0 0', color: '#999' }}>No history yet.</p>
                      )}
                      {history.map((h) => (
                        <div
                          key={h.id}
                          style={{
                            borderTop: '1px solid #eee',
                            paddingTop: '0.5rem',
                            marginTop: '0.5rem',
                            fontSize: '0.875rem',
                          }}
                        >
                          <div>
                            <strong>Was:</strong> {h.old_term} — {h.old_definition}
                          </div>
                          <div style={{ color: '#777' }}>
                            {new Date(h.changed_at).toLocaleString()} · changed by{' '}
                            {h.changed_by === 0 ? '🤖 AI' : `user ${h.changed_by}`}
                            {h.old_ai_generated && ' · was AI-generated'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </main>
    </>
  );
}
