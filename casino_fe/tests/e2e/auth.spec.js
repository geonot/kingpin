import { test, expect } from '@playwright/test';

/**
 * E2E tests for user authentication flows
 * Tests login, registration, logout, and session management
 */

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Start each test from homepage
    await page.goto('/');
  });

  test('should register new user successfully', async ({ page }) => {
    // Navigate to registration page
    await page.click('text=Register');
    await expect(page).toHaveURL('/register');

    // Fill registration form
    const timestamp = Date.now();
    const username = `testuser${timestamp}`;
    const email = `test${timestamp}@example.com`;

    await page.fill('input[type="text"]', username);
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', 'password123');
    
    // Fill confirm password
    const passwordInputs = await page.locator('input[type="password"]').all();
    await passwordInputs[1].fill('password123');
    
    // Accept terms
    await page.check('input[type="checkbox"]');

    // Submit form
    await page.click('button[type="submit"]');

    // Should redirect to slots page after successful registration
    await expect(page).toHaveURL('/slots');
    
    // Should show user in header
    await expect(page.locator('.user-info')).toContainText(username);
  });

  test('should login existing user successfully', async ({ page }) => {
    // Navigate to login page
    await page.click('text=Login');
    await expect(page).toHaveURL('/login');

    // Fill login form (assuming test user exists)
    await page.fill('input[type="text"]', 'testuser');
    await page.fill('input[type="password"]', 'password123');

    // Submit form
    await page.click('button[type="submit"]');

    // Should redirect to slots page
    await expect(page).toHaveURL('/slots');
    
    // Should show user balance and navigation
    await expect(page.locator('.user-balance')).toBeVisible();
    await expect(page.locator('text=Slots')).toBeVisible();
    await expect(page.locator('text=Tables')).toBeVisible();
  });

  test('should handle login validation errors', async ({ page }) => {
    await page.click('text=Login');

    // Try to submit empty form
    await page.click('button[type="submit"]');
    
    // Should show validation errors
    await expect(page.locator('.field-error')).toContainText('Username is required');

    // Fill only username
    await page.fill('input[type="text"]', 'testuser');
    await page.click('button[type="submit"]');
    
    // Should show password required error
    await expect(page.locator('.field-error')).toContainText('Password is required');
  });

  test('should handle invalid credentials gracefully', async ({ page }) => {
    await page.click('text=Login');

    // Fill with invalid credentials
    await page.fill('input[type="text"]', 'invaliduser');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');

    // Should show error message
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText(/invalid|incorrect/i);
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('input[type="text"]', 'testuser');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    // Wait for redirect
    await expect(page).toHaveURL('/slots');

    // Open user dropdown
    await page.click('.profile-dropdown-toggle');
    
    // Click logout
    await page.click('.logout-button');

    // Should redirect to homepage and show login/register buttons
    await expect(page).toHaveURL('/');
    await expect(page.locator('text=Login')).toBeVisible();
    await expect(page.locator('text=Register')).toBeVisible();
  });

  test('should remember user session on page reload', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[type="text"]', 'testuser');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/slots');

    // Reload page
    await page.reload();

    // Should still be logged in
    await expect(page.locator('.user-info')).toBeVisible();
    await expect(page.locator('.user-balance')).toBeVisible();
  });

  test('should redirect unauthenticated users from protected pages', async ({ page }) => {
    // Try to access protected page without login
    await page.goto('/tables');

    // Should redirect to login page
    await expect(page).toHaveURL('/login');
    
    // Should show login form
    await expect(page.locator('form')).toBeVisible();
  });

  test('should handle session timeout gracefully', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[type="text"]', 'testuser');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    // Simulate expired session by clearing localStorage
    await page.evaluate(() => {
      localStorage.removeItem('userSession');
      localStorage.removeItem('refreshToken');
    });

    // Try to navigate to protected page
    await page.goto('/slots');

    // Should redirect to login
    await expect(page).toHaveURL('/login');
  });
});
