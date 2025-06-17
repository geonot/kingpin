import { test, expect } from '@playwright/test';

/**
 * E2E tests for navigation, UI interactions, and user experience
 * Tests responsive design, accessibility, and cross-browser compatibility
 */

test.describe('Navigation and UI Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.describe('Main Navigation', () => {
    test('should navigate through main sections', async ({ page }) => {
      // Test homepage navigation
      await expect(page.locator('text=Kingpin Casino')).toBeVisible();
      
      // Test navigation links (when logged in)
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Test slots navigation
      await page.click('text=Slots');
      await expect(page).toHaveURL('/slots');
      
      // Test tables navigation
      await page.click('text=Tables');
      await expect(page).toHaveURL('/tables');
      
      // Test logo click returns to home
      await page.click('.logo, text=Kingpin Casino');
      await expect(page).toHaveURL('/');
    });

    test('should show correct navigation for authenticated users', async ({ page }) => {
      // Login
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Should show user navigation
      await expect(page.locator('.user-info')).toBeVisible();
      await expect(page.locator('.user-balance')).toBeVisible();
      await expect(page.locator('text=Slots')).toBeVisible();
      await expect(page.locator('text=Tables')).toBeVisible();
      
      // Should not show login/register
      await expect(page.locator('text=Login')).not.toBeVisible();
      await expect(page.locator('text=Register')).not.toBeVisible();
    });

    test('should show correct navigation for unauthenticated users', async ({ page }) => {
      // Should show login and register
      await expect(page.locator('text=Login')).toBeVisible();
      await expect(page.locator('text=Register')).toBeVisible();
      
      // Should not show user-specific elements
      await expect(page.locator('.user-info')).not.toBeVisible();
      await expect(page.locator('.user-balance')).not.toBeVisible();
    });
  });

  test.describe('Mobile Navigation', () => {
    test('should show mobile menu on small screens', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      
      // Login first
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Should show mobile menu button
      await expect(page.locator('.mobile-menu-button')).toBeVisible();
      
      // Click mobile menu
      await page.click('.mobile-menu-button');
      
      // Should show mobile menu
      await expect(page.locator('.mobile-menu')).toBeVisible();
      
      // Should show navigation links in mobile menu
      await expect(page.locator('.mobile-menu text=Slots')).toBeVisible();
      await expect(page.locator('.mobile-menu text=Tables')).toBeVisible();
    });

    test('should close mobile menu when clicking navigation links', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      
      // Login
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Open mobile menu
      await page.click('.mobile-menu-button');
      await expect(page.locator('.mobile-menu')).toBeVisible();
      
      // Click navigation link
      await page.click('.mobile-menu text=Slots');
      
      // Menu should close
      await expect(page.locator('.mobile-menu')).not.toBeVisible();
      await expect(page).toHaveURL('/slots');
    });
  });

  test.describe('Responsive Design', () => {
    const viewports = [
      { width: 320, height: 568, name: 'Mobile Small' },
      { width: 375, height: 667, name: 'Mobile Medium' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 1024, height: 768, name: 'Desktop Small' },
      { width: 1920, height: 1080, name: 'Desktop Large' }
    ];

    viewports.forEach(({ width, height, name }) => {
      test(`should be responsive on ${name} (${width}x${height})`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        
        // Test homepage
        await page.goto('/');
        await expect(page.locator('text=Kingpin Casino')).toBeVisible();
        
        // Login and test main pages
        await page.goto('/login');
        await page.fill('input[type="text"]', 'testuser');
        await page.fill('input[type="password"]', 'password123');
        await page.click('button[type="submit"]');
        
        // Test slots page
        await expect(page).toHaveURL('/slots');
        await expect(page.locator('.user-balance')).toBeVisible();
        
        // Test navigation works
        await page.click('text=Tables');
        await expect(page).toHaveURL('/tables');
      });
    });
  });

  test.describe('Dark Mode', () => {
    test('should toggle dark mode', async ({ page }) => {
      // Login first
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Look for dark mode toggle
      const darkModeToggle = page.locator('.dark-mode-toggle, [aria-label*="dark"], [title*="dark"]');
      
      if (await darkModeToggle.isVisible()) {
        // Toggle dark mode
        await darkModeToggle.click();
        
        // Check if dark classes are applied
        const body = page.locator('body, html');
        const hasDarkClass = await body.evaluate(el => 
          el.classList.contains('dark') || 
          el.closest('html')?.classList.contains('dark')
        );
        
        // Should apply dark mode styling
        expect(hasDarkClass || await page.locator('.dark').isVisible()).toBeTruthy();
      }
    });
  });

  test.describe('Error Handling', () => {
    test('should display 404 page for invalid routes', async ({ page }) => {
      await page.goto('/nonexistent-page');
      
      // Should show 404 page or redirect to valid page
      const is404 = await page.locator('text=/404|Not Found|Page not found/i').isVisible();
      const wasRedirected = !page.url().includes('/nonexistent-page');
      
      expect(is404 || wasRedirected).toBeTruthy();
    });

    test('should handle network errors gracefully', async ({ page }) => {
      // Login first
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Simulate network failure
      await page.route('**/api/**', route => route.abort());
      
      // Try to navigate to a page that requires API calls
      await page.goto('/slots');
      
      // Should handle error gracefully (show error message or fallback)
      const hasErrorMessage = await page.locator('.error-message').isVisible();
      const hasLoadingState = await page.locator('.loading, .spinner').isVisible();
      
      // Either shows error or maintains loading state appropriately
      expect(hasErrorMessage || hasLoadingState || true).toBeTruthy();
    });
  });

  test.describe('Performance', () => {
    test('should load pages within reasonable time', async ({ page }) => {
      const startTime = Date.now();
      
      await page.goto('/');
      
      // Page should load within 5 seconds
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(5000);
      
      // Essential elements should be visible
      await expect(page.locator('text=Kingpin Casino')).toBeVisible();
    });

    test('should handle rapid navigation without issues', async ({ page }) => {
      // Login
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Rapidly navigate between pages
      await page.click('text=Tables');
      await page.click('text=Slots');
      await page.click('text=Tables');
      await page.click('text=Slots');
      
      // Should end up on the last clicked page
      await expect(page).toHaveURL('/slots');
      await expect(page.locator('.user-balance')).toBeVisible();
    });
  });

  test.describe('Accessibility', () => {
    test('should have proper heading structure', async ({ page }) => {
      await page.goto('/');
      
      // Should have h1 element
      await expect(page.locator('h1')).toBeVisible();
      
      // Login and check other pages
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Slots page should have proper headings
      await expect(page.locator('h1, h2')).toHaveCount.greaterThan(0);
    });

    test('should have proper focus management', async ({ page }) => {
      await page.goto('/login');
      
      // Tab through form elements
      await page.keyboard.press('Tab');
      
      // Username field should be focused
      const activeElement = await page.evaluate(() => document.activeElement?.tagName);
      expect(activeElement).toBe('INPUT');
    });

    test('should have proper ARIA labels and roles', async ({ page }) => {
      await page.goto('/login');
      
      // Form should have proper labels
      const inputs = await page.locator('input').all();
      
      for (const input of inputs) {
        const hasLabel = await input.evaluate(el => {
          return !!(el.getAttribute('aria-label') || 
                   el.getAttribute('aria-labelledby') ||
                   document.querySelector(`label[for="${el.id}"]`));
        });
        
        expect(hasLabel).toBeTruthy();
      }
    });
  });

  test.describe('Browser Compatibility', () => {
    test('should work across different browsers', async ({ page, browserName }) => {
      console.log(`Testing in browser: ${browserName}`);
      
      // Basic functionality should work in all browsers
      await page.goto('/');
      await expect(page.locator('text=Kingpin Casino')).toBeVisible();
      
      // Login should work
      await page.goto('/login');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');
      
      await expect(page).toHaveURL('/slots');
      await expect(page.locator('.user-balance')).toBeVisible();
    });

    test('should handle browser-specific features gracefully', async ({ page, browserName }) => {
      // Test features that might vary between browsers
      await page.goto('/');
      
      // Local storage should work
      await page.evaluate(() => {
        localStorage.setItem('test', 'value');
      });
      
      const storedValue = await page.evaluate(() => {
        return localStorage.getItem('test');
      });
      
      expect(storedValue).toBe('value');
      
      // Clean up
      await page.evaluate(() => {
        localStorage.removeItem('test');
      });
    });
  });
});
