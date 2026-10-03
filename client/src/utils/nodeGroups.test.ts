import { describe, expect, it } from 'vitest';

import type { NodeGroupInfo } from '../types';
import { getNodeGroupSelectionValue } from './nodeGroups';

const nodegroups: NodeGroupInfo[] = [
  { name: 'group-a', nodes: ['alpha', 'beta'] },
  { name: 'empty', nodes: [] },
];

describe('getNodeGroupSelectionValue', () => {
  it('matches a group by exact node set regardless of order', () => {
    expect(
      getNodeGroupSelectionValue(['beta', 'alpha'], ['alpha', 'beta', 'gamma'], nodegroups),
    ).toBe('group-a');
  });

  it('uses All when all available nodes are selected', () => {
    expect(getNodeGroupSelectionValue(['beta', 'alpha'], ['alpha', 'beta'], nodegroups)).toBe(
      'All',
    );
    expect(getNodeGroupSelectionValue(['All'], ['alpha', 'beta'], nodegroups)).toBe('All');
  });

  it('returns no match for partial selections and empty groups', () => {
    expect(getNodeGroupSelectionValue(['alpha'], ['alpha', 'beta'], nodegroups)).toBeNull();
    expect(getNodeGroupSelectionValue([], ['alpha'], nodegroups)).toBeNull();
  });

  it('does not guess when multiple groups have the same membership', () => {
    const duplicateMemberships = [
      { name: 'first', nodes: ['alpha'] },
      { name: 'second', nodes: ['alpha'] },
    ];

    expect(
      getNodeGroupSelectionValue(['alpha'], ['alpha', 'beta'], duplicateMemberships),
    ).toBeNull();
  });
});
