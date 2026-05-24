let currentPage = 1;
let filters = { category: '', source: '', status: '', start_date: '', end_date: '' };
let lastLoadedItems = [];
let currentSearchItem = null;

async function loadStats() {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stats').textContent = `共 ${data.total} 条新闻`;

    const catSelect = document.getElementById('categoryFilter');
    const srcSelect = document.getElementById('sourceFilter');

    Object.keys(data.categories).forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.text = `${cat} (${data.categories[cat]})`;
        catSelect.appendChild(opt);
    });

    Object.keys(data.sources).forEach(src => {
        const opt = document.createElement('option');
        opt.value = src;
        opt.text = `${src} (${data.sources[src]})`;
        srcSelect.appendChild(opt);
    });
}

async function loadNews() {
    const params = new URLSearchParams({ page: currentPage, page_size: 12 });
    if (filters.category) params.append('category', filters.category);
    if (filters.source) params.append('source', filters.source);
    if (filters.status) params.append('status', filters.status);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    const res = await fetch(`/api/news?${params}`);
    const data = await res.json();

    lastLoadedItems = data.items;
    renderGrid(data.items);
    renderPagination(data.total, data.page_size);
}

function renderGrid(items) {
    const grid = document.getElementById('newsGrid');
    grid.innerHTML = items.map(item => `
        <div class="news-card" onclick="showModal(${item.id})">
            <h3>${escapeHtml(item.title)}</h3>
            <div class="meta">
                <span>${item.created_at ? item.created_at.slice(0, 16) : item.time}</span>
                <span>${escapeHtml(item.source)}</span>
            </div>
            ${item.raw_status ? `<span class="status-tag status-${item.raw_status}">${escapeHtml(item.raw_status)}</span>` : ''}
            ${item.category ? `<span class="category-tag">${escapeHtml(item.category)}</span>` : ''}
        </div>
    `).join('');
}

function renderPagination(total, pageSize) {
    const totalPages = Math.ceil(total / pageSize);
    const pag = document.getElementById('pagination');
    let html = '';

    if (currentPage > 1) html += '<button onclick="goToPage(1)">«</button>';
    if (currentPage > 1) html += `<button onclick="goToPage(${currentPage - 1})">‹</button>`;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
            html += `<button onclick="goToPage(${i})" class="${i === currentPage ? 'active' : ''}">${i}</button>`;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
            html += '<span>...</span>';
        }
    }

    if (currentPage < totalPages) html += `<button onclick="goToPage(${currentPage + 1})">›</button>`;
    if (currentPage < totalPages) html += `<button onclick="goToPage(${totalPages})">»</button>`;

    pag.innerHTML = html;
}

async function showModal(id) {
    try {
        const item = lastLoadedItems.find(i => i.id === id);
        if (!item) return;

        document.getElementById('modalTitle').textContent = item.title;
        document.getElementById('modalTime').textContent = item.time;
        document.getElementById('modalSource').textContent = item.source;
        document.getElementById('modalStatus').textContent = item.raw_status ? `状态: ${item.raw_status}` : '';
        document.getElementById('modalCategory').textContent = item.category || '未分类';
        const url = item.url && item.url.startsWith('http') ? item.url : '#';
        document.getElementById('modalUrl').href = escapeHtml(url);
        document.getElementById('modalContent').textContent = item.content || '无内容';
        document.getElementById('modalReport').textContent = item.analysis_report || '无分析报告';

        document.getElementById('modal').classList.add('show');
    } catch (e) {
        console.error('Failed to load modal:', e);
    }
}

function closeModal() {
    document.getElementById('modal').classList.remove('show');
}

function goToPage(page) {
    currentPage = page;
    loadNews();
}

function resetFilters() {
    filters = { category: '', source: '', status: '', start_date: '', end_date: '' };
    document.getElementById('categoryFilter').value = '';
    document.getElementById('sourceFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';
    currentPage = 1;
    loadNews();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

document.getElementById('categoryFilter').addEventListener('change', e => {
    filters.category = e.target.value;
    currentPage = 1;
    loadNews();
});

document.getElementById('sourceFilter').addEventListener('change', e => {
    filters.source = e.target.value;
    currentPage = 1;
    loadNews();
});

document.getElementById('startDate').addEventListener('change', e => {
    filters.start_date = e.target.value;
    currentPage = 1;
    loadNews();
});

document.getElementById('endDate').addEventListener('change', e => {
    filters.end_date = e.target.value;
    currentPage = 1;
    loadNews();
});

document.getElementById('statusFilter').addEventListener('change', e => {
    filters.status = e.target.value;
    currentPage = 1;
    loadNews();
});

document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
});

async function searchById() {
    const id = document.getElementById('searchId').value.trim();
    if (!id) return;

    const res = await fetch(`/api/news?id=${encodeURIComponent(id)}`);
    if (!res.ok) {
        alert('查找失败');
        return;
    }
    const data = await res.json();
    if (data.items && data.items.length > 0) {
        currentSearchItem = data.items[0];
        showModalDirect(data.items[0]);
    } else {
        alert('未找到该ID对应的新闻');
    }
}

function showModalDirect(item) {
    try {
        document.getElementById('modalTitle').textContent = item.title;
        document.getElementById('modalTime').textContent = item.created_at ? item.created_at.slice(0, 16) : item.time;
        document.getElementById('modalSource').textContent = item.source;
        document.getElementById('modalStatus').textContent = item.raw_status ? `状态: ${item.raw_status}` : '';
        document.getElementById('modalCategory').textContent = item.category || '未分类';
        const url = item.url && item.url.startsWith('http') ? item.url : '#';
        document.getElementById('modalUrl').href = escapeHtml(url);
        document.getElementById('modalContent').textContent = item.content || '无内容';
        document.getElementById('modalReport').textContent = item.analysis_report || '无分析报告';

        document.getElementById('modal').classList.add('show');
    } catch (e) {
        console.error('Failed to load modal:', e);
    }
}

loadStats();
loadNews();