import { createRouter, createWebHistory } from 'vue-router';
import store from '@/store'; // Import store to check auth state

// View Components - Use dynamic imports for lazy loading
const Home = () => import('@views/Home.vue');
const Slots = () => import('@views/Slots.vue');
const Slot = () => import('@views/Slot.vue');
const Tables = () => import('@views/Tables.vue');
const PokerTables = () => import('@/views/PokerTables.vue');
const PokerTable = () => import('@/views/PokerTable.vue'); // Added PokerTable
const Blackjack = () => import('@views/Blackjack.vue');
const Register = () => import('@views/Register.vue');
const Login = () => import('@views/Login.vue');
const Deposit = () => import('@views/Deposit.vue');
const Withdraw = () => import('@views/Withdraw.vue');
const Settings = () => import('@views/Settings.vue');
const Spacecrash = () => import('@/views/Spacecrash.vue'); // Import Spacecrash view
const Plinko = () => import('@views/Plinko.vue'); // Added Plinko

// Placeholder components for routes added
const Terms = () => import('@/views/static/TermsPage.vue');
const Privacy = () => import('@/views/static/PrivacyPage.vue');
const ResponsibleGaming = () => import('@/views/static/ResponsibleGamingPage.vue');
const AdminDashboard = () => import('@/views/admin/AdminDashboard.vue');
const AccessDeniedPage = () => import('@/views/AccessDeniedPage.vue');


const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: 'Kingpin Casino - Home' }
  },
  {
    path: '/slots',
    name: 'Slots',
    component: Slots,
     meta: { title: 'Slots', requiresAuth: true } // Requires authentication
   },
  {
    path: '/slot/:id(\\d+)', // Ensure ID is numeric
    name: 'Slot',
    component: Slot,
    props: true, // Pass route params as props
    meta: { title: 'Play Slot', requiresAuth: true }
  },
  {
    path: '/tables',
    name: 'Tables',
    component: Tables,
    meta: { title: 'Table Games', requiresAuth: true }
  },
  {
    path: '/blackjack/:id(\\d+)', // Ensure ID is numeric
    name: 'Blackjack',
    component: Blackjack,
    props: true, // Pass route params as props
    meta: { title: 'Play Blackjack', requiresAuth: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { title: 'Register', guestOnly: true } // Only accessible if not logged in
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: 'Login', guestOnly: true }
  },
  {
    path: '/deposit',
    name: 'Deposit',
    component: Deposit,
    meta: { title: 'Deposit', requiresAuth: true }
  },
  {
    path: '/withdraw',
    name: 'Withdraw',
    component: Withdraw,
    meta: { title: 'Withdraw', requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { title: 'Settings', requiresAuth: true }
  },
  {
    path: '/spacecrash',
    name: 'Spacecrash',
    component: Spacecrash,
    meta: { title: 'Spacecrash', requiresAuth: true }
  },
  {
    path: '/plinko',
    name: 'Plinko',
    component: Plinko,
    meta: { title: 'Plinko', requiresAuth: true }
  },
  {
    path: '/poker/tables',
    name: 'PokerTables',
    component: PokerTables,
    meta: { title: 'Poker Tables', requiresAuth: true }
  },
  {
    path: '/poker/table/:id(\\d+)', // Ensure ID is numeric
    name: 'PokerTable',
    component: PokerTable,
    props: true, // Pass route params as props
    meta: { title: 'Poker Table', requiresAuth: true }
  },
   // Placeholder routes for footer links
  { path: '/terms', name: 'Terms', component: Terms, meta: { title: 'Terms & Conditions' } },
  { path: '/privacy', name: 'Privacy', component: Privacy, meta: { title: 'Privacy Policy' } },
  { path: '/responsible-gaming', name: 'ResponsibleGaming', component: ResponsibleGaming, meta: { title: 'Responsible Gaming' } },

   // Admin Route Example
   {
     path: '/admin',
     name: 'AdminDashboard',
     component: AdminDashboard,
     meta: { title: 'Admin Dashboard', requiresAuth: true, requiresAdmin: true } // Requires admin privileges
   },
  {
    path: '/access-denied',
    name: 'AccessDenied',
    component: AccessDeniedPage,
    meta: { title: 'Access Denied' }
  },

   // Catch-all 404 route
   {
     path: '/:pathMatch(.*)*', // Matches everything else
     name: 'NotFound',
     component: () => import('@/views/NotFoundPage.vue'),
     meta: { title: 'Page Not Found' }
   }
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL), // Use HTML5 history mode
  routes,
  // Scroll behavior: scroll to top on new route navigation
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0 };
    }
  }
});

// --- Navigation Guards ---
router.beforeEach((to, from, next) => {
  const isAuthenticated = store.getters.isAuthenticated;
  const isAdmin = store.getters.isAdmin;

  // Set page title
  document.title = `${to.meta.title || 'Kingpin Casino'}`;

  // Guest Only Routes (Login, Register)
  if (to.meta.guestOnly && isAuthenticated) {
    next({ name: 'Slots' }); // Redirect logged-in users away from guest pages
    return;
  }

  // Routes requiring Authentication
  if (to.meta.requiresAuth && !isAuthenticated) {
     // Store intended destination for redirect after login
    next({ name: 'Login', query: { redirect: to.fullPath } });
    return;
  }

  // Routes requiring Admin privileges
  if (to.meta.requiresAdmin && !isAdmin) {
      console.warn(`Access denied: Route ${to.name} requires admin privileges. User ID: ${store.state.user?.id}`); // Enhanced log
      // Redirect non-admins away to AccessDenied page
      next({ name: 'AccessDenied' }); // Changed from 'Slots'
      return;
  }

  // If no specific rules match, allow navigation
  next();
});

export default router;
