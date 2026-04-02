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
    const { container: primaryContainer } = render(<Badge variant="primary">Primary</Badge>);
    expect((primaryContainer.firstChild as HTMLElement).className).toContain('bg-white/10');
    expect((primaryContainer.firstChild as HTMLElement).className).toContain('text-white');

    const { container: successContainer } = render(<Badge variant="success">Success</Badge>);
    expect((successContainer.firstChild as HTMLElement).className).toContain('bg-emerald-500/10');
    expect((successContainer.firstChild as HTMLElement).className).toContain('text-emerald-400');
  });

  it('renders dot indicator when showDot is true', () => {
    const { container } = render(<Badge showDot variant="success">With Dot</Badge>);
    // Look for the dot span
    const dot = container.querySelector('span.w-1\\.5.h-1\\.5');
    expect(dot).toBeInTheDocument();
    expect(dot?.className).toContain('bg-emerald-400');
  });

  it('renders pulse animation when pulse is true', () => {
    const { container } = render(<Badge showDot pulse variant="danger">Pulse</Badge>);
    const dot = container.querySelector('span.w-1\\.5.h-1\\.5');
    expect(dot?.className).toContain('animate-ping');
  });
});
