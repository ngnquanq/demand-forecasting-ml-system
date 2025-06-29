document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('predictForm');
    const tableHead = document.querySelector('#resultsTable thead');
    const tableBody = document.querySelector('#resultsTable tbody');
    const chartCanvas = document.getElementById('forecastChart');
    const ctx = chartCanvas.getContext('2d');
    const downloadCsvBtn = document.getElementById('downloadCsvBtn'); // Renamed
    const downloadChartBtn = document.getElementById('downloadChartBtn'); // New button
    const loadingIndicator = document.getElementById('loadingIndicator');

    let chart;
    let latestCSV = '';
    let currentMode = 'file-upload'; // 'file-upload' or 'db-query'

    // Form elements
    const fileInput = document.getElementById('file');
    const forecastHoursInput = document.getElementById('forecast_hours');
    const windowSizesInput = document.getElementById('window_sizes');
    const startTimeInput = document.getElementById('start_time');
    const stopTimeInput = document.getElementById('stop_time');
    const dataRangeDisplay = document.getElementById('data-range-display');

    // Tab elements
    const tabs = document.querySelectorAll('.tabs li');
    const fileUploadContent = document.getElementById('file-upload-content');
    const dbQueryContent = document.getElementById('db-query-content');

    // --- Utility Functions ---

    function showLoading() {
        loadingIndicator.classList.add('is-active');
    }

    function hideLoading() {
        loadingIndicator.classList.remove('is-active');
    }

    function formatDateForInput(isoString) {
        if (!isoString) return '';
        // input type="datetime-local" expects 'YYYY-MM-DDTHH:MM'
        const dt = new Date(isoString);
        const year = dt.getFullYear();
        const month = String(dt.getMonth() + 1).padStart(2, '0');
        const day = String(dt.getDate()).padStart(2, '0');
        const hours = String(dt.getHours()).padStart(2, '0');
        const minutes = String(dt.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    function formatDateForDisplay(isoString) {
        if (!isoString) return 'N/A';
        const options = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' };
        return new Date(isoString).toLocaleString(undefined, options);
    }

    function buildCSV(prediction) {
        if (!prediction || Object.keys(prediction).length === 0) return '';
        const firstKey = Object.keys(prediction)[0];
        const cols = Object.keys(prediction[firstKey]);
        const lines = [];
        lines.push(['date_time', ...cols].join(','));
        for (const dt of Object.keys(prediction)) {
            const row = cols.map(c => prediction[dt][c]);
            lines.push([dt, ...row].join(','));
        }
        return lines.join('\n');
    }

    function populateTableAndChart(prediction) {
        if (!prediction || Object.keys(prediction).length === 0) {
            tableHead.innerHTML = '';
            tableBody.innerHTML = '<tr><td colspan="5" class="has-text-centered">No prediction data available.</td></tr>'; // Adjust colspan as needed
            if (chart) chart.destroy();
            chartCanvas.style.display = 'none'; // Hide chart if no data
            downloadCsvBtn.style.display = 'none'; // Hide CSV button
            downloadChartBtn.style.display = 'none'; // Hide Chart button
            latestCSV = '';
            return;
        }

        chartCanvas.style.display = 'block'; // Show chart if data exists
        downloadCsvBtn.style.display = 'inline-block'; // Show CSV button
        downloadChartBtn.style.display = 'inline-block'; // Show Chart button

        const firstKey = Object.keys(prediction)[0];
        const cols = Object.keys(prediction[firstKey]);
        tableHead.innerHTML = '<tr><th>Date Time</th>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
        tableBody.innerHTML = '';
        const labels = [];
        const predVals = [];
        const realVals = [];
        for (const dt of Object.keys(prediction)) {
            const row = prediction[dt];
            const cells = cols.map(c => `<td>${row[c]}</td>`).join('');
            tableBody.insertAdjacentHTML('beforeend', `<tr><td>${dt}</td>${cells}</tr>`);
            labels.push(dt);
            predVals.push(row['predicted_users']);
            // Only push real_users if it exists to avoid errors on pure future predictions
            if (row['real_users'] !== undefined) {
                 realVals.push(row['real_users']);
            } else {
                 realVals.push(null); // Or some other placeholder if no actual data
            }
        }
        latestCSV = buildCSV(prediction);

        if (chart) chart.destroy();
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {label: 'Predicted Users', data: predVals, borderColor: 'red', fill: false, tension: 0.1},
                    {label: 'Actual Users', data: realVals, borderColor: 'blue', fill: false, tension: 0.1}
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date Time'
                        },
                        // --- START CHART.JS GRID LINE REMOVAL ---
                        grid: {
                            display: false, // Hides vertical grid lines
                            drawBorder: false // Hides the axis line itself (optional, but often looks cleaner)
                        },
                        // --- END CHART.JS GRID LINE REMOVAL ---
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Users'
                        },
                        // --- START CHART.JS GRID LINE REMOVAL ---
                        grid: {
                            display: false, // Hides horizontal grid lines
                            drawBorder: false // Hides the axis line itself (optional)
                        },
                        // --- END CHART.JS GRID LINE REMOVAL ---
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                    }
                }
            }
        });
    }

    // --- Initial Load & Event Listeners ---

    // Fetch min/max dates on page load for DB query mode
    async function fetchMinMaxDates() {
        showLoading();
        try {
            const res = await fetch('/data-range');
            const data = await res.json();
            if (data.min_time && data.max_time) {
                const minTimeDisplay = formatDateForDisplay(data.min_time);
                const maxTimeDisplay = formatDateForDisplay(data.max_time);
                dataRangeDisplay.textContent = `From ${minTimeDisplay} to ${maxTimeDisplay}`;

                // Set default values for start/stop time inputs (e.g., last 24 hours of available data)
                const defaultStartTime = new Date(new Date(data.max_time).getTime() - (24 * 60 * 60 * 1000)); // 24 hours before max
                startTimeInput.value = formatDateForInput(defaultStartTime.toISOString());
                stopTimeInput.value = formatDateForInput(data.max_time);
            } else {
                dataRangeDisplay.textContent = 'No data available in the database.';
            }
        } catch (error) {
            console.error('Error fetching data range:', error);
            dataRangeDisplay.textContent = 'Error loading data range.';
        } finally {
            hideLoading();
        }
    }

    // Tab switching logic
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('is-active'));
            tab.classList.add('is-active');

            fileUploadContent.classList.add('is-hidden');
            dbQueryContent.classList.add('is-hidden');

            currentMode = tab.dataset.tab;

            if (currentMode === 'file-upload') {
                fileUploadContent.classList.remove('is-hidden');
                fileInput.setAttribute('required', 'true');
                startTimeInput.removeAttribute('required');
                stopTimeInput.removeAttribute('required');
            } else { // db-query
                dbQueryContent.classList.remove('is-hidden');
                fileInput.removeAttribute('required');
                startTimeInput.setAttribute('required', 'true');
                stopTimeInput.setAttribute('required', 'true');
                fetchMinMaxDates(); // Fetch dates when switching to DB mode
            }
        });
    });

    // Form submission handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        showLoading();

        let endpoint = '';
        let requestBody; // This will hold FormData or be null

        const forecastHours = forecastHoursInput.value;
        const windowSizes = windowSizesInput.value;

        try {
            if (currentMode === 'file-upload') {
                if (!fileInput.files.length) {
                    alert('Please select a CSV file.');
                    hideLoading();
                    return;
                }
                
                // Construct URLSearchParams for forecast_hours and window_sizes
                const params = new URLSearchParams({
                    forecast_hours: forecastHours,
                    window_sizes: windowSizes
                });
                
                // The endpoint now includes the query parameters
                endpoint = `/predict-tuning?${params.toString()}`;
                
                // Create FormData for the file only
                requestBody = new FormData();
                requestBody.append('file', fileInput.files[0]);

            } else { // db-query
                const startTime = startTimeInput.value;
                const stopTime = stopTimeInput.value;

                if (!startTime || !stopTime) {
                    alert('Please select start and stop times.');
                    hideLoading();
                    return;
                }

                // Convert datetime-local format (YYYY-MM-DDTHH:MM) to the required format (YYYY-MM-DD HH:MM:SS+00)
                const formattedStartTime = new Date(startTime).toISOString().replace(/\.000Z$/, '+00');
                const formattedStopTime = new Date(stopTime).toISOString().replace(/\.000Z$/, '+00');

                endpoint = '/predict-tuning-db';
                const params = new URLSearchParams({
                    forecast_hours: forecastHours,
                    window_sizes: windowSizes,
                    start_time: formattedStartTime,
                    stop_time: formattedStopTime
                });
                endpoint = `${endpoint}?${params.toString()}`;
                requestBody = null; // No body needed for POST with query params
            }

            const res = await fetch(endpoint, {
                method: 'POST',
                body: requestBody, // This will be FormData for file upload, null for DB query
                // No specific headers for FormData, fetch sets it automatically
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || `Server error: ${res.status} ${res.statusText}`);
            }

            const data = await res.json();
            populateTableAndChart(data.prediction);
            alert(`Prediction successful! MAE: ${data.mae !== null ? data.mae.toFixed(2) : 'N/A'}`); // Handle potential null MAE

        } catch (error) {
            console.error('Prediction error:', error);
            alert(`Prediction failed: ${error.message || error}`);
            populateTableAndChart(null); // Clear table/chart on error
        } finally {
            hideLoading();
        }
    });

    // Event listener for CSV download button (updated ID)
    downloadCsvBtn.addEventListener('click', () => {
        if (!latestCSV) {
            alert('No data to download.');
            return;
        }
        const blob = new Blob([latestCSV], {type: 'text/csv'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prediction.csv';
        a.click();
        URL.revokeObjectURL(url);
    });

    // NEW Event listener for Chart download button
    downloadChartBtn.addEventListener('click', () => {
        if (chart) {
            const imageData = chart.toBase64Image('image/png', 1); // Get image data as PNG
            const a = document.createElement('a');
            a.href = imageData;
            a.download = 'forecast_chart.png'; // Suggested filename
            a.click();
        } else {
            alert('No chart data to download.');
        }
    });

    // Initial fetch of min/max dates if DB query tab is active by default
    // Or, more robustly, fetch when the tab is actually switched to.
    // By default, 'file-upload' is active, so we don't fetch initially for 'db-query'.
    // The `fetchMinMaxDates()` is called when `db-query` tab is clicked.
});