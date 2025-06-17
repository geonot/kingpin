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
