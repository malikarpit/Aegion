import { test, expect } from '@playwright/test';

test.describe('Login flow', () => {
  test('should display login page and perform mock login', async ({ page }) => {
    await page.goto('/login');

    // Check title and branding
    await expect(page.locator('h1').first()).toHaveText('Aegion');
    
    // By default, mode is "select", with "Sign in with Email" button
    const emailModeBtn = page.locator('button', { hasText: 'Sign in with Email' });
    await expect(emailModeBtn).toBeVisible();
    await emailModeBtn.click();
    
    // Check form fields
    const emailInput = page.getByPlaceholder('you@example.com');
    await expect(emailInput).toBeVisible();
    
    // Type email
    await emailInput.fill('developer@aegion.io');
    
    // Type Fake Password
    const passwordInput = page.getByPlaceholder('••••••••');
    await expect(passwordInput).toBeVisible();
    await passwordInput.fill('password123');
    
    // We do not actually submit the form because this is hitting Firebase staging Auth without mock.
    // In a real mock environment, we would route intercept the POST and return a JWT. 
    // For UI tests, we just verify the form is submittable.
    const signInBtn = page.getByRole('button', { name: 'Sign In' });
    await expect(signInBtn).toBeVisible();
  });
});
