
import { Student, TrainingClass, Transaction, Product, Role, User, ProgressReport, SessionCompletion, LessonPlan, Application, LandingPageContent } from './types';

export const SKILLS_LIST = [
  "Service", "Lobbing", "Smashing", "Drop Shot", "Netting", "Footwork", "Defense"
];

export const MOCK_ADMIN: User = {
  id: 'admin1',
  name: 'RSBE Founder',
  role: Role.ADMIN,
  avatar: 'https://i.pravatar.cc/150?u=admin',
  username: 'admin',
  password: 'pw1234'
};

export const MOCK_COACH: User = {
  id: 'coach1',
  name: 'Coach Firdaus',
  role: Role.COACH,
  avatar: 'https://i.pravatar.cc/150?u=coach1',
  username: 'coach.firdaus',
  password: 'rsbe2024user'
};

export const MOCK_COACH_2: User = {
  id: 'coach2',
  name: 'Coach Sarah',
  role: Role.COACH,
  avatar: 'https://i.pravatar.cc/150?u=coach2',
  username: 'coach.sarah',
  password: 'rsbe2024user'
};

export const MOCK_CLIENT: User = {
  id: 'c1',
  name: 'Lee Zii Jia',
  role: Role.CLIENT,
  avatar: 'https://i.pravatar.cc/150?u=parent',
  username: 'parent.lee',
  password: 'parentpassword'
};

export const MOCK_TEST_CLIENT: User = {
  id: 'c2',
  name: 'Siti\'s Parent',
  role: Role.CLIENT,
  avatar: 'https://i.pravatar.cc/150?u=testuser',
  username: 'test.user',
  password: 'testpassword'
};

export const DEFAULT_LANDING_CONTENT: LandingPageContent = {
  heroTitle: "RSBE ACADEMY",
  heroSubtitle: "Managing Malaysia's future champions with a world-class digital syllabus, personalized video tracking, and elite performance analysis.",
  announcementText: "Elite Badminton Management",
  contactEmail: "support@rsbe.my",
  instagramLink: "#",
  tiktokLink: "#",
  availablePrograms: [
    "Youth Development (6-12 Years)",
    "Junior Competitive (13-17 Years)",
    "Corporate Adult Training",
    "Private Elite Coaching"
  ],
  availableLocations: [
    "Stadium Alpha",
    "Kuala Lumpur Central",
    "Selangor Sports Complex"
  ]
};

export const MOCK_APPLICATIONS: Application[] = [
  {
    id: 'app1',
    studentName: 'Daniel Tan',
    contactNumber: '+6012-3456789',
    program: 'Youth Development (6-12 Years)',
    preferredLocation: 'Stadium Alpha',
    submissionDate: '2023-11-25',
    status: 'PENDING'
  },
  {
    id: 'app2',
    studentName: 'Sarah Lim',
    contactNumber: '+6017-8899001',
    program: 'Junior Competitive (13-17 Years)',
    preferredLocation: 'Kuala Lumpur Central',
    submissionDate: '2023-11-24',
    status: 'PENDING'
  },
  {
    id: 'app3',
    studentName: 'Michael Wong',
    contactNumber: '+6019-2233445',
    program: 'Private Elite Coaching',
    preferredLocation: 'Selangor Sports Complex',
    submissionDate: '2023-11-20',
    status: 'APPROVED'
  }
];

export const CLASSES: TrainingClass[] = [
  { 
    id: 'cl1', 
    name: 'Junior Elites', 
    coachId: 'coach1', 
    schedule: 'Mon/Wed 4-6PM', 
    price: 250,
    salaryPerSession: 80,
    totalSessionsPerMonth: 8,
    location: 'Stadium Alpha',
    hallNumber: 'Main Hall',
    courtNumber: 'Court 1 & 2',
    evaluationDueDate: '2024-12-25'
  },
  { 
    id: 'cl2', 
    name: 'Adult Beginners', 
    coachId: 'admin1', 
    schedule: 'Tue/Thu 8-10PM', 
    price: 300,
    salaryPerSession: 100,
    totalSessionsPerMonth: 8,
    location: 'Kuala Lumpur Central',
    hallNumber: 'Hall B',
    courtNumber: 'Court 5',
    evaluationDueDate: '2024-12-30'
  },
  { 
    id: 'cl3', 
    name: 'Weekend Warriors', 
    coachId: 'coach1', 
    schedule: 'Sat/Sun 9-11AM', 
    price: 200,
    salaryPerSession: 70,
    totalSessionsPerMonth: 8,
    location: 'Selangor Sports Complex',
    hallNumber: 'Indoor Arena',
    courtNumber: 'Court 10',
    evaluationDueDate: '2024-12-20'
  },
];

