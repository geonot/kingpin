import { createRouter, createWebHistory } from 'vue-router';
import store from '@/store'; // Import store to check auth state

// View Components - Use dynamic imports for lazy loading
const Home = () => import('@views/Home.vue');
const Slots = () => import('@views/Slots.vue');
const Slot = () => import('@views/Slot.vue');
const Tables = () => import('@views/Tables.vue');
const Blackjack = () => import('@views/Blackjack.vue');
const Register = () => import('@views/Register.vue');
const Login = () => import('@views/Login.vue');
const Deposit = () => import('@views/Deposit.vue');
const Withdraw = () => import('@views/Withdraw.vue');
const Settings = () => import('@views/Settings.vue');

// Placeholder components for routes added
const Terms = () => import('@/components/placeholders/PlaceholderContent.vue'); // Replace with actual
const Privacy = () => import('@/components/placeholders/PlaceholderContent.vue'); // Replace with actual
const ResponsibleGaming = () => import('@/components/placeholders/PlaceholderContent.vue'); // Replace with actual
const AdminDashboard = () => import('@/components/admin/AdminDashboard.vue'); // Replace with actual Admin component


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

   // Catch-all 404 route
   {
     path: '/:pathMatch(.*)*', // Matches everything else
     name: 'NotFound',
     component: () => import('@/components/placeholders/NotFound.vue'), // Lazy load a 404 component
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
      console.warn(`Access denied: Route ${to.name} requires admin privileges.`);
      // Redirect non-admins away (e.g., to home or slots page)
      next({ name: 'Slots' }); // Or show an 'Access Denied' page
      return;
  }

  // If no specific rules match, allow navigation
  next();
});

export default router;
