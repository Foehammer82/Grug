import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { GrugNote } from '../types';

export default function PersonalNotesPage() {
  useAuth();
  const qc = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const { data: note, isLoading } = useQuery<GrugNote>({
    queryKey: ['personal-notes'],
    queryFn: async () => {
      const res = await client.get<GrugNote>('/api/personal/notes');
      return res.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      const res = await client.put<GrugNote>('/api/personal/notes', { content });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['personal-notes'] });
      setEditing(false);
    },
  });

  function handleEdit() {
    setDraft(note?.content ?? '');
    setEditing(true);
  }

  function handleCancel() {
    setEditing(false);
    setDraft('');
  }

  function handleSave() {
    saveMutation.mutate(draft);
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 900 }}>
      <Typography variant="body2" color="text.secondary">
        Grug&apos;s personal notes about you — things he&apos;s learned from your DMs and
        interactions. You can review and edit them here.
      </Typography>

      {editing ? (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <TextField
            multiline
            fullWidth
            minRows={10}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Markdown content…"
            sx={{ mb: 2 }}
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              size="small"
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="outlined" size="small" onClick={handleCancel}>
              Cancel
            </Button>
            {saveMutation.isError && (
              <Typography color="error" variant="caption" sx={{ alignSelf: 'center' }}>
                Error saving notes.
              </Typography>
            )}
          </Box>
        </Paper>
      ) : (
        <>
          <Box>
            <Button variant="contained" size="small" onClick={handleEdit}>
              Edit
            </Button>
          </Box>
          {note?.content ? (
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Box sx={{ '& a': { color: 'primary.main' } }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {note.content}
                </ReactMarkdown>
              </Box>
            </Paper>
          ) : (
            <Typography color="text.secondary">
              No personal notes yet. Grug will add notes here as he gets to know you.
            </Typography>
          )}
        </>
      )}
    </Stack>
  );
}
