import { beforeEach, describe, expect, it } from 'vitest';

import useSelectedNodesStore from './useSelectedNodes';

describe('useSelectedNodesStore.selectNodes', () => {
  beforeEach(() => {
    useSelectedNodesStore.setState({ selected: ['All'] });
  });

  it('selects the requested group nodes', () => {
    useSelectedNodesStore.getState().selectNodes(['beta', 'alpha'], ['alpha', 'beta', 'gamma']);

    expect(useSelectedNodesStore.getState().selected).toEqual(['beta', 'alpha']);
  });

  it('normalizes empty and all-node selections to All', () => {
    const { selectNodes } = useSelectedNodesStore.getState();

    selectNodes(['alpha', 'beta'], ['alpha', 'beta']);
    expect(useSelectedNodesStore.getState().selected).toEqual(['All']);

    selectNodes([], ['alpha', 'beta']);
    expect(useSelectedNodesStore.getState().selected).toEqual(['All']);
  });
});