export const MOCK_SESSION_LOGS: SessionCompletion[] = [
  {
    id: 'log1',
    classId: 'cl1',
    date: '2023-11-20',
    completed: true,
    reflection: "Students were focused on backhand clears today. Xiao Ming is struggling with the high backhand. Need to emphasize weight transfer in next session.",
    status: 'APPROVED'
  },
  {
    id: 'log2',
    classId: 'cl1',
    date: '2023-11-22',
    completed: true,
    reflection: "Great energy. We did multi-shuttle drills for defense. Most students showed better reaction times. Smashing drills were slightly messy, need more structure.",
    status: 'PENDING'
  },
  {
    id: 'log3',
    classId: 'cl3',
    date: '2023-11-21',
    completed: true,
    reflection: "Beginner group. Still struggling with service consistency. Focused on grip and contact point. Sarah needs individual attention for her footwork recovery.",
    status: 'APPROVED'
  }
];

export const MOCK_LESSON_PLANS: LessonPlan[] = [
  {
    id: 'lp1',
    classId: 'cl1',
    date: '2023-11-20', 
    topics: ["Net Play Dominance", "Reflex Agility", "Doubles Rotation"],
    checklist: [
       { task: "10 mins Dynamic Warm-up (emphasis on ankles)", completed: true },
       { task: "Shadow Footwork: 6 corners x 3 sets", completed: true },
       { task: "Multi-shuttle: Net kills (20 tubes per pair)", completed: true },
       { task: "Defensive drives: 10 mins continuous", completed: false },
       { task: "Half-court singles 11 points (Winner stays)", completed: true }
    ],
    reflection: ""
  },
  {
    id: 'lp2',
    classId: 'cl2',
    date: '2023-11-25',
    topics: ["Basic Grip", "High Service", "Forehand Clear"],
    checklist: [
       { task: "Grip correction check", completed: false },
       { task: "Service drill: Target buckets x 50", completed: false },
       { task: "Forehand clear mechanics step-by-step", completed: false },
       { task: "Fun Game: King of the Court", completed: false }
    ],
    reflection: ""
  },
  {
    id: 'lp3',
    classId: 'cl3',
    date: '2023-11-21',
    topics: ["Match Strategy", "Stamina"],
    checklist: [
       { task: "2km Jog Warmup", completed: true },
       { task: "Full Court Matchplay", completed: true }
    ],
    reflection: ""
  }
];

export const STUDENTS: Student[] = [
  { 
    id: 's1', 
    name: 'Xiao Ming', 
    parentId: 'c1', 
    classId: 'cl1', 
    status: 'ACTIVE',
    lastSessionDate: '2023-11-05',
    skills: { "Service": 4, "Lobbing": 5, "Smashing": 3, "Drop Shot": 4, "Netting": 3, "Footwork": 4, "Defense": 3 },
    skillReflections: { "Smashing": "Great power, needs better recovery speed.", "Service": "Consistent high service, but needs to work on flick variations." },
    attendance: { '2023-10-01': true, '2023-10-03': true, '2023-11-01': true, '2023-11-05': false },
    payments: { '2023-10': { status: 'PAID', confirmedDate: '2023-10-01', receiptId: 'RC-001' }, '2023-11': { status: 'UNPAID' } },
    videos: ['https://www.w3schools.com/html/mov_bbb.mp4']
  },
  { 
    id: 's2', 
    name: 'Siti Aminah', 
    parentId: 'c2', 
    classId: 'cl1', 
    status: 'INACTIVE',
    lastSessionDate: '2023-08-15',
    skills: { "Service": 3, "Lobbing": 4, "Smashing": 2, "Drop Shot": 3, "Netting": 2, "Footwork": 3, "Defense": 2 },
    attendance: { '2023-10-01': true, '2023-10-03': false },
    payments: { '2023-10': { status: 'PAID', confirmedDate: '2023-10-05', receiptId: 'RC-002' } },
    videos: []
  },
  { 
    id: 's3', 
    name: 'Ahmad Rafiq', 
    parentId: 'c3', 
    classId: 'cl2', 
    status: 'ACTIVE',
    lastSessionDate: '2023-11-10',
    skills: { "Service": 2, "Lobbing": 3 },
    attendance: { '2023-11-10': true },
    payments: { '2023-11': { status: 'PAID', confirmedDate: '2023-11-01', receiptId: 'RC-003' } },
    videos: []
  },
  {
    id: 's4',
    name: 'John Doe',
    parentId: 'c4',
    classId: 'cl3',
    status: 'INACTIVE',
    lastSessionDate: '2023-10-01',
    skills: { "Service": 1 },
    attendance: {},
    payments: {},
    videos: []
  }
];

