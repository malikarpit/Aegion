import { test, expect } from '@playwright/test';

test.describe('Login flow', () => {
  test('should display login page and perform mock login', async ({ page }) => {
    await page.goto('/login');

    // Check title and branding
    await expect(page.locator('h2')).toContainText('Sign in to Aegion');
    
    // Check form fields
    const emailInput = page.getByPlaceholder('name@company.com');
    await expect(emailInput).toBeVisible();
    
    // Type email
    await emailInput.fill('developer@aegion.io');
    
    // Click continue
    const continueBtn = page.getByRole('button', { name: 'Continue with Email' });
    await continueBtn.click();
    
    // Should transition to OTP mode
    await expect(page.getByText('Enter the secure code')).toBeVisible();
    
    // Type fake code
    const optInput = page.getByPlaceholder('Enter code');
    await optInput.fill('123456');
    
    // Click verify
    const verifyBtn = page.getByRole('button', { name: 'Verify Identity' });
    await verifyBtn.click();
    
    // In our mock setup, this might redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard.*/);
  });
});
