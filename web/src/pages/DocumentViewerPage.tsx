/**
 * DocumentViewerPage — view or download a single campaign document.
 *
 * Accessible via /guilds/:guildId/campaigns/:campaignId/documents/:docId
 * Regular members can only view public documents; GMs and admins see all.
 */
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DownloadIcon from '@mui/icons-material/Download';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import client from '../api/client';
import type { Document } from '../types';

export default function DocumentViewerPage() {
  const { guildId, campaignId, docId } = useParams<{
    guildId: string;
    campaignId: string;
    docId: string;
  }>();
  const navigate = useNavigate();

  const {
    data: doc,
    isLoading,
    isError,
  } = useQuery<Document>({
    queryKey: ['campaign-document', guildId, campaignId, docId],
    queryFn: async () => {
      // Fetch the document list and find the requested document.
      // Non-GMs will only receive public docs from the list endpoint, which
      // naturally enforces visibility without a dedicated single-doc GET.
      const res = await client.get<Document[]>(
        `/api/guilds/${guildId}/campaigns/${campaignId}/documents`,
      );
      const found = res.data.find((d) => d.id === Number(docId));
      if (!found) throw new Error('Document not found or not accessible.');
      return found;
    },
    enabled: !!guildId && !!campaignId && !!docId,
    retry: false,
  });

  const downloadUrl = `/api/guilds/${guildId}/campaigns/${campaignId}/documents/${docId}/download`;

  const isPdf = doc?.filename.toLowerCase().endsWith('.pdf');
  const isText =
    doc?.filename.toLowerCase().endsWith('.txt') ||
    doc?.filename.toLowerCase().endsWith('.md') ||
    doc?.filename.toLowerCase().endsWith('.rst');

  const { data: textContent } = useQuery<string>({
    queryKey: ['campaign-document-text', guildId, campaignId, docId],
    queryFn: async () => {
      const res = await client.get<Blob>(downloadUrl, { responseType: 'blob' });
      return await (res.data as Blob).text();
    },
    enabled: !!doc && isText && !!doc.file_path,
    retry: false,
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !doc) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(`/guilds/${guildId}/campaigns`)}
          sx={{ mb: 2 }}
        >
          Back to Campaigns
        </Button>
        <Typography color="error">
          Document not found or you don't have permission to view it.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Back nav */}
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate(`/guilds/${guildId}/campaigns`)}
        sx={{ alignSelf: 'flex-start' }}
      >
        Back to Campaigns
      </Button>

      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
        <Typography variant="h6">{doc.filename}</Typography>
        <Chip
          size="small"
          icon={doc.is_public ? <PublicOutlinedIcon /> : <LockOutlinedIcon />}
          label={doc.is_public ? 'Public' : 'Private'}
          color={doc.is_public ? 'success' : 'default'}
          variant="outlined"
        />
        <Chip size="small" label={`${doc.chunk_count} chunks indexed`} variant="outlined" />
      </Stack>

      {doc.description && (
        <Typography variant="body2" color="text.secondary">
          {doc.description}
        </Typography>
      )}

      <Typography variant="caption" color="text.secondary">
        Added {new Date(doc.created_at).toLocaleDateString()}
      </Typography>

      <Divider />

      {/* Actions */}
      {doc.file_path && (
        <Stack direction="row" spacing={1}>
          <Button
            variant="contained"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => window.open(downloadUrl, '_blank')}
          >
            Download
          </Button>
        </Stack>
      )}

      {/* Inline viewer */}
      {doc.file_path ? (
        <>
          {isPdf && (
            <Box
              component="iframe"
              src={downloadUrl}
              sx={{
                width: '100%',
                height: '75vh',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
              }}
              title={doc.filename}
            />
          )}
          {isText && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              {textContent !== undefined ? (
                <Typography
                  variant="body2"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    maxHeight: '70vh',
                    overflow: 'auto',
                  }}
                >
                  {textContent}
                </Typography>
              ) : (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={20} />
                </Box>
              )}
            </Paper>
          )}
          {!isPdf && !isText && (
            <Typography variant="body2" color="text.secondary">
              Preview not available for this file type. Use the Download button above.
            </Typography>
          )}
        </>
      ) : (
        <Typography variant="body2" color="text.secondary">
          Raw file not available for this document (it was indexed before file storage was
          introduced). Only the extracted text chunks are available via Grug.
        </Typography>
      )}
    </Box>
  );
}
