
import React, { useState } from 'react';
import { User, LandingPageContent, Student } from './types';
import { DEFAULT_LANDING_CONTENT, STUDENTS as MOCK_STUDENTS } from './constants';
import LandingPage from './components/LandingPage';
import AdminDashboard from './components/AdminDashboard';
import CoachDashboard from './components/CoachDashboard';
import ClientPortal from './components/ClientPortal';
import { Navigation } from './components/Navigation';

const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [view, setView] = useState<'LANDING' | 'DASHBOARD'>('LANDING');
  
  // Lifted state for shared data
  const [students, setStudents] = useState<Student[]>(MOCK_STUDENTS);
  const [landingContent, setLandingContent] = useState<LandingPageContent>(DEFAULT_LANDING_CONTENT);

  const handleLogin = (user: User) => {
    setCurrentUser(user);
    setView('DASHBOARD');
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setView('LANDING');
  };

  const handleUpdateStudent = (updatedStudent: Student) => {
    setStudents(prevStudents => 
      prevStudents.map(s => s.id === updatedStudent.id ? updatedStudent : s)
    );
  };
  
  const handleUpdateStudents = (newStudents: Student[]) => {
    setStudents(newStudents);
  };

  const handleUpdateSelf = (updates: Partial<User>) => {
    if (currentUser) {
      setCurrentUser(prev => ({ ...prev!, ...updates }));
    }
  };

  const renderDashboard = () => {
    if (!currentUser) return null;

    switch (currentUser.role) {
      case 'ADMIN':
        return <AdminDashboard 
                  students={students} 
                  onUpdateStudents={setStudents}
                  landingContent={landingContent} 
                  onUpdateLandingContent={setLandingContent} 
                />;
      case 'COACH':
        return <CoachDashboard 
                  coach={currentUser} 
                  students={students}
                  onUpdateStudent={handleUpdateStudent}
                />;
      case 'CLIENT':
        const studentProfile = students.find(s => s.parentId === currentUser.id);
        if (!studentProfile) {
          return <div>Error: Student profile not found.</div>;
        }
        return <ClientPortal 
                  user={currentUser} 
                  student={studentProfile}
                  onUpdateStudent={handleUpdateStudent}
                  onUpdateSelf={handleUpdateSelf}
                />;
      default:
        return null;
    }
  };

  if (view === 'LANDING') {
    return <LandingPage onLogin={handleLogin} content={landingContent} />;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navigation user={currentUser!} onLogout={handleLogout} />
      <main className={`pt-20 pb-12 ${currentUser?.role === 'ADMIN' ? '' : 'px-4 max-w-7xl mx-auto'}`}>
        {renderDashboard()}
      </main>
    </div>
  );
};

export default App;
