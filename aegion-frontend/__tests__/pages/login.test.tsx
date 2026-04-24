import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LoginPage from '@/app/login/page';

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: null,
    signInWithGoogle: vi.fn(),
    signInWithEmail: vi.fn(),
    loading: false,
    error: null,
  })
}));

describe('Login Page', () => {
  it('renders login form correctly', () => {
    render(<LoginPage />);
    expect(screen.getByText('Aegion')).toBeInTheDocument();
    expect(screen.getByText('AI Governance Control Plane')).toBeInTheDocument();
    expect(screen.getByText('Continue with Google')).toBeInTheDocument();
  });

  it('toggles to email mode when Sign in with Email is clicked', () => {
    render(<LoginPage />);
    
    // Check initial state (select mode)
    const emailBtn = screen.getByText('Sign in with Email');
    expect(emailBtn).toBeInTheDocument();
    
    // Click Sign in with Email
    fireEvent.click(emailBtn);
    
    // Should now show Email/Password inputs
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
  });
});
