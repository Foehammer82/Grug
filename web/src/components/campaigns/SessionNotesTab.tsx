import { useState, useRef, useEffect } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Pagination,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArticleIcon from '@mui/icons-material/Article';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ScienceIcon from '@mui/icons-material/Science';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import type { DocumentSearchResult, SessionNote, SynthesisStatus } from '../../types';

interface SessionNotesTabProps {
  guildId: string;
  campaignId: number;
  isAdmin: boolean;
  currentUserId: string;
}

const STATUS_COLORS: Record<SynthesisStatus, 'default' | 'warning' | 'success' | 'error'> = {
  pending: 'warning',
  processing: 'warning',
  done: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<SynthesisStatus, string> = {
  pending: 'Pending',
  processing: 'Processing…',
  done: 'Done',
  failed: 'Failed',
};

/** A single session note row with expand-to-read. */
function NoteRow({
  note,
  guildId,
  isAdmin,
  currentUserId,
}: {
  note: SessionNote;
  guildId: string;
  isAdmin: boolean;
  currentUserId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const qc = useQueryClient();

  const canWrite = isAdmin || note.submitted_by === currentUserId;

  const resynthMutation = useMutation({
    mutationFn: async () => {
      await client.post(
        `/api/guilds/${guildId}/campaigns/${note.campaign_id}/session-notes/${note.id}/synthesize`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session-notes', guildId, note.campaign_id] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await client.delete(
        `/api/guilds/${guildId}/campaigns/${note.campaign_id}/session-notes/${note.id}`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session-notes', guildId, note.campaign_id] });
      setConfirmDelete(false);
    },
  });

  const displayTitle = note.title || '(untitled)';
  const displayDate = note.session_date
    ? new Date(note.session_date + 'T00:00:00').toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : null;

  return (
    <>
      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'hidden',
        }}
      >
        {/* Row header */}
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{
            px: 1.5,
            py: 0.75,
            bgcolor: 'action.hover',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => setExpanded((v) => !v)}
        >
          <IconButton size="small" tabIndex={-1}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>

          <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1, minWidth: 0 }}>
            {displayTitle}
          </Typography>

          {displayDate && (
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
              {displayDate}
            </Typography>
          )}

          <Chip
            label={STATUS_LABELS[note.synthesis_status]}
            color={STATUS_COLORS[note.synthesis_status]}
            size="small"
            sx={{ height: 18, fontSize: '0.65rem', flexShrink: 0 }}
          />

          {canWrite && (
            <Stack direction="row" spacing={0.25} onClick={(e) => e.stopPropagation()}>
              <Tooltip title="Re-run synthesis">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => resynthMutation.mutate()}
                    disabled={resynthMutation.isPending || note.synthesis_status === 'processing'}
                  >
                    {resynthMutation.isPending ? (
                      <CircularProgress size={14} />
                    ) : (
                      <AutoFixHighIcon sx={{ fontSize: 14 }} />
                    )}
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Delete note">
                <IconButton
                  size="small"
                  color="error"
                  onClick={() => setConfirmDelete(true)}
                >
                  <DeleteIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
            </Stack>
          )}
        </Stack>

        {/* Expanded content */}
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <Box sx={{ p: 1.5 }}>
            {note.synthesis_status === 'done' && note.clean_notes ? (
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'inherit',
                  m: 0,
                  color: 'text.primary',
                }}
              >
                {note.clean_notes}
              </Typography>
            ) : note.synthesis_status === 'failed' ? (
              <Stack spacing={0.5}>
                <Alert severity="error" sx={{ mb: 1 }}>
                  Synthesis failed
                  {note.synthesis_error ? `: ${note.synthesis_error}` : '.'}
                </Alert>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  Raw notes:
                </Typography>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0, opacity: 0.8 }}
                >
                  {note.raw_notes}
                </Typography>
              </Stack>
            ) : (
              <Stack spacing={0.5}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <CircularProgress size={14} />
                  <Typography variant="caption" color="text.secondary">
                    {note.synthesis_status === 'processing'
                      ? 'LLM is cleaning up these notes…'
                      : 'Synthesis pending — clean notes will appear here soon.'}
                  </Typography>
                </Stack>
                <Divider sx={{ my: 0.5 }} />
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  Raw notes:
                </Typography>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0, opacity: 0.8 }}
                >
                  {note.raw_notes}
                </Typography>
              </Stack>
            )}
          </Box>
        </Collapse>
      </Box>

      {/* Delete confirmation dialog */}
      <Dialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete session note?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This will permanently delete <strong>{displayTitle}</strong> and remove it from
            the campaign's searchable history. This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setConfirmDelete(false)}>
            Cancel
          </Button>
          <Button
            size="small"
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

