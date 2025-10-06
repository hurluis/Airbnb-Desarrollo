(() => {
  const normalizeBase = (value) => {
    if (!value) {
      return '';
    }
    return value.endsWith('/') ? value.slice(0, -1) : value;
  };

  const candidateBases = [];
  const metaBase = document.querySelector('meta[name="api-base-url"]');
  if (metaBase?.content) {
    candidateBases.push(normalizeBase(metaBase.content));
  }

  candidateBases.push('/api');
  candidateBases.push('');

  let resolvedBase = null;

  const fetchWithBase = async (base, path, options) => {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return fetch(`${base}${cleanPath}`, options);
  };

  const tryCandidates = async (path, options) => {
    const basesToTry = resolvedBase !== null
      ? [resolvedBase, ...candidateBases.filter((base) => base !== resolvedBase)]
      : candidateBases;

    let lastError;

    for (const base of basesToTry) {
      try {
        const response = await fetchWithBase(base, path, options);

        if (response.status === 404 && base !== '') {
          // Puede que estemos golpeando la ruta equivocada (por ejemplo /api en local)
          // Continuamos probando con la siguiente opción.
          continue;
        }

        resolvedBase = base;
        return response;
      } catch (error) {
        lastError = error;
      }
    }

    if (lastError) {
      throw lastError;
    }

    return fetchWithBase('', path, options);
  };

  window.apiFetch = async (path, options = {}) => {
    return tryCandidates(path, options);
  };

  Object.defineProperty(window, 'API_BASE_URL', {
    get() {
      return resolvedBase ?? candidateBases[0] ?? '';
    }
  });
})();
