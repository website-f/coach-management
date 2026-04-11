
import React, { useState, useMemo, useRef } from 'react';
import { 
  BarChart3, Users, DollarSign, Calendar, 
  CheckCircle2, Video, FileText, Plus,
  ArrowUpRight, ArrowDownRight, Zap,
  TrendingUp, Trophy, Activity, MessageSquare,
  Search, Filter, ChevronRight, Star, XCircle, Clock3, Edit3, Save, Trash2, ListChecks,
  PieChart as PieIcon, Receipt, Download, FileSpreadsheet, RotateCcw, History, LayoutGrid,
  Coins, UserMinus, UserCheck, Info, MapPin, Folder, FolderOpen, MoreVertical, ExternalLink,
  MoveHorizontal, Check, Lock, Unlock, CreditCard, Ban, AlertCircle, ChevronLeft, ShoppingBag, GraduationCap,
  Cloud, Timer, BookOpen, Quote, Map as MapIcon, Hash, Settings, UserPlus, Trash, Camera, Upload, X, Play,
  Wallet, Send, Bell, Eye, CheckCircle, Image as ImageIcon, ThumbsUp, Table2, Printer, AlertTriangle,
  ClipboardList, CheckSquare, Square, Inbox, Globe, List, ArrowRightLeft, Package, Tag, Minus, Clock, EyeOff, Shield, Key
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell, Legend,
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts';
import { 
  TRANSACTIONS as MOCK_TRANSACTIONS, 
  CLASSES as MOCK_CLASSES, 
  SKILLS_LIST, 
  MOCK_COACH, 
  MOCK_COACH_2, 
  PRODUCTS,
  MOCK_SESSION_LOGS,
  MOCK_ADMIN,
  MOCK_LESSON_PLANS,
  MOCK_APPLICATIONS
} from '../constants';
import { generateTrainingPlan } from '../geminiService';
import { Student, TrainingClass, Transaction, User, Role, SessionCompletion, Application, LandingPageContent, Product } from '../types';

const COLORS = ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
const INCOME_COLORS = ['#10b981', '#34d399', '#6ee7b7', '#059669'];
const EXPENSE_COLORS = ['#ef4444', '#f87171', '#fca5a5', '#dc2626'];

interface Props {
  students: Student[];
  onUpdateStudents: (students: Student[] | ((prev: Student[]) => Student[])) => void;
  landingContent: LandingPageContent;
  onUpdateLandingContent: (content: LandingPageContent) => void;
}

const AdminDashboard: React.FC<Props> = ({ students, onUpdateStudents, landingContent, onUpdateLandingContent }) => {
  const [activeTab, setActiveTab] = useState<'FINANCE' | 'OPS' | 'PLANNING' | 'COACHES' | 'APPLICATIONS' | 'WEBSITE' | 'STORE'>('FINANCE');
  
  // Finance Sub-states
  const [financeView, setFinanceView] = useState<'OVERVIEW' | 'LEDGER'>('OVERVIEW');
  const [ledgerType, setLedgerType] = useState<'GENERAL' | 'INCOME' | 'EXPENSE' | 'FEES'>('GENERAL');
  const [feeFilter, setFeeFilter] = useState<'ALL' | 'OVERDUE' | 'PAID'>('ALL');

  // OPS States
  const [currentViewDate, setCurrentViewDate] = useState(new Date());
  const [confirmedDates, setConfirmedDates] = useState<Set<string>>(new Set());
  const [selectedDateForSubmission, setSelectedDateForSubmission] = useState<string>(new Date().toISOString().split('T')[0]);

  const [selectedLocation, setSelectedLocation] = useState<string | 'ALL'>('ALL');
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [trainingPlan, setTrainingPlan] = useState('');
  
  // Edit State
  const [isEditingClass, setIsEditingClass] = useState(false);
  const [editForm, setEditForm] = useState<Partial<TrainingClass>>({});

  // Product / Store State
  const [products, setProducts] = useState<Product[]>(PRODUCTS);
  const [isEditingProduct, setIsEditingProduct] = useState(false);
  const [productForm, setProductForm] = useState<Partial<Product>>({});
  const productFileInputRef = useRef<HTMLInputElement>(null);

  // Transfer State
  const [transferTargets, setTransferTargets] = useState<Record<string, string>>({});

  // Coach Management States
  const [coachesList, setCoachesList] = useState<User[]>([MOCK_COACH, MOCK_COACH_2, { id: 'admin1', name: 'RSBE Founder (Coach)', role: Role.COACH, avatar: 'https://i.pravatar.cc/150?u=admin', username: 'admin', password: 'password123' }]);
  const [selectedCoachId, setSelectedCoachId] = useState<string | null>(MOCK_COACH.id);
  const [coachView, setCoachView] = useState<'REFLECTIONS' | 'EVALUATIONS'>('REFLECTIONS');
  const [auditStudentId, setAuditStudentId] = useState<string | null>(null);
  const [coachSubView, setCoachSubView] = useState<'OVERVIEW' | 'CREDENTIALS' | 'HIRE'>('OVERVIEW');
  
  // New Coach Form State
  const [newCoachForm, setNewCoachForm] = useState({ name: '', email: '', username: '', password: '' });

  // Application State
  const [applications, setApplications] = useState<Application[]>(MOCK_APPLICATIONS);
  const [appLocationFilter, setAppLocationFilter] = useState<string>('ALL');

  // Website Edit State
  const [websiteForm, setWebsiteForm] = useState<LandingPageContent>(landingContent);
  const [newProgram, setNewProgram] = useState('');
  const [newLocation, setNewLocation] = useState('');

  // Master Data State (some remain local to admin)
  const [transactions, setTransactions] = useState<Transaction[]>(MOCK_TRANSACTIONS);
  const [classes, setClasses] = useState<TrainingClass[]>(MOCK_CLASSES);
  const [sessionLogs, setSessionLogs] = useState<SessionCompletion[]>(MOCK_SESSION_LOGS);
  
  // Proof Review State
  const [reviewingProof, setReviewingProof] = useState<{studentId: string, monthKey: string} | null>(null);
  const proofStudent = useMemo(() => students.find(s => s.id === reviewingProof?.studentId), [students, reviewingProof]);

  // Derived Locations
  const allLocations = useMemo(() => {
    const locsFromClasses = classes.map(c => c.location);
    return Array.from(new Set(['ALL', ...locsFromClasses]));
  }, [classes]);

  const financeStats = useMemo(() => {
    const income = transactions
      .filter(t => t.type === 'INCOME')
      .reduce((acc, t) => acc + t.amount, 0);
    const expense = transactions
      .filter(t => t.type === 'EXPENSE')
      .reduce((acc, t) => acc + t.amount, 0);
    return { income, expense, profit: income - expense };
  }, [transactions]);

  // Ledger Calculations
  const sortedTransactions = useMemo(() => {
    return [...transactions].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [transactions]);
  
  const monthlyChartData = useMemo(() => {
    const dataByMonth: { [key: string]: { month: string, income: number, expense: number } } = {};
    [...transactions].reverse().forEach(t => {
        const date = new Date(t.date);
        const month = date.toLocaleString('default', { month: 'short', year: '2-digit' });
        if (!dataByMonth[month]) {
            dataByMonth[month] = { month, income: 0, expense: 0 };
        }
        if (t.type === 'INCOME') dataByMonth[month].income += t.amount;
        else dataByMonth[month].expense += t.amount;
    });
    return Object.values(dataByMonth);
  }, [transactions]);

  const expenseCategoryData = useMemo(() => {
      const dataByCategory: { [key: string]: number } = {};
      transactions.filter(t => t.type === 'EXPENSE').forEach(t => {
          if (!dataByCategory[t.category]) dataByCategory[t.category] = 0;
          dataByCategory[t.category] += t.amount;
      });
      return Object.entries(dataByCategory).map(([name, value]) => ({ name, value }));
  }, [transactions]);

  const filteredLedgerTransactions = useMemo(() => {
    if (ledgerType === 'GENERAL') return sortedTransactions;
    if (ledgerType === 'INCOME') return sortedTransactions.filter(t => t.type === 'INCOME');
    if (ledgerType === 'EXPENSE') return sortedTransactions.filter(t => t.type === 'EXPENSE');
    return [];
  }, [sortedTransactions, ledgerType]);

  // Student Fee Ledger Calculations
  const feeReportData = useMemo(() => {
     const now = new Date();
     const currentMonthKey = `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}`;

     return students.map(student => {
        const cls = classes.find(c => c.id === student.classId);
        const basePrice = cls?.price || 0;
        
        const unpaidMonths = Object.entries(student.payments).filter(([key, val]) => (val as any).status === 'UNPAID');
        const paidMonths = Object.entries(student.payments).filter(([key, val]) => (val as any).status === 'PAID');
        
        const isCurrentPaid = student.payments[currentMonthKey]?.status === 'PAID';
        const monthsOverdue = unpaidMonths.length;
        
        const totalPenalty = unpaidMonths.reduce((acc, [key]) => {
           return key < currentMonthKey ? acc + 10 : acc;
        }, 0);

        const totalDue = (monthsOverdue * basePrice) + totalPenalty;
        
        const lastPayment = paidMonths.sort(([a], [b]) => b.localeCompare(a))[0];

        return {
           student,
           class: cls,
           isCurrentPaid,
           monthsOverdue,
           totalDue,
           unpaidMonths: unpaidMonths.map(([k]) => k).sort(),
           paidMonths: paidMonths.map(([k]) => k).sort().reverse(),
           lastPaymentDate: lastPayment ? (student.payments[lastPayment[0]] as any).confirmedDate : 'N/A'
        };
     }).sort((a, b) => b.totalDue - a.totalDue);
  }, [students, classes]);

  const filteredFeeReport = useMemo(() => {
     if (feeFilter === 'OVERDUE') return feeReportData.filter(d => d.totalDue > 0);
     if (feeFilter === 'PAID') return feeReportData.filter(d => d.isCurrentPaid && d.totalDue === 0);
     return feeReportData;
  }, [feeReportData, feeFilter]);

  const filteredClasses = useMemo(() => {
    if (selectedLocation === 'ALL') return classes;
    return classes.filter(c => c.location === selectedLocation);
  }, [classes, selectedLocation]);

  const opsStats = useMemo(() => {
    const total = students.length;
    const active = students.filter(s => s.status === 'ACTIVE').length;
    const inactive = students.filter(s => s.status === 'INACTIVE').length;
    return { total, active, inactive, classesCount: classes.length };
  }, [students, classes]);

  // Derived OPS data
  const selectedClass = useMemo(() => classes.find(c => c.id === selectedClassId), [classes, selectedClassId]);
  const classStudents = useMemo(() => students.filter(s => s.classId === selectedClassId), [students, selectedClassId]);
  
  // Derived Coach Audit Data
  const selectedCoach = useMemo(() => coachesList.find(c => c.id === selectedCoachId), [coachesList, selectedCoachId]);
  const coachClasses = useMemo(() => classes.filter(c => c.coachId === selectedCoachId), [classes, selectedCoachId]);
  const coachLogs = useMemo(() => sessionLogs.filter(log => classes.filter(c => c.coachId === selectedCoachId).some(c => c.id === log.classId)), [selectedCoachId, classes, sessionLogs]);
  const coachStudents = useMemo(() => students.filter(s => coachClasses.some(c => c.id === s.classId)), [students, coachClasses]);
  const coachPendingLogs = useMemo(() => coachLogs.filter(l => l.status === 'PENDING'), [coachLogs]);
  const coachApprovedLogs = useMemo(() => coachLogs.filter(l => l.status === 'APPROVED'), [coachLogs]);

  const filteredApplications = useMemo(() => {
    if (appLocationFilter === 'ALL') return applications;
    return applications.filter(app => app.preferredLocation === appLocationFilter);
  }, [applications, appLocationFilter]);
  
  // OPS Attendance Functions
  const handleOpsPrevMonth = () => {
    setCurrentViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };
  const handleOpsNextMonth = () => {
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

  const handleToggleAttendance = (studentId: string, date: string) => {
    if (confirmedDates.has(date)) return;
    const student = students.find(s => s.id === studentId);
    if (!student) return;
    
    const updatedAttendance = { ...student.attendance, [date]: !student.attendance[date] };
    onUpdateStudents(prev => prev.map(s => s.id === studentId ? { ...s, attendance: updatedAttendance } : s));
  };

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


  const handleAiPlan = async () => {
    setTrainingPlan('Generating elite season goals and progression markers using Gemini AI...');
    try {
      const result = await generateTrainingPlan("Elite Level");
      setTrainingPlan(result || 'No plan generated.');
    } catch (error) {
      console.error("Failed to generate plan:", error);
      setTrainingPlan('Failed to generate training plan.');
    }
  };

  const startEditClass = () => {
    if (!selectedClass) return;
    setEditForm(selectedClass);
    setIsEditingClass(true);
  };

  const startAddClass = () => {
    setEditForm({
        location: selectedLocation !== 'ALL' ? selectedLocation : '',
        price: 200, // Default price
        salaryPerSession: 80, // Default salary
        totalSessionsPerMonth: 8,
        name: '',
        coachId: coachesList[0]?.id || '',
        schedule: '',
        hallNumber: '',
        courtNumber: '',
    });
    setIsEditingClass(true);
  };

  const saveClassDetails = () => {
    if (editForm.id) {
        setClasses(prev => prev.map(c => c.id === editForm.id ? (editForm as TrainingClass) : c));
    } else {
        const newClass: TrainingClass = {
            id: `cl-${Date.now()}`,
            name: editForm.name || 'New Group',
            coachId: editForm.coachId || coachesList[0]?.id || 'coach1',
            schedule: editForm.schedule || 'TBD',
            price: Number(editForm.price) || 0,
            salaryPerSession: Number(editForm.salaryPerSession) || 0,
            totalSessionsPerMonth: Number(editForm.totalSessionsPerMonth) || 8,
            location: editForm.location || 'Main Center',
            hallNumber: editForm.hallNumber,
            courtNumber: editForm.courtNumber,
            evaluationDueDate: editForm.evaluationDueDate
        };
        setClasses(prev => [...prev, newClass]);
    }
    setIsEditingClass(false);
  };

  // Payment Handling
  const handleMarkPaid = (studentId: string, monthKey: string) => {
    onUpdateStudents(prev => prev.map(s => {
      if (s.id === studentId) {
        return {
          ...s,
          payments: {
            ...s.payments,
            [monthKey]: { 
              ...s.payments[monthKey],
              status: 'PAID', 
              confirmedDate: new Date().toISOString().split('T')[0],
              receiptId: `RC-${Math.floor(Math.random() * 10000)}`,
              isPendingApproval: false
            }
          }
        };
      }
      return s;
    }));
    setReviewingProof(null);
  };

  // Transfer Logic
  const handleTransferStudent = (studentId: string) => {
    const targetClassId = transferTargets[studentId];
    if (!targetClassId) return;

    onUpdateStudents(prev => prev.map(s => 
      s.id === studentId ? { ...s, classId: targetClassId } : s
    ));

    const newTargets = { ...transferTargets };
    delete newTargets[studentId];
    setTransferTargets(newTargets);
  };

  // Store / Product Logic
  const handleStockUpdate = (productId: string, change: number) => {
    setProducts(prev => prev.map(p => 
      p.id === productId ? { ...p, stock: Math.max(0, p.stock + change) } : p
    ));
  };

  const startEditProduct = (product?: Product) => {
    if (product) {
      setProductForm(product);
    } else {
      setProductForm({
        name: '',
        price: 0,
        stock: 0,
        image: 'https://via.placeholder.com/400',
        availability: 'READY'
      });
    }
    setIsEditingProduct(true);
  };

  const handleProductImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setProductForm(prev => ({ ...prev, image: reader.result as string }));
      };
      reader.readAsDataURL(file);
    }
  };

  const saveProduct = () => {
    if (!productForm.name) return; 

    if (productForm.id) {
      setProducts(prev => prev.map(p => p.id === productForm.id ? (productForm as Product) : p));
    } else {
      const newProduct: Product = {
        id: `p-${Date.now()}`,
        name: productForm.name,
        price: Number(productForm.price) || 0,
        stock: Number(productForm.stock) || 0,
        image: productForm.image || 'https://via.placeholder.com/400',
        availability: productForm.availability || 'READY'
      };
      setProducts(prev => [...prev, newProduct]);
    }
    setIsEditingProduct(false);
  };

  const deleteProduct = (id: string) => {
    if(confirm('Are you sure you want to delete this merchandise item?')) {
       setProducts(prev => prev.filter(p => p.id !== id));
    }
  };

  // Session Approval Handling
  const handleApproveSession = (logId: string) => {
    setSessionLogs(prev => prev.map(log => 
      log.id === logId ? { ...log, status: 'APPROVED' } : log
    ));
  };

  // Application Handling
  const handleApplicationAction = (appId: string, action: 'APPROVED' | 'REJECTED') => {
    setApplications(prev => prev.map(app => 
        app.id === appId ? { ...app, status: action } : app
    ));
  };

  const handleSaveWebsite = () => {
    onUpdateLandingContent(websiteForm);
    alert("Website content updated successfully!");
  };

  // Website List Helpers
  const addItem = (field: 'availablePrograms' | 'availableLocations', value: string) => {
    if (!value.trim()) return;
    setWebsiteForm(prev => ({
      ...prev,
      [field]: [...(prev[field] || []), value]
    }));
    if (field === 'availablePrograms') setNewProgram('');
    if (field === 'availableLocations') setNewLocation('');
  };

  const removeItem = (field: 'availablePrograms' | 'availableLocations', index: number) => {
    setWebsiteForm(prev => ({
      ...prev,
      [field]: (prev[field] || []).filter((_, i) => i !== index)
    }));
  };

  // Create New Coach
  const handleCreateCoach = () => {
     if (!newCoachForm.name || !newCoachForm.username || !newCoachForm.password) return;
     
     const newCoach: User = {
        id: `coach-${Date.now()}`,
        name: newCoachForm.name,
        role: Role.COACH,
        email: newCoachForm.email,
        username: newCoachForm.username,
        password: newCoachForm.password,
        avatar: `https://i.pravatar.cc/150?u=${newCoachForm.username}`
     };
     
     setCoachesList(prev => [...prev, newCoach]);
     setNewCoachForm({ name: '', email: '', username: '', password: '' });
     setCoachSubView('CREDENTIALS'); 
  };

  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-slate-50 gap-6">
      {/* Sidebar Navigation */}
      <aside className="lg:w-64 shrink-0">
        <div className="lg:fixed lg:w-64 lg:h-full bg-white rounded-3xl border border-slate-200 shadow-sm p-4 flex flex-col gap-2">
            <div className="px-4 py-3 mb-2">
                <h4 className="text-xs font-black uppercase text-slate-400 tracking-widest">Main Menu</h4>
            </div>
            
            <button 
                onClick={() => { setActiveTab('FINANCE'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'FINANCE' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <DollarSign size={18} /> Financials
            </button>
            
            <button 
                onClick={() => { setActiveTab('OPS'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'OPS' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <Activity size={18} /> Operations
            </button>
            
            <button 
                onClick={() => { setActiveTab('PLANNING'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'PLANNING' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <Zap size={18} /> Syllabus Plan
            </button>

            <button 
                onClick={() => { setActiveTab('COACHES'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'COACHES' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <GraduationCap size={18} /> Staff Mgmt
            </button>

            <button 
                onClick={() => { setActiveTab('APPLICATIONS'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'APPLICATIONS' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <Inbox size={18} /> Applications
                {applications.some(a => a.status === 'PENDING') && <span className="w-2 h-2 bg-red-500 rounded-full"></span>}
            </button>
            
            <button 
                onClick={() => { setActiveTab('STORE'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'STORE' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <ShoppingBag size={18} /> Store & Inventory
            </button>

            <div className="px-4 py-3 mt-4 mb-2 border-t border-slate-100">
                <h4 className="text-xs font-black uppercase text-slate-400 tracking-widest">Configuration</h4>
            </div>

             <button 
                onClick={() => { setActiveTab('WEBSITE'); setSelectedClassId(null); }} 
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all font-bold text-sm ${activeTab === 'WEBSITE' ? 'bg-sky-600 text-white shadow-lg shadow-sky-200' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
            >
                <Globe size={18} /> Website & Landing
            </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 pr-6 pl-6 lg:pl-0 pb-12">
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
            {activeTab === 'FINANCE' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <h2 className="text-3xl font-sporty uppercase tracking-tight">
                        {financeView === 'OVERVIEW' ? 'Financial Dashboard' : 'Official Ledger Book'}
                    </h2>
                    <div className="flex bg-white p-1 rounded-2xl border border-slate-100 shadow-sm">
                        <button onClick={() => setFinanceView('OVERVIEW')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase transition-all ${financeView === 'OVERVIEW' ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}>
                            <BarChart3 size={16} /> Overview
                        </button>
                        <button onClick={() => setFinanceView('LEDGER')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase transition-all ${financeView === 'LEDGER' ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}>
                            <Table2 size={16} /> Accounting Ledger
                        </button>
                    </div>
                </div>

                {financeView === 'OVERVIEW' && (
                    <div className="space-y-8 animate-in fade-in">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm relative overflow-hidden"><div className="absolute top-0 right-0 p-4 opacity-10"><ArrowUpRight size={80} className="text-green-500" /></div><h3 className="text-slate-500 font-black text-[10px] uppercase tracking-widest">Total Income</h3><p className="text-4xl font-sporty mt-2 text-green-600 tracking-tight">RM {financeStats.income.toLocaleString()}</p></div>
                            <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm relative overflow-hidden"><div className="absolute top-0 right-0 p-4 opacity-10"><ArrowDownRight size={80} className="text-red-500" /></div><h3 className="text-slate-500 font-black text-[10px] uppercase tracking-widest">Total Expenses</h3><p className="text-4xl font-sporty mt-2 text-red-500 tracking-tight">RM {financeStats.expense.toLocaleString()}</p></div>
                            <div className="bg-sky-600 p-8 rounded-3xl text-white shadow-xl relative overflow-hidden"><div className="absolute top-0 right-0 p-4 opacity-10"><Wallet size={80} className="text-white" /></div><h3 className="text-sky-200 font-black text-[10px] uppercase tracking-widest">Net Profit</h3><p className="text-4xl font-sporty mt-2 text-white tracking-tight">RM {financeStats.profit.toLocaleString()}</p></div>
                        </div>

                        <div className="grid lg:grid-cols-5 gap-8">
                            <div className="lg:col-span-3 bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                                <h3 className="text-lg font-bold mb-6 flex items-center gap-2"><TrendingUp size={20} className="text-sky-600" /> Monthly Performance</h3>
                                <div className="h-80">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={monthlyChartData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                            <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#64748b' }} />
                                            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                                            <Tooltip contentStyle={{ borderRadius: '16px', border: '1px solid #e2e8f0', fontSize: '12px' }} />
                                            <Legend wrapperStyle={{fontSize: '12px'}} />
                                            <Bar dataKey="income" fill="#10b981" name="Income" radius={[8, 8, 0, 0]} />
                                            <Bar dataKey="expense" fill="#ef4444" name="Expense" radius={[8, 8, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="lg:col-span-2 bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                                <h3 className="text-lg font-bold mb-6 flex items-center gap-2"><PieIcon size={20} className="text-sky-600" /> Expense Breakdown</h3>
                                <div className="h-80">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie data={expenseCategoryData} cx="50%" cy="50%" outerRadius={100} dataKey="value" nameKey="name" labelLine={false} label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => { const radius = innerRadius + (outerRadius - innerRadius) * 1.2; const x = cx + radius * Math.cos(-midAngle * (Math.PI / 180)); const y = cy + radius * Math.sin(-midAngle * (Math.PI / 180)); return (<text x={x} y={y} fill="#64748b" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={10}>{`${(percent * 100).toFixed(0)}%`}</text>);}}>
                                                {expenseCategoryData.map((entry, index) => <Cell key={`cell-${index}`} fill={EXPENSE_COLORS[index % EXPENSE_COLORS.length]} />)}
                                            </Pie>
                                            <Tooltip contentStyle={{ borderRadius: '16px', border: '1px solid #e2e8f0', fontSize: '12px' }} />
                                            <Legend iconType="circle" wrapperStyle={{fontSize: '10px'}} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {financeView === 'LEDGER' && (
                    <div className="space-y-6 animate-in fade-in">
                        <div className="flex bg-white p-1 rounded-2xl border border-slate-100 w-fit shadow-sm">
                            <button onClick={() => setLedgerType('GENERAL')} className={`px-6 py-2 rounded-xl text-xs font-black uppercase ${ledgerType === 'GENERAL' ? 'bg-slate-900 text-white shadow' : 'text-slate-500'}`}>General Ledger</button>
                            <button onClick={() => setLedgerType('INCOME')} className={`px-6 py-2 rounded-xl text-xs font-black uppercase ${ledgerType === 'INCOME' ? 'bg-slate-900 text-white shadow' : 'text-slate-500'}`}>Income</button>
                            <button onClick={() => setLedgerType('EXPENSE')} className={`px-6 py-2 rounded-xl text-xs font-black uppercase ${ledgerType === 'EXPENSE' ? 'bg-slate-900 text-white shadow' : 'text-slate-500'}`}>Expenses</button>
                            <button onClick={() => setLedgerType('FEES')} className={`px-6 py-2 rounded-xl text-xs font-black uppercase ${ledgerType === 'FEES' ? 'bg-slate-900 text-white shadow' : 'text-slate-500'}`}>Student Fees</button>
                        </div>

                        <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                            {ledgerType !== 'FEES' ? (
                                <div className="space-y-4">
                                    <h3 className="text-lg font-bold uppercase tracking-tight">All Transactions</h3>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left">
                                            <thead><tr className="border-b border-slate-100"><th className="p-3 text-[10px] uppercase font-black text-slate-400">Date</th><th className="p-3 text-[10px] uppercase font-black text-slate-400">Description</th><th className="p-3 text-[10px] uppercase font-black text-slate-400">Category</th><th className="p-3 text-[10px] uppercase font-black text-slate-400 text-right">Amount</th></tr></thead>
                                            <tbody>
                                                {filteredLedgerTransactions.map(t => (
                                                    <tr key={t.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                                                        <td className="p-3 text-xs font-bold text-slate-500">{t.date}</td>
                                                        <td className="p-3 text-sm font-bold text-slate-800">{t.description}</td>
                                                        <td className="p-3"><span className="text-[10px] font-black uppercase bg-slate-100 text-slate-500 px-2 py-1 rounded">{t.category}</span></td>
                                                        <td className={`p-3 text-sm font-bold text-right ${t.type === 'INCOME' ? 'text-green-600' : 'text-red-600'}`}>{t.type === 'INCOME' ? '+' : '-'} RM {t.amount.toLocaleString()}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-6">
                                    <div className="flex justify-between items-center">
                                        <h3 className="text-lg font-bold uppercase tracking-tight">Student Fee Status</h3>
                                        <div className="flex bg-slate-50 p-1 rounded-2xl border border-slate-100">
                                            <button onClick={() => setFeeFilter('ALL')} className={`px-4 py-1 rounded-xl text-[10px] font-black ${feeFilter === 'ALL' ? 'bg-white shadow' : 'text-slate-500'}`}>ALL</button>
                                            <button onClick={() => setFeeFilter('OVERDUE')} className={`px-4 py-1 rounded-xl text-[10px] font-black ${feeFilter === 'OVERDUE' ? 'bg-white shadow' : 'text-slate-500'}`}>OVERDUE</button>
                                            <button onClick={() => setFeeFilter('PAID')} className={`px-4 py-1 rounded-xl text-[10px] font-black ${feeFilter === 'PAID' ? 'bg-white shadow' : 'text-slate-500'}`}>PAID</button>
                                        </div>
                                    </div>
                                    <div className="space-y-3">
                                        {filteredFeeReport.map(({ student, class: cls, totalDue, unpaidMonths }) => {
                                            const pendingProof = Object.entries(student.payments).find(([k,v])=>(v as any).isPendingApproval);
                                            return (
                                                <div key={student.id} className={`p-4 rounded-3xl border transition-all ${totalDue > 0 ? 'bg-red-50/50 border-red-100' : 'bg-white border-slate-100'}`}>
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-4">
                                                            <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-sm font-bold">{student.name.charAt(0)}</div>
                                                            <div>
                                                                <p className="font-bold text-slate-900">{student.name}</p>
                                                                <p className="text-[10px] font-medium text-slate-500">{cls?.name || 'N/A'} • {cls?.location || 'N/A'}</p>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-4">
                                                            <div className="text-right">
                                                                <p className={`font-bold text-xl ${totalDue > 0 ? 'text-red-600' : 'text-green-600'}`}>{totalDue > 0 ? `RM ${totalDue}` : 'Paid Up'}</p>
                                                                {totalDue > 0 && <p className="text-[10px] font-medium text-slate-500">{unpaidMonths.length} month(s) overdue</p>}
                                                            </div>
                                                            {pendingProof ? (
                                                                <button onClick={() => setReviewingProof({ studentId: student.id, monthKey: pendingProof[0] })} className="flex items-center gap-2 px-4 py-2 bg-yellow-400 text-white rounded-xl text-xs font-black uppercase hover:bg-yellow-500 shadow-lg shadow-yellow-100 animate-pulse">
                                                                    <Eye size={14} /> Review Proof
                                                                </button>
                                                            ) : totalDue > 0 ? (
                                                                <button onClick={() => handleMarkPaid(student.id, unpaidMonths[0])} className="px-4 py-2 bg-slate-800 text-white rounded-xl text-xs font-black uppercase hover:bg-black">
                                                                    Manual Confirm
                                                                </button>
                                                            ) : null}
                                                        </div>
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
              </div>
            )}
            
            {activeTab === 'OPS' && (
              <div className="grid lg:grid-cols-4 gap-8 animate-in slide-in-from-bottom-4 duration-500">
                <div className="lg:col-span-1 space-y-6">
                   <div className="flex bg-white p-1 rounded-2xl border border-slate-200 w-full overflow-x-auto max-w-full">
                       {allLocations.map(loc => (
                         <button key={loc} onClick={() => setSelectedLocation(loc)} className={`flex-1 px-4 py-2 rounded-xl text-xs font-black transition-all whitespace-nowrap ${selectedLocation === loc ? 'bg-sky-600 text-white shadow' : 'text-slate-500'}`}>{loc}</button>
                       ))}
                   </div>
                   <div className="space-y-3 h-[calc(100vh-12rem)] overflow-y-auto pr-2">
                       {filteredClasses.map(cls => (
                         <button key={cls.id} onClick={() => { setSelectedClassId(cls.id); setSelectedStudentId(null); }} className={`w-full text-left p-6 rounded-3xl border transition-all relative overflow-hidden group ${selectedClassId === cls.id ? 'bg-slate-900 border-slate-900 text-white shadow-xl' : 'bg-white border-slate-100 hover:border-slate-200 text-slate-900'}`}>
                            <div className="font-sporty text-xl tracking-tight uppercase block mb-1">{cls.name}</div>
                            <p className={`text-[10px] font-black uppercase tracking-widest ${selectedClassId === cls.id ? 'text-sky-400' : 'text-slate-400'}`}>{cls.schedule}</p>
                         </button>
                       ))}
                   </div>
                </div>

                <div className="lg:col-span-3">
                   {!selectedClass ? (
                      <div className="h-96 bg-white rounded-[40px] border-2 border-dashed border-slate-100 flex flex-col items-center justify-center text-slate-400 gap-4 text-center p-12">
                         <Users size={32} className="opacity-20" />
                         <p className="font-bold">Select a class to view attendance and student details.</p>
                      </div>
                   ) : (
                      <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-8">
                         <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-slate-100">
                            <div>
                               <h3 className="text-2xl font-sporty uppercase tracking-tight">Attendance & Fee Status View</h3>
                               <div className="flex items-center gap-2 mt-1">
                                  <button onClick={handleOpsPrevMonth} className="p-1 hover:bg-slate-100 rounded-lg text-sky-600 transition-colors"><ChevronLeft size={16} /></button>
                                  <p className="text-xs font-bold text-slate-600 uppercase tracking-widest">{currentViewDate.toLocaleString('default', { month: 'long', year: 'numeric' })}</p>
                                  <button onClick={handleOpsNextMonth} className="p-1 hover:bg-slate-100 rounded-lg text-sky-600 transition-colors"><ChevronRight size={16} /></button>
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
                                 <th className="text-left p-4 sticky left-0 bg-white z-20 min-w-[200px] border-b border-slate-100"><span className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Student</span></th>
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
                                 const isPaid = (student.payments[currentMonthKey] as any)?.status === 'PAID';
                                 return (
                                   <tr key={student.id} className={`transition-colors ${!isPaid ? 'bg-red-50/40 hover:bg-red-50/60' : 'hover:bg-slate-50/50'}`}>
                                     <td className={`p-4 sticky left-0 z-20 border-b border-slate-50 font-bold text-slate-800 flex items-center gap-3 ${!isPaid ? 'bg-red-50/10' : 'bg-white'}`}>
                                       <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs relative ${!isPaid ? 'bg-red-100' : 'bg-slate-100'}`}>
                                         {student.name.charAt(0)}
                                         {!isPaid && <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-[8px] flex items-center justify-center border-2 border-white">!</div>}
                                       </div>
                                       <span>{student.name}</span>
                                     </td>
                                     {monthDates.map(d => {
                                       const isPresent = (student.attendance || {})[d.full];
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
                </div>
              </div>
            )}
            {activeTab === 'PLANNING' && (
                <div className="grid lg:grid-cols-2 gap-8">
                    <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                        <h3 className="text-xl font-bold flex items-center gap-2"><Trophy size={20} /> Academy Syllabus</h3>
                        <button onClick={handleAiPlan} className="w-full bg-sky-600 text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-xl shadow-sky-100"><Zap size={20} /> Generate AI Season Goal</button>
                    </div>
                    <div className="bg-slate-900 p-8 rounded-[40px] text-white"><h3 className="text-xl font-bold mb-4">Masterplan Output</h3><div className="h-[500px] overflow-y-auto pr-4 text-slate-400 font-mono text-sm leading-relaxed whitespace-pre-wrap">{trainingPlan || "Define modules..."}</div></div>
                </div>
            )}
            {activeTab === 'COACHES' && ( 
                <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                        <h2 className="text-3xl font-sporty uppercase tracking-tight">Staff Management</h2>
                        <div className="flex bg-white p-1 rounded-2xl border border-slate-100 shadow-sm">
                            <button onClick={() => setCoachSubView('OVERVIEW')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase transition-all ${coachSubView === 'OVERVIEW' ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}>
                                <LayoutGrid size={16} /> Overview
                            </button>
                            <button onClick={() => setCoachSubView('CREDENTIALS')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase transition-all ${coachSubView === 'CREDENTIALS' ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}>
                                <Key size={16} /> Credentials
                            </button>
                            <button onClick={() => setCoachSubView('HIRE')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black uppercase transition-all ${coachSubView === 'HIRE' ? 'bg-sky-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}>
                                <UserPlus size={16} /> Hire Staff
                            </button>
                        </div>
                    </div>

                    {coachSubView === 'OVERVIEW' && (
                      <div className="grid lg:grid-cols-3 gap-8">
                        <div className="lg:col-span-1 space-y-4">
                            <div className="space-y-2">
                                {coachesList.map(c => (
                                    <button key={c.id} onClick={() => setSelectedCoachId(c.id)} className={`w-full flex items-center gap-4 p-4 rounded-2xl border transition-all ${selectedCoachId === c.id ? 'bg-slate-900 text-white shadow-xl' : 'bg-white hover:border-slate-200'}`}>
                                        <img src={c.avatar} className="w-10 h-10 rounded-full" />
                                        <div>
                                            <p className="font-bold text-left">{c.name}</p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="lg:col-span-2 space-y-8">
                            {selectedCoach && (
                                <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                                    <h3 className="text-xl font-bold uppercase tracking-tight">Coach Performance: {selectedCoach.name}</h3>
                                    <div className="grid grid-cols-3 gap-4 text-center">
                                        <div className="bg-sky-50 p-4 rounded-2xl"><p className="text-3xl font-sporty">{coachClasses.length}</p><p className="text-[10px] font-black uppercase text-sky-700">Classes</p></div>
                                        <div className="bg-sky-50 p-4 rounded-2xl"><p className="text-3xl font-sporty">{coachStudents.length}</p><p className="text-[10px] font-black uppercase text-sky-700">Students</p></div>
                                        <div className="bg-sky-50 p-4 rounded-2xl"><p className="text-3xl font-sporty">{coachApprovedLogs.length}</p><p className="text-[10px] font-black uppercase text-sky-700">Sessions</p></div>
                                    </div>
                                </div>
                            )}
                            <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-4">
                               <h3 className="text-lg font-bold uppercase tracking-tight flex items-center justify-between">
                                  Pending Session Logs
                                  <span className="text-xs font-bold text-slate-400">{coachPendingLogs.length} logs</span>
                               </h3>
                               <div className="space-y-3">
                                  {coachPendingLogs.map(log => {
                                    const logClass = classes.find(c => c.id === log.classId);
                                    return(
                                      <div key={log.id} className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                          <p className="font-bold text-xs">{logClass?.name} - {log.date}</p>
                                          <p className="text-xs text-slate-600 italic mt-2">"{log.reflection}"</p>
                                          <div className="flex justify-end mt-2">
                                             <button onClick={() => handleApproveSession(log.id)} className="px-3 py-1 bg-sky-600 text-white rounded-lg text-[10px] font-black uppercase">Approve</button>
                                          </div>
                                      </div>
                                    )
                                  })}
                               </div>
                            </div>
                        </div>
                      </div>
                    )}
                    
                    {coachSubView === 'CREDENTIALS' && (
                       <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                         <table className="w-full">
                           <thead>
                             <tr className="border-b"><th className="text-left p-2 text-xs uppercase font-bold text-slate-400">Staff</th><th className="text-left p-2 text-xs uppercase font-bold text-slate-400">Username</th><th className="text-left p-2 text-xs uppercase font-bold text-slate-400">Password</th><th className="p-2"></th></tr>
                           </thead>
                           <tbody>
                             {coachesList.map(c => (
                               <tr key={c.id} className="border-b border-slate-50">
                                 <td className="p-3 font-bold">{c.name}</td>
                                 <td className="p-3 font-mono text-sm">{c.username}</td>
                                 <td className="p-3 font-mono text-sm">{c.password}</td>
                                 <td className="p-3 text-right"><button><Trash size={16} className="text-red-400"/></button></td>
                               </tr>
                             ))}
                           </tbody>
                         </table>
                       </div>
                    )}

                    {coachSubView === 'HIRE' && (
                       <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
                          <h3 className="text-xl font-bold mb-6">New Staff Enrollment</h3>
                          <div className="grid md:grid-cols-2 gap-6">
                            <input value={newCoachForm.name} onChange={e => setNewCoachForm({...newCoachForm, name: e.target.value})} placeholder="Full Name" className="p-3 border rounded-lg" />
                            <input value={newCoachForm.email} onChange={e => setNewCoachForm({...newCoachForm, email: e.target.value})} placeholder="Email Address" className="p-3 border rounded-lg" />
                            <input value={newCoachForm.username} onChange={e => setNewCoachForm({...newCoachForm, username: e.target.value})} placeholder="Username" className="p-3 border rounded-lg" />
                            <input value={newCoachForm.password} onChange={e => setNewCoachForm({...newCoachForm, password: e.target.value})} placeholder="Password" className="p-3 border rounded-lg" />
                          </div>
                          <button onClick={handleCreateCoach} className="mt-6 w-full py-3 bg-sky-600 text-white rounded-lg font-bold">Create Coach Account</button>
                       </div>
                    )}
                </div>
            )}
            {activeTab === 'APPLICATIONS' && ( 
              <div className="space-y-8">
                <h2 className="text-3xl font-sporty uppercase tracking-tight">New Student Applications</h2>
                <div className="flex bg-white p-1 rounded-2xl border border-slate-100 w-fit shadow-sm">
                  {allLocations.map(loc => (
                    <button key={loc} onClick={() => setAppLocationFilter(loc)} className={`px-4 py-1.5 rounded-xl text-xs font-black uppercase ${appLocationFilter === loc ? 'bg-slate-900 text-white shadow' : 'text-slate-500'}`}>{loc}</button>
                  ))}
                </div>
                <div className="space-y-4">
                  {filteredApplications.map(app => (
                    <div key={app.id} className={`p-6 rounded-3xl border ${app.status === 'PENDING' ? 'bg-white' : 'bg-slate-50'}`}>
                       <div className="flex flex-wrap items-center justify-between gap-4">
                          <div className="flex items-center gap-4">
                             <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold ${app.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-500'}`}>{app.studentName.charAt(0)}</div>
                             <div>
                               <p className="font-bold text-slate-900">{app.studentName}</p>
                               <p className="text-xs text-slate-500">{app.program}</p>
                             </div>
                          </div>
                          <div className="flex items-center gap-6">
                            <span className="text-xs font-bold text-slate-500">{app.preferredLocation}</span>
                            {app.status === 'PENDING' ? (
                              <div className="flex gap-2">
                                <button onClick={() => handleApplicationAction(app.id, 'REJECTED')} className="px-4 py-2 text-xs font-black uppercase bg-red-100 text-red-700 rounded-lg">Reject</button>
                                <button onClick={() => handleApplicationAction(app.id, 'APPROVED')} className="px-4 py-2 text-xs font-black uppercase bg-green-100 text-green-700 rounded-lg">Approve</button>
                              </div>
                            ) : (
                              <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase ${app.status === 'APPROVED' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>{app.status}</span>
                            )}
                          </div>
                       </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {activeTab === 'WEBSITE' && ( 
              <div className="space-y-8 animate-in slide-in-from-bottom-4">
                <h2 className="text-3xl font-sporty uppercase tracking-tight">Landing Page Content</h2>
                <div className="grid lg:grid-cols-2 gap-8">
                  {/* Left Column: Text Content */}
                  <div className="space-y-6">
                    <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                      <h3 className="text-lg font-bold text-slate-800 border-b border-slate-100 pb-4">Hero Section</h3>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Hero Title</label>
                        <input value={websiteForm.heroTitle} onChange={e => setWebsiteForm({...websiteForm, heroTitle: e.target.value})} className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-bold" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Hero Subtitle</label>
                        <textarea value={websiteForm.heroSubtitle} onChange={e => setWebsiteForm({...websiteForm, heroSubtitle: e.target.value})} className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium" rows={4} />
                      </div>
                       <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Announcement Banner</label>
                        <input value={websiteForm.announcementText} onChange={e => setWebsiteForm({...websiteForm, announcementText: e.target.value})} placeholder="Announcement Text" className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium" />
                      </div>
                    </div>
                     <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                      <h3 className="text-lg font-bold text-slate-800 border-b border-slate-100 pb-4">Contact & Social Links</h3>
                       <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Contact Email</label>
                        <input value={websiteForm.contactEmail} onChange={e => setWebsiteForm({...websiteForm, contactEmail: e.target.value})} placeholder="Contact Email" className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium" />
                      </div>
                       <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Instagram URL</label>
                        <input value={websiteForm.instagramLink} onChange={e => setWebsiteForm({...websiteForm, instagramLink: e.target.value})} placeholder="Instagram URL" className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium" />
                      </div>
                       <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">TikTok URL</label>
                        <input value={websiteForm.tiktokLink} onChange={e => setWebsiteForm({...websiteForm, tiktokLink: e.target.value})} placeholder="TikTok URL" className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium" />
                      </div>
                    </div>
                  </div>

                  {/* Right Column: List Management */}
                  <div className="space-y-6">
                    <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm space-y-6">
                      <h3 className="text-lg font-bold text-slate-800 border-b border-slate-100 pb-4">Registration Options</h3>
                      <div>
                        <h4 className="font-bold mb-4 text-sm text-slate-600">Available Programs</h4>
                        <div className="space-y-3 mb-4">
                          {websiteForm.availablePrograms.map((p, i) => 
                            <div key={i} className="flex items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl">
                              <p className="text-sm font-medium text-slate-700">{p}</p>
                              <button onClick={() => removeItem('availablePrograms', i)} className="p-1 text-slate-400 hover:text-red-500"><Trash size={16}/></button>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 p-2 border-t border-slate-100">
                          <input value={newProgram} onChange={e => setNewProgram(e.target.value)} placeholder="Add new program" className="flex-1 p-3 bg-white border border-slate-200 rounded-lg text-sm" />
                          <button onClick={() => addItem('availablePrograms', newProgram)} className="px-4 bg-slate-800 text-white rounded-lg font-bold text-sm">Add</button>
                        </div>
                      </div>
                       <div>
                        <h4 className="font-bold mb-4 text-sm text-slate-600">Available Locations</h4>
                        <div className="space-y-3 mb-4">
                          {websiteForm.availableLocations.map((l, i) => 
                            <div key={i} className="flex items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl">
                              <p className="text-sm font-medium text-slate-700">{l}</p>
                              <button onClick={() => removeItem('availableLocations', i)} className="p-1 text-slate-400 hover:text-red-500"><Trash size={16}/></button>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 p-2 border-t border-slate-100">
                           <input value={newLocation} onChange={e => setNewLocation(e.target.value)} placeholder="Add new location" className="flex-1 p-3 bg-white border border-slate-200 rounded-lg text-sm" />
                           <button onClick={() => addItem('availableLocations', newLocation)} className="px-4 bg-slate-800 text-white rounded-lg font-bold text-sm">Add</button>
                        </div>
                      </div>
                    </div>
                     <button onClick={handleSaveWebsite} className="w-full py-5 bg-sky-600 text-white font-black rounded-2xl text-sm uppercase tracking-widest hover:bg-sky-700 transition-all shadow-lg shadow-sky-200">
                       Save All Changes
                     </button>
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'STORE' && ( 
              <div className="space-y-8">
                 <div className="flex justify-between items-center">
                   <h2 className="text-3xl font-sporty uppercase tracking-tight">Merchandise & Inventory</h2>
                   <button onClick={() => startEditProduct()} className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-bold flex items-center gap-2"><Plus size={16}/> Add Product</button>
                 </div>
                 <div className="grid md:grid-cols-3 gap-8">
                   {products.map(p => (
                     <div key={p.id} className="bg-white rounded-3xl border border-slate-100 overflow-hidden">
                        <img src={p.image} className="w-full h-48 object-cover" />
                        <div className="p-4">
                          <h3 className="font-bold">{p.name}</h3>
                          <p className="text-sky-600 font-bold">RM {p.price}</p>
                          <div className="flex items-center justify-between mt-4">
                             <div className="flex items-center gap-2">
                               <button onClick={() => handleStockUpdate(p.id, -1)} className="p-1 border rounded-full"><Minus size={14}/></button>
                               <span className="font-bold w-8 text-center">{p.stock}</span>
                               <button onClick={() => handleStockUpdate(p.id, 1)} className="p-1 border rounded-full"><Plus size={14}/></button>
                             </div>
                             <div>
                                <button onClick={() => deleteProduct(p.id)} className="p-2"><Trash2 size={16} className="text-red-400"/></button>
                                <button onClick={() => startEditProduct(p)} className="p-2"><Edit3 size={16} className="text-slate-600"/></button>
                             </div>
                          </div>
                        </div>
                     </div>
                   ))}
                 </div>

                 {isEditingProduct && (
                    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                      <div className="bg-white rounded-2xl p-6 w-full max-w-md space-y-4">
                         <h3 className="text-lg font-bold">{productForm.id ? 'Edit Product' : 'Add Product'}</h3>
                         <input value={productForm.name} onChange={e => setProductForm({...productForm, name: e.target.value})} placeholder="Product Name" className="w-full p-2 border rounded" />
                         <input value={productForm.price} type="number" onChange={e => setProductForm({...productForm, price: Number(e.target.value)})} placeholder="Price" className="w-full p-2 border rounded" />
                         <input value={productForm.stock} type="number" onChange={e => setProductForm({...productForm, stock: Number(e.target.value)})} placeholder="Stock" className="w-full p-2 border rounded" />
                         <button onClick={() => productFileInputRef.current?.click()} className="w-full p-2 border rounded text-sm">Upload Image</button>
                         <input type="file" ref={productFileInputRef} onChange={handleProductImageUpload} className="hidden" />
                         <div className="flex gap-4">
                           <button onClick={() => setIsEditingProduct(false)} className="flex-1 p-2 bg-slate-100 rounded">Cancel</button>
                           <button onClick={saveProduct} className="flex-1 p-2 bg-sky-600 text-white rounded">Save</button>
                         </div>
                      </div>
                    </div>
                 )}
              </div>
            )}
        </div>
      </main>

      {reviewingProof && proofStudent && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-white w-full max-w-lg rounded-[40px] shadow-2xl overflow-hidden border border-slate-100 animate-in zoom-in-95 duration-300">
                <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <div>
                        <h3 className="text-2xl font-sporty tracking-tight uppercase">Verify Payment</h3>
                        <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest mt-1">For {proofStudent.name} • {reviewingProof.monthKey}</p>
                    </div>
                    <button onClick={() => setReviewingProof(null)} className="p-2 text-slate-400 hover:text-red-500 transition-colors"><XCircle size={24} /></button>
                </div>
                <div className="p-8 space-y-6">
                    <div className="aspect-square w-full bg-slate-100 rounded-3xl overflow-hidden border border-slate-200">
                        <img src={(proofStudent.payments[reviewingProof.monthKey] as any).proofUrl} alt="Payment Proof" className="w-full h-full object-contain" />
                    </div>
                    <div className="flex gap-4">
                        <button onClick={() => setReviewingProof(null)} className="flex-1 py-4 bg-slate-100 text-slate-600 font-bold rounded-2xl uppercase text-xs tracking-widest hover:bg-slate-200">Cancel</button>
                        <button onClick={() => handleMarkPaid(reviewingProof.studentId, reviewingProof.monthKey)} className="flex-1 py-4 bg-sky-600 text-white font-black rounded-2xl uppercase text-xs tracking-widest hover:bg-sky-700 shadow-lg shadow-sky-100">Confirm & Approve</button>
                    </div>
                </div>
            </div>
        </div>
      )}

    </div>
  );
};

export default AdminDashboard;
