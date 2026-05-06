import { request } from "./_request";

export interface DepartmentModelPref {
  department_id: string;
  model_id: string | null;
  effective_model_id: string | null;
}

export const getDepartmentModelPref = (departmentSlug: string) =>
  request<DepartmentModelPref>(`/api/departments/${departmentSlug}/model-pref`);

export const setDepartmentModelPref = (departmentSlug: string, modelId: string) =>
  request<DepartmentModelPref>(`/api/departments/${departmentSlug}/model-pref`, {
    method: "PUT",
    body: JSON.stringify({ model_id: modelId }),
  });

export const clearDepartmentModelPref = (departmentSlug: string) =>
  request<void>(`/api/departments/${departmentSlug}/model-pref`, {
    method: "DELETE",
  });
