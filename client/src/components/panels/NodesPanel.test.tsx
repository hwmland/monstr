import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import useNodes from '../../hooks/useNodes';
import useSelectedNodesStore from '../../store/useSelectedNodes';
import type { NodeGroupInfo, NodeInfo } from '../../types';
import NodesPanel from './NodesPanel';

vi.mock('../../hooks/useNodes', () => ({ default: vi.fn() }));
vi.mock('../../services/apiClient', () => ({
  fetchActiveCompactions: vi.fn().mockResolvedValue({}),
  fetchIp24Status: vi.fn().mockResolvedValue({}),
}));
vi.mock('../GroupNodeIcon', async () => {
  const React = await import('react');
  return {
    default: ({ icon }: { icon: string }) =>
      React.createElement('span', { 'data-testid': 'group-node-icon', 'data-icon': icon }),
  };
});

const nodes: NodeInfo[] = [
  { name: 'alpha', path: '/logs/alpha.log' },
  { name: 'beta', path: '/logs/beta.log' },
  { name: 'gamma', path: '/logs/gamma.log' },
];

const nodegroups: NodeGroupInfo[] = [
  { name: 'group-a', nodes: ['alpha', 'beta'], icon: 'mdi:home' },
  { name: 'empty-group', nodes: [] },
];

describe('NodesPanel nodegroup selection', () => {
  beforeEach(() => {
    useSelectedNodesStore.setState({ selected: ['All'] });
    vi.mocked(useNodes).mockReturnValue({
      nodes,
      nodegroups,
      isLoading: false,
      error: undefined,
      nodegroupsError: undefined,
      refresh: vi.fn(),
    });
  });

  it('maps exact node-button selections to groups and selects group members from the combo', async () => {
    const user = userEvent.setup();
    render(<NodesPanel />);

    const groupIcons = screen.getAllByTestId('group-node-icon');
    expect(groupIcons).toHaveLength(2);
    expect(groupIcons[0]).toHaveAttribute('data-icon', 'mdi:home');
    expect(
      screen.getByRole('button', { name: 'alpha' }).querySelector('.node-card__name-row')
        ?.firstElementChild,
    ).toHaveAttribute('data-testid', 'group-node-icon');

    const selector = screen.getByRole('button', { name: 'Node group selection' });
    const selectedLabel = () => selector.querySelector('.panel-controls-combo__label')?.textContent;
    expect(selectedLabel()).toBe('All');

    await user.click(screen.getByRole('button', { name: 'alpha' }));
    expect(selectedLabel()).toBe('<groups>');

    await user.click(screen.getByRole('button', { name: 'beta' }));
    expect(selectedLabel()).toBe('group-a');

    await user.click(screen.getByRole('button', { name: 'gamma' }));
    expect(selectedLabel()).toBe('All');

    await user.click(screen.getByText('▾'));
    expect(screen.getByRole('button', { name: 'empty-group' })).toBeDisabled();
    expect(
      screen
        .getByRole('button', { name: 'group-a' })
        .querySelector('.panel-controls-combo__icon [data-testid="group-node-icon"]'),
    ).toHaveAttribute('data-icon', 'mdi:home');
    await user.click(screen.getByRole('button', { name: 'group-a' }));
    expect(selectedLabel()).toBe('group-a');
    expect(
      selector.querySelector('.panel-controls-combo__button .panel-controls-combo__icon'),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'alpha' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'beta' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'gamma' })).toHaveAttribute('aria-pressed', 'false');
  });
});
