import { Navigate, Route, Routes } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import EventsPage from './pages/EventsPage';
import GuildConfigPage from './pages/GuildConfigPage';
import LoginPage from './pages/LoginPage';
import TasksPage from './pages/TasksPage';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/guilds/:guildId/config" element={<GuildConfigPage />} />
      <Route path="/guilds/:guildId/events" element={<EventsPage />} />
      <Route path="/guilds/:guildId/tasks" element={<TasksPage />} />
      <Route path="/guilds/:guildId/documents" element={<DocumentsPage />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
