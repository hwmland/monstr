import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const iconifyMock = vi.hoisted(() => ({
  loadIcon: vi.fn(),
}));

vi.mock('@iconify/react', async () => {
  const React = await import('react');
  return {
    Icon: ({ icon }: { icon: string }) =>
      React.createElement('svg', { 'data-testid': 'loaded-mdi-icon', 'data-icon': icon }),
    loadIcon: iconifyMock.loadIcon,
  };
});

import GroupNodeIcon from './GroupNodeIcon';

describe('GroupNodeIcon', () => {
  beforeEach(() => {
    iconifyMock.loadIcon.mockResolvedValue({});
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the icon after loading it from Iconify', async () => {
    render(<GroupNodeIcon icon="mdi:home" />);

    expect(await screen.findByTestId('loaded-mdi-icon')).toHaveAttribute('data-icon', 'mdi:home');
    expect(iconifyMock.loadIcon).toHaveBeenCalledWith('mdi:home');
  });

  it('keeps the icon slot visible and accessible when loading fails', async () => {
    iconifyMock.loadIcon.mockRejectedValue(new Error('Iconify unavailable'));
    render(<GroupNodeIcon icon="mdi:home" />);

    expect(
      await screen.findByRole('img', { name: 'Icon mdi:home could not be loaded' }),
    ).toHaveTextContent('!');
  });
});
