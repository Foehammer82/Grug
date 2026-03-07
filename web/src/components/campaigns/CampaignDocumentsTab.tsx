/**
 * CampaignDocumentsTab — per-campaign document management.
 *
 * Documents (PDFs, text files, maps, module notes, encounter prep, etc.) are
 * completely separate from Session Notes. Session Notes are user-submitted
 * session recaps processed by LLM synthesis; Documents are pre-existing files
 * uploaded verbatim and chunked for RAG retrieval.
 *
 * GMs and guild admins can upload, edit, and delete documents, and see all
 * documents regardless of visibility.
 * Regular campaign members only see public documents.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import client from '../../api/client';
import { TABLE_HEADER_SX } from '../../types';
import type { Document, DocumentSearchResult } from '../../types';

const ALLOWED_EXT = ['.txt', '.md', '.rst', '.pdf'];
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

interface Props {
  guildId: string;
  campaignId: number;
  /** True when the current user is the campaign GM or an admin in GM-mode. */
  isGm: boolean;
  isAdmin: boolean;
}

export default function CampaignDocumentsTab({ guildId, campaignId, isGm, isAdmin }: Props) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const canManage = isGm || isAdmin;

  // ── Upload dialog ──────────────────────────────────────────────────────────
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadIsPublic, setUploadIsPublic] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Edit dialog ────────────────────────────────────────────────────────────
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [editDesc, setEditDesc] = useState('');
  const [editIsPublic, setEditIsPublic] = useState(false);

  // ── RAG test panel ─────────────────────────────────────────────────────────
  const [testQuery, setTestQuery] = useState('');
  const [testDocId, setTestDocId] = useState<number | ''>('');
  const [testResult, setTestResult] = useState<DocumentSearchResult | null>(null);

  // ── Queries ────────────────────────────────────────────────────────────────
  const base = `/api/guilds/${guildId}/campaigns/${campaignId}/documents`;

  const { data: docs, isLoading } = useQuery<Document[]>({
    queryKey: ['campaign-documents', guildId, campaignId],
    queryFn: async () => (await client.get<Document[]>(base)).data,
    enabled: !!guildId && !!campaignId,
  });

  // ── Mutations ──────────────────────────────────────────────────────────────
  const uploadMutation = useMutation({
    mutationFn: async ({
      file,
      description,
      isPublic,
    }: {
      file: File;
      description: string;
      isPublic: boolean;
    }) => {
      const form = new FormData();
      form.append('file', file);
      form.append('description', description);
      form.append('is_public', String(isPublic));
      await client.post(base, form, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-documents', guildId, campaignId] });
      closeUpload();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUploadError(detail ?? 'Upload failed. Please try again.');
    },
  });

  const editMutation = useMutation({
    mutationFn: async ({
      id,
      description,
      isPublic,
    }: {
      id: number;
      description: string;
      isPublic: boolean;
    }) => {
      await client.patch(`${base}/${id}`, {
        description: description || null,
        is_public: isPublic,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaign-documents', guildId, campaignId] });
      setEditDoc(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => client.delete(`${base}/${id}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['campaign-documents', guildId, campaignId] }),
  });

  const searchMutation = useMutation({
    mutationFn: async ({ query, docId }: { query: string; docId: number | '' }) => {
      const res = await client.post<DocumentSearchResult>(`${base}/search`, {
        query,
        k: 5,
        document_id: docId || null,
      });
      return res.data;
    },
    onSuccess: (data) => setTestResult(data),
  });

  // ── Helpers ────────────────────────────────────────────────────────────────
  function closeUpload() {
    setUploadOpen(false);
    setUploadFile(null);
    setUploadDesc('');
    setUploadIsPublic(false);
    setUploadError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setUploadError('');
    if (!f) {
      setUploadFile(null);
      return;
    }
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXT.includes(ext)) {
      setUploadError(`Unsupported type. Allowed: ${ALLOWED_EXT.join(', ')}`);
      setUploadFile(null);
      return;
    }
    if (f.size > MAX_SIZE_BYTES) {
      setUploadError('File exceeds 10 MB limit.');
      setUploadFile(null);
      return;
    }
    setUploadFile(f);
  }

  function openEdit(d: Document) {
    setEditDoc(d);
    setEditDesc(d.description ?? '');
    setEditIsPublic(d.is_public);
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

      {/* Header row */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        alignItems={{ xs: 'stretch', sm: 'center' }}
        justifyContent="space-between"
        spacing={1}
      >
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: { sm: 560 } }}>
          {canManage
            ? 'Files indexed for Grug to reference — module PDFs, maps, encounter prep, NPC rosters, etc. Private documents are GM-only; public documents are visible to players and referenced by Grug when answering their questions.'
            : 'Reference documents shared by the GM for this campaign.'}
        </Typography>
        {canManage && (
          <Button
            variant="contained"
            size="small"
            onClick={() => setUploadOpen(true)}
            sx={{ alignSelf: { xs: 'flex-end', sm: 'center' }, flexShrink: 0 }}
          >
            Upload Document
          </Button>
        )}
      </Stack>

      {/* Document list */}
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress size={24} />
        </Box>
      ) : !docs || docs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {canManage
            ? 'No documents uploaded yet. Use the button above to add module PDFs, maps, or other reference material.'
            : 'No documents have been shared for this campaign yet.'}
        </Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {[
                  'Filename',
                  'Description',
                  ...(canManage ? ['Visibility'] : []),
                  'Chunks',
                  'Added',
                  'Actions',
                ].map((h) => (
                  <TableCell key={h} sx={TABLE_HEADER_SX}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {docs.map((d) => (
                <TableRow key={d.id} hover>
                  <TableCell>{d.filename}</TableCell>
                  <TableCell>{d.description ?? '—'}</TableCell>
                  {canManage && (
                    <TableCell>
                      <Tooltip
                        title={d.is_public ? 'Public — visible to players' : 'Private — GM only'}
                      >
                        <Chip
                          size="small"
                          icon={d.is_public ? <PublicOutlinedIcon /> : <LockOutlinedIcon />}
                          label={d.is_public ? 'Public' : 'Private'}
                          color={d.is_public ? 'success' : 'default'}
                          variant="outlined"
                        />
                      </Tooltip>
                    </TableCell>
                  )}
                  <TableCell>{d.chunk_count}</TableCell>
                  <TableCell>{new Date(d.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      {d.file_path && (
                        <Tooltip title="View document">
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() =>
                              navigate(
                                `/guilds/${guildId}/campaigns/${campaignId}/documents/${d.id}`,
                              )
                            }
                            sx={{ minWidth: 0, px: 1 }}
                          >
                            <VisibilityOutlinedIcon fontSize="small" />
                          </Button>
                        </Tooltip>
                      )}
                      {canManage && (
                        <>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => openEdit(d)}
                          >
                            Edit
                          </Button>
                          <Button
                            size="small"
                            color="error"
                            variant="outlined"
                            disabled={deleteMutation.isPending}
                            onClick={() => deleteMutation.mutate(d.id)}
                          >
                            Delete
                          </Button>
                        </>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* RAG search test panel — GM/admin only */}
      {canManage && (
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">Test RAG Search</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Run a live semantic search against this campaign's indexed documents to verify
                retrieval quality. Lower distance scores mean a closer match.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
                <TextField
                  label="Search query"
                  value={testQuery}
                  onChange={(e) => {
                    setTestQuery(e.target.value);
                    setTestResult(null);
                  }}
                  size="small"
                  fullWidth
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && testQuery.trim())
                      searchMutation.mutate({ query: testQuery.trim(), docId: testDocId });
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
                    <MenuItem value="">
                      <em>All documents</em>
                    </MenuItem>
                    {(docs ?? []).map((d) => (
                      <MenuItem key={d.id} value={d.id}>
                        {d.filename}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  size="small"
                  disabled={!testQuery.trim() || searchMutation.isPending}
                  onClick={() =>
                    searchMutation.mutate({ query: testQuery.trim(), docId: testDocId })
                  }
                  sx={{ whiteSpace: 'nowrap', mt: { xs: 0, sm: '4px' } }}
                >
                  {searchMutation.isPending ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    'Search'
                  )}
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
                          <Stack
                            direction="row"
                            spacing={1}
                            alignItems="center"
                            flexWrap="wrap"
                            sx={{ mb: 1 }}
                          >
                            <Typography variant="caption" fontWeight="bold">
                              {chunk.filename}
                            </Typography>
                            <Chip
                              label={`chunk ${chunk.chunk_index}`}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={`score ${chunk.distance}`}
                              size="small"
                              color={
                                chunk.distance < 0.3
                                  ? 'success'
                                  : chunk.distance < 0.6
                                    ? 'warning'
                                    : 'default'
                              }
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

      {/* Upload dialog */}
      <Dialog open={uploadOpen} onClose={closeUpload} fullWidth maxWidth="sm">
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
              <Typography variant="caption" color="error">
                {uploadError}
              </Typography>
            )}
            <TextField
              label="Description (optional)"
              helperText="e.g. 'PF2e Beginner Box module', 'Dungeon map — floor 2', 'NPC roster'"
              value={uploadDesc}
              onChange={(e) => setUploadDesc(e.target.value)}
              multiline
              minRows={2}
              fullWidth
              size="small"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={uploadIsPublic}
                  onChange={(e) => setUploadIsPublic(e.target.checked)}
                  size="small"
                />
              }
              label={
                <Stack>
                  <Typography variant="body2">Make public</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Public documents are visible to all players and referenced by Grug when
                    answering their questions. Documents are private by default.
                  </Typography>
                </Stack>
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeUpload}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!uploadFile || uploadMutation.isPending}
            onClick={() =>
              uploadFile &&
              uploadMutation.mutate({
                file: uploadFile,
                description: uploadDesc,
                isPublic: uploadIsPublic,
              })
            }
          >
            {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
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
            <FormControlLabel
              control={
                <Switch
                  checked={editIsPublic}
                  onChange={(e) => setEditIsPublic(e.target.checked)}
                  size="small"
                />
              }
              label={
                <Stack>
                  <Typography variant="body2">Public</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Public documents are visible to players and referenced by Grug in
                    player queries.
                  </Typography>
                </Stack>
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDoc(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={editMutation.isPending}
            onClick={() =>
              editDoc &&
              editMutation.mutate({
                id: editDoc.id,
                description: editDesc,
                isPublic: editIsPublic,
              })
            }
          >
            {editMutation.isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
