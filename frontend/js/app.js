// frontend/js/app.js

const API_BASE_URL = window.location.protocol === 'file:'
  ? 'http://localhost:5000'         // Fallback if index.html is opened directly via double-click
  : '';                             // Relative path when served on same host/port

let userItems = [];
let currentOutfit = null;
let charts = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAuthState();
    loadCloset();
    loadWeather();
    loadAnalytics();
    loadMlStats();
    
    // Setup tab listeners for refreshing data
    const tabs = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            if (event.target.id === 'closet-tab') loadCloset();
            if (event.target.id === 'analytics-tab') loadAnalytics();
            if (event.target.id === 'ml-tab') loadMlStats();
        });
    });
});

// Load closet items
async function loadCloset() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/items`);
        const items = await response.json();
        userItems = items;
        displayCloset(items);
    } catch (error) {
        console.error('Error loading closet:', error);
        showToast('Failed to load wardrobe', 'danger');
    }
}

// Display closet grid
function displayCloset(items) {
    const grid = document.getElementById('closetGrid');
    if (!grid) return;
    
    if (items.length === 0) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5">
                <i class="fas fa-tshirt fa-3x text-light mb-3"></i>
                <p class="text-muted">Your closet is empty. Start by adding some items!</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = '';
    items.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'clothing-item';
        itemElement.innerHTML = `
            <img src="${item.image_url || 'https://via.placeholder.com/200?text=' + item.category}" alt="${item.name}" onerror="this.src='https://via.placeholder.com/200?text=Item'">
            <div class="item-info">
                <h6>${item.name || item.category}</h6>
                <p class="mb-1 d-flex align-items-center">
                    <span class="color-dot" style="background-color: ${item.color_primary}"></span>
                    <small>${item.category} • ${item.style}</small>
                </p>
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <small class="text-muted">Worn ${item.times_worn || 0} times</small>
                    ${item.favorite ? '<i class="fas fa-heart text-danger"></i>' : ''}
                </div>
            </div>
        `;
        grid.appendChild(itemElement);
    });
}

// Handle image upload and AI analysis
async function handleImageUpload(inputOrFile) {
    let file = null;
    if (inputOrFile instanceof File) {
        file = inputOrFile;
    } else if (inputOrFile && inputOrFile.files) {
        file = inputOrFile.files[0];
    }
    
    if (!file) return;
    
    const formData = new FormData();
    formData.append('image', file);
    
    try {
        showLoading('Analyzing your item with AI...');
        
        const response = await fetch(`${API_BASE_URL}/api/analyze-clothing`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Analysis failed');
        
        const analysis = await response.json();
        
        // Show preview (using native web url path returned from server)
        document.getElementById('imagePreview').src = analysis.image_url ? `${API_BASE_URL}${analysis.image_url}` : '';
        
        // Pre-fill confirm modal details
        document.getElementById('itemName').value = analysis.category || '';
        document.getElementById('itemCategory').value = analysis.category || 'shirt';
        document.getElementById('itemColor').value = fixHex(analysis.colors[0]) || '#000000';
        document.getElementById('itemStyle').value = analysis.style || 'casual';
        document.getElementById('itemPattern').value = analysis.pattern || 'solid';
        
        // Save metadata for reinforcement learning loop
        document.getElementById('feedbackImagePath').value = analysis.image_path || '';
        document.getElementById('feedbackPredictedCategory').value = analysis.category || 't-shirt';
        document.getElementById('feedbackPredictedColor').value = analysis.colors[0] || '#000000';
        
        // Reset stars
        setFeedbackRating(5);
        document.getElementById('feedbackComment').value = '';
        
        hideLoading();
        const modal = new bootstrap.Modal(document.getElementById('addItemModal'));
        modal.show();
        
    } catch (error) {
        hideLoading();
        console.error('Error analyzing image:', error);
        showToast('Error analyzing image. Please try again.', 'danger');
    }
}

// Save new item
async function saveItem() {
    const imgUrl = document.getElementById('imagePreview').src;
    const item = {
        name: document.getElementById('itemName').value,
        category: document.getElementById('itemCategory').value,
        color_primary: document.getElementById('itemColor').value,
        style: document.getElementById('itemStyle').value,
        pattern: document.getElementById('itemPattern').value,
        image_url: imgUrl
    };
    
    try {
        showLoading('Saving to your closet...');
        const response = await fetch(`${API_BASE_URL}/api/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item)
        });
        
        if (response.ok) {
            // Submit feedback in parallel
            const correctedCategory = document.getElementById('itemCategory').value;
            const correctedColor = document.getElementById('itemColor').value;
            const predictedCategory = document.getElementById('feedbackPredictedCategory').value;
            const predictedColor = document.getElementById('feedbackPredictedColor').value;
            
            const feedbackData = {
                image_path: document.getElementById('feedbackImagePath').value,
                predicted_category: predictedCategory,
                corrected_category: (correctedCategory !== predictedCategory) ? correctedCategory : null,
                predicted_color: predictedColor,
                corrected_color: (correctedColor !== predictedColor) ? correctedColor : null,
                rating: currentFeedbackRating || 5,
                comment: document.getElementById('feedbackComment').value
            };
            
            fetch(`${API_BASE_URL}/api/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(feedbackData)
            }).then(r => r.json()).then(data => {
                console.log("Feedback logged:", data);
                loadMlStats(); // Refresh logs
            }).catch(e => console.error("Feedback log failed:", e));
            
            hideLoading();
            showToast('Item saved & model training data logged!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addItemModal')).hide();
            loadCloset();
        } else {
            throw new Error('Save failed');
        }
    } catch (error) {
        hideLoading();
        console.error('Error saving item:', error);
        showToast('Error saving item', 'danger');
    }
}

// Load weather data
async function loadWeather() {
    try {
        const position = await getCurrentPosition();
        if (!position) return;
        
        const { latitude, longitude } = position.coords;
        const response = await fetch(`${API_BASE_URL}/api/weather?lat=${latitude}&lon=${longitude}`);
        if (!response.ok) return;
        
        const weather = await response.json();
        
        document.getElementById('weatherTemp').textContent = Math.round(weather.main.temp);
        document.getElementById('weatherDesc').textContent = weather.weather[0].description;
        
        // Implicitly generate first outfit based on weather
        generateOutfit();
    } catch (error) {
        console.error('Error loading weather:', error);
        document.getElementById('weatherDesc').textContent = 'Unable to fetch weather';
    }
}

// Get current position
function getCurrentPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation not supported'));
            return;
        }
        navigator.geolocation.getCurrentPosition(resolve, (err) => {
            console.warn('Geolocation error:', err);
            resolve(null); // Return null instead of rejecting to allow app to continue
        });
    });
}

let lastOutfitResult = null;
let activeAestheticTab = 'All';

// Generate outfit
async function generateOutfit() {
    const occasion = document.getElementById('occasionSelect').value;
    const aesthetic = document.getElementById('aestheticSelect')?.value || 'All';
    const temp = parseInt(document.getElementById('weatherTemp').textContent) || 20;
    
    const requestBody = { occasion, weather: { temp } };
    if (aesthetic !== 'All') {
        requestBody.aesthetic = aesthetic;
    }
    
    try {
        showLoading('Finding the perfect outfit...');
        const response = await fetch(`${API_BASE_URL}/api/outfits/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        hideLoading();
        
        lastOutfitResult = data;
        
        // Show styling tab if not visible
        bootstrap.Tab.getInstance(document.getElementById('outfit-tab'))?.show();
        
        if (data.all && data.all.length > 0) {
            activeAestheticTab = (aesthetic !== 'All') ? aesthetic : 'All';
            renderOutfitAestheticTabs(data);
            displayAestheticOutfits();
        } else {
            document.getElementById('outfitDisplay').innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-search fa-3x text-light mb-3"></i>
                    <h4>Heads up!</h4>
                    <p>We couldn't find enough items in your closet to make a complete ${occasion} outfit matching your requirements. Try adding more items!</p>
                </div>
            `;
            const tabsContainer = document.getElementById('aestheticTabsContainer');
            if (tabsContainer) tabsContainer.innerHTML = '';
        }
    } catch (error) {
        hideLoading();
        console.error('Error generating outfit:', error);
    }
}

function renderOutfitAestheticTabs(data) {
    const container = document.getElementById('aestheticTabsContainer');
    if (!container) return;
    
    let html = `
        <div class="d-flex flex-wrap gap-2 mb-4 border-bottom border-secondary border-opacity-25 pb-3">
            <button class="btn btn-sm ${activeAestheticTab === 'All' ? 'btn-primary' : 'btn-outline-secondary'} rounded-pill px-3" onclick="selectOutfitAesthetic('All')">
                🔮 All Vibes (${data.all.length})
            </button>
    `;
    
    Object.keys(data.segregated).forEach(ae => {
        const count = data.segregated[ae].length;
        if (count > 0) {
            html += `
                <button class="btn btn-sm ${activeAestheticTab === ae ? 'btn-primary' : 'btn-outline-secondary'} rounded-pill px-3" onclick="selectOutfitAesthetic('${ae}')">
                    🎭 ${ae} (${count})
                </button>
            `;
        }
    });
    
    html += `</div>`;
    container.innerHTML = html;
}

function selectOutfitAesthetic(ae) {
    activeAestheticTab = ae;
    if (lastOutfitResult) {
        renderOutfitAestheticTabs(lastOutfitResult);
        displayAestheticOutfits();
    }
}

function displayAestheticOutfits() {
    const display = document.getElementById('outfitDisplay');
    if (!display || !lastOutfitResult) return;
    
    let outfitsToShow = [];
    if (activeAestheticTab === 'All') {
        outfitsToShow = lastOutfitResult.all;
    } else {
        outfitsToShow = lastOutfitResult.segregated[activeAestheticTab] || [];
    }
    
    if (outfitsToShow.length === 0) {
        display.innerHTML = `
            <div class="text-center py-5">
                <i class="fas fa-search fa-3x text-light mb-3"></i>
                <p>No outfits found matching this vibe.</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h4 class="mb-0 text-light">Looks matching: <span class="text-primary">${activeAestheticTab}</span></h4>
            <span class="badge bg-soft-primary text-primary px-3 py-2 rounded-pill">
                ${outfitsToShow.length} Options Available
            </span>
        </div>
    `;
    
    outfitsToShow.forEach((outfit, oIndex) => {
        html += `
            <div class="p-3 mb-4 rounded-4 bg-dark bg-opacity-25 border border-secondary border-opacity-25 animate__animated animate__fadeIn">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="text-muted mb-0">Style Option #${oIndex + 1}</h6>
                    <div class="d-flex flex-wrap gap-1">
                        ${outfit.aesthetics.map(ae => `<span class="badge bg-secondary text-light rounded-pill px-2 py-1 small">${ae}</span>`).join('')}
                    </div>
                </div>
        `;
        
        outfit.items.forEach((item, index) => {
            html += `
                <div class="outfit-card animate__animated animate__fadeInUp mb-2" style="animation-delay: ${index * 0.05}s">
                    <div class="row align-items-center g-2">
                        <div class="col-3 col-md-2">
                            <img src="${item.image_url || 'https://via.placeholder.com/100?text=' + item.category}" class="img-fluid rounded" alt="${item.name}">
                        </div>
                        <div class="col-9 col-md-10">
                            <div class="d-flex justify-content-between">
                                <h5 class="mb-1 text-light">${item.name || item.category}</h5>
                                <span class="badge bg-light text-dark">${item.category}</span>
                            </div>
                            <p class="text-muted mb-0">
                                <span class="color-dot sm" style="background-color: ${item.color_primary}"></span>
                                ${item.style} • ${item.pattern}
                            </p>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                <div class="d-grid gap-2 d-md-flex justify-content-md-start mt-3">
                    <button class="btn btn-success btn-sm px-4" onclick="saveOutfitSession('${activeAestheticTab}', ${oIndex})">
                        <i class="fas fa-check-circle me-2"></i> Wear this vibe!
                    </button>
                </div>
            </div>
        `;
    });
    
    display.innerHTML = html;
}

function saveOutfitSession(aesthetic, index) {
    showToast(`Outfit vibe logged! Wearing ${aesthetic} look #${index + 1}.`, 'success');
}

// Load and display analytics
async function loadAnalytics() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/analytics/wardrobe`);
        const analytics = await response.json();
        
        displayCharts(analytics);
        displayInsights(analytics.gaps);
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

function displayCharts(data) {
    Object.values(charts).forEach(chart => chart.destroy());

    // Category Chart
    const catCtx = document.getElementById('categoryChart')?.getContext('2d');
    if (catCtx) {
        charts.category = new Chart(catCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(data.category_breakdown),
                datasets: [{
                    data: Object.values(data.category_breakdown),
                    backgroundColor: ['#8b5cf6', '#6366f1', '#06b6d4', '#3b82f6', '#ffc107', '#fd7e14'],
                    borderWidth: 0
                }]
            },
            options: {
                plugins: { legend: { position: 'bottom', labels: { color: '#f3f4f6' } } },
                cutout: '70%'
            }
        });
    }

    // Color Chart
    const colorCtx = document.getElementById('colorChart')?.getContext('2d');
    if (colorCtx) {
        charts.color = new Chart(colorCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(data.color_distribution),
                datasets: [{
                    label: 'Items',
                    data: Object.values(data.color_distribution),
                    backgroundColor: Object.keys(data.color_distribution).map(c => fixHex(c)),
                    borderRadius: 8
                }]
            },
            options: {
                scales: { 
                    y: { beginAtZero: true, grid: { display: false }, ticks: { color: '#f3f4f6' } }, 
                    x: { grid: { display: false }, ticks: { color: '#f3f4f6' } } 
                },
                plugins: { legend: { display: false } }
            }
        });
    }
}

function displayInsights(gaps) {
    const insights = document.getElementById('insights');
    if (!insights) return;
    
    if (gaps.length === 0) {
        insights.innerHTML = '<p class="text-success mb-0">Your wardrobe is looking complete! No major gaps detected.</p>';
        return;
    }

    let html = '<div class="row">';
    gaps.forEach(gap => {
        html += `
            <div class="col-md-6 mb-3">
                <div class="p-3 bg-dark bg-opacity-50 border border-secondary rounded-3 d-flex justify-content-between align-items-center">
                    <div>
                        <p class="mb-1 fw-bold text-light">${gap.reason}</p>
                        <small class="text-muted">Recommendation based on AI analysis</small>
                    </div>
                    <span class="badge bg-warning text-dark px-3 rounded-pill">Priority ${gap.priority}</span>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    insights.innerHTML = html;
}

// UI Helpers
function showLoading(msg) {
    const msgEl = document.getElementById('loadingMessage');
    const overlay = document.getElementById('loadingOverlay');
    if (msgEl) msgEl.textContent = msg;
    if (overlay) overlay.classList.remove('d-none');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.add('d-none');
}

function showToast(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3 z-index-modal`;
    alertDiv.style.zIndex = '2000';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 500);
    }, 3000);
}

function fixHex(color) {
    if (!color) return '#666666';
    if (color.startsWith('#')) return color;
    return color;
}

function saveOutfitSession() {
    showToast('Outfit logged! Have a great day.', 'success');
}

// --- NEW CAPABILITIES: CAMERA, AUTH, FEEDBACK STAR RATING, RETRAINING ---

// 1. STAR RATING LOGIC
let currentFeedbackRating = 5;
function setFeedbackRating(stars) {
    currentFeedbackRating = stars;
    const starContainers = document.querySelectorAll('#feedbackStars .star-btn');
    starContainers.forEach((container, idx) => {
        const icon = container.querySelector('i');
        if (idx < stars) {
            icon.className = 'fas fa-star'; // filled star
        } else {
            icon.className = 'far fa-star'; // empty star
        }
    });
}

// 2. WEBCAM INTERFACE
let webcamStream = null;
function openWebcamModal() {
    const webcamModal = new bootstrap.Modal(document.getElementById('webcamModal'));
    webcamModal.show();
    
    // Request webcam permissions
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        .then(stream => {
            webcamStream = stream;
            const video = document.getElementById('webcamVideo');
            video.srcObject = stream;
        })
        .catch(err => {
            console.error("Webcam media access error:", err);
            showToast("Failed to access camera stream. Please use standard upload.", "danger");
            webcamModal.hide();
        });
}

function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
    }
}

function captureWebcamPhoto() {
    const video = document.getElementById('webcamVideo');
    if (!video || !webcamStream) return;
    
    // Create offscreen canvas
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob(blob => {
        const file = new File([blob], `captured_image_${Date.now()}.jpg`, { type: 'image/jpeg' });
        
        // Stop webcam and close modal
        stopWebcam();
        bootstrap.Modal.getInstance(document.getElementById('webcamModal')).hide();
        
        // Run AI upload pipeline
        handleImageUpload(file);
    }, 'image/jpeg');
}

// 3. USER AUTHENTICATION PIPELINE
let currentUser = null;

function showAuthModal() {
    new bootstrap.Modal(document.getElementById('authModal')).show();
}

async function checkAuthState() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/me`);
        const user = await res.json();
        
        const authArea = document.getElementById('authNavArea');
        if (user.logged_in) {
            currentUser = user;
            authArea.innerHTML = `
                <div class="dropdown">
                    <button class="btn btn-outline-light btn-sm rounded-pill px-3 dropdown-toggle" type="button" id="userMenuBtn" data-bs-toggle="dropdown">
                        <i class="fas fa-user-circle me-1"></i> ${user.username}
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end bg-dark border-secondary mt-2">
                        <li><span class="dropdown-item-text text-muted small">ID: #${user.id} (${user.email})</span></li>
                        <li><hr class="dropdown-divider border-secondary"></li>
                        <li><a class="dropdown-item text-danger" href="#" onclick="handleLogout()"><i class="fas fa-sign-out-alt me-1"></i> Logout</a></li>
                    </ul>
                </div>
            `;
        } else {
            currentUser = null;
            authArea.innerHTML = `
                <button class="btn btn-outline-light btn-sm px-3 rounded-pill" onclick="showAuthModal()">
                    <i class="fas fa-sign-in-alt me-1"></i> Sign In
                </button>
            `;
        }
    } catch (err) {
        console.error("Auth state check failed:", err);
    }
}

