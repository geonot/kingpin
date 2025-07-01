// E2E Test Helpers for Kingpin Casino
import { expect } from '@playwright/test';

/**
 * Login user with credentials
 */
export async function loginUser(page, username = 'testuser', password = 'password123') {
  await page.goto('/login');
  
  await page.fill('[data-testid="username-input"]', username);
  await page.fill('[data-testid="password-input"]', password);
  await page.click('[data-testid="login-button"]');
  
  // Wait for successful login redirect
  await page.waitForURL('/dashboard', { timeout: 10000 });
  await expect(page.locator('[data-testid="user-balance"]')).toBeVisible();
}

/**
 * Clear browser storage and cookies
 */
export async function clearStorage(page) {
  await page.context().clearCookies();
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

/**
 * Wait for game to load completely
 */
export async function waitForGameLoad(page, gameSelector = '[data-testid="game-canvas"]') {
  await expect(page.locator(gameSelector)).toBeVisible();
  await page.waitForTimeout(2000); // Allow game assets to load
}

/**
 * Check user balance and return value
 */
export async function getUserBalance(page) {
  const balanceElement = page.locator('[data-testid="user-balance"]');
  await expect(balanceElement).toBeVisible();
  const balanceText = await balanceElement.textContent();
  return parseFloat(balanceText.replace(/[^0-9.-]+/g, ''));
}

/**
 * Navigate to specific game section
 */
export async function navigateToGameSection(page, section) {
  const navLink = page.locator(`[data-testid="${section}-nav"]`);
  await expect(navLink).toBeVisible();
  await navLink.click();
  await page.waitForURL(`**/${section}**`);
}

/**
 * Logout user
 */
export async function logoutUser(page) {
  await page.click('[data-testid="user-menu"]');
  await page.click('[data-testid="logout-button"]');
  await page.waitForURL('/login');
}

/**
 * Register a new unique user
 */
export async function registerUniqueUser(page, password = 'password123') {
  await page.goto('/register');

  const timestamp = Date.now();
  const username = `testuser${timestamp}`;
  const email = `test${timestamp}@example.com`;

  // Adjust selectors based on actual registration form input fields
  // Using data-testid attributes is more robust if they exist
  const usernameInput = page.locator('input[name="username"], [data-testid="username-input"]').first();
  const emailInput = page.locator('input[name="email"], [data-testid="email-input"]').first();
  const passwordInput = page.locator('input[name="password"], [data-testid="password-input"]').first();
  const confirmPasswordInput = page.locator('input[name="confirmPassword"], [data-testid="confirm-password-input"]').first(); // Assuming a confirm password field

  await usernameInput.fill(username);
  await emailInput.fill(email);
  await passwordInput.fill(password);

  // Fill confirm password if the field exists and is separate
  if (await confirmPasswordInput.isVisible() && (await passwordInput.getAttribute('name')) !== (await confirmPasswordInput.getAttribute('name'))) {
    await confirmPasswordInput.fill(password);
  } else if (await page.locator('input[name="password_confirmation"]').isVisible()) { // Common alternative name
    await page.locator('input[name="password_confirmation"]').fill(password);
  } else {
    // Attempt to find by type if multiple password fields exist for confirmation
    const passwordFields = await page.locator('input[type="password"]').all();
    if (passwordFields.length > 1) {
        await passwordFields[1].fill(password);
    }
  }

  const termsCheckbox = page.locator('input[type="checkbox"][name="terms"], [data-testid="terms-checkbox"]').first();
  if (await termsCheckbox.isVisible()) {
    await termsCheckbox.check();
  }

  // Adjust selector for submit button
  await page.click('button[type="submit"], [data-testid="register-button"]');

  // Wait for successful registration redirect (e.g., to dashboard or slots page)
  await page.waitForURL(/\/dashboard|\/slots/, { timeout: 10000 });

  return { username, email, password };
}
