import { Box, CircularProgress, Divider, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import client from '../api/client';

export default function RoadmapPage() {
  const { data, isLoading, isError } = useQuery<{ content: string }>({
    queryKey: ['roadmap'],
    queryFn: async () => {
      const res = await client.get<{ content: string }>('/api/roadmap');
      return res.data;
    },
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !data) {
    return (
      <Box sx={{ p: 4 }}>
        <Typography color="error">Failed to load roadmap.</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        maxWidth: 800,
        mx: 'auto',
        px: { xs: 2, sm: 4 },
        py: 4,
        // Markdown prose styles — all scoped so they don't bleed out
        '& h1': { typography: 'h4', fontWeight: 700, mt: 4, mb: 1 },
        '& h2': { typography: 'h5', fontWeight: 600, mt: 4, mb: 1 },
        '& h3': { typography: 'h6', fontWeight: 600, mt: 3, mb: 0.5 },
        '& p':  { typography: 'body1', color: 'text.secondary', my: 0.75 },
        '& ul, & ol': { pl: 3, my: 0.5, color: 'text.secondary' },
        '& li': { typography: 'body1', mb: 0.4 },
        '& li > ul, & li > ol': { mt: 0.25 },
        '& a': { color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
        '& code': {
          fontFamily: 'monospace',
          fontSize: '0.85em',
          bgcolor: 'action.hover',
          px: 0.5,
          py: 0.1,
          borderRadius: 0.5,
        },
        '& pre': {
          bgcolor: 'action.hover',
          borderRadius: 1,
          p: 2,
          overflow: 'auto',
          '& code': { bgcolor: 'transparent', p: 0 },
        },
        '& blockquote': {
          borderLeft: '3px solid',
          borderColor: 'divider',
          pl: 2,
          ml: 0,
          color: 'text.disabled',
          fontStyle: 'italic',
        },
        '& hr': { my: 2 },
        '& strong': { fontWeight: 700, color: 'text.primary' },
        '& table': { borderCollapse: 'collapse', width: '100%', my: 1.5 },
        '& th, & td': {
          border: '1px solid',
          borderColor: 'divider',
          px: 1.5,
          py: 0.75,
          typography: 'body2',
        },
        '& th': { bgcolor: 'action.hover', fontWeight: 600 },
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          hr: () => <Divider sx={{ my: 3 }} />,
        }}
      >
        {data.content}
      </ReactMarkdown>
    </Box>
  );
}
