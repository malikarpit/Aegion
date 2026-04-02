import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DashboardPage from '@/app/dashboard/page';

// Mock the Recharts module so it doesn't complain about DOM measurements
vi.mock('recharts', () => {
  const Original = vi.importActual('recharts');
  return {
    ...Original,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
    LineChart: ({ children }: any) => <div>{children}</div>,
    Line: () => <div data-testid="recharts-line" />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    CartesianGrid: () => <div />,
    Tooltip: () => <div />,
    PieChart: ({ children }: any) => <div>{children}</div>,
    Pie: () => <div data-testid="recharts-pie" />,
    Cell: () => <div />,
  };
});

describe('Dashboard Page', () => {
  it('renders the dashboard title and layout', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Council Overview')).toBeInTheDocument();
  });

  it('renders stats cards with mock data', () => {
    render(<DashboardPage />);
    // Check if the mock stats are rendering
    expect(screen.getByText('Active Sessions')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument(); // Mock data value
    expect(screen.getByText('Decisions Made')).toBeInTheDocument();
    expect(screen.getByText('Pending Proposals')).toBeInTheDocument();
  });

  it('renders the activity feed', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Recent Activity')).toBeInTheDocument();
  });

  it('renders charts', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Cost vs Limit')).toBeInTheDocument();
    expect(screen.getByText('Decision Distribution')).toBeInTheDocument();
    expect(screen.getByText('Risk Level')).toBeInTheDocument();
  });
});
