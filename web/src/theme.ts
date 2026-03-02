import { createTheme } from '@mui/material/styles';

const shared = {
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif',
  },
};

export const darkTheme = createTheme({
  ...shared,
  palette: {
    mode: 'dark',
    primary:   { main: '#58a6ff', dark: '#388bfd', light: '#79b8ff', contrastText: '#fff' },
    error:     { main: '#f85149' },
    success:   { main: '#3fb950' },
    background: { default: '#0d1117', paper: '#161b22' },
    divider:   '#30363d',
    text: {
      primary:   '#e6edf3',
      secondary: 'rgba(220,232,242,0.60)',
      disabled:  'rgba(220,232,242,0.30)',
    },
  },
  components: {
    MuiAppBar:     { defaultProps: { elevation: 0 }, styleOverrides: { root: { borderBottom: '1px solid #30363d', backgroundColor: '#010409' } } },
    MuiTableHead:  { styleOverrides: { root: { '& .MuiTableCell-head': { background: '#21262d', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'rgba(220,232,242,0.60)' } } } },
    MuiTableCell:  { styleOverrides: { root: { borderColor: '#30363d' } } },
    MuiTableRow:   { styleOverrides: { root: { '&:last-child td': { border: 0 }, '&:hover': { backgroundColor: 'rgba(88,166,255,0.06)' } } } },
    MuiPaper:      { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiCard:       { styleOverrides: { root: { backgroundImage: 'none', border: '1px solid #30363d' } } },
    MuiChip:       { styleOverrides: { root: { fontWeight: 600 } } },
    MuiButton:     { styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
    MuiToggleButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 500 } } },
    MuiTab:        { styleOverrides: { root: { '&:focus-visible': { outline: 'none' }, '&.Mui-focusVisible': { outline: 'none' } } } },
  },
});

export const lightTheme = createTheme({
  ...shared,
  palette: {
    mode: 'light',
    primary:   { main: '#0969da', dark: '#0550ae', light: '#218bff', contrastText: '#fff' },
    error:     { main: '#cf222e' },
    success:   { main: '#1a7f37' },
    background: { default: '#ffffff', paper: '#f6f8fa' },
    divider:   '#d0d7de',
    text: {
      primary:   '#1f2328',
      secondary: 'rgba(87,96,106,0.85)',
      disabled:  'rgba(87,96,106,0.45)',
    },
  },
  components: {
    MuiAppBar:     { defaultProps: { elevation: 0 }, styleOverrides: { root: { borderBottom: '1px solid #d0d7de', backgroundColor: '#f6f8fa', color: '#1f2328' } } },
    MuiTableHead:  { styleOverrides: { root: { '& .MuiTableCell-head': { background: '#eaeef2', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'rgba(87,96,106,0.85)' } } } },
    MuiTableCell:  { styleOverrides: { root: { borderColor: '#d0d7de' } } },
    MuiTableRow:   { styleOverrides: { root: { '&:last-child td': { border: 0 }, '&:hover': { backgroundColor: 'rgba(9,105,218,0.04)' } } } },
    MuiCard:       { styleOverrides: { root: { border: '1px solid #d0d7de' } } },
    MuiChip:       { styleOverrides: { root: { fontWeight: 600 } } },
    MuiButton:     { styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
    MuiToggleButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 500 } } },
    MuiTab:        { styleOverrides: { root: { '&:focus-visible': { outline: 'none' }, '&.Mui-focusVisible': { outline: 'none' } } } },
  },
});
