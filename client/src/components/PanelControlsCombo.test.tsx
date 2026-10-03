import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import PanelControlsCombo from './PanelControlsCombo';

describe('PanelControlsCombo', () => {
  it('shows a display-only unmatched label and disables empty groups', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <PanelControlsCombo
        options={[
          { value: 'All', label: 'All' },
          { value: 'empty', label: 'empty', disabled: true },
          { value: 'group-a', label: 'group-a' },
        ]}
        activeValue={null}
        displayOnlyLabel="<groups>"
        onSelect={onSelect}
        ariaLabel="Node group selection"
      />,
    );

    expect(screen.getByText('<groups>')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Node group selection' }));
    expect(onSelect).not.toHaveBeenCalled();

    await user.click(screen.getByText('▾'));
    const menu = screen.getByRole('listbox');
    expect(within(menu).queryByText('<groups>')).not.toBeInTheDocument();
    expect(within(menu).getByRole('button', { name: 'empty' })).toBeDisabled();

    await user.click(within(menu).getByRole('button', { name: 'empty' }));
    expect(onSelect).not.toHaveBeenCalled();

    await user.click(within(menu).getByRole('button', { name: 'group-a' }));
    expect(onSelect).toHaveBeenCalledWith('group-a');
  });

  it('shows an option icon in the active value and expanded list', async () => {
    const user = userEvent.setup();
    render(
      <PanelControlsCombo
        options={[
          { value: 'All', label: 'All' },
          {
            value: 'group-a',
            label: 'group-a',
            icon: <span data-testid="group-icon" aria-hidden="true" />,
          },
        ]}
        activeValue="group-a"
        onSelect={vi.fn()}
      />,
    );

    const combo = screen.getByRole('button', { name: 'Select option' });
    expect(
      combo.querySelector('.panel-controls-combo__icon [data-testid="group-icon"]'),
    ).toBeTruthy();

    await user.click(screen.getByText('▾'));
    const menu = screen.getByRole('listbox');
    expect(
      within(menu)
        .getByRole('button', { name: 'group-a' })
        .querySelector('.panel-controls-combo__icon [data-testid="group-icon"]'),
    ).toBeTruthy();
  });
});
