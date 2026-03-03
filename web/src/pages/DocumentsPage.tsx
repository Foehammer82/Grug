import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import { TABLE_HEADER_SX } from '../types';
import type { Document, DocumentSearchResult } from '../types';

const ALLOWED_EXT = ['.txt', '.md', '.rst', '.pdf'];

export default function DocumentsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();
  const { isAdmin } = useGuildContext();

  // Upload dialog state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Edit dialog state
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [editDesc, setEditDesc] = useState('');

  // RAG test panel state
  const [testQuery, setTestQuery] = useState('');
  const [testDocId, setTestDocId] = useState<number | ''>('');
  const [testResult, setTestResult] = useState<DocumentSearchResult | null>(null);

  const { data: docs, isLoading } = useQuery<Document[]>({
    queryKey: ['documents', guildId],
    queryFn: async () => {
      const res = await client.get<Document[]>(`/api/guilds/${guildId}/documents`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ file, description }: { file: File; description: string }) => {
      const form = new FormData();
      form.append('file', file);
      form.append('description', description);
      await client.post(`/api/guilds/${guildId}/documents`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents', guildId] });
      handleUploadClose();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUploadError(detail ?? 'Upload failed. Please try again.');
    },
  });

  const editMutation = useMutation({
    mutationFn: async ({ id, description }: { id: number; description: string }) => {
      await client.patch(`/api/guilds/${guildId}/documents/${id}`, { description: description || null });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents', guildId] });
      setEditDoc(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/documents/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', guildId] }),
  });

  const searchMutation = useMutation({
    mutationFn: async ({ query, docId }: { query: string; docId: number | '' }) => {
      const res = await client.post<DocumentSearchResult>(
        `/api/guilds/${guildId}/documents/search`,
        { query, k: 5, document_id: docId || null },
      );
      return res.data;
    },
    onSuccess: (data) => setTestResult(data),
  });

  function handleUploadClose() {
    setUploadOpen(false);
    setUploadFile(null);
    setUploadDesc('');
    setUploadError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setUploadError('');
    if (!f) { setUploadFile(null); return; }
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXT.includes(ext)) {
      setUploadError(`Unsupported type. Allowed: ${ALLOWED_EXT.join(', ')}`);
      setUploadFile(null);
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setUploadError('File exceeds 10 MB limit.');
      setUploadFile(null);
      return;
    }
    setUploadFile(f);
  }

  function handleEditOpen(doc: Document) {
    setEditDoc(doc);
    setEditDesc(doc.description ?? '');
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 600 }}>
          Text files indexed for Grug to search during conversation (RAG). When you ask Grug
          about rules, lore, or campaign notes, Grug looks here first.
        </Typography>
        {isAdmin && (
          <Button variant="contained" size="small" onClick={() => setUploadOpen(true)}>
            Upload Document
          </Button>
        )}
      </Stack>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !docs || docs.length === 0 ? (
        <Typography color="text.secondary">No documents indexed yet.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Filename', 'Description', 'Chunks', 'Added', ...(isAdmin ? ['Actions'] : [])].map((h) => (
                  <TableCell key={h} sx={TABLE_HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {docs.map((d) => (
                <TableRow key={d.id} hover>
                  <TableCell>{d.filename}</TableCell>
                  <TableCell>{d.description ?? '—'}</TableCell>
                  <TableCell>{d.chunk_count}</TableCell>
                  <TableCell>{new Date(d.created_at).toLocaleDateString()}</TableCell>
                  {isAdmin && (
                    <TableCell>
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => handleEditOpen(d)}
                        >
                          Edit
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          onClick={() => deleteMutation.mutate(d.id)}
                          disabled={deleteMutation.isPending}
                        >
                          Delete
                        </Button>
                      </Stack>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ── RAG Search Test (admin only) ── */}
      {isAdmin && (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">Test RAG Search</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Run a live semantic search against indexed documents to verify retrieval quality.
                Lower distance scores mean a closer match.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
                <TextField
                  label="Search query"
                  value={testQuery}
                  onChange={(e) => { setTestQuery(e.target.value); setTestResult(null); }}
                  size="small"
                  fullWidth
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && testQuery.trim()) {
                      searchMutation.mutate({ query: testQuery.trim(), docId: testDocId });
                    }
                  }}
                />
                <FormControl size="small" sx={{ minWidth: 200 }}>
                  <InputLabel shrink>Filter by document</InputLabel>
                  <Select
                    value={testDocId}
                    onChange={(e) => setTestDocId(e.target.value as number | '')}
                    label="Filter by document"
                    displayEmpty
                    notched
                  >
                    <MenuItem value=""><em>All documents</em></MenuItem>
                    {(docs ?? []).map((d) => (
                      <MenuItem key={d.id} value={d.id}>{d.filename}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  size="small"
                  disabled={!testQuery.trim() || searchMutation.isPending}
                  onClick={() => searchMutation.mutate({ query: testQuery.trim(), docId: testDocId })}
                  sx={{ whiteSpace: 'nowrap', mt: { xs: 0, sm: '4px' } }}
                >
                  {searchMutation.isPending
                    ? <CircularProgress size={16} color="inherit" />
                    : 'Search'}
                </Button>
              </Stack>

              {testResult && (
                <>
                  <Divider />
                  {testResult.error ? (
                    <Typography color="error" variant="body2">
                      Search failed — check server logs.
                    </Typography>
                  ) : testResult.chunks.length === 0 ? (
                    <Typography color="text.secondary" variant="body2">
                      No matching chunks found.
                    </Typography>
                  ) : (
                    <Stack spacing={1.5}>
                      {testResult.chunks.map((chunk, i) => (
                        <Paper key={i} variant="outlined" sx={{ p: 1.5 }}>
                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1 }}>
                            <Typography variant="caption" fontWeight="bold">{chunk.filename}</Typography>
                            <Chip label={`chunk ${chunk.chunk_index}`} size="small" variant="outlined" />
                            <Chip
                              label={`score ${chunk.distance}`}
                              size="small"
                              color={chunk.distance < 0.3 ? 'success' : chunk.distance < 0.6 ? 'warning' : 'default'}
                            />
                          </Stack>
                          <Typography
                            variant="body2"
                            sx={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              fontSize: '0.75rem',
                              maxHeight: 200,
                              overflow: 'auto',
                              bgcolor: 'action.hover',
                              borderRadius: 1,
                              p: 1,
                            }}
                          >
                            {chunk.text}
                          </Typography>
                        </Paper>
                      ))}
                    </Stack>
                  )}
                </>
              )}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {/* ── Upload dialog ── */}
      <Dialog open={uploadOpen} onClose={handleUploadClose} fullWidth maxWidth="sm">
        <DialogTitle>Upload Document</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Button variant="outlined" component="label" size="small">
              {uploadFile ? uploadFile.name : 'Choose file (.txt, .md, .rst, .pdf)'}
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.rst,.pdf"
                hidden
                onChange={handleFileChange}
              />
            </Button>
            {uploadError && (
              <Typography variant="caption" color="error">{uploadError}</Typography>
            )}
            <TextField
              label="Description (optional)"
              value={uploadDesc}
              onChange={(e) => setUploadDesc(e.target.value)}
              multiline
              minRows={2}
              fullWidth
              size="small"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleUploadClose}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!uploadFile || uploadMutation.isPending}
            onClick={() => uploadFile && uploadMutation.mutate({ file: uploadFile, description: uploadDesc })}
          >
            {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Edit dialog ── */}
      <Dialog open={!!editDoc} onClose={() => setEditDoc(null)} fullWidth maxWidth="sm">
        <DialogTitle>Edit Document</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>{editDoc?.filename}</strong>
            </Typography>
            <TextField
              label="Description"
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
              multiline
              minRows={2}
              fullWidth
              size="small"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDoc(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={editMutation.isPending}
            onClick={() => editDoc && editMutation.mutate({ id: editDoc.id, description: editDesc })}
          >
            {editMutation.isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
