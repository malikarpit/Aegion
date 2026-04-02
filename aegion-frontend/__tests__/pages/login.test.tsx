import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LoginPage from '@/app/login/page';

describe('Login Page', () => {
  it('renders login form correctly', () => {
    render(<LoginPage />);
    expect(screen.getByText('Sign in to Aegion')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('name@company.com')).toBeInTheDocument();
    expect(screen.getByText('Continue with Google')).toBeInTheDocument();
  });

  it('toggles to OTP mode when form submitted', () => {
    render(<LoginPage />);
    
    // Simulate typing email
    const emailInput = screen.getByPlaceholderText('name@company.com');
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    
    // Check continue button (email mode)
    const continueBtn = screen.getByText('Continue with Email');
    expect(continueBtn).toBeInTheDocument();
    
    // Click continue
    fireEvent.click(continueBtn);
    
    // Should now show OTP input
    expect(screen.getByText(/Enter the secure code/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter code')).toBeInTheDocument();
    expect(screen.getByText('Verify Identity')).toBeInTheDocument();
  });
});
