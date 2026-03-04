import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SyncIcon from '@mui/icons-material/Sync';
import DeleteIcon from '@mui/icons-material/Delete';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import type { Character } from '../types';

const SYSTEM_LABELS: Record<string, string> = {
  pf2e: 'Pathfinder 2E',
  dnd5e: 'D&D 5e',
  unknown: 'Unknown',
};

const SYSTEM_COLORS: Record<string, 'error' | 'primary' | 'default' | 'secondary' | 'info' | 'success' | 'warning'> = {
  pf2e: 'error',
  dnd5e: 'primary',
  unknown: 'default',
};

export default function CharactersPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  useGuildContext(); // ensures we're within GuildLayout
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [showLink, setShowLink] = useState(false);
  const [pathbuilderId, setPathbuilderId] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { data: characters, isLoading } = useQuery<Character[]>({
    queryKey: ['guild-characters', guildId],
    queryFn: async () => {
      const res = await client.get<Character[]>(`/api/guilds/${guildId}/characters`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const linkMutation = useMutation({
    mutationFn: async () => {
      const id = parseInt(pathbuilderId, 10);
      if (isNaN(id)) throw new Error('Invalid Pathbuilder ID');
      await client.post(`/api/guilds/${guildId}/characters/link-pathbuilder`, {
        pathbuilder_id: id,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['guild-characters', guildId] });
      setPathbuilderId('');
      setShowLink(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => client.delete(`/api/guilds/${guildId}/characters/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['guild-characters', guildId] });
      setDeleteId(null);
    },
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) =>
      client.post(`/api/guilds/${guildId}/characters/${id}/sync-pathbuilder`),
    onSuccess: () => {
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

  return (
    <>
      {/* Header */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="h6" fontWeight={700}>
          Characters
        </Typography>
        <Button
          variant="outlined"
          size="small"
          onClick={() => setShowLink((v) => !v)}
        >
          {showLink ? 'Cancel' : '+ Link Pathbuilder'}
        </Button>
      </Stack>

      {/* Quick link form */}
      <Collapse in={showLink} unmountOnExit>
        <Paper
          variant="outlined"
          component="form"
          sx={{ p: 2, mb: 3 }}
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault();
            linkMutation.mutate();
          }}
        >
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Enter your Pathbuilder 2e character ID. You can find it in Pathbuilder
              under Export &gt; Share &gt; the number in the URL.
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                label="Pathbuilder ID"
                size="small"
                required
                type="number"
                value={pathbuilderId}
                onChange={(e) => setPathbuilderId(e.target.value)}
                sx={{ width: 200 }}
                slotProps={{ htmlInput: { min: 1 } }}
              />
              <Button
                type="submit"
                variant="contained"
                size="small"
                disabled={linkMutation.isPending || !pathbuilderId.trim()}
              >
                {linkMutation.isPending ? 'Linking…' : 'Link'}
              </Button>
            </Stack>
            {linkMutation.isError && (
              <Typography variant="caption" color="error">
                {(linkMutation.error as { response?: { data?: { detail?: string } } })?.response
                  ?.data?.detail ?? 'Failed to link character. Check the ID and try again.'}
              </Typography>
            )}
          </Stack>
        </Paper>
      </Collapse>

      {/* Character grid */}
      {!characters || characters.length === 0 ? (
        <Typography color="text.secondary">
          No characters yet. Link a Pathbuilder character or upload one via Discord with{' '}
          <Typography component="code" variant="body2" sx={{ fontFamily: 'monospace' }}>
            /character upload
          </Typography>
          .
        </Typography>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 2,
          }}
        >
          {characters.map((ch) => {
            const sd = ch.structured_data;
            const headline = [
              sd?.level != null && `Level ${sd.level}`,
              sd?.class_and_subclass,
              sd?.race_or_ancestry,
            ]
              .filter(Boolean)
              .join(' · ');

            return (
              <Card
                key={ch.id}
                variant="outlined"
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  '&:hover': { borderColor: 'primary.main' },
                  transition: 'border-color 0.15s',
                }}
              >
                <CardActionArea
                  onClick={() => navigate(`/guilds/${guildId}/characters/${ch.id}`)}
                  sx={{ flex: 1 }}
                >
                  <CardContent>
                    <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
                      <Typography variant="subtitle1" fontWeight={700} noWrap sx={{ flex: 1 }}>
                        {ch.name}
                      </Typography>
                      <Chip
                        label={SYSTEM_LABELS[ch.system] ?? ch.system}
                        size="small"
                        color={SYSTEM_COLORS[ch.system] ?? 'default'}
                        variant="outlined"
                      />
                    </Stack>
                    {headline && (
                      <Typography variant="body2" color="text.secondary" mb={1}>
                        {headline}
                      </Typography>
                    )}
                    {/* Quick stats row */}
                    <Stack direction="row" spacing={2} flexWrap="wrap">
                      {sd?.armor_class != null && (
                        <Box sx={{ textAlign: 'center' }}>
                          <Typography variant="caption" color="text.disabled" display="block">AC</Typography>
                          <Typography variant="body2" fontWeight={700}>{sd.armor_class}</Typography>
                        </Box>
                      )}
                      {sd?.hp?.max != null && (
                        <Box sx={{ textAlign: 'center' }}>
                          <Typography variant="caption" color="text.disabled" display="block">HP</Typography>
                          <Typography variant="body2" fontWeight={700}>{sd.hp.max}</Typography>
                        </Box>
                      )}
                      {sd?.speed && (
                        <Box sx={{ textAlign: 'center' }}>
                          <Typography variant="caption" color="text.disabled" display="block">Speed</Typography>
                          <Typography variant="body2" fontWeight={700}>{sd.speed}</Typography>
                        </Box>
                      )}
                    </Stack>
                    {ch.pathbuilder_id && (
                      <Chip
                        label="Pathbuilder"
                        size="small"
                        color="success"
                        variant="outlined"
                        sx={{ mt: 1 }}
                      />
                    )}
                  </CardContent>
                </CardActionArea>

                {/* Action buttons */}
                <Stack
                  direction="row"
                  justifyContent="flex-end"
                  spacing={0.5}
                  sx={{ px: 1, pb: 1 }}
                >
                  {ch.pathbuilder_id && (
                    <Tooltip title="Sync from Pathbuilder">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          syncMutation.mutate(ch.id);
                        }}
                        disabled={syncMutation.isPending}
                      >
                        <SyncIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  <Tooltip title="Delete character">
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteId(ch.id);
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Card>
            );
          })}
        </Box>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle>Delete Character</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete{' '}
            <strong>{characters?.find((c) => c.id === deleteId)?.name}</strong>?
            This cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteId && deleteMutation.mutate(deleteId)}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
