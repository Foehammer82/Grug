import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
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
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface Document {
  id: number;
  filename: string;
  description: string | null;
  chunk_count: number;
  created_at: string;
}

const HEADER_SX = {
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.05em',
  color: 'text.secondary',
};

const ALLOWED_EXT = ['.txt', '.md', '.rst', '.pdf'];

export default function DocumentsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  // Upload dialog state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Edit dialog state
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [editDesc, setEditDesc] = useState('');

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
        <Button variant="contained" size="small" onClick={() => setUploadOpen(true)}>
          Upload Document
        </Button>
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
                {['Filename', 'Description', 'Chunks', 'Added', 'Actions'].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
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
