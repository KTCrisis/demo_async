// Global state
let currentEnv = '';
let authHeader = '';
let bulkPreviewSubjects = [];
let currentSpec = null;
let currentSpecFilename = null;

// API Base URL
const API_BASE = window.location.origin;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initTabNavigation();
    initEventListeners();
    initAsyncAPIListeners();
    loadEnvironments();
});

function initAuth() {
    // Prompt for credentials if not in localStorage
    let username = localStorage.getItem('username');
    let password = localStorage.getItem('password');

    if (!username || !password) {
        username = prompt('Username:', 'admin');
        password = prompt('Password:', 'admin123');
        
        if (username && password) {
            localStorage.setItem('username', username);
            localStorage.setItem('password', password);
        }
    }

    authHeader = 'Basic ' + btoa(username + ':' + password);
    document.getElementById('userInfo').textContent = `👤 ${username}`;
}

function initTabNavigation() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabName);
    });

    // If switching to AsyncAPI tab and no topics loaded yet
    if (tabName === 'asyncapi' && currentEnv) {
        const topicsGrid = document.getElementById('topicsGrid');
        if (!topicsGrid.children.length) {
            loadTopics();
        }
    }
}

function initEventListeners() {
    // Environment selector
    document.getElementById('envSelector').addEventListener('change', (e) => {
        currentEnv = e.target.value;
        showToast('Environment changed', `Now using: ${currentEnv}`, 'info');
        
        // Clear AsyncAPI views when environment changes
        document.getElementById('topicsGrid').innerHTML = '';
        showAsyncAPIView('topics');
    });

    // Dashboard
    document.getElementById('runHealthCheck').addEventListener('click', runHealthCheck);

    // Schemas
    document.getElementById('loadSchemas').addEventListener('click', loadSchemas);

    // Bulk operations
    document.getElementById('purgeSoftDeleted').addEventListener('click', purgeSoftDeleted);
    document.getElementById('previewBulkDelete').addEventListener('click', previewBulkDelete);
    document.getElementById('executeBulkDelete').addEventListener('click', executeBulkDelete);

    // History
    document.getElementById('refreshHistory').addEventListener('click', loadHistory);

    // Modal
    document.getElementById('modalCancel').addEventListener('click', closeModal);
}

function initAsyncAPIListeners() {
    // Topics view
    document.getElementById('loadTopics').addEventListener('click', loadTopics);
    document.getElementById('viewGeneratedSpecs').addEventListener('click', () => {
        showAsyncAPIView('specsList');
        loadGeneratedSpecs();
    });

    // Spec viewer
    document.getElementById('backToTopics').addEventListener('click', () => {
        showAsyncAPIView('topics');
    });
    document.getElementById('downloadSpec').addEventListener('click', downloadCurrentSpec);
    document.getElementById('copySpec').addEventListener('click', copySpecToClipboard);
    document.getElementById('openInStudio').addEventListener('click', openInAsyncAPIStudio);

    // Specs list view
    document.getElementById('backToTopicsFromList').addEventListener('click', () => {
        showAsyncAPIView('topics');
    });
    document.getElementById('refreshSpecsList').addEventListener('click', loadGeneratedSpecs);

    // Viewer tabs
    document.querySelectorAll('.viewer-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.viewerTab;
            switchViewerTab(tab);
        });
    });
}