export const PROGRESS_REPORTS: ProgressReport[] = [
  {
    id: 'rep1',
    studentId: 's1',
    period: 'JAN 2024 - JUN 2024',
    dateGenerated: '2024-06-30',
    attendanceRate: 92,
    totalSessions: 48,
    skillsSnapshot: { "Service": 4, "Lobbing": 5, "Smashing": 3, "Drop Shot": 4, "Netting": 3, "Footwork": 4, "Defense": 3 },
    coachReflection: "Xiao Ming has shown exceptional dedication this semester. His lobbing depth has improved significantly. Future focus should be on overhead smash accuracy.",
    status: 'ADVANCED'
  },
  {
    id: 'rep2',
    studentId: 's2',
    period: 'JAN 2024 - JUN 2024',
    dateGenerated: '2024-06-30',
    attendanceRate: 85,
    totalSessions: 48,
    skillsSnapshot: { "Service": 3, "Lobbing": 4, "Smashing": 2, "Drop Shot": 3, "Netting": 2, "Footwork": 3, "Defense": 2 },
    coachReflection: "Siti shows great potential and has a positive attitude. Her lobbing consistency has improved markedly. Key areas for development are smash power and defensive reaction time.",
    status: 'DEVELOPING'
  }
];

export const TRANSACTIONS: Transaction[] = [
  { id: 't1', type: 'INCOME', category: 'SUBSCRIPTION', amount: 250, date: '2023-10-01', description: 'Xiao Ming Monthly Fees', metadata: { classId: 'cl1', studentId: 's1', monthKey: '2023-10' } },
  { id: 't1b', type: 'INCOME', category: 'SUBSCRIPTION', amount: 300, date: '2023-10-02', description: 'Ahmad Subscription', metadata: { classId: 'cl2', studentId: 's3', monthKey: '2023-10' } },
  { id: 't1c', type: 'INCOME', category: 'SUBSCRIPTION', amount: 200, date: '2023-10-03', description: 'Ali Subscription', metadata: { classId: 'cl3' } },
  { id: 't2', type: 'EXPENSE', category: 'RENTAL', amount: 1200, date: '2023-10-05', description: 'Court Rental Stadium Alpha' },
  { id: 't3', type: 'EXPENSE', category: 'MERCHANDISE', amount: 500, date: '2023-10-07', description: 'T-shirt Order Batch #4' },
  { id: 't4', type: 'INCOME', category: 'MERCHANDISE', amount: 45, date: '2023-10-08', description: 'T-shirt Sale - Adult L', metadata: { productId: 'p1' } },
  { id: 't5', type: 'INCOME', category: 'MERCHANDISE', amount: 170, date: '2023-10-09', description: 'Yonex Shuttlecocks Sale x2', metadata: { productId: 'p2' } },
  { id: 't6', type: 'EXPENSE', category: 'SALARY', amount: 960, date: '2023-10-30', description: 'Coach Firdaus Salary', metadata: { coachId: 'coach1', sessions: 12 } },
  { id: 't7', type: 'EXPENSE', category: 'SALARY', amount: 800, date: '2023-10-30', description: 'Coach Admin Salary', metadata: { coachId: 'admin1', sessions: 8 } },
];

export const PRODUCTS: Product[] = [
  { id: 'p1', name: 'RSBE Official Jersey', price: 45, image: 'https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&q=80&w=400', stock: 50, availability: 'READY' },
  { id: 'p2', name: 'Yonex Shuttlecocks (Tube)', price: 85, image: 'https://images.unsplash.com/photo-1626225967045-9c76db7b62a9?auto=format&fit=crop&q=80&w=400', stock: 20, availability: 'READY' },
  { id: 'p3', name: 'RSBE Water Bottle', price: 25, image: 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&q=80&w=400', stock: 100, availability: 'READY' },
  { id: 'p4', name: 'Limited Ed. Hoodie', price: 120, image: 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&q=80&w=400', stock: 0, availability: 'PREORDER' },
];
