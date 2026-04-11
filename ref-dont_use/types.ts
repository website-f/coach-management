
export enum Role {
  ADMIN = 'ADMIN',
  COACH = 'COACH',
  CLIENT = 'CLIENT'
}

export interface User {
  id: string;
  name: string;
  role: Role;
  avatar?: string;
  email?: string;
  username?: string;
  password?: string;
}

export interface Student {
  id: string;
  name: string;
  parentId: string;
  classId: string;
  status: 'ACTIVE' | 'INACTIVE';
  lastSessionDate?: string;
  skills: { [key: string]: number }; // 1-5 scale as requested
  skillReflections?: { [key: string]: string }; // Justification for the rating
  attendance: { [date: string]: boolean };
  payments: { 
    [monthKey: string]: { 
      status: 'PAID' | 'UNPAID'; 
      confirmedDate?: string; 
      receiptId?: string;
      isPendingApproval?: boolean;
      proofUrl?: string; 
    } 
  };
  videos: string[]; // URLs
}

export interface Application {
  id: string;
  studentName: string;
  contactNumber: string;
  program: string;
  preferredLocation: string;
  submissionDate: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
}

export interface LandingPageContent {
  heroTitle: string;
  heroSubtitle: string;
  announcementText: string;
  contactEmail: string;
  instagramLink: string;
  tiktokLink: string;
  availablePrograms: string[];
  availableLocations: string[];
}

export interface ProgressReport {
  id: string;
  studentId: string;
  period: string; // e.g., "Jan 2024 - Jun 2024"
  dateGenerated: string;
  attendanceRate: number;
  totalSessions: number;
  skillsSnapshot: { [key: string]: number };
  coachReflection: string;
  status: 'ELITE' | 'ADVANCED' | 'DEVELOPING' | 'FOUNDATION';
}

export interface TrainingClass {
  id: string;
  name: string;
  coachId: string;
  schedule: string;
  price: number;
  salaryPerSession: number;
  totalSessionsPerMonth: number;
  location: string;
  hallNumber?: string;
  courtNumber?: string;
  evaluationDueDate?: string; // New field for deadlines
}

export interface Transaction {
  id: string;
  type: 'INCOME' | 'EXPENSE';
  category: 'SUBSCRIPTION' | 'RENTAL' | 'SALARY' | 'MERCHANDISE' | 'OTHER';
  amount: number;
  date: string;
  description: string;
  receiptUrl?: string;
  penaltyApplied?: number;
  metadata?: {
    classId?: string;
    coachId?: string;
    productId?: string;
    sessions?: number;
    studentId?: string;
    monthKey?: string;
  };
}

export interface SessionCompletion {
  id: string;
  classId: string;
  date: string;
  completed: boolean;
  reflection?: string;
  videoUploaded?: boolean;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
}

export interface LessonPlan {
  id: string;
  classId: string;
  date: string;
  topics: string[];
  checklist: { task: string; completed: boolean }[];
  reflection: string;
}

export interface Product {
  id: string;
  name: string;
  price: number;
  image: string;
  stock: number;
  availability: 'READY' | 'PREORDER';
}
