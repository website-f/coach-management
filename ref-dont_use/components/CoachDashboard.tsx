
import React, { useState, useEffect } from 'react';
import { User, Student, ProgressReport } from '../types';
import { 
  Calendar, CheckCircle2, Info,
  Users, Star, MessageSquare,
  Check, XCircle, Activity,
  Sparkles, Lock, RotateCcw, AlertCircle,
  ChevronLeft, ChevronRight, Save, FileCheck,
  ClipboardList, Clock3, Timer, MapPin, Hash, Target, ListTodo,
  LayoutDashboard, UserCheck as UserCheckIcon, Wallet
} from 'lucide-react';
import { CLASSES, SKILLS_LIST as INITIAL_SKILLS, PROGRESS_REPORTS, MOCK_LESSON_PLANS, MOCK_SESSION_LOGS } from '../constants';
import { summarizeReflection } from '../geminiService';

interface Props {
  coach: User;
  students: Student[];
  onUpdateStudent: (student: Student) => void;
}

const CoachDashboard: React.FC<Props> = ({ coach, students, onUpdateStudent }) => {
  const [activeTab, setActiveTab] = useState<'DASHBOARD' | 'SESSION_LOG' | 'PLAYER_EVALS' | 'ATTENDANCE' | 'EARNINGS'>('DASHBOARD');
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  
  // Checklist State
  const [checklistState, setChecklistState] = useState<{[taskId: number]: boolean}>({});

  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);

  // Date State for Attendance History
  const [currentViewDate, setCurrentViewDate] = useState(new Date());

  // Attendance records now managed via parent state, but need a local version for interaction before saving
  const [attendanceRecords, setAttendanceRecords] = useState<{[studentId: string]: {[date: string]: boolean}}>(
    students.reduce((acc, s) => ({...acc, [s.id]: s.attendance}), {})
  );
  
  // Confirmed/Locked Dates State
  const [confirmedDates, setConfirmedDates] = useState<Set<string>>(new Set());
  const [selectedDateForSubmission, setSelectedDateForSubmission] = useState<string>(new Date().toISOString().split('T')[0]);

  const myClasses = CLASSES.filter(c => c.coachId === coach.id);
  const selectedClass = myClasses.find(c => c.id === selectedClassId);
  const classStudents = students.filter(s => s.classId === selectedClassId);
  const activeStudent = classStudents.find(s => s.id === selectedStudentId);

  const currentLessonPlan = selectedClassId 
    ? MOCK_LESSON_PLANS.find(p => p.classId === selectedClassId) || MOCK_LESSON_PLANS[0]
    : null;
    
  // Dashboard Stats
  const totalStudents = myClasses.reduce((sum, cls) => sum + students.filter(s => s.classId === cls.id).length, 0);
  const pendingEvals = myClasses.filter(c => c.evaluationDueDate && new Date(c.evaluationDueDate) > new Date()).length;
  const urgentDeadlines = myClasses.filter(c => getDeadlineStatus(c.evaluationDueDate) === 'URGENT');


  useEffect(() => {
    setChecklistState({});
  }, [selectedClassId]);

  const approvedLogs = MOCK_SESSION_LOGS.filter(log => 
    log.status === 'APPROVED' && myClasses.some(c => c.id === log.classId)
  );
  const pendingLogs = MOCK_SESSION_LOGS.filter(log => 
    log.status === 'PENDING' && myClasses.some(c => c.id === log.classId)
  );

  const totalEarned = approvedLogs.reduce((acc, log) => {
     const cls = myClasses.find(c => c.id === log.classId);
     return acc + (cls?.salaryPerSession || 0);
  }, 0);

  const pendingEarned = pendingLogs.reduce((acc, log) => {
     const cls = myClasses.find(c => c.id === log.classId);
     return acc + (cls?.salaryPerSession || 0);
  }, 0);
  
  const handlePrevMonth = () => {
    setCurrentViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };
  const handleNextMonth = () => {
    setCurrentViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const getDaysInMonth = (date: Date) => {
    const days = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
    return Array.from({ length: days }, (_, i) => {
      const d = new Date(date.getFullYear(), date.getMonth(), i + 1);
      return { full: d.toISOString().split('T')[0], date: i + 1, day: d.toLocaleString('default', { weekday: 'short' }) };
    });
  };

  const monthDates = getDaysInMonth(currentViewDate);
  const currentMonthKey = currentViewDate.toISOString().slice(0, 7);
  const currentMonthName = currentViewDate.toLocaleString('default', { month: 'short' });

  const handleToggleAttendance = (studentId: string, date: string) => {
    if (confirmedDates.has(date)) return;
    const student = students.find(s => s.id === studentId);
    if (!student) return;
    
    const updatedAttendance = { ...student.attendance, [date]: !student.attendance[date] };
    onUpdateStudent({ ...student, attendance: updatedAttendance });
  };
  
  useEffect(() => {
    setAttendanceRecords(students.reduce((acc, s) => ({ ...acc, [s.id]: s.attendance }), {}));
  }, [students]);

  const confirmDailyAttendance = () => {
    if (!selectedDateForSubmission) return;
    setConfirmedDates(prev => new Set(prev).add(selectedDateForSubmission));
  };

  const undoDailyAttendance = () => {
    if (!selectedDateForSubmission) return;
    setConfirmedDates(prev => {
      const next = new Set(prev);
      next.delete(selectedDateForSubmission);
      return next;
    });
  };

  const handleUpdateSkill = (studentId: string, skill: string, rating: number) => {
    const studentToUpdate = students.find(s => s.id === studentId);
    if (!studentToUpdate) return;
    const updatedStudent = {
      ...studentToUpdate,
      skills: { ...studentToUpdate.skills, [skill]: rating }
    };
    onUpdateStudent(updatedStudent);
  };

  const handleUpdateReflection = (studentId: string, skill: string, text: string) => {
    const studentToUpdate = students.find(s => s.id === studentId);
    if (!studentToUpdate) return;
    const updatedStudent = {
      ...studentToUpdate,
      skillReflections: { ...studentToUpdate.skillReflections, [skill]: text }
    };
    onUpdateStudent(updatedStudent);
  };

  const handleGenerateReport = async () => {
    if (!activeStudent) return;
    setIsGeneratingReport(true);
    setReportSuccess(false);

    const notes = Object.entries(activeStudent.skillReflections || {})
      .filter(([skill]) => INITIAL_SKILLS.includes(skill))
      .map(([skill, note]) => `${skill}: ${note}`)
      .join('\n');
    
    const summary = await summarizeReflection(notes || "Student is showing consistent effort in all areas.");
    
    setTimeout(() => {
      setIsGeneratingReport(false);
      setReportSuccess(true);
      setTimeout(() => setReportSuccess(false), 3000);
    }, 1500);
  };

  const RatingStars = ({ value, onChange }: { value: number, onChange: (val: number) => void }) => (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button 
          key={star} 
          onClick={() => onChange(star)}
          className={`transition-all hover:scale-125 ${star <= value ? 'text-yellow-400 fill-yellow-400' : 'text-slate-200'}`}
        >
          <Star size={18} />
        </button>
      ))}
    </div>
  );

  function getDeadlineStatus(dateStr?: string) {
    if (!dateStr) return null;
    const deadline = new Date(dateStr);
    const now = new Date();
    const diff = (deadline.getTime() - now.getTime()) / (1000 * 3600 * 24);
    
    if (diff < 0) return 'EXPIRED';
    if (diff <= 3) return 'URGENT';
    return 'ON_TRACK';
  }

  const deadlineStatus = getDeadlineStatus(selectedClass?.evaluationDueDate);

  const tabs = [
    { id: 'DASHBOARD', label: 'Dashboard' },
    { id: 'SESSION_LOG', label: 'Session Log' },
    { id: 'PLAYER_EVALS', label: 'Player Evals' },
    { id: 'ATTENDANCE', label: 'Attendance' },
    { id: 'EARNINGS', label: 'Earnings' },
  ] as const;


  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex bg-white p-1 rounded-2xl border border-slate-200 w-fit overflow-x-auto max-w-full">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-6 py-2 rounded-xl text-sm font-bold transition-all whitespace-nowrap ${activeTab === tab.id ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-sky-600'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-4 gap-8">
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-xl font-bold flex items-center gap-2 px-2 uppercase tracking-tighter">
            <Calendar className="text-sky-600" size={20} /> Select Class
          </h3>
          <div className="space-y-3">
            {myClasses.map(cls => (
              <button key={cls.id} onClick={() => { setSelectedClassId(cls.id); setSelectedStudentId(null); }} className={`w-full text-left p-6 rounded-3xl border transition-all relative overflow-hidden group ${selectedClassId === cls.id ? 'bg-sky-600 border-sky-600 text-white shadow-xl' : 'bg-white border-slate-100 hover:border-sky-200 text-slate-900'}`}>
                <div className="flex justify-between items-start w-full">
                  <div className="pr-2">
                    <span className="font-sporty text-xl tracking-tight uppercase block mb-1">{cls.name}</span>
                    <p className={`text-[10px] font-black uppercase tracking-widest ${selectedClassId === cls.id ? 'text-sky-200' : 'text-slate-400'}`}>{cls.schedule}</p>
                  </div>
                  <div className={`shrink-0 px-2 py-1 rounded-lg text-[10px] font-black whitespace-nowrap ${selectedClassId === cls.id ? 'bg-white/20' : 'bg-slate-100 text-slate-500'}`}>
                     {students.filter(s => s.classId === cls.id).length} Students
                  </div>
                </div>
                {cls.evaluationDueDate && (
                  <div className={`mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg text-[8px] font-black uppercase tracking-widest border ${
                    selectedClassId === cls.id ? 'bg-white/20 border-white/30 text-white' : 'bg-slate-50 border-slate-100 text-slate-400'
                  }`}>
                    <Clock3 size={10} /> Due: {cls.evaluationDueDate}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3">
          {activeTab === 'DASHBOARD' && (
             <div className="grid lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-8">
                   <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                      <h2 className="text-3xl font-sporty tracking-tight text-slate-900 mb-1 uppercase">Welcome, {coach.name.split(' ')[0]}!</h2>
                      <p className="text-slate-500 font-medium">Here's your mission for today. Let's build champions.</p>
                   </div>
                   <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                      <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
                        <div className="p-2 bg-sky-600 text-white rounded-xl shadow-lg shadow-sky-200"><Target size={20} /></div>
                        <div>
                           <h3 className="font-bold text-lg text-slate-900 leading-none">Today's Focus: {selectedClass?.name || 'No Class Selected'}</h3>
                           <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest mt-1">Directives for {new Date().toLocaleDateString()}</p>
                        </div>
                      </div>
                      {!selectedClass ? (
                         <div className="text-center py-12 text-slate-400 italic">Please select a class to view the lesson plan.</div>
                      ) : currentLessonPlan && (
                         <div className="space-y-4 animate-in fade-in">
                            <div className="grid grid-cols-2 gap-4">
                               <button onClick={() => setActiveTab('ATTENDANCE')} className="p-4 bg-sky-50 border border-sky-100 text-sky-700 rounded-2xl text-xs font-black uppercase flex items-center justify-center gap-2 hover:bg-sky-100 transition-colors">Take Attendance</button>
                               <button onClick={() => setActiveTab('PLAYER_EVALS')} className="p-4 bg-sky-50 border border-sky-100 text-sky-700 rounded-2xl text-xs font-black uppercase flex items-center justify-center gap-2 hover:bg-sky-100 transition-colors">Evaluate Players</button>
                            </div>
                            <div className="space-y-2 pt-4">
                               {[
                                   { task: "Take Attendance (Priority)", completed: false }, 
                                   ...currentLessonPlan.checklist
                               ].map((item, idx) => (
                                  <div key={idx} className={`w-full text-left p-3 rounded-xl border flex items-center gap-3 ${ checklistState[idx] ? 'bg-green-50/50 border-green-200/50 text-green-800/70' : 'bg-white'}`}>
                                     <div className={`w-5 h-5 rounded-md flex items-center justify-center border-2 ${ checklistState[idx] ? 'bg-green-500 border-green-500 text-white' : 'bg-white border-slate-300'}`}>
                                        {checklistState[idx] && <Check size={12} strokeWidth={3} />}
                                     </div>
                                     <span className={`text-sm font-bold ${checklistState[idx] ? 'line-through opacity-70' : 'text-slate-600'}`}>{item.task}</span>
                                  </div>
                               ))}
                            </div>
                         </div>
                      )}
                   </div>
                </div>
                <div className="lg:col-span-1 space-y-8">
                   <div className="space-y-4">
                      <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex items-center gap-4">
                         <div className="p-3 bg-sky-50 text-sky-600 rounded-xl"><Users size={20}/></div>
                         <div><p className="text-3xl font-sporty leading-none">{totalStudents}</p><p className="text-[9px] font-black uppercase text-slate-400">Total Students</p></div>
                      </div>
                      <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex items-center gap-4">
                         <div className="p-3 bg-sky-50 text-sky-600 rounded-xl"><ClipboardList size={20}/></div>
                         <div><p className="text-3xl font-sporty leading-none">{myClasses.length}</p><p className="text-[9px] font-black uppercase text-slate-400">Classes Assigned</p></div>
                      </div>
                      <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex items-center gap-4">
                         <div className="p-3 bg-sky-50 text-sky-600 rounded-xl"><UserCheckIcon size={20}/></div>
                         <div><p className="text-3xl font-sporty leading-none">{pendingEvals}</p><p className="text-[9px] font-black uppercase text-slate-400">Pending Evals</p></div>
                      </div>
                   </div>
                   <div className="bg-white p-6 rounded-3xl border border-red-100 shadow-sm space-y-4">
                      <h4 className="text-[10px] font-black uppercase text-red-500 tracking-widest flex items-center gap-2"><AlertCircle size={14}/> Urgent Deadlines</h4>
                      <div className="space-y-2">
                        {urgentDeadlines.length > 0 ? urgentDeadlines.map(c => (
                           <div key={c.id} className="p-3 bg-red-50/50 rounded-xl text-xs">
                              <p className="font-bold text-red-800">{c.name}</p>
                              <p className="font-medium text-slate-500 text-[10px]">Due: {c.evaluationDueDate}</p>
                           </div>
                        )) : <p className="text-xs text-slate-400 italic">No urgent deadlines.</p>}
                      </div>
                   </div>
                </div>
             </div>
          )}

          {activeTab !== 'DASHBOARD' && !selectedClass && (
            <div className="h-96 bg-white rounded-[40px] border-2 border-dashed border-slate-100 flex flex-col items-center justify-center text-slate-400 gap-4 text-center p-12">
              <Users size={32} className="opacity-20" />
              <p className="font-bold">Select a class to continue.</p>
            </div>
          )}

          {activeTab !== 'DASHBOARD' && selectedClass && (
            <div className="space-y-6">
              {activeTab === 'SESSION_LOG' && (
                <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-8">
                  <div className="flex flex-col md:flex-row justify-between items-start gap-6">
                    <div>
                      <h2 className="text-3xl font-sporty tracking-tight text-slate-900 mb-1 uppercase">{selectedClass.name} Session Log</h2>
                      <p className="text-slate-500 font-medium">{selectedClass.schedule} • {classStudents.length} Students</p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <div className="bg-sky-50 border border-sky-100 px-4 py-2 rounded-2xl flex items-center gap-2">
                            <MapPin size={14} className="text-sky-600" />
                            <div className="flex flex-col">
                                <span className="text-[8px] font-black text-slate-400 uppercase tracking-widest">Venue Details</span>
                                <span className="text-[10px] font-bold text-slate-900">{selectedClass.location}</span>
                            </div>
                        </div>
                        {(selectedClass.hallNumber || selectedClass.courtNumber) && (
                            <div className="bg-sky-50 border border-sky-100 px-4 py-2 rounded-2xl flex items-center gap-2">
                                <Hash size={14} className="text-sky-600" />
                                <div className="flex flex-col">
                                    <span className="text-[8px] font-black text-slate-400 uppercase tracking-widest">Assignment</span>
                                    <span className="text-[10px] font-bold text-slate-900">
                                        {selectedClass.hallNumber ? `${selectedClass.hallNumber}` : ''} 
                                        {selectedClass.hallNumber && selectedClass.courtNumber ? ' • ' : ''}
                                        {selectedClass.courtNumber ? `${selectedClass.courtNumber}` : ''}
                                    </span>
                                </div>
                            </div>
                        )}
                        <span className="bg-green-100 text-green-700 px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-wider self-start">Session Active</span>
                    </div>
                  </div>

                  {currentLessonPlan && (
                    <div className="bg-slate-50 border border-slate-100 rounded-[32px] p-8 space-y-8 animate-in fade-in slide-in-from-right-4">
                       <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
                          <div className="p-2 bg-sky-600 text-white rounded-xl shadow-lg shadow-sky-200"><Target size={20} /></div>
                          <div>
                             <h3 className="font-bold text-lg text-slate-900 leading-none">Daily Lesson Plan</h3>
                             <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest mt-1">Directives for {new Date().toLocaleDateString()}</p>
                          </div>
                       </div>

                       <div className="grid md:grid-cols-3 gap-8">
                          <div className="md:col-span-1 space-y-4">
                             <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Core Focus Topics</h4>
                             <div className="flex flex-wrap gap-2">
                                {currentLessonPlan.topics.map((topic, i) => (
                                   <span key={i} className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-700 shadow-sm">{topic}</span>
                                ))}
                             </div>
                          </div>
                          
                          <div className="md:col-span-2 space-y-4">
                             <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-widest flex items-center gap-2">
                                <ListTodo size={14} /> Session Tasks Checklist
                             </h4>
                             <div className="space-y-2">
                                {[
                                    { task: "Take Attendance (Priority)", completed: false }, 
                                    ...currentLessonPlan.checklist
                                ].map((item, idx) => (
                                   <button 
                                      key={idx}
                                      onClick={() => setChecklistState(prev => ({...prev, [idx]: !prev[idx]}))}
                                      className={`w-full text-left p-3 rounded-xl border transition-all flex items-center gap-3 group ${
                                         checklistState[idx] 
                                            ? 'bg-green-50 border-green-200 text-green-800' 
                                            : idx === 0 
                                                ? 'bg-yellow-50 border-yellow-200 text-yellow-900 hover:border-yellow-300' 
                                                : 'bg-white border-slate-200 hover:border-sky-300 text-slate-600'
                                      }`}
                                   >
                                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center border transition-all ${
                                         checklistState[idx] 
                                            ? 'bg-green-500 border-green-500 text-white' 
                                            : idx === 0 
                                                ? 'bg-white border-yellow-400 text-yellow-400' 
                                                : 'bg-white border-slate-300'
                                      }`}>
                                         {checklistState[idx] && <Check size={14} strokeWidth={3} />}
                                         {!checklistState[idx] && idx === 0 && <AlertCircle size={14} />}
                                      </div>
                                      <span className={`text-sm font-bold ${checklistState[idx] ? 'line-through opacity-70' : ''}`}>
                                        {item.task}
                                        {idx === 0 && !checklistState[idx] && <span className="ml-2 text-[10px] font-black bg-yellow-400 text-white px-1.5 py-0.5 rounded uppercase tracking-wide">Action Required</span>}
                                      </span>
                                   </button>
                                ))}
                             </div>
                             <div className="flex justify-end pt-2">
                                <p className="text-[10px] text-slate-400 italic font-medium">
                                   {Object.values(checklistState).filter(Boolean).length}/{currentLessonPlan.checklist.length + 1} tasks completed
                                </p>
                             </div>
                          </div>
                       </div>
                    </div>
                  )}

                  <div className="pt-4 border-t border-slate-100">
                    <h4 className="font-bold flex items-center gap-2 text-slate-800 mb-4 uppercase tracking-widest text-xs"><Info className="text-yellow-500" size={16} /> Honest Session Reflection</h4>
                    <textarea className="w-full p-6 bg-black text-white rounded-[32px] focus:ring-4 focus:ring-sky-600 transition-all text-sm placeholder:text-slate-600 border-none font-medium" placeholder="Analyze your class performance honestly. Admin will use this to track student growth." rows={4} />
                    <button className="w-full mt-6 bg-sky-600 text-white py-5 rounded-2xl font-black uppercase tracking-[0.2em] hover:bg-sky-700 shadow-xl shadow-sky-100 transition-all active:scale-95">Submit Log & Complete Class</button>
                  </div>
                </div>
              )}

              {activeTab === 'PLAYER_EVALS' && (
                <div className="grid lg:grid-cols-5 gap-8">
                  <div className="lg:col-span-2 space-y-6">
                    <div className="flex items-center justify-between px-2">
                        <h4 className="font-bold flex items-center gap-2 text-slate-800 uppercase tracking-widest text-xs">
                          <Users className="text-sky-600" size={16} /> Student Roster
                        </h4>
                    </div>

                    <div className="space-y-2">
                        {classStudents.map(student => (
                          <button key={student.id} onClick={() => setSelectedStudentId(student.id)} className={`w-full text-left p-4 rounded-2xl border transition-all flex items-center gap-4 ${selectedStudentId === student.id ? 'bg-slate-900 border-slate-900 text-white shadow-xl' : 'bg-white border-slate-100 hover:border-slate-200 text-slate-900'}`}>
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${selectedStudentId === student.id ? 'bg-sky-600' : 'bg-slate-100'}`}>
                              {student.name.charAt(0)}
                            </div>
                            <div className="flex-1 overflow-hidden">
                              <p className="font-bold truncate leading-tight">{student.name}</p>
                            </div>
                          </button>
                        ))}
                    </div>
                  </div>
                  <div className="lg:col-span-3">
                     {activeStudent ? (
                       <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-8 animate-in fade-in slide-in-from-right-4 duration-500">
                          <div className="flex justify-between items-center border-b border-slate-100 pb-6">
                            <div className="space-y-2">
                              <h3 className="text-2xl font-sporty tracking-tight uppercase leading-none">Evaluation: {activeStudent.name}</h3>
                              {selectedClass.evaluationDueDate && (
                                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-xl text-[10px] font-black uppercase tracking-[0.1em] border shadow-sm ${
                                  deadlineStatus === 'URGENT' 
                                    ? 'bg-red-50 text-red-600 border-red-100 animate-pulse' 
                                    : 'bg-sky-50 text-sky-600 border-sky-100'
                                }`}>
                                  <Timer size={14} /> 
                                  <span>{deadlineStatus === 'URGENT' ? 'Urgent Deadline' : 'Submission Due'}: {selectedClass.evaluationDueDate}</span>
                                </div>
                              )}
                            </div>
                            <button 
                              disabled={isGeneratingReport}
                              onClick={handleGenerateReport}
                              className={`flex items-center gap-2 px-6 py-3 rounded-2xl font-black uppercase tracking-widest text-[10px] shadow-xl transition-all active:scale-95 ${
                                reportSuccess ? 'bg-green-500 text-white shadow-green-100' : 
                                isGeneratingReport ? 'bg-slate-100 text-slate-400' : 'bg-sky-600 text-white shadow-sky-100 hover:bg-sky-700'
                              }`}
                            >
                              {reportSuccess ? <Check size={14} /> : isGeneratingReport ? <RotateCcw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                              {reportSuccess ? 'Report Sent' : isGeneratingReport ? 'Generating...' : 'Finalize & Send Report'}
                            </button>
                          </div>

                          <div className="space-y-6">
                            <div className="flex items-center justify-between">
                              <h4 className="font-bold text-xs uppercase tracking-widest text-slate-400">Progression Checklist</h4>
                              <span className="text-[10px] font-black bg-slate-100 text-slate-500 px-2 py-1 rounded">Academy Standard</span>
                            </div>
                            
                            <div className="grid gap-6">
                               {INITIAL_SKILLS.map(skill => (
                                 <div key={skill} className="space-y-3 p-6 bg-slate-50 rounded-3xl border border-slate-100 group hover:border-sky-200 transition-all">
                                    <div className="flex items-center justify-between">
                                      <span className="font-bold text-slate-800 text-sm uppercase tracking-tight">{skill} Proficiency</span>
                                      <RatingStars 
                                        value={activeStudent.skills[skill] || 0} 
                                        onChange={(val) => handleUpdateSkill(activeStudent.id, skill, val)} 
                                      />
                                    </div>
                                    <div className="relative">
                                      <MessageSquare size={12} className="absolute top-4 left-4 text-slate-300" />
                                      <textarea 
                                        value={activeStudent.skillReflections?.[skill] || ''}
                                        onChange={(e) => handleUpdateReflection(activeStudent.id, skill, e.target.value)}
                                        className="w-full pl-10 pr-4 py-3 bg-white border border-slate-200 rounded-xl text-xs font-medium placeholder:text-slate-300 focus:ring-2 focus:ring-sky-600 focus:border-transparent outline-none transition-all"
                                        placeholder={`Notes for ${skill} development...`}
                                        rows={2}
                                      />
                                    </div>
                                 </div>
                               ))}
                            </div>
                          </div>
                       </div>
                     ) : (
                       <div className="h-full bg-white rounded-[40px] border border-slate-100 border-dashed flex flex-col items-center justify-center text-slate-300 p-12 text-center">
                          <ClipboardList size={48} className="mb-4 opacity-10" />
                          <p className="font-bold italic text-slate-400">Select a player to begin evaluation.</p>
                       </div>
                     )}
                  </div>
                </div>
              )}

              {activeTab === 'ATTENDANCE' && (
                <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm animate-in fade-in slide-in-from-right-4 duration-500 space-y-8">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-slate-100">
                     <div>
                        <h3 className="text-2xl font-sporty uppercase tracking-tight">Attendance & Fee Status View</h3>
                        <div className="flex items-center gap-2 mt-1">
                           <button onClick={handlePrevMonth} className="p-1 hover:bg-slate-100 rounded-lg text-sky-600 transition-colors"><ChevronLeft size={16} /></button>
                           <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">{currentViewDate.toLocaleString('default', { month: 'long', year: 'numeric' })}</p>
                           <button onClick={handleNextMonth} className="p-1 hover:bg-slate-100 rounded-lg text-sky-600 transition-colors"><ChevronRight size={16} /></button>
                        </div>
                     </div>
                     <div className="flex flex-wrap gap-4 items-center bg-slate-50 p-4 rounded-3xl border border-slate-100">
                        <div className="flex items-center gap-3">
                           <Calendar size={18} className="text-sky-600" />
                           <select className="bg-transparent text-sm font-bold text-slate-900 border-none focus:ring-0 outline-none cursor-pointer" value={selectedDateForSubmission} onChange={(e) => setSelectedDateForSubmission(e.target.value)}>
                              {monthDates.map(d => (<option key={d.full} value={d.full}>{d.date} {d.day}</option>))}
                           </select>
                        </div>
                        <div className="h-6 w-px bg-slate-200"></div>
                        {confirmedDates.has(selectedDateForSubmission) ? (
                          <div className="flex items-center gap-3 animate-in fade-in slide-in-from-right-2">
                             <span className="flex items-center gap-1.5 px-3 py-1.5 bg-green-100 text-green-700 rounded-xl text-[10px] font-black uppercase">
                                <Lock size={12} /> Logged
                             </span>
                             <button onClick={undoDailyAttendance} className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-red-500 border border-red-100 rounded-xl text-[10px] font-black uppercase hover:bg-red-500 hover:text-white transition-all shadow-sm">
                                <RotateCcw size={12} /> Edit
                             </button>
                          </div>
                        ) : (
                          <button onClick={confirmDailyAttendance} className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-xl text-xs font-black uppercase tracking-widest hover:bg-sky-700 shadow-lg shadow-sky-100 transition-all active:scale-95">
                             <CheckCircle2 size={16} /> Confirm Log
                          </button>
                        )}
                     </div>
                  </div>

                  <div className="overflow-x-auto pb-4">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr>
                          <th className="text-left p-4 sticky left-0 bg-white z-20 min-w-[340px] border-b border-slate-100"><span className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Student / Payment History View</span></th>
                          {monthDates.map(d => (
                            <th key={d.full} className={`p-2 border-b border-slate-100 min-w-[50px] transition-all ${confirmedDates.has(d.full) ? 'bg-sky-50/50' : ''}`}>
                              <div className="flex flex-col items-center">
                                <span className="text-[10px] font-black text-sky-600 uppercase">{d.day}</span>
                                <span className="text-sm font-bold text-slate-900">{d.date}</span>
                                {confirmedDates.has(d.full) && <Lock size={10} className="text-sky-400 mt-0.5" />}
                              </div>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {classStudents.map(student => {
                          const totalAttended = Object.values(attendanceRecords[student.id] || {}).filter(Boolean).length;
                          const isPaid = (student.payments[currentMonthKey] as any)?.status === 'PAID';
                          
                          const allUnpaidPaymentKeys = Object.entries(student.payments)
                              .filter(([key, val]: [string, any]) => val.status === 'UNPAID')
                              .map(([key]) => key)
                              .sort();

                          const missedMonthsCount = allUnpaidPaymentKeys.length;
                          const missedMonthsList = allUnpaidPaymentKeys.map(key => {
                              const [year, month] = key.split('-');
                              return new Date(parseInt(year), parseInt(month) - 1).toLocaleString('default', { month: 'short' });
                          }).join(', ');

                          return (
                            <tr key={student.id} className={`transition-colors ${!isPaid ? 'bg-red-50/40 hover:bg-red-50/60' : 'hover:bg-slate-50/50'}`}>
                              <td className={`p-4 sticky left-0 z-20 border-b border-slate-50 font-bold text-slate-800 flex items-center justify-between gap-3 ${!isPaid ? 'bg-red-50/10' : 'bg-white'}`}>
                                 <div className="flex items-center gap-3">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs relative ${!isPaid ? 'bg-red-100' : 'bg-slate-100'}`}>
                                       {student.name.charAt(0)}
                                    </div>
                                    <div className="flex flex-col">
                                       <div className="flex items-center gap-2">
                                         <span className="text-sm font-bold truncate max-w-[140px]">{student.name}</span>
                                         {!isPaid && <AlertCircle size={14} className="text-red-500 shrink-0" />}
                                       </div>
                                       
                                       <div className="flex flex-col gap-1 mt-1">
                                          <div>
                                              {isPaid ? (
                                                  <span className="text-[8px] font-black text-green-600 uppercase px-1.5 py-0.5 bg-green-50 rounded border border-green-100">{currentMonthName} Paid</span>
                                              ) : (
                                                  <span className="text-[8px] font-black text-white uppercase px-1.5 py-0.5 bg-red-600 rounded border border-red-700 shadow-sm">{currentMonthName} Pending</span>
                                              )}
                                          </div>

                                          {missedMonthsCount > 0 && (
                                              <div className="bg-red-50 border border-red-100 rounded-lg p-1.5 flex flex-col gap-0.5">
                                                  <span className="text-[8px] font-black text-red-600 uppercase flex items-center gap-1">
                                                      <AlertCircle size={8} /> {missedMonthsCount} Months Missed
                                                  </span>
                                                  <span className="text-[8px] font-bold text-slate-500 leading-tight max-w-[120px] flex flex-wrap">
                                                      {missedMonthsList}
                                                  </span>
                                              </div>
                                          )}
                                      </div>
                                    </div>
                                 </div>
                                 <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg shrink-0 ${!isPaid ? 'bg-red-100 text-red-600' : 'bg-sky-50 text-sky-600'}`}>
                                    <Activity size={10} />
                                    <span className="text-[10px] font-black">{totalAttended}</span>
                                 </div>
                              </td>
                              {monthDates.map(d => {
                                const isPresent = (attendanceRecords[student.id] || {})[d.full];
                                const isLocked = confirmedDates.has(d.full);
                                return (
                                  <td key={d.full} className={`p-1 border-b border-slate-50 text-center transition-all ${isLocked ? 'bg-sky-50/30' : ''}`}>
                                    <button disabled={isLocked} onClick={() => handleToggleAttendance(student.id, d.full)} className={`w-8 h-8 rounded-lg transition-all flex items-center justify-center relative ${isPresent ? 'bg-sky-600 text-white shadow-lg shadow-sky-100' : 'bg-slate-100 text-transparent border border-slate-200'}`}>
                                      <Check size={14} />
                                      {isLocked && <div className="absolute inset-0 bg-slate-900/10 rounded-lg"></div>}
                                    </button>
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {activeTab === 'EARNINGS' && (
                <div className="grid md:grid-cols-2 gap-8">
                  <div className="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm relative overflow-hidden group">
                     <h3 className="text-slate-400 font-black text-[10px] uppercase tracking-[0.2em] mb-4">Current Verified Earned</h3>
                     <p className="text-6xl font-sporty tracking-tight text-green-600 leading-none">RM {totalEarned}</p>
                     <p className="text-xs font-bold text-slate-400 mt-4 uppercase tracking-widest">Calculated from approved sessions</p>
                  </div>
                   <div className="bg-white p-10 rounded-[40px] border border-slate-100 shadow-sm relative overflow-hidden group">
                     <h3 className="text-slate-400 font-black text-[10px] uppercase tracking-[0.2em] mb-4">Pending Approval</h3>
                     <p className="text-6xl font-sporty tracking-tight text-yellow-500 leading-none">RM {pendingEarned}</p>
                     <p className="text-xs font-bold text-slate-400 mt-4 uppercase tracking-widest">Awaiting admin verification</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CoachDashboard;