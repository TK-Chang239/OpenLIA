import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useDirtyForm } from '../useDirtyForm';

describe('useDirtyForm', () => {
  it('is not dirty when values match initial', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1, b: 'x' }));
    expect(result.current.isDirty).toBe(false);
  });

  it('becomes dirty when a field changes', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1, b: 'x' }));
    act(() => result.current.setField('a', 2));
    expect(result.current.isDirty).toBe(true);
    expect(result.current.values.a).toBe(2);
  });

  it('reset() restores initial values and clears dirty', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1 }));
    act(() => result.current.setField('a', 9));
    act(() => result.current.reset());
    expect(result.current.values.a).toBe(1);
    expect(result.current.isDirty).toBe(false);
  });

  it('markSaved() adopts current values as the new baseline', () => {
    const { result } = renderHook(() => useDirtyForm({ a: 1 }));
    act(() => result.current.setField('a', 2));
    act(() => result.current.markSaved());
    expect(result.current.isDirty).toBe(false);
    expect(result.current.values.a).toBe(2);
  });
});
