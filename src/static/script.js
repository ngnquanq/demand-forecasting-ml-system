+77-0
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('predictForm');
    const tableHead = document.querySelector('#resultsTable thead');
    const tableBody = document.querySelector('#resultsTable tbody');
    const ctx = document.getElementById('forecastChart').getContext('2d');
    let chart;
    let latestCSV = '';

    function buildCSV(prediction) {
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
        if (!prediction) return;
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
            realVals.push(row['real_users']);
        }
        latestCSV = buildCSV(prediction);
        if (chart) chart.destroy();
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {label: 'Predicted', data: predVals, borderColor: 'red', fill: false},
                    {label: 'Actual', data: realVals, borderColor: 'blue', fill: false}
                ]
            },
            options: {responsive: true, scales:{x:{display:false}}}
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('file');
        if (!fileInput.files.length) return;
        const forecastHours = document.getElementById('forecast_hours').value;
        const windowSizes = document.getElementById('window_sizes').value;
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        const params = new URLSearchParams({forecast_hours: forecastHours, window_sizes: windowSizes});
        const res = await fetch(`/predict-tuning?${params}`, {method:'POST', body: formData});
        const data = await res.json();
        populateTableAndChart(data.prediction);
    });

    document.getElementById('downloadBtn').addEventListener('click', () => {
        if (!latestCSV) return;
        const blob = new Blob([latestCSV], {type: 'text/csv'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prediction.csv';
        a.click();
        URL.revokeObjectURL(url);
    });
});