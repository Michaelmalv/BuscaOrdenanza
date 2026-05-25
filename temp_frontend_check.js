
    const uploadForm = document.getElementById('uploadForm');
    const searchForm = document.getElementById('searchForm');
    const uploadButton = document.getElementById('uploadButton');
    const resultBox = document.getElementById('resultBox');
    const searchResults = document.getElementById('searchResults');
    const docList = document.getElementById('docList');
    const markdownViewer = document.getElementById('markdownViewer');
    const fragmentList = document.getElementById('fragmentList');
    const fragmentQuery = document.getElementById('fragmentQuery');
    const fragmentSearch = document.getElementById('fragmentSearch');
    const fragmentClear = document.getElementById('fragmentClear');
    const fragmentPrev = document.getElementById('fragmentPrev');
    const fragmentNext = document.getElementById('fragmentNext');
    const fragmentPageInfo = document.getElementById('fragmentPageInfo');
    const openRawMarkdown = document.getElementById('openRawMarkdown');
    const refreshDocs = document.getElementById('refreshDocs');
    const uploadStatus = document.getElementById('uploadStatus');

    let activeDocumentId = null;
    let activeFragmentId = null;
    let activeSearchQuery = '';
    let currentFragmentPage = 1;
    let currentFragmentPageSize = 5;
    let currentFragmentTotalPages = 1;
    let currentFragmentQuery = '';

    function escapeHtml(value) {
      return value
        .toString()
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function highlightText(text, query) {
      const escaped = escapeHtml(text || '');
      const terms = (query || '').trim().split(/\s+/).filter(Boolean);
      if (!terms.length) return escaped;

      let highlighted = escaped;
      for (const term of terms) {
        const safeTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const pattern = new RegExp(`(${safeTerm})`, 'gi');
        highlighted = highlighted.replace(pattern, '<mark>$1</mark>');
      }
      return highlighted;
    }

    function renderMarkdown(markdown) {
      markdownViewer.innerHTML = '<div style="white-space: pre-wrap; word-break: break-word; line-height: 1.7">' + highlightText(markdown, activeSearchQuery) + '</div>';
    }

    function renderFragmentPreview(fragment) {
      markdownViewer.innerHTML = `
        <div style="white-space: pre-wrap; word-break: break-word; line-height: 1.7">
          <div class="muted" style="margin-bottom: 12px">Fragmento ${escapeHtml(fragment.chunk_number)} · ${escapeHtml(fragment.section)}</div>
          ${highlightText(fragment.content_markdown, activeSearchQuery)}
        </div>
      `;
    }

    async function loadDocuments() {
      docList.innerHTML = '<p class="muted">Cargando PDFs subidos...</p>';
      const response = await fetch(`/api/pdfs?t=${Date.now()}`, { cache: 'no-store' });
      const documents = await response.json();

      if (!documents.length) {
        docList.innerHTML = '<p class="muted">Todavía no hay PDFs subidos.</p>';
        return;
      }

      docList.innerHTML = '';
      documents.forEach((document) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'doc-item' + (document.id === activeDocumentId ? ' active' : '');
        button.innerHTML = `<strong>${escapeHtml(document.title)}</strong><br><span class="muted">${escapeHtml(document.original_filename || document.filename)}</span><br><span class="fragment-meta">${document.converted ? 'Markdown generado' : 'Pendiente de conversión'}</span>`;
        button.addEventListener('click', () => loadMarkdown(document.id));
        docList.appendChild(button);
      });
    }

    async function loadFragments(documentId, page = 1) {
      currentFragmentPage = page;
      fragmentList.innerHTML = '<p class="muted">Cargando fragmentos...</p>';
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(currentFragmentPageSize),
      });
      if (currentFragmentQuery.trim()) {
        params.set('q', currentFragmentQuery.trim());
      }

      const response = await fetch(`/api/documentos/${encodeURIComponent(documentId)}/fragmentos?${params.toString()}&t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) {
        fragmentList.innerHTML = '<p class="muted">No se pudieron cargar los fragmentos.</p>';
        return;
      }

      const payload = await response.json();
      const fragments = payload.items || [];
      currentFragmentTotalPages = payload.total_pages || 1;

      fragmentPageInfo.textContent = payload.total
        ? `Mostrando ${fragments.length} fragmentos de ${payload.total} · página ${payload.page} de ${payload.total_pages}`
        : 'No hay fragmentos para mostrar.';

      if (!fragments.length) {
        fragmentList.innerHTML = '<p class="muted">Este documento no tiene fragmentos disponibles.</p>';
        return;
      }

      fragmentList.innerHTML = '';
      fragments.forEach((fragment) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'fragment-item' + (fragment.id === activeFragmentId ? ' active' : '');
        button.innerHTML = `
          <strong>Fragmento ${escapeHtml(fragment.chunk_number)}</strong><br>
          <span class="muted">${escapeHtml(fragment.section)}</span>
          <span class="fragment-meta">Relevancia: ${escapeHtml(fragment.score || 0)} · ${escapeHtml((fragment.content_text || '').slice(0, 160))}${fragment.content_text && fragment.content_text.length > 160 ? '...' : ''}</span>
        `;
        button.addEventListener('click', () => {
          activeFragmentId = fragment.id;
          renderFragmentPreview(fragment);
          loadFragments(documentId, currentFragmentPage);
        });
        fragmentList.appendChild(button);
      });

      fragmentPrev.disabled = currentFragmentPage <= 1;
      fragmentNext.disabled = currentFragmentPage >= currentFragmentTotalPages;
    }

    async function loadMarkdown(documentId, fragmentHint = null) {
      activeDocumentId = documentId;
      activeFragmentId = fragmentHint ? fragmentHint.id : null;
      openRawMarkdown.disabled = false;
      markdownViewer.textContent = 'Cargando Markdown...';
      const response = await fetch(`/api/documentos/${encodeURIComponent(documentId)}/markdown?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) {
        markdownViewer.textContent = 'No se pudo cargar el documento.';
        return;
      }
      const data = await response.json();
      renderMarkdown(data.markdown);
      if (fragmentHint && fragmentHint.chunk_number) {
        currentFragmentQuery = '';
        fragmentQuery.value = '';
      }

      const targetPage = fragmentHint && fragmentHint.chunk_number
        ? Math.max(1, Math.ceil(fragmentHint.chunk_number / currentFragmentPageSize))
        : 1;

      await loadFragments(documentId, targetPage);
      if (fragmentHint) {
        renderFragmentPreview(fragmentHint);
      }
      await loadDocuments();
    }

    async function uploadSelectedFiles() {
      const files = document.getElementById('files').files;
      if (!files.length) {
        resultBox.textContent = 'Selecciona al menos un archivo.';
        uploadStatus.textContent = 'Selecciona al menos un archivo.';
        return;
      }

      const formData = new FormData();
      for (const file of files) formData.append('files', file);

      resultBox.textContent = 'Procesando...';
      uploadStatus.textContent = 'Subiendo archivos...';
      try {
        const response = await fetch('/api/subida-archivos', {
          method: 'POST',
          body: formData,
        });
        const rawText = await response.text();
        let data = null;
        try {
          data = JSON.parse(rawText);
        } catch {
          data = { message: rawText };
        }

        if (!response.ok) {
          const detail = data?.detail || data?.message || `Error HTTP ${response.status}`;
          resultBox.textContent = JSON.stringify({ ok: false, detail }, null, 2);
          uploadStatus.textContent = `No se pudieron cargar los archivos: ${detail}`;
          return;
        }

        resultBox.textContent = JSON.stringify(data, null, 2);
        const uploaded = (data.files || []).map((item) => item.source_file).filter(Boolean);
        uploadStatus.textContent = uploaded.length
          ? `Carga completada: ${uploaded.join(', ')}`
          : 'Carga completada.';
        await loadDocuments();
      } catch (error) {
        resultBox.textContent = 'Error: ' + error;
        uploadStatus.textContent = 'No se pudo completar la carga.';
      }
    }

    uploadButton.addEventListener('click', uploadSelectedFiles);

    searchForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const query = document.getElementById('query').value.trim();
      if (!query) {
        searchResults.innerHTML = '<p class="muted">Escribe algo para buscar.</p>';
        return;
      }

      searchResults.innerHTML = '<p class="muted">Buscando...</p>';
      try {
        const response = await fetch('/api/buscar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, limit: 10 }),
        });
        const data = await response.json();
        const hits = data.results?.hits || [];
        activeSearchQuery = query;
        if (activeDocumentId) {
          const markdownResponse = await fetch(`/api/documentos/${encodeURIComponent(activeDocumentId)}/markdown`);
          if (markdownResponse.ok) {
            const markdownData = await markdownResponse.json();
            renderMarkdown(markdownData.markdown);
          }
        }

        if (!hits.length) {
          searchResults.innerHTML = '<p class="muted">Sin resultados.</p>';
          return;
        }

        searchResults.innerHTML = '';
        hits.forEach((hit) => {
          const item = document.createElement('div');
          item.className = 'result-item';
          item.innerHTML = `
            <h4>${escapeHtml(hit.title || hit.document_id || 'Documento')}</h4>
            <p class="muted">Sección: ${escapeHtml(hit.section || 'Sin sección')} | Archivo: ${escapeHtml(hit.source || '')}</p>
            <p>${highlightText((hit.content_text || '').slice(0, 400), query)}</p>
            <button type="button" class="secondary" style="margin-top: 10px;" data-document="${escapeHtml(hit.document_id || '')}">Ver fragmento exacto</button>
          `;
          const button = item.querySelector('button[data-document]');
          if (button) {
            button.addEventListener('click', () => loadMarkdown(hit.document_id, hit));
          }
          searchResults.appendChild(item);
        });
      } catch (error) {
        searchResults.innerHTML = '<p class="muted">Error: ' + error + '</p>';
      }
    });

    fragmentSearch.addEventListener('click', async () => {
      if (!activeDocumentId) {
        fragmentPageInfo.textContent = 'Selecciona primero un documento.';
        return;
      }
      currentFragmentQuery = fragmentQuery.value.trim();
      activeFragmentId = null;
      await loadFragments(activeDocumentId, 1);
    });

    fragmentClear.addEventListener('click', async () => {
      if (!activeDocumentId) {
        return;
      }
      fragmentQuery.value = '';
      currentFragmentQuery = '';
      activeFragmentId = null;
      await loadFragments(activeDocumentId, 1);
    });

    fragmentPrev.addEventListener('click', async () => {
      if (!activeDocumentId || currentFragmentPage <= 1) {
        return;
      }
      await loadFragments(activeDocumentId, currentFragmentPage - 1);
    });

    fragmentNext.addEventListener('click', async () => {
      if (!activeDocumentId || currentFragmentPage >= currentFragmentTotalPages) {
        return;
      }
      await loadFragments(activeDocumentId, currentFragmentPage + 1);
    });

    openRawMarkdown.addEventListener('click', () => {
      if (!activeDocumentId) {
        return;
      }
      window.open(`/api/documentos/${encodeURIComponent(activeDocumentId)}/markdown-raw`, '_blank', 'noopener,noreferrer');
    });

    refreshDocs.addEventListener('click', loadDocuments);
    loadDocuments();
  