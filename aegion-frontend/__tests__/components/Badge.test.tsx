import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Badge } from '@/components/ui/Badge';

describe('Badge Component', () => {
  it('renders children correctly', () => {
    render(<Badge>Test Badge</Badge>);
    expect(screen.getByText('Test Badge')).toBeInTheDocument();
  });

  it('applies default classes', () => {
    const { container } = render(<Badge>Default</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('inline-flex');
    expect(badge.className).toContain('items-center');
    expect(badge.className).toContain('rounded-full');
  });

  it('renders with variants correctly', () => {
    const { container: neutralContainer } = render(<Badge variant="neutral">Neutral</Badge>);
    expect((neutralContainer.firstChild as HTMLElement).className).toContain('bg-white/5');
    expect((neutralContainer.firstChild as HTMLElement).className).toContain('text-slate-400');

    const { container: successContainer } = render(<Badge variant="success">Success</Badge>);
    expect((successContainer.firstChild as HTMLElement).className).toContain('bg-emerald-500/10');
    expect((successContainer.firstChild as HTMLElement).className).toContain('text-emerald-400');
  });

  it('renders dot indicator when dot is true', () => {
    const { container } = render(<Badge dot variant="success">With Dot</Badge>);
    // Look for the inner dot span with bg-current
    const dotWrapper = container.querySelector('span.relative.flex');
    expect(dotWrapper).toBeInTheDocument();
    const innerDot = container.querySelector('span.bg-current:not(.animate-ping)');
    expect(innerDot).toBeInTheDocument();
  });

  it('renders pulse animation when pulse is true', () => {
    const { container } = render(<Badge dot pulse variant="danger">Pulse</Badge>);
    const pulseDot = container.querySelector('.animate-ping');
    expect(pulseDot).toBeInTheDocument();
  });
});
