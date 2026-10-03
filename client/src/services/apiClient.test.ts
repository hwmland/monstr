import type { AxiosResponse } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient, fetchNodeGroups } from './apiClient';

const responseWithData = (data: unknown): AxiosResponse<unknown> =>
  ({ data }) as AxiosResponse<unknown>;

describe('fetchNodeGroups', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads group names, flattened node memberships, and optional icons', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(
      responseWithData([
        { name: 'group-a', nodes: ['alpha', 'beta'], icon: 'mdi:home' },
        { name: 'empty', nodes: [], icon: null },
        { name: 'legacy', nodes: ['gamma'] },
      ]),
    );

    await expect(fetchNodeGroups()).resolves.toEqual([
      { name: 'group-a', nodes: ['alpha', 'beta'], icon: 'mdi:home' },
      { name: 'empty', nodes: [] },
      { name: 'legacy', nodes: ['gamma'] },
    ]);
    expect(get).toHaveBeenCalledWith('/nodegroups');
  });

  it('reports malformed group response data', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(
      responseWithData([{ name: 'group-a', nodes: 'alpha' }]),
    );

    await expect(fetchNodeGroups()).rejects.toThrow('Unexpected nodegroup entry format');
  });

  it('reports malformed group icon identifiers', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(
      responseWithData([{ name: 'group-a', nodes: ['alpha'], icon: 'lucide:home' }]),
    );

    await expect(fetchNodeGroups()).rejects.toThrow('Unexpected nodegroup icon format');
  });
});