/** Dialog for submitting new session notes (text paste or file upload). */
function AddSessionNoteDialog({
  open,
  onClose,
  guildId,
  campaignId,
}: {
  open: boolean;
  onClose: () => void;
  guildId: string;
  campaignId: number;
}) {
  const qc = useQueryClient();
  const [rawNotes, setRawNotes] = useState('');
  const [title, setTitle] = useState('');
  const [sessionDate, setSessionDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [fileName, setFileName] = useState('');
  const [fileContents, setFileContents] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setRawNotes('');
    setTitle('');
    setSessionDate(new Date().toISOString().slice(0, 10));
    setFileName('');
    setFileContents(null);
  };

  const submitMutation = useMutation({
    mutationFn: async () => {
      const notes = fileContents ?? rawNotes;
      if (!notes.trim()) throw new Error('Notes must not be empty.');
      await client.post(`/api/guilds/${guildId}/campaigns/${campaignId}/session-notes`, {
        raw_notes: notes,
        title: title.trim() || null,
        session_date: sessionDate || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session-notes', guildId, campaignId] });
      reset();
      onClose();
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    // Auto-fill title from filename (strip extension).
    if (!title) {
      setTitle(file.name.replace(/\.[^.]+$/, ''));
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      setFileContents((ev.target?.result as string) ?? null);
    };
    reader.readAsText(file);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const isReady = !!(fileContents ?? rawNotes.trim());
  const error = submitMutation.isError
    ? ((submitMutation.error as Error)?.message ?? 'Submission failed.')
    : null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Add Session Notes</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <Stack direction="row" spacing={1}>
            <TextField
              label="Title (optional)"
              size="small"
              fullWidth
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Session 12 — The Sunken Vault"
            />
            <TextField
              label="Session Date"
              size="small"
              type="date"
              value={sessionDate}
              onChange={(e) => setSessionDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 180 }}
            />
          </Stack>

          {fileContents ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <UploadFileIcon fontSize="small" color="primary" />
              <Typography variant="body2" sx={{ flex: 1 }}>
                {fileName}
              </Typography>
              <Button
                size="small"
                color="error"
                onClick={() => {
                  setFileName('');
                  setFileContents(null);
                  if (fileRef.current) fileRef.current.value = '';
                }}
              >
                Remove
              </Button>
            </Stack>
          ) : (
            <>
              <TextField
                label="Paste raw notes here"
                multiline
                minRows={8}
                maxRows={20}
                fullWidth
                size="small"
                value={rawNotes}
                onChange={(e) => setRawNotes(e.target.value)}
                placeholder="Dump your session notes in any format — shorthand, bullet points, stream of consciousness. Grug will clean them up."
              />
              <Stack direction="row" alignItems="center" spacing={1}>
                <Divider sx={{ flex: 1 }} />
                <Typography variant="caption" color="text.secondary">
                  or
                </Typography>
                <Divider sx={{ flex: 1 }} />
              </Stack>
              <Button
                variant="outlined"
                size="small"
                startIcon={<UploadFileIcon />}
                onClick={() => fileRef.current?.click()}
                sx={{ alignSelf: 'flex-start' }}
              >
                Upload .txt / .md / .rst / .pdf / .docx file
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.rst,.pdf,.docx,.doc"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
            </>
          )}

          {error && (
            <Alert severity="error">{error}</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button size="small" onClick={handleClose}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          disabled={!isReady || submitMutation.isPending}
          onClick={() => submitMutation.mutate()}
        >
          {submitMutation.isPending ? 'Submitting…' : 'Submit Notes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Session Log dialog — paginated view of synthesised notes by session date
// ---------------------------------------------------------------------------

function SessionLogDialog({
  open,
  onClose,
  notes,
}: {
  open: boolean;
  onClose: () => void;
  notes: SessionNote[];
}) {
  const [page, setPage] = useState(1);

  // Reset to first page whenever the dialog opens or note list changes.
  useEffect(() => {
    if (open) setPage(1);
  }, [open]);

  const doneSorted = [...notes]
    .filter((n) => n.synthesis_status === 'done' && n.clean_notes)
    .sort((a, b) => {
      const da = a.session_date ?? '';
      const db = b.session_date ?? '';
      // Most-recent first; fall back to id desc inside the same date.
      return db !== da ? db.localeCompare(da) : b.id - a.id;
    });

  const note = doneSorted[page - 1] ?? null;

  const displayDate = (d: string | null) =>
    d
      ? new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
      : null;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        Session Log
        {doneSorted.length > 0 && (
          <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
            ({page} / {doneSorted.length})
          </Typography>
        )}
      </DialogTitle>
      <DialogContent dividers>
        {doneSorted.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No synthesised session notes yet. Submit some notes and wait for synthesis to complete.
          </Typography>
        ) : note ? (
          <Stack spacing={1.5}>
            <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
              <Typography variant="subtitle1" fontWeight={600}>
                {note.title || '(untitled)'}
              </Typography>
              {note.session_date && (
                <Chip label={displayDate(note.session_date)} size="small" variant="outlined" />
              )}
            </Stack>
            <Typography
              variant="body2"
              component="pre"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'inherit',
                m: 0,
                lineHeight: 1.75,
              }}
            >
              {note.clean_notes}
            </Typography>
          </Stack>
        ) : null}
      </DialogContent>
      {doneSorted.length > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
          <Pagination
            count={doneSorted.length}
            page={page}
            onChange={(_, v) => setPage(v)}
            size="small"
            siblingCount={2}
          />
        </Box>
      )}
      <DialogActions>
        <Button size="small" onClick={onClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// RAG test dialog — admin-only search probe against campaign notes index
// ---------------------------------------------------------------------------

function RagTestDialog({
  open,
  onClose,
  guildId,
  campaignId,
}: {
  open: boolean;
  onClose: () => void;
  guildId: string;
  campaignId: number;
}) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<DocumentSearchResult | null>(null);

  const testMutation = useMutation({
    mutationFn: async (q: string) => {
      const res = await client.post<DocumentSearchResult>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/session-notes/test-rag`,
        { query: q, k: 5 },
      );
      return res.data;
    },
    onSuccess: (data) => setResult(data),
  });

  const handleClose = () => {
    setQuery('');
    setResult(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Test Session Notes RAG</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          <Stack direction="row" spacing={1}>
            <TextField
              label="Search query"
              placeholder="e.g. What happened in the first dungeon?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              fullWidth
              size="small"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && query.trim()) testMutation.mutate(query.trim());
              }}
            />
            <Button
              variant="contained"
              size="small"
              disabled={!query.trim() || testMutation.isPending}
              onClick={() => testMutation.mutate(query.trim())}
              sx={{ whiteSpace: 'nowrap' }}
            >
              {testMutation.isPending ? 'Searching…' : 'Search'}
            </Button>
          </Stack>

          {result && (
            result.error ? (
              <Alert severity="error">RAG search failed.</Alert>
            ) : result.chunks.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No matching chunks found. The campaign may not have any indexed session notes yet.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {result.chunks.map((chunk, i) => (
                  <Box
                    key={i}
                    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                      <Chip
                        label={`chunk #${chunk.chunk_index}`}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.65rem', height: 18 }}
                      />
                      <Chip
                        label={`dist ${chunk.distance}`}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.65rem', height: 18 }}
                      />
                      <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                        {chunk.filename}
                      </Typography>
                    </Stack>
                    <Typography
                      variant="body2"
                      component="pre"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        m: 0,
                      }}
                    >
                      {chunk.text}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button size="small" onClick={handleClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Session notes tab — lists notes and provides submission UI. */
export default function SessionNotesTab({
  guildId,
  campaignId,
  isAdmin,
  currentUserId,
}: SessionNotesTabProps) {
  const [addOpen, setAddOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [ragOpen, setRagOpen] = useState(false);

  const {
    data: notes = [],
    isLoading,
    isError,
  } = useQuery<SessionNote[]>({
    queryKey: ['session-notes', guildId, campaignId],
    queryFn: async () => {
      const res = await client.get<SessionNote[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/session-notes`,
      );
      return res.data;
    },
    staleTime: 30_000,
    refetchInterval: (query) => {
      // Poll while any note is still processing so the status chip updates.
      const data = query.state.data ?? [];
      const hasPending = data.some(
        (n) => n.synthesis_status === 'pending' || n.synthesis_status === 'processing',
      );
      return hasPending ? 5_000 : false;
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (isError) {
    return (
      <Alert severity="error" sx={{ mt: 1 }}>
        Failed to load session notes.
      </Alert>
    );
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          {notes.length === 0 ? 'No session notes yet.' : `${notes.length} session note${notes.length === 1 ? '' : 's'}`}
        </Typography>
        <Stack direction="row" spacing={0.5} alignItems="center">
          {isAdmin && (
            <Tooltip title="Test RAG search">
              <IconButton size="small" onClick={() => setRagOpen(true)}>
                <ScienceIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Session Log">
            <IconButton size="small" onClick={() => setLogOpen(true)}>
              <ArticleIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => setAddOpen(true)}
          >
            Add Notes
          </Button>
        </Stack>
      </Stack>

      <Stack spacing={1}>
        {notes.map((note) => (
          <NoteRow
            key={note.id}
            note={note}
            guildId={guildId}
            isAdmin={isAdmin}
            currentUserId={currentUserId}
          />
        ))}
      </Stack>

      <AddSessionNoteDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        guildId={guildId}
        campaignId={campaignId}
      />

      <SessionLogDialog
        open={logOpen}
        onClose={() => setLogOpen(false)}
        notes={notes}
      />

      {isAdmin && (
        <RagTestDialog
          open={ragOpen}
          onClose={() => setRagOpen(false)}
          guildId={guildId}
          campaignId={campaignId}
        />
      )}
    </Box>
  );
}
