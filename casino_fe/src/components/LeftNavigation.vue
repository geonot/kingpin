<template>
  <aside class="w-64 bg-bg-secondary text-text-primary p-4 shadow-lg flex flex-col space-y-6 fixed top-0 left-0 h-full pt-16">
    <!-- Adjust pt-16 based on header height -->
    <div>
      <h3 class="text-xs text-text-secondary uppercase font-semibold mb-2">Main Menu</h3>
      <nav class="space-y-1">
        <router-link to="/" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-home mr-2"></i> <!-- Placeholder for icon -->
          Home
        </router-link>
        <router-link to="/slots" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-dice-d20 mr-2"></i> <!-- Placeholder for icon -->
          Slots
        </router-link>
        <router-link to="/blackjack" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-cards mr-2"></i> <!-- Placeholder for icon, fas fa-cards may not exist -->
          Blackjack
        </router-link>
        <router-link to="/plinko" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-csgo mr-2"></i> <!-- Placeholder for icon -->
          Plinko
        </router-link>
        <router-link to="/spacecrash" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-rocket mr-2"></i> <!-- Placeholder for icon -->
          Spacecrash
        </router-link>
        <router-link to="/poker-tables" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-poker-chip mr-2"></i> <!-- Placeholder for icon -->
          Poker
        </router-link>
      </nav>
    </div>

    <div>
      <h3 class="text-xs text-text-secondary uppercase font-semibold mb-2">Player Area</h3>
      <nav class="space-y-1">
        <router-link to="/deposit" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-wallet mr-2"></i>
          Deposit
        </router-link>
        <router-link to="/withdraw" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-money-bill-wave mr-2"></i>
          Withdraw
        </router-link>
        <router-link to="/transactions" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-history mr-2"></i>
          Transactions
        </router-link>
        <router-link to="/bonuses" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-gift mr-2"></i>
          Bonuses
        </router-link>
        <router-link to="/promotions" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-bullhorn mr-2"></i>
          Promotions
        </router-link>
        <router-link to="/settings" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-cog mr-2"></i>
          Settings
        </router-link>
      </nav>
    </div>

    <div>
      <h3 class="text-xs text-text-secondary uppercase font-semibold mb-2">Information</h3>
      <nav class="space-y-1">
        <router-link to="/terms" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-file-contract mr-2"></i>
          Terms & Conditions
        </router-link>
        <router-link to="/privacy" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-shield-alt mr-2"></i>
          Privacy Policy
        </router-link>
        <router-link to="/responsible-gaming" exact-active-class="bg-highlight text-accent font-semibold" class="nav-link">
          <i class="fas fa-balance-scale mr-2"></i>
          Responsible Gaming
        </router-link>
      </nav>
    </div>
  </aside>
</template>

<script>
export default {
  name: 'LeftNavigation',
  // TODO: Add logic for user authentication to show/hide Player Area links if needed
};
</script>

<style scoped>
.nav-link {
  @apply flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150;
  color: var(--color-text-primary); /* Explicitly use CSS var */
}

.nav-link:hover {
  background-color: var(--color-highlight); /* Use highlight for hover */
  color: var(--color-accent); /* Use accent for text on hover */
}

/* Active link styles are handled by exact-active-class prop in router-link */
/* Using Tailwind classes: bg-highlight text-accent font-semibold */

/* Dark mode specific adjustments if needed beyond variable changes */
.dark .nav-link {
   color: var(--color-text-primary); /* Will use dark mode text primary */
}

.dark .nav-link:hover {
  background-color: var(--color-highlight); /* Highlight is gold, should be fine */
  color: var(--color-accent); /* Accent in dark mode is light-purple, text should be dark for contrast or light if bg is dark enough */
  /* If --color-highlight (gold) needs different text color in dark mode hover, adjust here */
}

.dark .nav-link.router-link-exact-active {
    background-color: var(--color-highlight); /* Gold */
    color: var(--color-accent); /* Dark mode accent (light-purple). This might need adjustment for contrast if Gold bg + Light Purple text is not good. */
                                /* Consider a dark text on gold for active link in dark mode too. */
}

/* Placeholder icon styles (assumes Font Awesome is or will be installed) */
.fas {
  width: 1.25em; /* Equivalent to fa-fw for fixed width */
  text-align: center;
}
</style>
