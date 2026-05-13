/**
 * Typed client for slot-default CRUD. Wraps `/settings/admin/llm/slot-defaults/*`.
 */
import { request } from './_request';

export type SlotKind = 'department' | 'system_role';

export interface SlotDefault {
  slot_kind: SlotKind;
  slot_id: string;
  model_id: string;
}

export const listSlotDefaults = () =>
  request<{ defaults: SlotDefault[] }>('/api/settings/admin/llm/slot-defaults');

export const setSlotDefault = (slot_kind: SlotKind, slot_id: string, model_id: string) =>
  request<SlotDefault>(`/api/settings/admin/llm/slot-defaults/${slot_kind}/${slot_id}`, {
    method: 'PUT',
    body: JSON.stringify({ model_id }),
  });

export const deleteSlotDefault = (slot_kind: SlotKind, slot_id: string) =>
  request<void>(`/api/settings/admin/llm/slot-defaults/${slot_kind}/${slot_id}`, {
    method: 'DELETE',
  });
