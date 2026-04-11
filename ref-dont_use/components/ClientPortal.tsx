
import React, { useState, useRef } from 'react';
import { User, Student } from '../types';
import { 
  Calendar, CreditCard, ShoppingBag, 
  Video, ChevronRight, Download, Clock, AlertCircle,
  Award, Star, Activity, User as UserIcon, Check, Receipt, Camera,
  Upload, Image as ImageIcon, Smartphone, CheckCircle, ChevronDown
} from 'lucide-react';
import { 
  Radar, RadarChart, PolarGrid, PolarAngleAxis, 
  PolarRadiusAxis, ResponsiveContainer 
} from 'recharts';
import { PRODUCTS, PROGRESS_REPORTS } from '../constants';

interface Props {
  user: User;
  student: Student;
  onUpdateStudent: (student: Student) => void;
  onUpdateSelf: (user: Partial<User>) => void;
}

const ClientPortal: React.FC<Props> = ({ user, student, onUpdateStudent, onUpdateSelf }) => {
  const [activeTab, setActiveTab] = useState<'HOME' | 'REPORTS' | 'PAYMENTS' | 'STORE' | 'SETTINGS'>('HOME');
  const [selectedPaymentMonth, setSelectedPaymentMonth] = useState<string>('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const proofUploadRef = useRef<HTMLInputElement>(null);

  if (!student) return <div className="p-20 text-center font-bold">No associated student profile found. Please contact RSBE support.</div>;

  const reports = PROGRESS_REPORTS.filter(r => r.studentId === student.id);

  const radarData = Object.entries(student.skills).map(([subject, value]) => ({
    subject,
    A: value as number,
    fullMark: 5
  }));

  const handleProofUpload = (e: React.ChangeEvent<HTMLInputElement>, monthKey: string) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result as string;
        const updatedStudent: Student = {
          ...student,
          payments: {
            ...student.payments,
            [monthKey]: {
              ...student.payments[monthKey],
              status: 'UNPAID', // Still unpaid until admin approves
              isPendingApproval: true,
              proofUrl: base64,
              confirmedDate: new Date().toISOString().split('T')[0] // Timestamp of upload
            }
          }
        };
        onUpdateStudent(updatedStudent);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onUpdateSelf) {
      const reader = new FileReader();
      reader.onloadend = () => {
        onUpdateSelf({ avatar: reader.result as string });
      };
      reader.readAsDataURL(file);
    }
  };

  const calculatePenalty = (status: string) => {
    if (status === 'PAID') return 0;
    const today = new Date();
    if (today.getDate() > 7) {
       const weeksLate = Math.floor((today.getDate() - 7) / 7) + 1;
       return weeksLate * 10;
    }
    return 0;
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto animate-in fade-in duration-500">
      {/* Tab Nav */}
      <div className="flex gap-8 border-b border-slate-200 overflow-x-auto">
        {(['HOME', 'REPORTS', 'PAYMENTS', 'STORE', 'SETTINGS'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-4 px-2 text-sm font-bold transition-all relative whitespace-nowrap ${
              activeTab === tab ? 'text-sky-600' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            {tab === 'REPORTS' ? '6-MONTH PROGRESS' : tab === 'SETTINGS' ? 'MY PROFILE' : tab}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-sky-600 rounded-full"></div>
            )}
          </button>
        ))}
      </div>

      {activeTab === 'HOME' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-sky-600 p-8 rounded-[40px] text-white flex flex-col md:flex-row items-center gap-8 shadow-2xl shadow-sky-200">
              <div className="w-24 h-24 bg-white/20 rounded-full flex items-center justify-center text-4xl font-bold backdrop-blur-md overflow-hidden border-4 border-white/10">
                {user.avatar ? <img src={user.avatar} className="w-full h-full object-cover" /> : student.name.charAt(0)}
              </div>
              <div className="text-center md:text-left flex-1">
                <h2 className="text-3xl font-sporty tracking-tight uppercase leading-none">{student.name}'s Dashboard</h2>
                <p className="text-sky-100 font-medium mt-1 uppercase tracking-widest text-[10px]">Elite Academy Member • Enrollment ID: RSBE-{student.id.toUpperCase()}</p>
                <div className="mt-6 flex flex-wrap gap-2 justify-center md:justify-start">
                  <span className="bg-sky-500/50 px-4 py-1.5 rounded-full text-[10px] font-black uppercase border border-white/10">92% Attendance Rate</span>
                  <span className="bg-yellow-400/50 px-4 py-1.5 rounded-full text-[10px] font-black uppercase border border-white/10 text-yellow-50">Advanced Group</span>
                </div>
              </div>
            </div>

            <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm">
              <div className="flex items-center justify-between mb-8">
                <h3 className="text-xl font-bold flex items-center gap-2 uppercase tracking-tight">
                   <Activity size={20} className="text-sky-600" /> Professional Skills breakdown
                </h3>
              </div>
              <div className="grid md:grid-cols-2 gap-8 items-center">
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                      <PolarGrid stroke="#e2e8f0" />
                      <PolarAngleAxis dataKey="subject" tick={{fill: '#64748b', fontSize: 10, fontWeight: 700}} />
                      <PolarRadiusAxis angle={30} domain={[0, 5]} axisLine={false} tick={false} />
                      <Radar
                        name={student.name}
                        dataKey="A"
                        stroke="#0284c7"
                        strokeWidth={4}
                        fill="#0284c7"
                        fillOpacity={0.15}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-5">
                  {radarData.map(item => (
                    <div key={item.subject} className="space-y-1.5">
                      <div className="flex justify-between text-[10px] font-black uppercase text-slate-400 tracking-wider">
                         <span>{item.subject}</span>
                         <span className="text-sky-600">{item.A}/5</span>
                      </div>
                      <div className="h-2 bg-slate-50 rounded-full overflow-hidden border border-slate-100">
                         <div className="h-full bg-sky-500 rounded-full shadow-[0_0_8px_rgba(2,132,199,0.3)] transition-all duration-1000" style={{ width: `${(item.A/5)*100}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

             <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm">
              <h3 className="text-xl font-bold mb-6 flex items-center gap-2 uppercase tracking-tight">
                <Video size={20} className="text-red-500" /> Proof of Improvement
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {student.videos.length > 0 ? student.videos.map((v, i) => (
                  <div key={i} className="group relative rounded-2xl overflow-hidden aspect-video bg-black shadow-lg">
                    <video className="w-full h-full object-cover opacity-60">
                      <source src={v} type="video/mp4" />
                    </video>
                    <div className="absolute inset-0 flex items-center justify-center group-hover:bg-sky-600/30 transition-all cursor-pointer">
                      <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center text-sky-600 shadow-xl group-hover:scale-110 transition-transform">
                        <ChevronRight size={24} />
                      </div>
                    </div>
                    <div className="absolute bottom-4 left-4 text-white">
                      <p className="text-[10px] font-black uppercase tracking-widest opacity-80">Latest Session</p>
                      <p className="text-sm font-bold">Smash Power Proof</p>
                    </div>
                  </div>
                )) : (
                  <div className="col-span-2 text-center py-12 border-2 border-dashed border-slate-100 rounded-2xl text-slate-400 italic">
                    Training proof clips will be uploaded by your coach soon.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="bg-slate-900 p-8 rounded-[40px] text-white shadow-2xl shadow-slate-900/20 relative overflow-hidden group">
               <div className="absolute top-0 right-0 p-12 opacity-5 -mr-10 -mt-10 group-hover:scale-110 transition-transform"><CreditCard size={120} /></div>
               <div className="relative z-10">
                  <h4 className="font-sporty text-2xl tracking-tight text-white uppercase leading-none">Subscription Fee</h4>
                  <p className="text-[10px] font-black text-sky-400 uppercase tracking-widest mt-2 flex items-center gap-2">
                    <Clock size={12} /> Due in 3 days
                  </p>
                  <p className="text-4xl font-sporty mt-6 tracking-tight">RM 250</p>
                  <button onClick={() => setActiveTab('PAYMENTS')} className="mt-8 w-full py-4 bg-sky-600 text-white font-black uppercase tracking-widest rounded-2xl hover:bg-sky-700 transition-all shadow-xl shadow-sky-900/40 active:scale-95">
                    Pay Now
                  </button>
               </div>
            </div>

            <div className="bg-white p-8 rounded-[40px] border border-slate-100 shadow-sm">
              <h3 className="font-bold mb-6 flex items-center gap-2 uppercase tracking-tight border-b border-slate-50 pb-4">
                <Calendar size={18} className="text-sky-600" /> Training Schedule
              </h3>
              <div className="space-y-4">
                {[
                  { date: '15 Oct', time: '4:00 PM', topic: 'Smash Speed' },
                  { date: '17 Oct', time: '4:00 PM', topic: 'Footwork' },
                  { date: '22 Oct', time: '4:00 PM', topic: 'Defense Drills' },
                ].map((s, i) => (
                  <div key={i} className="flex items-center gap-4 p-4 rounded-2xl bg-slate-50 hover:bg-slate-100 transition-all cursor-pointer group">
                    <div className="w-10 h-10 bg-white rounded-xl flex flex-col items-center justify-center text-[10px] font-black uppercase border border-slate-200 group-hover:border-sky-200">
                       <span className="text-sky-600 leading-none">{s.date.split(' ')[0]}</span>
                       <span className="text-slate-400">{s.date.split(' ')[1]}</span>
                    </div>
                    <div>
                      <p className="font-bold text-sm text-slate-900 leading-none">{s.topic}</p>
                      <p className="text-[10px] text-slate-500 mt-1 uppercase font-medium">{s.time} Session</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'PAYMENTS' && (
        <div className="grid lg:grid-cols-2 gap-12 animate-in slide-in-from-right-4 duration-500">
          <div className="space-y-8">
            <h3 className="text-2xl font-sporty tracking-tight uppercase">Billing & Financial Proof</h3>
            
            <div className="space-y-6">
              <div className="flex justify-between items-end">
                  <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-widest px-2">Current Outstanding</h4>
                  {/* Month Selection Dropdown */}
                  <div className="relative">
                      <select 
                        value={selectedPaymentMonth || Object.keys(student.payments).sort().find(k => student.payments[k].status === 'UNPAID') || ''} 
                        onChange={(e) => setSelectedPaymentMonth(e.target.value)}
                        className="appearance-none bg-white border border-slate-200 text-slate-700 text-xs font-bold py-2 pl-4 pr-10 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-600 shadow-sm cursor-pointer"
                      >
                         {Object.keys(student.payments).sort().map(month => (
                             <option key={month} value={month}>
                                {month} {student.payments[month].status === 'PAID' ? '(Paid)' : '(Unpaid)'}
                             </option>
                         ))}
                         {!Object.keys(student.payments).length && <option value="">No Billing History</option>}
                      </select>
                      <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
              </div>
              
              {(() => {
                 const monthKey = selectedPaymentMonth || Object.keys(student.payments).sort().find(k => student.payments[k].status === 'UNPAID') || '';
                 if (!monthKey) return <div className="p-10 rounded-[40px] bg-green-50 border-4 border-green-100 text-center text-green-700 font-bold">All payments are settled. Thank you!</div>;

                 const payment = student.payments[monthKey] || { status: 'UNPAID' };
                 const isPaid = payment.status === 'PAID';
                 const isPending = payment.isPendingApproval;
                 const penalty = calculatePenalty(payment.status);
                 const baseFee = 250;
                 const total = baseFee + penalty;
                 const displayMonthName = new Date(monthKey + '-02').toLocaleString('default', { month: 'long', year: 'numeric' });

                 return (
                   <div className={`p-10 rounded-[40px] border-4 flex flex-col shadow-2xl transition-all ${isPaid ? 'bg-slate-50 border-slate-100' : isPending ? 'bg-yellow-50 border-yellow-200' : 'bg-white border-sky-600 shadow-sky-100'}`}>
                      <div className="flex items-center justify-between mb-8">
                         <div>
                            <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Billing Month</p>
                            <h5 className="text-3xl font-sporty tracking-tight uppercase leading-none mt-1">{displayMonthName}</h5>
                         </div>
                         <div className={`px-4 py-2 rounded-2xl text-[10px] font-black uppercase tracking-widest ${isPaid ? 'bg-green-100 text-green-700' : isPending ? 'bg-yellow-400 text-white' : 'bg-red-600 text-white'}`}>
                            {isPaid ? 'Payment Confirmed' : isPending ? 'Pending Approval' : 'Unpaid Overdue'}
                         </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-8 items-end">
                         <div>
                            <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Total Fees Due</p>
                            <div className="flex items-baseline gap-2">
                                <p className="text-4xl font-sporty tracking-tight mt-1">RM {total}</p>
                                {penalty > 0 && !isPaid && <span className="text-[10px] font-bold text-red-500">(+RM{penalty} late fee)</span>}
                            </div>
                         </div>
                         <div className="space-y-3">
                            {!isPaid && !isPending ? (
                               <div className="flex flex-col gap-3">
                                  <input 
                                     type="file" 
                                     className="hidden" 
                                     ref={proofUploadRef} 
                                     accept="image/*" 
                                     onChange={(e) => handleProofUpload(e, monthKey)} 
                                  />
                                  <button 
                                     onClick={() => proofUploadRef.current?.click()}
                                     className="w-full bg-slate-900 text-white font-black uppercase tracking-widest py-4 rounded-2xl hover:bg-black transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-2"
                                  >
                                     <Upload size={18} /> Upload Proof
                                  </button>
                                  <button className="w-full bg-sky-600 text-white font-black uppercase tracking-widest py-4 rounded-2xl shadow-xl shadow-sky-100 flex items-center justify-center gap-2 hover:bg-sky-700 active:scale-95">
                                     <CreditCard size={18} /> Direct Pay
                                  </button>
                               </div>
                            ) : isPending ? (
                               <div className="space-y-3">
                                  <div className="p-4 bg-white rounded-2xl border border-yellow-200 flex items-center gap-3">
                                     <ImageIcon size={20} className="text-yellow-600" />
                                     <span className="text-[10px] font-black uppercase text-yellow-700">Slip Submitted</span>
                                  </div>
                                  <p className="text-[10px] text-slate-500 italic px-2 leading-tight">Admin is reviewing your transfer slip. Receipt will be generated upon approval.</p>
                               </div>
                            ) : (
                               <div className="space-y-3">
                                  <button className="w-full bg-white text-sky-600 border-2 border-sky-100 font-black uppercase tracking-widest py-4 rounded-2xl shadow-xl shadow-sky-50 flex items-center justify-center gap-2">
                                     <Receipt size={18} /> Get Receipt
                                  </button>
                               </div>
                            )}
                         </div>
                      </div>
                   </div>
                 );
              })()}
            </div>

            <div className="space-y-6 pt-12">
               <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-widest px-2">History & Verification</h4>
               <div className="grid gap-4">
                  {Object.entries(student.payments)
                    .filter(([_, val]) => (val as any).status === 'PAID')
                    .map(([month, val], idx) => {
                      const paymentVal = val as any;
                      return (
                      <div key={idx} className="bg-white p-6 rounded-3xl border border-slate-100 flex items-center justify-between hover:border-sky-200 transition-all group">
                         <div className="flex items-center gap-4">
                            <div className="p-3 bg-slate-50 text-slate-400 rounded-xl group-hover:bg-sky-50 group-hover:text-sky-600 transition-all">
                               <Receipt size={20} />
                            </div>
                            <div>
                               <p className="font-bold text-slate-900">Month: {month}</p>
                               <p className="text-[10px] font-black uppercase text-slate-400">Ref: {paymentVal.receiptId || 'System'}</p>
                            </div>
                         </div>
                         <div className="flex gap-2">
                           <button className="flex items-center gap-2 text-[10px] font-black uppercase text-sky-600 bg-sky-50 px-4 py-2 rounded-xl hover:bg-sky-600 hover:text-white transition-all">
                              <Download size={14} /> PDF
                           </button>
                         </div>
                      </div>
                    )})}
               </div>
            </div>
          </div>

          <div className="bg-sky-900 p-12 rounded-[50px] text-white flex flex-col justify-between shadow-2xl relative overflow-hidden group border-8 border-sky-800">
             <div className="absolute top-0 right-0 p-12 opacity-5 -mr-16 -mt-16 group-hover:scale-110 transition-transform"><Smartphone size={250} /></div>
             <div className="relative z-10">
                <div className="w-20 h-20 bg-yellow-400 rounded-3xl flex items-center justify-center text-sky-900 font-sporty text-5xl shadow-xl mb-12">R</div>
                <h3 className="text-5xl font-sporty tracking-tighter text-white uppercase leading-[0.9] mb-8">Direct <span className="text-yellow-400 italic">Billing</span> Setup</h3>
                <p className="text-sky-100 text-lg leading-relaxed max-w-sm mb-12">Forget transfer slips. Connect your bank card for automated fee settlement and instant receipt generation.</p>
                <div className="space-y-4">
                   {[ "Automated Late-fee Protection", "One-click Receipt Archive", "Family Discount Enrollment" ].map((feat, i) => (
                      <div key={i} className="flex items-center gap-4">
                         <div className="w-6 h-6 bg-yellow-400 rounded-full flex items-center justify-center text-sky-900 shadow-lg shadow-yellow-900/20"><Check size={14} strokeWidth={4} /></div>
                         <span className="text-sm font-bold tracking-tight">{feat}</span>
                      </div>
                   ))}
                </div>
             </div>
             <button className="mt-16 py-6 bg-white text-sky-900 rounded-[32px] font-black uppercase tracking-[0.2em] shadow-2xl hover:bg-yellow-400 transition-all transform active:scale-95 text-lg">
                Enable Auto-Pay
             </button>
          </div>
        </div>
      )}

      {activeTab === 'REPORTS' && (
        <div className="space-y-8 animate-in slide-in-from-right-4 duration-500">
           <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                 <h2 className="text-3xl font-sporty tracking-tight uppercase">Semi-Annual Progress Reports</h2>
                 <p className="text-slate-500 font-medium">Official performance snapshots generated every 6 months.</p>
              </div>
           </div>

           <div className="grid gap-12">
              {reports.map((report) => (
                <div key={report.id} className="bg-white p-12 rounded-[50px] border-4 border-slate-900 shadow-2xl relative overflow-hidden group">
                   <div className="flex flex-col md:flex-row justify-between items-start mb-12 border-b-2 border-slate-100 pb-10 gap-8">
                      <div>
                         <div className="w-16 h-16 bg-sky-600 rounded-2xl flex items-center justify-center text-white font-sporty text-4xl mb-6 shadow-xl">R</div>
                         <h3 className="text-5xl font-sporty tracking-tight uppercase text-slate-900">Official Report Card</h3>
                         <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mt-2">RSBE Badminton Academy</p>
                      </div>
                      <div className="text-right">
                         <div className="inline-block bg-slate-950 text-white px-6 py-2 rounded-full text-xs font-black uppercase tracking-[0.2em] mb-4">
                            Period: {report.period}
                         </div>
                      </div>
                   </div>

                   <div className="grid lg:grid-cols-3 gap-12 items-start">
                      <div className="lg:col-span-1 space-y-10">
                         <div className="space-y-6">
                            <h4 className="text-[10px] font-black uppercase text-sky-600 tracking-[0.2em]">Student Details</h4>
                            <p className="text-3xl font-bold text-slate-900 leading-none">{student.name}</p>
                         </div>
                         <div className="space-y-6 bg-slate-50 p-8 rounded-3xl border border-slate-100">
                            <h4 className="text-[10px] font-black uppercase text-slate-500 tracking-[0.2em]">Attendance Record</h4>
                            <div className="flex items-end gap-3">
                               <p className="text-5xl font-sporty leading-none text-sky-600">{report.attendanceRate}%</p>
                               <p className="text-xs font-bold text-slate-400 pb-1">({report.totalSessions} Sessions)</p>
                            </div>
                         </div>
                      </div>

                      <div className="lg:col-span-2 space-y-10">
                         <div>
                            <h4 className="text-[10px] font-black uppercase text-slate-500 tracking-[0.2em] mb-8">Skill Proficiency Matrix</h4>
                            <div className="grid sm:grid-cols-2 gap-x-12 gap-y-6">
                               {Object.entries(report.skillsSnapshot).map(([skill, val]) => (
                                 <div key={skill} className="flex items-center justify-between group/skill">
                                    <span className="text-sm font-bold text-slate-700 uppercase tracking-tight">{skill}</span>
                                    <div className="flex gap-1 text-yellow-400">
                                       {[1,2,3,4,5].map(s => (
                                         <Star key={s} size={14} fill={s <= val ? "currentColor" : "none"} className={s > val ? "text-slate-200" : ""} />
                                       ))}
                                    </div>
                                 </div>
                               ))}
                            </div>
                         </div>
                         
                         <div className="space-y-6">
                            <h4 className="text-[10px] font-black uppercase text-slate-500 tracking-[0.2em]">Coach Reflection</h4>
                            <p className="text-lg text-slate-800 leading-relaxed font-medium pl-6 border-l-4 border-sky-600">
                               "{report.coachReflection}"
                            </p>
                         </div>
                      </div>
                   </div>
                </div>
              ))}
           </div>
        </div>
      )}

      {activeTab === 'STORE' && (
        <div className="space-y-8 animate-in slide-in-from-right-4 duration-500">
          <div className="flex justify-between items-center">
            <h3 className="text-2xl font-sporty tracking-tight uppercase">Official Academy Shop</h3>
            <button className="flex items-center gap-2 bg-slate-900 text-white px-6 py-3 rounded-2xl font-black uppercase tracking-widest text-[10px]">
              <ShoppingBag size={18} /> (0) Cart
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {PRODUCTS.map(p => (
              <div key={p.id} className="bg-white rounded-[40px] overflow-hidden border border-slate-100 group shadow-sm hover:shadow-xl transition-all">
                <div className="aspect-square bg-slate-100 relative overflow-hidden">
                  <img src={p.image} alt={p.name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                  {p.availability === 'PREORDER' ? (
                     <div className="absolute top-4 right-4 bg-sky-600 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-black text-white uppercase tracking-widest shadow-lg">
                        Pre-Order
                     </div>
                  ) : (
                     <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-black text-sky-600 uppercase tracking-widest">
                        Stock: {p.stock}
                     </div>
                  )}
                </div>
                <div className="p-8">
                  <h4 className="text-xl font-bold text-slate-900 mb-1">{p.name}</h4>
                  <div className="flex items-center justify-between mt-6">
                    <span className="text-3xl font-sporty text-sky-600 tracking-tight">RM {p.price}</span>
                    <button className="p-4 bg-sky-600 text-white rounded-2xl hover:bg-sky-700 transition-colors shadow-lg active:scale-90">
                      <ShoppingBag size={20} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'SETTINGS' && (
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-right-4">
           <div className="bg-white p-12 rounded-[50px] border border-slate-100 shadow-xl shadow-slate-200/50 space-y-12">
              <div className="flex flex-col items-center gap-6">
                 <div className="relative group">
                    <img src={user.avatar} className="w-48 h-48 rounded-[40px] border-4 border-white shadow-2xl object-cover" alt={user.name} />
                    <button onClick={() => fileInputRef.current?.click()} className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-all rounded-[40px] flex flex-col items-center justify-center text-white gap-2 backdrop-blur-sm">
                      <Camera size={32} />
                      <span className="text-[10px] font-black uppercase tracking-widest">Update Photo</span>
                    </button>
                    <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleAvatarUpload} />
                 </div>
                 <div className="text-center">
                    <h2 className="text-4xl font-sporty tracking-tight uppercase leading-none">{user.name}</h2>
                    <p className="text-sky-600 font-black uppercase tracking-widest text-[10px] mt-2">RSBE Academy Member</p>
                 </div>
              </div>
              <div className="grid md:grid-cols-2 gap-8">
                 <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 px-1">Full Name</label>
                    <input className="w-full bg-slate-50 border border-slate-100 rounded-2xl px-6 py-4 font-bold text-slate-900 outline-none" value={user.name} readOnly />
                 </div>
                 <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 px-1">Email</label>
                    <input className="w-full bg-slate-50 border border-slate-100 rounded-2xl px-6 py-4 font-bold text-slate-900 outline-none" value={user.email || 'parent@rsbe.my'} readOnly />
                 </div>
              </div>
           </div>
        </div>
      )}
    </div>
  );
};

export default ClientPortal;
