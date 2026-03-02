import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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

export default function DocumentsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: docs, isLoading } = useQuery<Document[]>({
    queryKey: ['documents', guildId],
    queryFn: async () => {
      const res = await client.get<Document[]>(`/api/guilds/${guildId}/documents`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/documents/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', guildId] }),
  });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="body2" color="text.secondary">
          Text files indexed for Grug to search during conversation (RAG). When you ask Grug
          about rules, lore, or campaign notes, Grug looks here first. Upload files using
          the <strong>/upload_doc</strong> Discord slash command.
        </Typography>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !docs || docs.length === 0 ? (
        <Typography color="text.secondary">No documents indexed.</Typography>
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
                <Button
                  size="small"
                  color="error"
                  variant="outlined"
                  onClick={() => deleteMutation.mutate(d.id)}
                  disabled={deleteMutation.isPending}
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
        </TableContainer>
      )}
    </Box>
  );
}