// ============================================================================
// API Functions
// ============================================================================

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Authorization': authHeader,
            'Content-Type': 'application/json'
        }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        
        if (response.status === 401) {
            localStorage.removeItem('username');
            localStorage.removeItem('password');
            showToast('Authentication Failed', 'Please refresh and login again', 'error');
            throw new Error('Authentication failed');
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'API request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ============================================================================
// Environment Functions
// ============================================================================

async function loadEnvironments() {
    try {
        const data = await apiCall('/api/environments');
        const selector = document.getElementById('envSelector');
        
        selector.innerHTML = '<option value="">Select Environment</option>';
        
        data.environments.forEach(env => {
            const option = document.createElement('option');
            option.value = env.name;
            option.textContent = `${env.name.toUpperCase()} ${env.configured ? '✔' : '✗'}`;
            option.disabled = !env.configured;
            selector.appendChild(option);
        });
    } catch (error) {
        showToast('Error', 'Failed to load environments', 'error');
    }
}

// ============================================================================
// Health Check Functions
// ============================================================================

async function runHealthCheck() {
    if (!currentEnv) {
        showToast('Error', 'Please select an environment first', 'warning');
        return;
    }

    const resultsDiv = document.getElementById('healthCheckResults');
    const loadingDiv = document.getElementById('healthCheckLoading');
    const statsDiv = document.getElementById('quickStats');

    resultsDiv.innerHTML = '';
    loadingDiv.style.display = 'flex';

    try {
        const data = await apiCall(`/api/check/${currentEnv}`, 'POST');
        
        loadingDiv.style.display = 'none';
        
        // Display checks
        Object.entries(data.checks).forEach(([checkName, result]) => {
            const statusClass = result.status.toLowerCase();
            const icon = getStatusIcon(result.status);
            
            const checkDiv = document.createElement('div');
            checkDiv.className = `health-check-item ${statusClass}`;
            checkDiv.innerHTML = `
                <div class="health-icon">${icon}</div>
                <div class="health-info">
                    <div class="health-title">${checkName.replace(/_/g, ' ')}</div>
                    <div class="health-message">${result.message}</div>
                </div>
            `;
            resultsDiv.appendChild(checkDiv);
        });

        // Update stats
        updateQuickStats(data);
        
        const statusClass = data.summary.status === 'OK' ? 'success' : 
                           data.summary.status === 'WARNING' ? 'warning' : 'error';
        showToast('Health Check Complete', `Status: ${data.summary.status}`, statusClass);
        
    } catch (error) {
        loadingDiv.style.display = 'none';
        showToast('Error', error.message, 'error');
    }
}

function updateQuickStats(healthData) {
    const stats = document.getElementById('quickStats').children;
    
    const subjectCount = healthData.checks.subject_count?.count || 0;
    const softDeleted = healthData.checks.soft_deleted?.count || 0;
    const versionExplosions = healthData.checks.version_explosion?.explosions?.length || 0;
    const totalIssues = healthData.summary.total_issues || 0;
    
    stats[0].querySelector('.stat-value').textContent = subjectCount;
    stats[1].querySelector('.stat-value').textContent = softDeleted;
    stats[2].querySelector('.stat-value').textContent = versionExplosions;
    stats[3].querySelector('.stat-value').textContent = totalIssues;
}

function getStatusIcon(status) {
    const icons = {
        'OK': '✅',
        'WARNING': '⚠️',
        'CRITICAL': '🚨',
        'ERROR': '❌'
    };
    return icons[status] || '❓';
}

// ============================================================================
// Schema Management Functions
// ============================================================================

async function loadSchemas() {
    if (!currentEnv) {
        showToast('Error', 'Please select an environment first', 'warning');
        return;
    }

    const tableDiv = document.getElementById('schemasTable');
    const loadingDiv = document.getElementById('schemasLoading');
    
    const pattern = document.getElementById('schemaSearchPattern').value;
    const minVersions = document.getElementById('minVersionsFilter').value;
    
    let url = `/api/schemas/${currentEnv}`;
    const params = new URLSearchParams();
    if (pattern) params.append('pattern', pattern);
    if (minVersions) params.append('min_versions', minVersions);
    if (params.toString()) url += '?' + params.toString();

    tableDiv.innerHTML = '';
    loadingDiv.style.display = 'flex';

    try {
        const data = await apiCall(url);
        
        loadingDiv.style.display = 'none';
        
        if (data.subjects.length === 0) {
            tableDiv.innerHTML = '<p class="text-muted">No schemas found</p>';
            return;
        }

        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Subject</th>
                    <th>Versions</th>
                    <th>Latest Version</th>
                    <th>Size (KB)</th>
                    <th>Type</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${data.subjects.map(schema => `
                    <tr>
                        <td>${schema.subject}</td>
                        <td>${schema.version_count}</td>
                        <td>${schema.latest_version || '-'}</td>
                        <td>${schema.size_kb}</td>
                        <td>${schema.schema_type || 'AVRO'}</td>
                        <td>
                            <button class="btn btn-secondary action-btn" onclick="softDeleteSchema('${schema.subject}')">
                                Soft Delete
                            </button>
                            <button class="btn btn-danger action-btn" onclick="hardDeleteSchema('${schema.subject}')">
                                Hard Delete
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        
        tableDiv.appendChild(table);
        
        showToast('Success', `Loaded ${data.subjects.length} schemas`, 'success');
        
    } catch (error) {
        loadingDiv.style.display = 'none';
        showToast('Error', error.message, 'error');
    }
}

async function softDeleteSchema(subject) {
    if (!confirm(`Soft delete schema: ${subject}?\n\nThis can be reversed.`)) {
        return;
    }

    try {
        const result = await apiCall(`/api/schemas/${currentEnv}/${subject}/soft-delete`, 'POST');
        
        if (result.success) {
            showToast('Success', `Soft deleted: ${subject}`, 'success');
            loadSchemas(); // Reload list
        } else {
            showToast('Error', result.error, 'error');
        }
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

async function hardDeleteSchema(subject) {
    const confirmed = await showConfirmModal(
        'Permanent Deletion',
        `Are you sure you want to PERMANENTLY delete: ${subject}?\n\nThis action CANNOT be undone!`
    );
    
    if (!confirmed) return;

    try {
        const result = await apiCall(
            `/api/schemas/${currentEnv}/${subject}/hard-delete`, 
            'POST',
            { confirm: true }
        );
        
        if (result.success) {
            showToast('Success', `Permanently deleted: ${subject}`, 'success');
            loadSchemas(); // Reload list
        } else {
            showToast('Error', result.error, 'error');
        }
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

// ============================================================================
// Bulk Operations Functions
// ============================================================================

async function purgeSoftDeleted() {
    if (!currentEnv) {
        showToast('Error', 'Please select an environment first', 'warning');
        return;
    }

    const confirmed = await showConfirmModal(
        'Purge Soft-Deleted Schemas',
        'This will PERMANENTLY delete ALL soft-deleted schemas. This action CANNOT be undone!\n\nAre you sure?'
    );
    
    if (!confirmed) return;

    try {
        const result = await apiCall(`/api/purge-soft-deleted/${currentEnv}`, 'POST', { confirm: true });
        
        if (result.success) {
            const count = result.success_count || result.count || 0;
            showToast('Success', `Purged ${count} soft-deleted schemas`, 'success');
        } else {
            showToast('Error', result.error || 'Purge failed', 'error');
        }
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

async function previewBulkDelete() {
    if (!currentEnv) {
        showToast('Error', 'Please select an environment first', 'warning');
        return;
    }

    const minVersions = document.getElementById('bulkMinVersions').value;
    const pattern = document.getElementById('bulkPattern').value;

    if (!minVersions && !pattern) {
        showToast('Warning', 'Please specify at least one filter', 'warning');
        return;
    }

    try {
        let url = `/api/schemas/${currentEnv}`;
        const params = new URLSearchParams();
        if (pattern) params.append('pattern', pattern);
        if (minVersions) params.append('min_versions', minVersions);
        url += '?' + params.toString();

        const data = await apiCall(url);
        bulkPreviewSubjects = data.subjects.map(s => s.subject);
        
        const previewDiv = document.getElementById('bulkPreview');
        const contentDiv = document.getElementById('bulkPreviewContent');
        
        if (bulkPreviewSubjects.length === 0) {
            contentDiv.innerHTML = '<p class="text-muted">No schemas match the filters</p>';
            previewDiv.style.display = 'block';
            document.getElementById('executeBulkDelete').disabled = true;
            return;
        }

        contentDiv.innerHTML = `
            <p><strong>${bulkPreviewSubjects.length} schemas</strong> will be affected:</p>
            <div class="preview-list">
                ${bulkPreviewSubjects.map(s => `<div class="preview-item">${s}</div>`).join('')}
            </div>
        `;
        
        previewDiv.style.display = 'block';
        document.getElementById('executeBulkDelete').disabled = false;
        
        showToast('Preview Ready', `${bulkPreviewSubjects.length} schemas match filters`, 'info');
        
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

async function executeBulkDelete() {
    if (bulkPreviewSubjects.length === 0) {
        showToast('Error', 'No schemas selected', 'warning');
        return;
    }

    const deleteType = document.getElementById('bulkDeleteType').value;
    
    const confirmed = await showConfirmModal(
        `Bulk ${deleteType === 'hard' ? 'Hard' : 'Soft'} Delete`,
        `Are you sure you want to ${deleteType} delete ${bulkPreviewSubjects.length} schemas?${
            deleteType === 'hard' ? '\n\nThis action CANNOT be undone!' : ''
        }`
    );
    
    if (!confirmed) return;

    try {
        const result = await apiCall(`/api/bulk-delete/${currentEnv}`, 'POST', {
            subjects: bulkPreviewSubjects,
            type: deleteType,
            confirm: true
        });
        
        showToast(
            'Bulk Delete Complete', 
            `Success: ${result.success_count}, Failed: ${result.failure_count}`,
            result.failure_count > 0 ? 'warning' : 'success'
        );
        
        // Reset
        document.getElementById('bulkPreview').style.display = 'none';
        document.getElementById('executeBulkDelete').disabled = true;
        bulkPreviewSubjects = [];
        
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

// ============================================================================
// AsyncAPI Functions
// ============================================================================

function showAsyncAPIView(view) {
    // Hide all views
    document.getElementById('asyncapiTopicsView').style.display = 'none';
    document.getElementById('asyncapiSpecView').style.display = 'none';
    document.getElementById('asyncapiSpecsListView').style.display = 'none';

    // Show selected view
    if (view === 'topics') {
        document.getElementById('asyncapiTopicsView').style.display = 'block';
    } else if (view === 'spec') {
        document.getElementById('asyncapiSpecView').style.display = 'block';
    } else if (view === 'specsList') {
        document.getElementById('asyncapiSpecsListView').style.display = 'block';
    }
}

async function loadTopics() {
    if (!currentEnv) {
        showToast('Error', 'Please select an environment first', 'warning');
        return;
    }

    const gridDiv = document.getElementById('topicsGrid');
    const loadingDiv = document.getElementById('topicsLoading');

    gridDiv.innerHTML = '';
    loadingDiv.style.display = 'flex';

    try {
        const data = await apiCall(`/api/asyncapi/topics/${currentEnv}`);
        
        loadingDiv.style.display = 'none';

        if (data.topics.length === 0) {
            gridDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3>No topics found</h3>
                    <p>No Kafka topics available in this environment</p>
                </div>
            `;
            return;
        }

        // Create topic cards
        data.topics.forEach(topic => {
            const card = createTopicCard(topic);
            gridDiv.appendChild(card);
        });

        showToast('Success', `Loaded ${data.topics.length} topics`, 'success');

    } catch (error) {
        loadingDiv.style.display = 'none';
        showToast('Error', error.message, 'error');
    }
}

function createTopicCard(topic) {
    const card = document.createElement('div');
    card.className = 'topic-card';
    
    const hasSchema = topic.schemas_count > 0;
    const badgeClass = hasSchema ? 'has-schema' : 'no-schema';
    const badgeText = hasSchema ? '✓ Schema' : '⚠ No Schema';

    card.innerHTML = `
        <div class="topic-card-header">
            <h3 class="topic-name">${topic.name}</h3>
            <span class="topic-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="topic-stats">
            <div class="topic-stat">
                <div class="topic-stat-label">Partitions</div>
                <div class="topic-stat-value">${topic.partitions}</div>
            </div>
            <div class="topic-stat">
                <div class="topic-stat-label">Schemas</div>
                <div class="topic-stat-value">${topic.schemas_count}</div>
            </div>
        </div>
        <div class="topic-actions">
            <button class="btn-generate" onclick="generateAsyncAPI('${topic.name}')" ${!hasSchema ? 'disabled' : ''}>
                🔧 Generate AsyncAPI
            </button>
        </div>
    `;

    return card;
}

async function generateAsyncAPI(topicName) {
    const button = event.target;
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '⏳ Generating...';

    try {
        const data = await apiCall(`/api/asyncapi/generate/${currentEnv}/${topicName}`, 'POST');

        if (data.success) {
            currentSpec = data.spec;
            currentSpecFilename = data.filepath.split('/').pop();
            
            displaySpec(data);
            showAsyncAPIView('spec');
            
            showToast('Success', `AsyncAPI spec generated for ${topicName}`, 'success');
        } else {
            showToast('Error', data.error || 'Generation failed', 'error');
        }
    } catch (error) {
        showToast('Error', error.message, 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

function displaySpec(data) {
    // Parse YAML to get spec info
    const info = extractSpecInfo(data.spec);

    // Update spec info banner
    document.getElementById('specInfo').innerHTML = `
        <h3>📄 ${info.title || data.topic}</h3>
        <div class="spec-info-grid">
            <div class="spec-info-item">
                <div class="spec-info-label">Topic</div>
                <div class="spec-info-value">${data.topic}</div>
            </div>
            <div class="spec-info-item">
                <div class="spec-info-label">Version</div>
                <div class="spec-info-value">${info.version || '1.0.0'}</div>
            </div>
            <div class="spec-info-item">
                <div class="spec-info-label">Schemas</div>
                <div class="spec-info-value">${data.schemas_count}</div>
            </div>
            <div class="spec-info-item">
                <div class="spec-info-label">AsyncAPI</div>
                <div class="spec-info-value">3.0.0</div>
            </div>
        </div>
    `;

    // Update YAML view
    document.getElementById('specYaml').textContent = data.spec;

    // ==========================================
    // 👇 METS LA CONFIG ICI 👇
    // ==========================================
    
    // Update Interactive Preview avec AsyncAPI Web Component
    const viewerContainer = document.getElementById('asyncapi-viewer-container');
    viewerContainer.innerHTML = '';
    viewerContainer.classList.add('loading');
    
    // Créer le Web Component
    const asyncapiComponent = document.createElement('asyncapi-component');
    
    // Configurer avec tous les paramètres
    asyncapiComponent.setAttribute('schema', data.spec);
    asyncapiComponent.setAttribute('config', JSON.stringify({
        show: {
            sidebar: true,           // Afficher la sidebar
            info: true,              // Section info
            servers: true,           // Section serveurs
            operations: true,        // Section operations
            messages: true,          // Section messages
            schemas: true,           // Section schemas
            errors: true            // Afficher les erreurs
        },
        sidebar: {
            showOperations: 'byDefault',  // Opérations visibles par défaut
            showServers: 'byDefault',
            showMessages: 'byDefault'
        },
        parserOptions: {
            resolver: {
                resolveRemoteRefs: true  // Résoudre les $ref externes
            }
        },

        theme: {
                colors: {
                    text: {
                        primary: '#f0e9e9ff',
                        secondary: '#333333',
                        muted: '#4a4a4a'
                    },
                    background: {
                        primary: '#080808ff',
                        secondary: '#f5f5f5'
                    }
                }
            }
    }));
    
    asyncapiComponent.setAttribute('cssImportPath', 
        'https://unpkg.com/@asyncapi/react-component@latest/styles/default.min.css'
    );
    
    // Ajouter au container
    viewerContainer.appendChild(asyncapiComponent);
    
    // Enlever le loading après un court délai
    setTimeout(() => {
        viewerContainer.classList.remove('loading');
    }, 500); 

    // Update JSON view
    try {
        const jsonPreview = {
            asyncapi: '3.0.0',
            info: info,
            note: 'Full specification available in YAML tab'
        };
        document.getElementById('specJson').textContent = JSON.stringify(jsonPreview, null, 2);
    } catch (e) {
        document.getElementById('specJson').textContent = 'Error parsing YAML';
    }

    // Highlight code if hljs is available
    if (typeof hljs !== 'undefined') {
        document.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
    }

    // Switch to YAML tab by default
    switchViewerTab('yaml');
}

function extractSpecInfo(yamlSpec) {
    const info = {};
    const lines = yamlSpec.split('\n');
    
    let inInfo = false;
    lines.forEach(line => {
        if (line.trim() === 'info:') {
            inInfo = true;
        } else if (inInfo && line.startsWith('  ') && line.includes(':')) {
            const [key, ...valueParts] = line.trim().split(':');
            const value = valueParts.join(':').trim().replace(/['"]/g, '');
            info[key] = value;
        } else if (inInfo && !line.startsWith('  ')) {
            inInfo = false;
        }
    });
    
    return info;
}

function generatePreview(yamlSpec) {
    const info = extractSpecInfo(yamlSpec);
    
    return `
        <div class="spec-preview-section">
            <h4>📋 Information</h4>
            <table>
                <tr>
                    <td><span class="spec-preview-label">Title:</span></td>
                    <td><span class="spec-preview-value">${info.title || 'N/A'}</span></td>
                </tr>
                <tr>
                    <td><span class="spec-preview-label">Version:</span></td>
                    <td><span class="spec-preview-value">${info.version || 'N/A'}</span></td>
                </tr>
                <tr>
                    <td><span class="spec-preview-label">Description:</span></td>
                    <td><span class="spec-preview-value">${info.description || 'N/A'}</span></td>
                </tr>
            </table>
        </div>

        <div class="spec-preview-section">
            <h4>🔌 Servers</h4>
            <p class="text-muted">Kafka cluster connection details are defined in the servers section of the spec.</p>
        </div>

        <div class="spec-preview-section">
            <h4>📡 Channels</h4>
            <p class="text-muted">The specification includes channel definitions for Kafka topics with message schemas.</p>
        </div>

        <div class="spec-preview-section">
            <h4>⚙️ Operations</h4>
            <p class="text-muted">Publish and subscribe operations are defined for interacting with the topic.</p>
        </div>

        <div class="spec-preview-section">
            <h4>📝 Note</h4>
            <p>View the YAML tab for the complete specification, or download it to import into AsyncAPI Studio.</p>
        </div>
    `;
}

function switchViewerTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.viewer-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.viewerTab === tab);
    });

    // Update content
    document.querySelectorAll('.viewer-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tab}-view`).classList.add('active');
}

async function downloadCurrentSpec() {
    if (!currentSpec) {
        showToast('Error', 'No spec to download', 'warning');
        return;
    }

    try {
        const blob = new Blob([currentSpec], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = currentSpecFilename || 'asyncapi.yaml';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Success', 'Spec downloaded', 'success');
    } catch (error) {
        showToast('Error', 'Download failed', 'error');
    }
}

async function copySpecToClipboard() {
    if (!currentSpec) {
        showToast('Error', 'No spec to copy', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(currentSpec);
        
        // Visual feedback
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '✓ Copied!';
        button.classList.add('copy-success');
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('copy-success');
        }, 2000);

        showToast('Success', 'Spec copied to clipboard', 'success');
    } catch (error) {
        showToast('Error', 'Copy failed', 'error');
    }
}

function openInAsyncAPIStudio() {
    if (!currentSpec) {
        showToast('Error', 'No spec to open', 'warning');
        return;
    }

    // Encode spec in URL
    const encoded = encodeURIComponent(currentSpec);
    const studioUrl = `https://studio.asyncapi.com/?base64=${btoa(currentSpec)}`;
    
    window.open(studioUrl, '_blank');
    showToast('Info', 'Opening in AsyncAPI Studio', 'info');
}

async function loadGeneratedSpecs() {
    const gridDiv = document.getElementById('specsListGrid');
    const loadingDiv = document.getElementById('specsListLoading');

    gridDiv.innerHTML = '';
    loadingDiv.style.display = 'flex';

    try {
        const data = await apiCall('/api/asyncapi/specs');
        
        loadingDiv.style.display = 'none';

        if (data.specs.length === 0) {
            gridDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <h3>No specifications yet</h3>
                    <p>Generate AsyncAPI specs from topics to see them here</p>
                </div>
            `;
            return;
        }

        // Create spec cards
        data.specs.forEach(spec => {
            const card = createSpecCard(spec);
            gridDiv.appendChild(card);
        });

        showToast('Success', `Loaded ${data.specs.length} specifications`, 'success');

    } catch (error) {
        loadingDiv.style.display = 'none';
        showToast('Error', error.message, 'error');
    }
}

function createSpecCard(spec) {
    const card = document.createElement('div');
    card.className = 'spec-list-card';
    
    const createdDate = new Date(spec.created).toLocaleString();

    card.innerHTML = `
        <h3>${spec.title}</h3>
        <div class="spec-list-info">
            <div class="spec-list-info-item">
                <span class="spec-list-info-label">Version:</span>
                <span class="spec-list-info-value">${spec.version}</span>
            </div>
            <div class="spec-list-info-item">
                <span class="spec-list-info-label">Channels:</span>
                <span class="spec-list-info-value">${spec.channels}</span>
            </div>
            <div class="spec-list-info-item">
                <span class="spec-list-info-label">Created:</span>
                <span class="spec-list-info-value">${createdDate}</span>
            </div>
            <div class="spec-list-info-item">
                <span class="spec-list-info-label">File:</span>
                <span class="spec-list-info-value">${spec.filename}</span>
            </div>
        </div>
        <div class="spec-list-actions">
            <button class="btn btn-primary btn-sm" onclick="viewSpec('${spec.filename}')">
                👁️ View
            </button>
            <button class="btn btn-secondary btn-sm" onclick="downloadSpec('${spec.filename}')">
                💾 Download
            </button>
        </div>
    `;

    return card;
}

async function viewSpec(filename) {
    try {
        const response = await fetch(`${API_BASE}/api/asyncapi/specs/${filename}?format=yaml`, {
            headers: {
                'Authorization': authHeader
            }
        });

        if (!response.ok) {
            throw new Error('Failed to load spec');
        }

        const yamlContent = await response.text();
        
        currentSpec = yamlContent;
        currentSpecFilename = filename;
        
        // Extract topic name from filename
        const topicName = filename.replace(/^test_/, '').replace(/_\d+\.yaml$/, '');
        
        displaySpec({
            success: true,
            topic: topicName,
            spec: yamlContent,
            schemas_count: 1,
            filepath: filename
        });
        
        showAsyncAPIView('spec');
        
    } catch (error) {
        showToast('Error', 'Failed to load specification', 'error');
    }
}

async function downloadSpec(filename) {
    try {
        window.location.href = `${API_BASE}/api/asyncapi/download/${filename}`;
        showToast('Success', 'Download started', 'success');
    } catch (error) {
        showToast('Error', 'Download failed', 'error');
    }
}


// ============================================================================
// AI Chat Functions
// ============================================================================

let currentChatSession = null;

function initChatListeners() {
    document.getElementById('sendChatMessage').addEventListener('click', sendChatMessage);
    document.getElementById('clearChat').addEventListener('click', clearChatSession);
    
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

async function startChatSession() {
    try {
        const data = await apiCall('/api/chat/start', 'POST');
        currentChatSession = data.session_id;
        
        // Message de bienvenue
        addChatMessage(
            'assistant',
            '👋 Hello! I\'m your AI assistant for Kafka schemas and AsyncAPI. I can help you:\n\n' +
            '• Understand your schemas\n' +
            '• Generate AsyncAPI docs\n' +
            '• Analyze topics\n' +
            '• Explain message structures\n\n' +
            'What would you like to know?'
        );
    } catch (error) {
        showToast('Error', 'Failed to start chat session', 'error');
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    if (!currentChatSession) {
        await startChatSession();
    }
    
    // Afficher le message utilisateur
    addChatMessage('user', message);
    input.value = '';
    
    // Afficher typing indicator
    showTypingIndicator();
    
    try {
        const data = await apiCall('/api/chat/message', 'POST', {
            session_id: currentChatSession,
            message: message,
            environment: currentEnv
        });
        
        removeTypingIndicator();
        addChatMessage('assistant', data.response);
        
    } catch (error) {
        removeTypingIndicator();
        addChatMessage('assistant', '❌ Sorry, I encountered an error. Please try again.');
        showToast('Error', error.message, 'error');
    }
}

function addChatMessage(role, content) {
    const messagesDiv = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    
    messageDiv.innerHTML = `
        <div class="chat-avatar">${avatar}</div>
        <div class="chat-bubble">
            ${formatChatMessage(content)}
            <div class="chat-timestamp">${new Date().toLocaleTimeString()}</div>
        </div>
    `;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function formatChatMessage(content) {
    // Simple markdown-like formatting
    let formatted = content
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
    
    return formatted;
}

function showTypingIndicator() {
    const messagesDiv = document.getElementById('chatMessages');
    
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typingIndicator';
    typingDiv.className = 'chat-message assistant';
    typingDiv.innerHTML = `
        <div class="chat-avatar">🤖</div>
        <div class="chat-bubble">
            <div class="chat-typing">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messagesDiv.appendChild(typingDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

function clearChatSession() {
    if (!confirm('Clear chat history?')) return;
    
    document.getElementById('chatMessages').innerHTML = '';
    currentChatSession = null;
    startChatSession();
}

// Initialiser au chargement
document.addEventListener('DOMContentLoaded', () => {
    // ... (autres initialisations)
    initChatListeners();
    
    // Auto-start chat session when switching to chat tab
    document.querySelector('[data-tab="chat"]').addEventListener('click', () => {
        if (!currentChatSession) {
            startChatSession();
        }
    });
});

// ============================================================================
// History Functions
// ============================================================================

async function loadHistory() {
    const tableDiv = document.getElementById('historyTable');
    
    try {
        const data = await apiCall('/api/history');
        
        if (data.history.length === 0) {
            tableDiv.innerHTML = '<p class="text-muted">No operation history</p>';
            return;
        }

        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Environment</th>
                    <th>Operation</th>
                    <th>User</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${data.history.map(entry => `
                    <tr>
                        <td>${new Date(entry.timestamp).toLocaleString()}</td>
                        <td>${entry.environment}</td>
                        <td>${entry.operation.replace(/_/g, ' ')}</td>
                        <td>${entry.user}</td>
                        <td class="text-${entry.status === 'success' ? 'success' : 'danger'}">
                            ${entry.status}
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        
        tableDiv.innerHTML = '';
        tableDiv.appendChild(table);
        
    } catch (error) {
        showToast('Error', error.message, 'error');
    }
}

// ============================================================================
// UI Helper Functions
// ============================================================================

function showToast(title, message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalMessage').textContent = message;
        
        modal.classList.add('show');
        
        const confirmBtn = document.getElementById('modalConfirm');
        const cancelBtn = document.getElementById('modalCancel');
        
        const handleConfirm = () => {
            cleanup();
            resolve(true);
        };
        
        const handleCancel = () => {
            cleanup();
            resolve(false);
        };
        
        const cleanup = () => {
            modal.classList.remove('show');
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
        };
        
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
    });
}

function closeModal() {
    document.getElementById('confirmModal').classList.remove('show');
}

// Close modal on outside click
document.getElementById('confirmModal').addEventListener('click', (e) => {
    if (e.target.id === 'confirmModal') {
        closeModal();
    }
});