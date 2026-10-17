const gridSize = 16; // Size of the 16x16 grid for drawing digits
let grid = Array(gridSize).fill().map(() => Array(gridSize).fill(0)); // 2D array representing the grid state (0 = off, 1 = on)
let lastImageCriter = null; // Stores the last submitted hexadecimal grid string
let lastProbMax = null; // Stores the index of the highest probability from the last prediction
let currentTab = 'home'; // Tracks the active tab in admin.html (home, feedbacks, batches, models)
let feedbackIds = []; // Array of feedback IDs fetched from the database
let currentFeedbackId = 1; // Current feedback ID being viewed in admin.html
let batchStart = 0; // Starting index for paginated training batches display
let modelStart = 0; // Starting index for paginated models display

/**
 * Initializes a 16x16 grid in the specified container, optionally enabling click interactions.
 * Used in index.html for the interactive drawing grid and in admin.html for displaying feedback grids.
 * @param {HTMLElement} container - The DOM element to render the grid into.
 * @param {boolean} [interactive=false] - If true, cells are clickable to toggle their state.
 */
function initGrid(container, interactive = false) {
    // Clear existing content in the container
    container.innerHTML = '';
    // Create 16 rows
    for (let i = 0; i < gridSize; i++) {
        const row = document.createElement('div');
        row.className = 'grid-row';
        // Create 16 cells per row
        for (let j = 0; j < gridSize; j++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            // Add click event listener for interactive grids
            if (interactive) {
                cell.addEventListener('click', () => toggleCell(i, j, cell));
            }
            row.appendChild(cell);
        }
        container.appendChild(row);
    }
}

/**
 * Displays a 16x16 grid in the specified container using a hexadecimal image_criter string.
 * Converts the hex string to binary and sets cell states (active/inactive) for visualization.
 * Used in admin.html to show feedback grids stored in the SQLite database.
 * @param {HTMLElement} container - The DOM element to render the grid into.
 * @param {string} imageCriter - 64-character hexadecimal string representing the grid.
 */
function displayGrid(container, imageCriter) {
    // Convert hexadecimal string to binary array
    const binary = hexToBinary(imageCriter);
    // Initialize a non-interactive grid
    initGrid(container);
    // Set cell states based on binary values
    for (let i = 0; i < gridSize; i++) {
        for (let j = 0; j < gridSize; j++) {
            const cell = container.querySelector(`.grid-row:nth-child(${i+1}) .grid-cell:nth-child(${j+1})`);
            if (binary[i*16 + j]) cell.classList.add('active');
        }
    }
}

/**
 * Converts a hexadecimal string to a binary array (256 bits) for grid representation.
 * Used to prepare grid data for display in admin.html and for model input in __deamon__.py.
 * @param {string} hex - 64-character hexadecimal string.
 * @returns {number[]} Array of 256 binary values (0 or 1).
 */
function hexToBinary(hex) {
    const binary = [];
    // Process each hexadecimal character
    for (const char of hex) {
        // Convert hex to decimal
        const value = parseInt(char, 16);
        // Convert decimal to 4-bit binary string
        const bits = value.toString(2).padStart(4, '0');
        // Add binary digits to the array
        binary.push(...bits.split('').map(Number));
    }
    return binary;
}

/**
 * Converts the current 16x16 grid (grid array) to a 64-character hexadecimal string.
 * Returns null if the grid is empty or invalid. Used to prepare data for the /predict endpoint.
 * @returns {string|null} 64-character hexadecimal string or null if invalid/empty.
 */
function gridToHex() {
    // Flatten the grid and convert to binary string array
    const binary = grid.flat().map(bit => bit.toString());
    // Check if the grid is empty
    if (binary.every(bit => bit === '0')) return null;
    let hex = '';
    // Process 4 bits at a time to create hex digits
    for (let i = 0; i < binary.length; i += 4) {
        const nibble = binary.slice(i, i + 4).join('');
        const value = parseInt(nibble, 2);
        if (isNaN(value)) return null;
        hex += value.toString(16).toUpperCase();
    }
    // Ensure the output is exactly 64 characters
    return hex.length === 64 ? hex : null;
}

