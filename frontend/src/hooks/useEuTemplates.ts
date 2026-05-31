import { useCallback, useEffect, useState } from "react";
import {
  fetchTemplates, uploadTemplate, deleteTemplate, type EuTemplate,
} from "../api/earnings-update";

export function useEuTemplates() {
  const [templates, setTemplates] = useState<EuTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { templates: rows } = await fetchTemplates();
      setTemplates(rows);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const upload = useCallback(async (name: string, source_markdown: string) => {
    const created = await uploadTemplate({ name, source_markdown });
    await refresh();
    return created;
  }, [refresh]);

  const remove = useCallback(async (id: string) => {
    await deleteTemplate(id);
    await refresh();
  }, [refresh]);

  return { templates, loading, error, refresh, upload, remove };
}