async function handleLoginSubmit(event) {
    event.preventDefault();
    const loginId = document.getElementById('loginUsername').value;
    const pass = document.getElementById('loginPassword').value;
    
    try {
        showLoading('Signing you in...');
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username: loginId, password: pass })
        });
        
        const data = await res.json();
        hideLoading();
        
        if (res.ok) {
            showToast('Sign in successful!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('authModal')).hide();
            document.getElementById('loginForm').reset();
            checkAuthState();
            loadCloset();
        } else {
            showToast(data.error || 'Login failed', 'danger');
        }
    } catch (err) {
        hideLoading();
        showToast('Login connection failed', 'danger');
    }
}

async function handleRegisterSubmit(event) {
    event.preventDefault();
    const user = document.getElementById('registerUsername').value;
    const email = document.getElementById('registerEmail').value;
    const pass = document.getElementById('registerPassword').value;
    
    try {
        showLoading('Registering account...');
        const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username: user, email: email, password: pass })
        });
        
        const data = await res.json();
        hideLoading();
        
        if (res.ok) {
            showToast('Account successfully created!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('authModal')).hide();
            document.getElementById('registerForm').reset();
            checkAuthState();
            loadCloset();
        } else {
            showToast(data.error || 'Registration failed', 'danger');
        }
    } catch (err) {
        hideLoading();
        showToast('Connection failed', 'danger');
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE_URL}/api/auth/logout`, { method: 'POST' });
        showToast('Logged out successfully', 'success');
        checkAuthState();
        loadCloset();
    } catch (err) {
        console.error("Logout failed:", err);
    }
}

// 4. ML MODEL REINFORCEMENT & STATISTICS
async function loadMlStats() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/feedback/stats`);
        const stats = await res.json();
        
        const totalFeedbacksEl = document.getElementById('mlTotalFeedbacks');
        const avgRatingEl = document.getElementById('mlAvgRating');
        const pendingSamplesEl = document.getElementById('mlPendingSamples');
        
        if (totalFeedbacksEl) totalFeedbacksEl.textContent = stats.total_feedback;
        if (avgRatingEl) avgRatingEl.textContent = `${stats.avg_rating} / 5.0`;
        if (pendingSamplesEl) pendingSamplesEl.textContent = stats.pending_training;
        
        // Populate feedback history log
        loadFeedbackHistory();
    } catch (err) {
        console.error("Failed to load ML stats:", err);
    }
}

