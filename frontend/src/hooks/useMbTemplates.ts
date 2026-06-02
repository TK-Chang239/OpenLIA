import { useCallback, useEffect, useState } from "react";

import {
  listMbTemplates,
  createMbTemplate,
  uploadMbTemplate,
  deleteMbTemplate,
  type MbTemplate,
  type MbTemplateCreateIn,
} from "../api/morning-briefing";

export function useMbTemplates() {
  const [templates, setTemplates] = useState<MbTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { templates: rows } = await listMbTemplates();
      setTemplates(rows);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** Create from markdown string (JSON body). */
  const create = useCallback(
    async (payload: MbTemplateCreateIn) => {
      const created = await createMbTemplate(payload);
      await refresh();
      return created;
    },
    [refresh],
  );

  /** Create from a document file (multipart upload). */
  const upload = useCallback(
    async (name: string, file: File) => {
      const created = await uploadMbTemplate(name, file);
      await refresh();
      return created;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteMbTemplate(id);
      await refresh();
    },
    [refresh],
  );

  return { templates, loading, error, refresh, create, upload, remove };
}