/**
 * Sends a POST request to the specified Flask endpoint with JSON data.
 * Communicates with __deamon__.py endpoints (/predict, /feedback, /tcp_relay) to interact with the SQLite database and model.
 * @param {string} url - The endpoint URL (e.g., '/predict', '/tcp_relay').
 * @param {Object} data - The JSON data to send.
 * @param {boolean} [isTcp=false] - If true, the request is relayed via TCP to the daemon.
 * @returns {Promise<Object>} The JSON response from the server.
 * @throws {Error} If the request fails or the response contains an error.
 */
async function sendRequest(url, data, isTcp = false) {
    try {
        // Send POST request to Flask server
        const response = await fetch(`http://localhost:20000${url}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        // Check for HTTP errors
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || `HTTP Error ${response.status}`);
        }
        // Parse JSON response
        const result = await response.json();
        // Check for application-level errors
        if (result.error) throw new Error(result.error);
        return result;
    } catch (error) {
        // Display error in the UI if possible
        const errorEl = document.getElementById('error-message');
        if (errorEl) errorEl.textContent = error.message;
        else alert(error.message);
        throw error;
    }
}

/**
 * Draws an SVG bar chart in the specified container using provided data.
 * Used to visualize prediction probabilities in index.html and model losses in admin.html.
 * @param {Object[]} data - Array of objects with label and value keys.
 * @param {HTMLElement} container - The SVG element to render the chart into.
 * @param {Object} options - Chart options (barWidth, maxHeight, labelKey, valueKey, onClick).
 */
function drawBarChart(data, container, options) {
    // Clear existing chart content
    container.innerHTML = '';
    const { barWidth, maxHeight, labelKey, valueKey } = options;
    // Extract values for scaling
    const values = data.map(item => item[valueKey]);
    const maxValue = Math.max(...values, 0.1);
    const minValue = Math.min(...values, 0);
    // Draw bars for each data point
    data.forEach((item, i) => {
        const x = i * (barWidth + 5);
        // Scale height based on value
        const height = ((item[valueKey] - minValue) / (maxValue - minValue) || 0) * maxHeight || 5;
        const y = maxHeight - height;
        // Create SVG rectangle for the bar
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', barWidth);
        rect.setAttribute('height', height);
        rect.setAttribute('class', 'bar');
        // Add click handler if provided
        if (options.onClick) rect.addEventListener('click', () => options.onClick(item));
        container.appendChild(rect);
        // Create SVG text for the label
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x + barWidth / 2);
        text.setAttribute('y', maxHeight + 20);
        text.setAttribute('class', 'bar-text');
        text.setAttribute('text-anchor', 'middle');
        text.textContent = item[labelKey];
        container.appendChild(text);
    });
}

// Index.html logic

/**
 * Toggles the state of a grid cell (on/off) in index.html and updates the grid array.
 * Triggered by user clicks on the interactive grid.
 * @param {number} i - Row index of the cell.
 * @param {number} j - Column index of the cell.
 * @param {HTMLElement} cell - The DOM element of the cell.
 */
function toggleCell(i, j, cell) {
    // Toggle cell state in the grid array
    grid[i][j] = 1 - grid[i][j];
    // Update cell appearance
    cell.classList.toggle('active', grid[i][j] === 1);
}

/**
 * Resets the grid to all zeros, clears the UI, and hides the feedback button in index.html.
 * Called when the user clicks the "Reset" button.
 */
function resetGrid() {
    // Reset grid array
    grid = Array(gridSize).fill().map(() => Array(gridSize).fill(0));
    // Reinitialize interactive grid
    const container = document.getElementById('grid-container');
    initGrid(container, true);
    // Clear stored prediction data
    lastImageCriter = null;
    lastProbMax = null;
    // Hide feedback button
    document.getElementById('feedback-btn').style.display = 'none';
    // Clear probability chart
    document.getElementById('prob-chart').innerHTML = '';
    // Reset prediction text
    document.getElementById('max-prob').textContent = 'Predicted Digit: None';
}

/**
 * Submits the current grid for prediction via the /predict endpoint in __deamon__.py.
 * Displays probabilities as a bar chart and enables feedback submission in index.html.
 */
async function submitGrid() {
    // Convert grid to hexadecimal
    const imageCriter = gridToHex();
    // Validate grid
    if (!imageCriter) {
        alert('Error: The grid is empty or invalid');
        return;
    }
    // Confirm submission
    if (!confirm('Confirm submission of the grid for prediction?')) return;
    // Store grid for feedback
    lastImageCriter = imageCriter;
    // Send prediction request
    const data = await sendRequest('/predict', { image_criter: imageCriter });
    // Find index of highest probability
    lastProbMax = data.probabilities.indexOf(Math.max(...data.probabilities));
    // Draw probability chart
    drawBarChart(
        data.probabilities.map((prob, i) => ({ id: i, value: prob })),
        document.getElementById('prob-chart'),
        { barWidth: 35, maxHeight: 250, labelKey: 'id', valueKey: 'value' }
    );
    // Update prediction text
    document.getElementById('max-prob').textContent = `Predicted Digit: ${lastProbMax} (${(data.probabilities[lastProbMax] * 100).toFixed(1)}%)`;
    // Show feedback button
    document.getElementById('feedback-btn').style.display = 'block';
}

/**
 * Sends feedback data (grid and predicted digit) to the /feedback endpoint in __deamon__.py.
 * Stores the feedback in the SQLite database via __gestion_sql__.py.
 */
async function sendFeedback() {
    // Validate prediction data
    if (!lastImageCriter || lastProbMax === null) {
        alert('Error: No prediction available for feedback');
        return;
    }
    // Confirm feedback submission
    if (!confirm('Confirm submission of feedback?')) return;
    // Send feedback request
    const data = await sendRequest('/feedback', { image_criter: lastImageCriter, prob_max: lastProbMax });
    // Notify user of success
    alert('Feedback submitted successfully');
    // Hide feedback button
    document.getElementById('feedback-btn').style.display = 'none';
}

// Admin.html logic

/**
 * Loads and displays a feedback entry by ID in admin.html.
 * Fetches data via /tcp_relay endpoint in __deamon__.py, which queries __gestion_sql__.py.
 * @param {number} id - The ID of the feedback to load.
 */
async function loadFeedback(id) {
    const container = document.querySelector('#feedbacks .grid-container');
    try {
        // Fetch feedback data
        const data = await sendRequest('/tcp_relay', { command: `get_feedback ${id}` }, true);
        const fb = data.data;
        if (!fb) throw new Error('Feedback not found');
        // Update current feedback ID
        currentFeedbackId = id;
        // Check if feedback is deleted
        if (fb.image_criter === '0'.repeat(64) || fb.prob_max === null) {
            document.getElementById('fb-id').textContent = id;
            document.getElementById('fb-prob-max').textContent = 'Deleted';
            document.getElementById('fb-date').textContent = '';
            document.getElementById('fb-model-id').textContent = '';
            initGrid(container);
            document.getElementById('no-feedback').style.display = 'none';
            return;
        }
        // Display feedback grid
        displayGrid(container, fb.image_criter);
        // Update feedback details
        document.getElementById('fb-id').textContent = fb.id;
        document.getElementById('fb-prob-max').textContent = fb.prob_max;
        document.getElementById('fb-date').textContent = fb.date;
        document.getElementById('fb-model-id').textContent = fb.id_version_modele;
        document.getElementById('no-feedback').style.display = 'none';
    } catch (error) {
        // Handle errors
        document.getElementById('error-message').textContent = error.message;
        document.getElementById('no-feedback').style.display = 'block';
        document.getElementById('fb-id').textContent = '';
        document.getElementById('fb-prob-max').textContent = '';
        document.getElementById('fb-date').textContent = '';
        document.getElementById('fb-model-id').textContent = '';
        initGrid(container);
    }
}

/**
 * Loads and displays a paginated list of training batches in admin.html.
 * Fetches data via /tcp_relay endpoint in __deamon__.py, which queries __gestion_sql__.py.
 */
async function loadBatches() {
    // Fetch batch data
    const data = await sendRequest('/tcp_relay', { command: 'list_training_batches' }, true);
    const table = document.getElementById('batches-table');
    // Clear existing table content
    table.innerHTML = '';
    // Display up to 10 batches
    const displayed = data.data.filter(b => b.id_min_feedback !== null).slice(batchStart, batchStart + 10);
    displayed.forEach(b => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${b.id}</td>
            <td>${b.id_min_feedback}</td>
            <td>${b.id_max_feedback}</td>
            <td><button onclick="deleteBatch(${b.id})">Delete</button></td>
        `;
        table.appendChild(row);
    });
}