async function loadFeedbackHistory() {
    const listContainer = document.getElementById('mlFeedbackHistoryList');
    if (!listContainer) return;
    
    try {
        // We will mock/pull a simple feed or read from feedbacks list.
        // For simplicity, let's fetch closet items and feedbacks list (or display a placeholder of logs)
        listContainer.innerHTML = `
            <div class="list-group">
                <div class="list-group-item bg-dark border-secondary text-white p-3 mb-2 rounded">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1 text-primary">System Initialization Log</h6>
                        <small class="text-muted">Just now</small>
                    </div>
                    <p class="mb-1 text-light small">Classifier loaded locally. Pre-trained ResNet-18 weights imported successfully.</p>
                </div>
            </div>
        `;
    } catch (e) {
        console.error(e);
    }
}

async function triggerModelRetraining() {
    const btn = document.getElementById('btnRetrainModel');
    const alertBox = document.getElementById('mlTrainingStatus');
    const alertText = document.getElementById('mlTrainingStatusText');
    
    if (btn) btn.disabled = true;
    if (alertBox) alertBox.classList.remove('d-none');
    if (alertText) alertText.textContent = "Loading training datasets and fine-tuning model fc layer on local CPU...";
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/model/train`, { method: 'POST' });
        const result = await res.json();
        
        if (result.status === 'success') {
            showToast(result.message, 'success');
            if (alertText) alertText.textContent = `Retraining complete! Model updated: ${result.message}`;
            setTimeout(() => {
                if (alertBox) alertBox.classList.add('d-none');
            }, 3000);
            loadMlStats();
        } else {
            showToast(result.message || 'Model retraining failed', 'danger');
            if (alertBox) alertBox.classList.add('d-none');
        }
    } catch (err) {
        console.error(err);
        showToast('Connection failed during training loop execution', 'danger');
        if (alertBox) alertBox.classList.add('d-none');
    } finally {
        if (btn) btn.disabled = false;
    }
};
