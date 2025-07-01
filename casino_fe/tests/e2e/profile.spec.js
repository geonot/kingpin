import { test, expect } from '@playwright/test';
import { loginUser, clearStorage, registerUniqueUser } from './helpers/test-helpers';

test.describe('User Profile and Settings', () => {
  let uniqueUser;

  test.beforeEach(async ({ page }) => {
    await clearStorage(page);
    // Register a new user for each test to ensure isolation for profile changes
    uniqueUser = await registerUniqueUser(page);
    // After registration, user is typically logged in and redirected.
    // Ensure we are on a page where settings/profile can be accessed.
    // For simplicity, let's assume registration lands on '/slots' and header is visible.
    await expect(page.locator('.user-info')).toContainText(uniqueUser.username);

    // Navigate to settings page - this might vary based on UI
    // Assuming there's a dropdown and a 'Settings' link
    if (await page.locator('.profile-dropdown-toggle').isVisible()) {
        await page.click('.profile-dropdown-toggle');
        await page.click('a[href="/settings"]');
    } else {
        // Fallback or direct navigation if dropdown is not standard
        await page.goto('/settings');
    }
    await expect(page).toHaveURL('/settings');
    await expect(page.locator('h1, h2')).toContainText(/Settings|Profile/i);
  });

  test('should display current user information on settings page', async ({ page }) => {
    await expect(page.locator('input[name="email"]')).toHaveValue(uniqueUser.email);
    // Username might be displayed as text, not in an input
    await expect(page.locator('body')).toContainText(uniqueUser.username);
  });

  test('should successfully change email with correct current password', async ({ page }) => {
    const newTimestamp = Date.now();
    const newEmail = `changed${newTimestamp}@example.com`;

    await page.fill('input[name="email"]', newEmail);
    await page.fill('input[name="currentPassword"]', uniqueUser.password);
    await page.click('button[type="submit"]:has-text("Update Settings")');

    // Check for success message (actual message might vary)
    await expect(page.locator('.success-message, .toast-success')).toContainText(/Settings updated|Email updated/i, { timeout: 10000 });

    // Verify new email is displayed if page reloads or shows updated info
    await page.reload(); // Or re-navigate to settings
    await expect(page.locator('input[name="email"]')).toHaveValue(newEmail);
  });

  test('should successfully change password with correct inputs', async ({ page }) => {
    const newPassword = 'newStrongPassword123!';

    await page.fill('input[name="currentPassword"]', uniqueUser.password);
    await page.fill('input[name="newPassword"]', newPassword);
    await page.fill('input[name="confirmNewPassword"]', newPassword);
    await page.click('button[type="submit"]:has-text("Update Settings")');

    await expect(page.locator('.success-message, .toast-success')).toContainText(/Settings updated|Password updated/i, { timeout: 10000 });

    // Logout and try logging in with the new password
    if (await page.locator('.profile-dropdown-toggle').isVisible()) {
        await page.click('.profile-dropdown-toggle');
        await page.click('.logout-button');
    } else {
        await page.getByRole('button', { name: /logout/i }).click();
    }
    await expect(page).toHaveURL('/');

    await loginUser(page, uniqueUser.username, newPassword); // loginUser helper uses username and password
    await expect(page.locator('.user-info')).toContainText(uniqueUser.username); // Verify login
  });

  test('should fail to change password with incorrect current password', async ({ page }) => {
    await page.fill('input[name="currentPassword"]', 'wrongOldPassword');
    await page.fill('input[name="newPassword"]', 'newStrongPassword123!');
    await page.fill('input[name="confirmNewPassword"]', 'newStrongPassword123!');
    await page.click('button[type="submit"]:has-text("Update Settings")');

    await expect(page.locator('.error-message, .toast-error')).toContainText(/Incorrect current password/i);
  });

  test('should fail to change password if new passwords do not match', async ({ page }) => {
    await page.fill('input[name="currentPassword"]', uniqueUser.password);
    await page.fill('input[name="newPassword"]', 'newStrongPassword123!');
    await page.fill('input[name="confirmNewPassword"]', 'mismatchedPassword123!');
    await page.click('button[type="submit"]:has-text("Update Settings")');

    await expect(page.locator('.error-message, .toast-error')).toContainText(/passwords do not match/i);
  });

  test('should fail to change password if new password is too weak', async ({ page }) => {
    await page.fill('input[name="currentPassword"]', uniqueUser.password);
    await page.fill('input[name="newPassword"]', 'weak');
    await page.fill('input[name="confirmNewPassword"]', 'weak');
    await page.click('button[type="submit"]:has-text("Update Settings")');

    await expect(page.locator('.error-message, .toast-error')).toContainText(/Password must be at least|complexity/i);
  });

  test('should not update settings if no changes are made', async ({ page }) => {
    // Simply click update without changing anything
    // This depends on whether currentPassword is required for any update action
    // Assuming for this test, if only currentPassword is provided (correctly), and no other fields, it might say "no changes"
    await page.fill('input[name="currentPassword"]', uniqueUser.password);
    await page.click('button[type="submit"]:has-text("Update Settings")');

    // Expect a message like "No settings were changed" or for the page to simply remain.
    // This assertion is highly dependent on actual application behavior for this edge case.
    // For now, we'll check that no error message indicating a failure appears.
    await expect(page.locator('.error-message, .toast-error')).not.toBeVisible({ timeout: 2000 });
    // Optionally, check for a specific "no changes" message if implemented.
    // await expect(page.locator('.info-message')).toContainText(/No settings were changed/i);
  });

});
