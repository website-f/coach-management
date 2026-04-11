
import React from 'react';
import { User, Role } from '../types';
import { LogOut, Bell, Shield, User as UserIcon, Medal } from 'lucide-react';

interface Props {
  user: User;
  onLogout: () => void;
}

export const Navigation: React.FC<Props> = ({ user, onLogout }) => {
  const getRoleIcon = () => {
    switch(user.role) {
      case Role.ADMIN: return <Shield size={14} />;
      case Role.COACH: return <Medal size={14} />;
      default: return <UserIcon size={14} />;
    }
  };

  const getRoleColor = () => {
    switch(user.role) {
      case Role.ADMIN: return 'bg-red-50 text-red-600 border-red-100';
      case Role.COACH: return 'bg-sky-50 text-sky-600 border-sky-100';
      default: return 'bg-slate-50 text-slate-600 border-slate-100';
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 z-50 px-4 md:px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-sky-600 rounded-lg flex items-center justify-center text-white font-sporty text-2xl shadow-lg shadow-sky-100">
          R
        </div>
        <span className="font-sporty text-2xl tracking-tight text-slate-800 hidden md:block">
          RSBE PRO MANAGER
        </span>
      </div>

      <div className="flex items-center gap-4">
        <button className="text-slate-500 hover:text-sky-600 relative p-2">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
        </button>
        <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-bold text-slate-900 leading-none">{user.name}</p>
            <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase mt-1 ${getRoleColor()}`}>
              {getRoleIcon()} {user.role}
            </div>
          </div>
          <img src={user.avatar} alt="User" className="w-9 h-9 rounded-full border-2 border-slate-100" />
          <button 
            onClick={onLogout}
            className="p-2 text-slate-400 hover:text-red-500 transition-colors"
            title="Logout"
          >
            <LogOut size={20} />
          </button>
        </div>
      </div>
    </nav>
  );
};