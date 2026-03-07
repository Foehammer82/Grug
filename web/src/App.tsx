import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import GuildLayout from './components/GuildLayout';
import AdminPage from './pages/AdminPage';
import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import EventsPage from './pages/EventsPage';
import GlossaryPage from './pages/GlossaryPage';
import GuildConfigPage from './pages/GuildConfigPage';
import LoginPage from './pages/LoginPage';
import NotesPage from './pages/NotesPage';
import PersonalLayout from './components/PersonalLayout';
import NotFoundPage from './pages/NotFoundPage';
import PersonalConfigPage from './pages/PersonalConfigPage';
import PersonalNotesPage from './pages/PersonalNotesPage';
import PersonalTasksPage from './pages/PersonalTasksPage';
import CampaignsPage from './pages/CampaignsPage';
import CampaignDetailPage from './pages/CampaignDetailPage';
import CharacterSheetPage from './pages/CharacterSheetPage';
import TasksPage from './pages/TasksPage';
import { useBotAvatar } from './hooks/useBotAvatar';


function App() {
  const botAvatar = useBotAvatar();

  // Keep the favicon in sync with the bot's Discord profile picture.
  useEffect(() => {
    const link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (link && botAvatar) {
      link.href = botAvatar;
    }
  }, [botAvatar]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/personal" element={<PersonalLayout />}>
          <Route index element={<Navigate to="config" replace />} />
          <Route path="config" element={<PersonalConfigPage />} />
          <Route path="tasks" element={<PersonalTasksPage />} />
          <Route path="notes" element={<PersonalNotesPage />} />
        </Route>
        <Route path="/guilds/:guildId" element={<GuildLayout />}>
          <Route path="config" element={<GuildConfigPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="glossary" element={<GlossaryPage />} />
          <Route path="notes" element={<NotesPage />} />
          <Route path="campaigns" element={<CampaignsPage />} />
          <Route path="campaigns/:campaignId" element={<CampaignDetailPage />} />
          <Route path="characters/:characterId" element={<CharacterSheetPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
