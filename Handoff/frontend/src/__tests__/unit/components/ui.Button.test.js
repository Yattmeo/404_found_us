import { render, screen } from '@testing-library/react';
import { Button } from '../../../components/ui/Button';

describe('Button', () => {
  it('renders children and default button element', () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('applies outline variant and size classes', () => {
    render(
      <Button variant="outline" size="sm">
        Outline
      </Button>,
    );

    const button = screen.getByRole('button', { name: /outline/i });
    expect(button).toHaveClass('border-2');
    expect(button).toHaveClass('h-9');
  });
});