/**
 * Deletes a training batch by ID via the /tcp_relay endpoint in __deamon__.py.
 * Updates the SQLite database via __gestion_sql__.py and refreshes the batch list.
 * @param {number} id - The ID of the batch to delete.
 */
async function deleteBatch(id) {
    // Confirm deletion
    if (confirm('Confirm deletion?')) {
        // Send delete request
        await sendRequest('/tcp_relay', { command: `delete_training_batch ${id}` }, true);
        // Refresh batch list
        loadBatches();
    }
}

/**
 * Loads and displays a paginated list of models with their losses as a bar chart in admin.html.
 * Fetches data via /tcp_relay endpoint in __deamon__.py, which queries __gestion_sql__.py.
 */
async function loadModels() {
    // Fetch model data
    const data = await sendRequest('/tcp_relay', { command: 'list_models' }, true);
    // Draw bar chart for model losses
    drawBarChart(
        data.data.filter(m => m.perte_moyenne !== null).slice(modelStart, modelStart + 10),
        document.getElementById('models-chart'),
        {
            barWidth: 50,
            maxHeight: 250,
            labelKey: 'id_version',
            valueKey: 'perte_moyenne',
            onClick: m => {
                // Display model details
                document.getElementById('model-details').textContent = `ID: ${m.id_version}, Loss: ${m.perte_moyenne}, Date: ${m.date}`;
                // Set up delete button
                document.getElementById('delete-model').onclick = async () => {
                    if (confirm('Confirm deletion?')) {
                        await sendRequest('/tcp_relay', { command: `delete_model ${m.id_version}` }, true);
                        loadModels();
                    }
                };
            }
        }
    );
}

