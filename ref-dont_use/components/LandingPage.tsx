
import React, { useState } from 'react';
// FIX: Import Role enum to be used for user creation.
import { User, LandingPageContent, Role } from '../types';
import { Trophy, TrendingUp, ArrowRight, ShieldCheck, UserCheck, MoreVertical, X, Lock, Key, User as UserIcon, Loader2, AlertCircle, Smartphone, CheckCircle, ChevronLeft } from 'lucide-react';
import { MOCK_ADMIN, MOCK_COACH, MOCK_COACH_2, MOCK_CLIENT, MOCK_TEST_CLIENT } from '../constants';

interface Props {
  onLogin: (user: User) => void;
  content: LandingPageContent;
}

const LandingPage: React.FC<Props> = ({ onLogin, content }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  
  // Login Modal State
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginRole, setLoginRole] = useState<'ADMIN' | 'COACH' | 'CLIENT' | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Registration State
  const [registrationStep, setRegistrationStep] = useState<'DETAILS' | 'ACCOUNT' | 'SUCCESS'>('DETAILS');
  const [regForm, setRegForm] = useState({
    name: '',
    contact: '',
    program: content.availablePrograms?.[0] || 'General Training',
    location: '',
    username: '',
    password: '',
    confirmPassword: ''
  });

  const ALL_USERS = [MOCK_ADMIN, MOCK_COACH, MOCK_COACH_2, MOCK_CLIENT, MOCK_TEST_CLIENT];

  const handleLoginClick = (role: 'ADMIN' | 'COACH' | 'CLIENT') => {
    setLoginRole(role);
    setUsername('');
    setPassword('');
    setError('');
    setShowLoginModal(true);
    setIsMenuOpen(false);
  };

  const attemptLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    // Simulate network delay
    setTimeout(() => {
      // Allow the newly created user to login for this session if matches
      const isNewUser = registrationStep === 'SUCCESS' && 
                        loginRole === 'CLIENT' && 
                        username === regForm.username && 
                        password === regForm.password;

      const user = ALL_USERS.find(u => 
        u.role === loginRole && 
        u.username === username && 
        u.password === password
      );

      if (user) {
        onLogin(user);
      } else if (isNewUser) {
        // Mock login for the new registration
        onLogin({
            id: 'new-client',
            name: regForm.name,
            // FIX: Use Role.CLIENT to match the enum type.
            role: Role.CLIENT,
            username: regForm.username,
            avatar: `https://i.pravatar.cc/150?u=${regForm.username}`
        });
      } else {
        setError('Invalid username or password.');
        setIsLoading(false);
      }
    }, 800);
  };

  const handleDetailsSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (regForm.name && regForm.contact && regForm.location) {
        setRegistrationStep('ACCOUNT');
    }
  };

  const handleAccountSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (regForm.username && regForm.password && regForm.password === regForm.confirmPassword) {
        // Simulate API call
        setTimeout(() => {
            setRegistrationStep('SUCCESS');
        }, 500);
    }
  };

  return (
    <div className="min-h-screen font-sans text-slate-900 bg-white relative">
      {/* Admin/Staff Access Menu */}
      <div className="absolute top-6 left-6 z-50">
        <button 
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="p-3 bg-white/10 backdrop-blur-md rounded-full text-white hover:bg-white/20 transition-all border border-white/10 shadow-lg"
          aria-label="Staff Access"
        >
          <MoreVertical size={24} />
        </button>

        {isMenuOpen && (
          <div className="absolute top-full left-0 mt-3 w-64 bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-200 origin-top-left">
            <div className="p-2 space-y-1">
              <div className="px-4 py-2 text-[10px] font-black uppercase text-slate-400 tracking-widest border-b border-slate-50 mb-1">
                Staff Portal Access
              </div>
              <button 
                onClick={() => handleLoginClick('ADMIN')}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 rounded-xl text-left transition-colors group"
              >
                <div className="p-2 bg-slate-100 rounded-lg group-hover:bg-slate-900 group-hover:text-white transition-colors">
                  <ShieldCheck size={16} />
                </div>
                <div>
                  <span className="block text-sm font-bold text-slate-900">Admin Login</span>
                  <span className="block text-[10px] font-medium text-slate-400">Management Dashboard</span>
                </div>
              </button>
              
              <button 
                onClick={() => handleLoginClick('COACH')}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 rounded-xl text-left transition-colors group"
              >
                <div className="p-2 bg-sky-50 text-sky-600 rounded-lg group-hover:bg-sky-600 group-hover:text-white transition-colors">
                  <UserCheck size={16} />
                </div>
                <div>
                  <span className="block text-sm font-bold text-slate-900">Coach Login</span>
                  <span className="block text-[10px] font-medium text-slate-400">Trainer & Staff Area</span>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-md rounded-[32px] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="p-8 relative">
              <button 
                onClick={() => setShowLoginModal(false)}
                className="absolute top-6 right-6 p-2 bg-slate-50 rounded-full text-slate-400 hover:text-slate-900 transition-colors"
              >
                <X size={20} />
              </button>
              
              <div className="text-center mb-8">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl shadow-lg ${
                  loginRole === 'ADMIN' ? 'bg-slate-900 text-white' : 
                  loginRole === 'COACH' ? 'bg-sky-600 text-white' : 
                  'bg-yellow-400 text-sky-900'
                }`}>
                  {loginRole === 'ADMIN' ? <ShieldCheck /> : loginRole === 'COACH' ? <UserCheck /> : <Trophy />}
                </div>
                <h3 className="text-2xl font-sporty tracking-tight uppercase">
                  {loginRole === 'ADMIN' ? 'Administrator' : loginRole === 'COACH' ? 'Staff Portal' : 'Student Portal'}
                </h3>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Secure Login</p>
              </div>

              <form onSubmit={attemptLogin} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Username</label>
                  <div className="relative group">
                    <UserIcon size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-sky-600 transition-colors" />
                    <input 
                      type="text" 
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-100 rounded-2xl pl-12 pr-4 py-4 font-bold text-slate-900 outline-none focus:ring-2 focus:ring-sky-600 focus:bg-white transition-all"
                      placeholder="Enter username"
                      autoFocus
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Password</label>
                  <div className="relative group">
                    <Key size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-sky-600 transition-colors" />
                    <input 
                      type="password" 
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-100 rounded-2xl pl-12 pr-4 py-4 font-bold text-slate-900 outline-none focus:ring-2 focus:ring-sky-600 focus:bg-white transition-all"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 text-red-600 rounded-xl text-xs font-bold animate-in slide-in-from-top-1">
                    <AlertCircle size={16} /> {error}
                  </div>
                )}

                <button 
                  type="submit" 
                  disabled={isLoading || !username || !password}
                  className={`w-full py-4 rounded-2xl font-black uppercase tracking-widest text-xs flex items-center justify-center gap-2 shadow-xl transition-all active:scale-95 mt-4 ${
                    loginRole === 'ADMIN' ? 'bg-slate-900 text-white hover:bg-black shadow-slate-200' : 
                    loginRole === 'COACH' ? 'bg-sky-600 text-white hover:bg-sky-700 shadow-sky-200' : 
                    'bg-yellow-400 text-sky-900 hover:bg-yellow-300 shadow-yellow-100'
                  } ${isLoading || !username || !password ? 'opacity-70 cursor-not-allowed' : ''}`}
                >
                  {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Lock size={16} />}
                  {isLoading ? 'Verifying...' : 'Access Dashboard'}
                </button>
              </form>
              
              <div className="mt-6 text-center">
                <p className="text-[10px] text-slate-400 font-medium">Forgot credentials? Contact system admin.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <header className="relative bg-sky-900 py-20 lg:py-28 overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <img 
            src="https://images.unsplash.com/photo-1626225967045-9c76db7b62a9?auto=format&fit=crop&q=80&w=2000" 
            alt="Badminton court" 
            className="w-full h-full object-cover"
          />
        </div>
        
        {/* Decorative Elements */}
        <div className="absolute top-0 right-0 w-1/3 h-full bg-gradient-to-l from-sky-800/50 to-transparent pointer-events-none"></div>
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-yellow-400 rounded-full blur-[100px] opacity-20"></div>

        <div className="relative max-w-7xl mx-auto px-6 flex flex-col lg:flex-row items-center gap-16">
          <div className="flex-1 text-center lg:text-left">
            <div className="inline-block bg-yellow-400/10 backdrop-blur-md px-4 py-1.5 rounded-full text-yellow-400 text-sm font-bold tracking-widest uppercase mb-8 border border-yellow-400/20">
              {content.announcementText}
            </div>
            <h1 className="text-6xl lg:text-9xl font-sporty text-white leading-[0.9] mb-8">
              {content.heroTitle} <span className="text-yellow-400 italic">ACADEMY</span>
            </h1>
            <p className="text-sky-100 text-xl max-w-2xl mb-12 leading-relaxed">
              {content.heroSubtitle}
            </p>
            
            {/* Call to Action - Client Only */}
            <div className="flex flex-col sm:flex-row flex-wrap justify-center lg:justify-start gap-4">
              <button 
                onClick={() => handleLoginClick('CLIENT')}
                className="bg-white hover:bg-slate-100 text-sky-900 px-10 py-5 rounded-2xl font-bold transition-all shadow-2xl flex items-center justify-center gap-3 transform hover:-translate-y-1 active:scale-95 text-lg"
              >
                Access Student Portal <ArrowRight size={20} />
              </button>
            </div>
          </div>
          
          <div className="flex-1 relative hidden lg:block">
             <div className="absolute inset-0 bg-yellow-400 rounded-3xl rotate-3 scale-105 opacity-10"></div>
             <img 
               src="https://images.unsplash.com/photo-1554068865-24cecd4e34b8?auto=format&fit=crop&q=80&w=800" 
               alt="Badminton action" 
               className="relative z-10 rounded-[40px] shadow-2xl border-8 border-white/5"
             />
          </div>
        </div>
      </header>

      {/* Feature Highlights */}
      <section className="py-24 bg-white relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-3 gap-12">
            {[
              { icon: <Trophy className="text-yellow-500" size={48} />, title: "Pro Syllabus", desc: "Structured training modules for every level from beginner to elite tournament prep." },
              { icon: <Smartphone className="text-sky-600" size={48} />, title: "Performance Apps", desc: "Dedicated interfaces for Web, iOS, and Android ensuring full business accessibility." },
              { icon: <TrendingUp className="text-green-500" size={48} />, title: "Video Proof", desc: "Personalized training clips provided to parents as proof of student progression." }
            ].map((f, i) => (
              <div key={i} className="p-10 rounded-[40px] bg-slate-50 border border-slate-100 hover:shadow-xl transition-all group">
                <div className="mb-8 p-4 bg-white rounded-3xl w-fit shadow-sm group-hover:scale-110 transition-transform">{f.icon}</div>
                <h3 className="text-2xl font-bold text-slate-900 mb-4 font-sporty tracking-wide uppercase">{f.title}</h3>
                <p className="text-slate-600 leading-relaxed text-lg">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Registration Funnel */}
      <section className="bg-white py-24 border-t border-slate-100">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-5xl font-bold mb-6 text-black font-sporty tracking-tight uppercase italic">Apply for Admission</h2>
          <p className="text-slate-600 mb-16 text-xl max-w-xl mx-auto">Elite coaching is in high demand. Secure your spot in the next intake by filling in your details below.</p>
          
          <div className="bg-slate-50 p-8 md:p-12 rounded-[40px] shadow-2xl shadow-slate-200/50 border border-slate-100 text-left transition-all duration-500">
            {registrationStep === 'DETAILS' && (
                <form onSubmit={handleDetailsSubmit} className="grid sm:grid-cols-2 gap-8 animate-in slide-in-from-right-4">
                    <div className="space-y-3">
                        <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Student Full Name</label>
                        <input 
                            type="text" 
                            required
                            value={regForm.name}
                            onChange={e => setRegForm({...regForm, name: e.target.value})}
                            className="w-full px-6 py-4 rounded-2xl border-none bg-black focus:ring-4 focus:ring-sky-600 outline-none text-white placeholder:text-slate-600 transition-all shadow-xl text-lg font-medium" 
                            placeholder="Name as per IC" 
                        />
                    </div>
                    <div className="space-y-3">
                        <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Contact Number</label>
                        <input 
                            type="tel" 
                            required
                            value={regForm.contact}
                            onChange={e => setRegForm({...regForm, contact: e.target.value})}
                            className="w-full px-6 py-4 rounded-2xl border-none bg-black focus:ring-4 focus:ring-sky-600 outline-none text-white placeholder:text-slate-600 transition-all shadow-xl text-lg font-medium" 
                            placeholder="+6012-XXXXXXX" 
                        />
                    </div>
                    <div className="space-y-3 sm:col-span-2">
                        <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Program Selection</label>
                        <div className="relative">
                            <select 
                                value={regForm.program}
                                onChange={e => setRegForm({...regForm, program: e.target.value})}
                                className="w-full px-6 py-4 rounded-2xl border-none bg-black focus:ring-4 focus:ring-sky-600 outline-none text-white appearance-none transition-all shadow-xl cursor-pointer text-lg font-medium"
                            >
                                {content.availablePrograms && content.availablePrograms.length > 0 ? (
                                    content.availablePrograms.map((prog, i) => (
                                    <option key={i} value={prog} className="bg-black text-white">{prog}</option>
                                    ))
                                ) : (
                                    <option value="General Training" className="bg-black text-white">General Training</option>
                                )}
                            </select>
                            <div className="absolute right-6 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                <ArrowRight size={20} className="rotate-90" />
                            </div>
                        </div>
                    </div>
                    
                    <div className="space-y-3 sm:col-span-2">
                        <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Location Preference</label>
                        <div className="relative">
                            <select 
                                required
                                value={regForm.location}
                                onChange={e => setRegForm({...regForm, location: e.target.value})}
                                className="w-full px-6 py-4 rounded-2xl border-none bg-black focus:ring-4 focus:ring-sky-600 outline-none text-white appearance-none transition-all shadow-xl cursor-pointer text-lg font-medium"
                            >
                                <option value="" disabled>Select a venue</option>
                                {content.availableLocations && content.availableLocations.length > 0 ? (
                                    content.availableLocations.map(loc => (
                                    <option key={loc} value={loc} className="bg-black text-white">{loc}</option>
                                    ))
                                ) : (
                                    <option value="" disabled>No locations available</option>
                                )}
                            </select>
                            <div className="absolute right-6 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                <ArrowRight size={20} className="rotate-90" />
                            </div>
                        </div>
                    </div>

                    <button type="submit" className="sm:col-span-2 bg-sky-600 text-white font-black py-5 rounded-2xl hover:bg-sky-700 transition-all shadow-2xl shadow-sky-200 transform hover:scale-[1.01] active:scale-[0.99] mt-6 uppercase tracking-widest text-lg flex items-center justify-center gap-3">
                        Next: Create Account <ArrowRight size={20} />
                    </button>
                    <p className="sm:col-span-2 text-center text-slate-400 text-xs mt-4">
                        Note: No free trial sessions. Enrollment is subject to initial assessment by RSBE head coach.
                    </p>
                </form>
            )}

            {registrationStep === 'ACCOUNT' && (
                <form onSubmit={handleAccountSubmit} className="space-y-8 animate-in slide-in-from-right-4 max-w-2xl mx-auto">
                    <div className="text-center mb-8">
                         <div className="w-16 h-16 bg-black rounded-2xl flex items-center justify-center mx-auto mb-4 text-white shadow-xl">
                            <UserIcon size={32} />
                         </div>
                         <h3 className="text-2xl font-bold text-slate-900">Create Student Login</h3>
                         <p className="text-slate-500">Set up your credentials to access the RSBE Portal apps.</p>
                    </div>

                    <div className="space-y-3 text-left">
                        <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Choose Username</label>
                        <div className="relative">
                            <UserIcon size={20} className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input 
                                type="text" 
                                required
                                value={regForm.username}
                                onChange={e => setRegForm({...regForm, username: e.target.value})}
                                className="w-full pl-14 pr-6 py-4 rounded-2xl border-none bg-white border border-slate-200 focus:ring-4 focus:ring-sky-600 outline-none text-slate-900 placeholder:text-slate-400 transition-all shadow-lg text-lg font-bold" 
                                placeholder="student.username" 
                            />
                        </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-6 text-left">
                        <div className="space-y-3">
                            <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Password</label>
                            <div className="relative">
                                <Key size={20} className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-500" />
                                <input 
                                    type="password" 
                                    required
                                    value={regForm.password}
                                    onChange={e => setRegForm({...regForm, password: e.target.value})}
                                    className="w-full pl-14 pr-6 py-4 rounded-2xl border-none bg-white border border-slate-200 focus:ring-4 focus:ring-sky-600 outline-none text-slate-900 placeholder:text-slate-400 transition-all shadow-lg text-lg font-bold" 
                                    placeholder="••••••••" 
                                />
                            </div>
                        </div>
                        <div className="space-y-3">
                            <label className="text-xs font-black text-black uppercase tracking-[0.2em]">Confirm Password</label>
                            <div className="relative">
                                <Key size={20} className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-500" />
                                <input 
                                    type="password" 
                                    required
                                    value={regForm.confirmPassword}
                                    onChange={e => setRegForm({...regForm, confirmPassword: e.target.value})}
                                    className={`w-full pl-14 pr-6 py-4 rounded-2xl border-none bg-white border ${regForm.confirmPassword && regForm.password !== regForm.confirmPassword ? 'border-red-500 focus:ring-red-500' : 'border-slate-200 focus:ring-sky-600'} outline-none text-slate-900 placeholder:text-slate-400 transition-all shadow-lg text-lg font-bold`}
                                    placeholder="••••••••" 
                                />
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-4 pt-4">
                        <button type="button" onClick={() => setRegistrationStep('DETAILS')} className="flex-1 py-5 rounded-2xl font-bold text-slate-500 hover:bg-slate-100 transition-all flex items-center justify-center gap-2">
                             <ChevronLeft size={20} /> Back
                        </button>
                        <button type="submit" disabled={!regForm.username || !regForm.password || regForm.password !== regForm.confirmPassword} className="flex-[2] bg-sky-600 text-white font-black py-5 rounded-2xl hover:bg-sky-700 transition-all shadow-2xl shadow-sky-200 transform hover:scale-[1.01] active:scale-[0.99] uppercase tracking-widest text-lg disabled:opacity-50 disabled:cursor-not-allowed">
                             Complete Registration
                        </button>
                    </div>
                </form>
            )}

            {registrationStep === 'SUCCESS' && (
                <div className="animate-in zoom-in-95 duration-500 py-12 text-center">
                    <div className="w-24 h-24 bg-green-500 rounded-full flex items-center justify-center text-white mx-auto mb-8 shadow-2xl shadow-green-200">
                        <CheckCircle size={48} />
                    </div>
                    <h3 className="text-4xl font-sporty uppercase tracking-tight text-slate-900 mb-4">Registration Successful!</h3>
                    <p className="text-xl text-slate-600 max-w-md mx-auto mb-12">
                        Welcome to RSBE Academy, <span className="font-bold text-slate-900">{regForm.name}</span>. Your student portal ID has been created.
                    </p>
                    <div className="bg-slate-100 p-6 rounded-3xl max-w-sm mx-auto mb-12 border border-slate-200">
                         <p className="text-xs font-black uppercase text-slate-400 tracking-widest mb-2">Your Login ID</p>
                         <p className="text-2xl font-bold text-sky-600 font-mono">{regForm.username}</p>
                    </div>
                    <button 
                        onClick={() => handleLoginClick('CLIENT')}
                        className="bg-slate-900 text-white px-12 py-5 rounded-2xl font-black uppercase tracking-widest text-lg hover:bg-black transition-all shadow-xl shadow-slate-300 transform hover:-translate-y-1"
                    >
                        Login to Portal
                    </button>
                </div>
            )}
          </div>
        </div>
      </section>

      <footer className="bg-slate-950 py-16 text-slate-500 text-center border-t border-slate-900">
        <div className="max-w-7xl mx-auto px-6">
          <div className="font-sporty text-3xl text-white mb-6 tracking-widest italic">RSBE ACADEMY</div>
          <p className="max-w-md mx-auto mb-8 text-sm">Professional badminton coaching and management. Building the next generation of shuttlers with integrity and innovation.</p>
          <div className="flex justify-center gap-8 mb-12">
            <a href={content.instagramLink} className="hover:text-white transition-colors">Instagram</a>
            <a href={content.tiktokLink} className="hover:text-white transition-colors">TikTok</a>
            <a href={`mailto:${content.contactEmail}`} className="hover:text-white transition-colors">Contact Support</a>
          </div>
          <p className="text-xs opacity-50 uppercase tracking-widest">© 2024 RSBE Badminton Academy. All Rights Reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;