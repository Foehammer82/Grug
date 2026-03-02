import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import GuildLayout from './components/GuildLayout';
import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import EventsPage from './pages/EventsPage';
import GlossaryPage from './pages/GlossaryPage';
import GuildConfigPage from './pages/GuildConfigPage';
import LoginPage from './pages/LoginPage';
import PersonalLayout from './components/PersonalLayout';
import PersonalRemindersPage from './pages/PersonalRemindersPage';
import PersonalTasksPage from './pages/PersonalTasksPage';
import RemindersPage from './pages/RemindersPage';
import TasksPage from './pages/TasksPage';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/personal" element={<PersonalLayout />}>
          <Route path="reminders" element={<PersonalRemindersPage />} />
          <Route path="tasks" element={<PersonalTasksPage />} />
        </Route>
        <Route path="/guilds/:guildId" element={<GuildLayout />}>
          <Route path="config" element={<GuildConfigPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="reminders" element={<RemindersPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="glossary" element={<GlossaryPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
