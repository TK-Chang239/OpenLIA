import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getRegisteredDepartmentIds } from '../../../api/settings';
import { UserOverridesPanel } from '../models/UserOverridesPanel';
import { ProviderCatalog } from '../models/ProviderCatalog';
import { SystemRolesPanel } from '../models/SystemRolesPanel';

interface Props {
  userRole: 'admin' | 'user';
}

export function ModelsSection({ userRole }: Props): JSX.Element {
  const { t } = useTranslation();
  const [departments, setDepartments] = useState<string[]>([]);

  useEffect(() => {
    getRegisteredDepartmentIds().then(setDepartments);
  }, []);

  const isAdmin = userRole === 'admin';
  return (
    <div className="max-w-4xl space-y-8">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">{t('settings.models.title')}</h1>
        <p className="mt-1 text-sm text-text-secondary">
          {t('settings.models.subtitle')}
        </p>
      </header>
      <UserOverridesPanel departments={departments} />
      <section className="space-y-3">
        <header>
          <h2 className="text-lg font-semibold text-text-primary">
            {t('settings.models.catalog_title')}
          </h2>
          <p className="text-sm text-text-secondary">
            {isAdmin
              ? t('settings.models.catalog_description_admin')
              : t('settings.models.catalog_description_user')}
          </p>
        </header>
        <ProviderCatalog departments={departments} isAdmin={isAdmin} />
      </section>
      {isAdmin ? <SystemRolesPanel /> : null}
    </div>
  );
}