// Event listeners for page initialization
document.addEventListener('DOMContentLoaded', () => {
    // Check if on index.html
    const isIndex = document.getElementById('grid-container');
    // Check if on admin.html
    const isAdmin = document.getElementById('home');
    
    if (isIndex) {
        // Initialize interactive grid for drawing
        initGrid(document.getElementById('grid-container'), true);
        // Add event listeners for buttons
        document.getElementById('reset-btn').addEventListener('click', resetGrid);
        document.getElementById('submit-btn').addEventListener('click', submitGrid);
        document.getElementById('feedback-btn').addEventListener('click', sendFeedback);
    }
    
    if (isAdmin) {
        // Fetch feedback IDs on page load
        sendRequest('/tcp_relay', { command: 'list_feedbacks' }, true).then(data => {
            feedbackIds = data.data ? data.data.map(f => f.id) : [];
            if (feedbackIds.length && currentTab === 'feedbacks') loadFeedback(currentFeedbackId);
            else if (feedbackIds.length === 0) document.getElementById('no-feedback').style.display = 'block';
        });
        
        // Set up tab navigation
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                // Update tab states
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                currentTab = tab.dataset.tab;
                document.getElementById(currentTab).classList.add('active');
                // Load content based on selected tab
                if (currentTab === 'feedbacks' && feedbackIds.length) loadFeedback(currentFeedbackId);
                else if (currentTab === 'feedbacks') document.getElementById('no-feedback').style.display = 'block';
                else if (currentTab === 'batches') loadBatches();
                else if (currentTab === 'models') loadModels();
            });
        });
        
        // Navigation for feedbacks
        document.getElementById('prev-fb').addEventListener('click', () => {
            const prevIndex = feedbackIds.indexOf(currentFeedbackId) - 1;
            const prevId = feedbackIds[prevIndex >= 0 ? prevIndex : 0];
            if (prevId) loadFeedback(prevId);
        });
        document.getElementById('next-fb').addEventListener('click', () => {
            const nextIndex = feedbackIds.indexOf(currentFeedbackId) + 1;
            const nextId = feedbackIds[nextIndex < feedbackIds.length ? nextIndex : feedbackIds.length - 1];
            if (nextId) loadFeedback(nextId);
        });
        // Search feedback by ID
        document.getElementById('fb-id-input').addEventListener('change', e => {
            const id = parseInt(e.target.value);
            if (feedbackIds.includes(id)) loadFeedback(id);
        });
        // Delete feedback
        document.getElementById('delete-fb').addEventListener('click', async () => {
            if (confirm('Confirm deletion?')) {
                await sendRequest('/tcp_relay', { command: `delete_feedback ${currentFeedbackId}` }, true);
                const currentIndex = feedbackIds.indexOf(currentFeedbackId);
                const nextId = feedbackIds[currentIndex + 1] || feedbackIds[currentIndex - 1] || null;
                if (nextId) loadFeedback(nextId);
                else {
                    document.getElementById('no-feedback').style.display = 'block';
                    document.getElementById('fb-id').textContent = '';
                    document.getElementById('fb-prob-max').textContent = '';
                    document.getElementById('fb-date').textContent = '';
                    document.getElementById('fb-model-id').textContent = '';
                    initGrid(document.querySelector('#feedbacks .grid-container'));
                }
            }
        });
        // Show batch creation form
        document.getElementById('create-batch').addEventListener('click', () => {
            document.getElementById('batch-form').style.display = 'flex';
        });
        // Submit batch creation
        document.getElementById('submit-batch').addEventListener('click', async () => {
            const min = parseInt(document.getElementById('batch-min').value);
            const max = parseInt(document.getElementById('batch-max').value);
            if (min && max && min <= max && feedbackIds.includes(min) && feedbackIds.includes(max)) {
                await sendRequest('/tcp_relay', { command: `add_training_batch ${min} ${max}` }, true);
                document.getElementById('batch-form').style.display = 'none';
                document.getElementById('error-message').textContent = 'Batch created';
            } else {
                document.getElementById('error-message').textContent = 'Invalid IDs';
            }
        });
        // Navigate batches
        document.getElementById('prev-batch').addEventListener('click', () => {
            batchStart = Math.max(0, batchStart - 10);
            loadBatches();
        });
        document.getElementById('next-batch').addEventListener('click', () => {
            batchStart += 10;
            loadBatches();
        });
        // Show model creation form
        document.getElementById('create-model').addEventListener('click', () => {
            document.getElementById('model-form').style.display = 'flex';
        });
        // Submit model creation
        document.getElementById('submit-model').addEventListener('click', async () => {
            const min = parseInt(document.getElementById('model-min').value);
            const max = parseInt(document.getElementById('model-max').value);
            if (min && max && min <= max) {
                await sendRequest('/tcp_relay', { command: `add_model ${min} ${max}` }, true);
                document.getElementById('model-form').style.display = 'none';
                document.getElementById('error-message').textContent = 'Model created';
            } else {
                document.getElementById('error-message').textContent = 'Invalid IDs';
            }
        });
        // Navigate models
        document.getElementById('prev-model').addEventListener('click', () => {
            modelStart = Math.max(0, modelStart - 10);
            loadModels();
        });
        document.getElementById('next-model').addEventListener('click', () => {
            modelStart += 10;
            loadModels();
        });
    }
});