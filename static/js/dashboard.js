let threatChart = null;
let latencyChart = null;

// Fetch metrics, update charts, load calibration settings, and logs
async function fetchSystemStats() {
    try {
        // 1. Fetch telemetry metrics
        const resMetrics = await fetch('/api/v1/metrics');
        const data = await resMetrics.json();
        
        document.getElementById('valTotal').innerText = data.total_scans;
        document.getElementById('valBlocked').innerText = data.blocked_scans;
        document.getElementById('valAvgRisk').innerText = (data.average_risk * 100).toFixed(2) + '%';
        document.getElementById('valAvgLatency').innerText = data.average_latency + ' ms';
        
        // 2. Populate Category Table
        const tableBody = document.getElementById('tblDistributionBody');
        tableBody.innerHTML = '';
        const categories = Object.keys(data.threat_distribution);
        if (categories.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--text-secondary);">No scan telemetry logged.</td></tr>`;
        } else {
            categories.forEach(cat => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${cat}</strong></td>
                    <td>${data.threat_distribution[cat]}</td>
                `;
                tableBody.appendChild(row);
            });
        }

        // 3. Fetch Recent Audit Logs
        const resLogs = await fetch('/api/v1/logs');
        const logs = await resLogs.json();

        const logsBody = document.getElementById('tblLogsBody');
        logsBody.innerHTML = '';

        if (logs.length === 0) {
            logsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No logs found.</td></tr>`;
        } else {
            logs.forEach(log => {
                const row = document.createElement('tr');
                
                const dateObj = new Date(log.timestamp);
                const cleanTime = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                
                const cleanPrompt = log.prompt_text.length > 40 
                    ? log.prompt_text.slice(0, 37) + "..." 
                    : log.prompt_text;

                const badgeClass = log.is_blocked === 1 ? 'badge bg-red' : 'badge bg-green';
                const statusLabel = log.is_blocked === 1 ? 'Blocked' : 'Passed';

                row.innerHTML = `
                    <td>${cleanTime}</td>
                    <td title="${log.prompt_text}">"${cleanPrompt}"</td>
                    <td>${(log.risk_score * 100).toFixed(1)}%</td>
                    <td>${log.category}</td>
                    <td><span class="${badgeClass}">${statusLabel}</span></td>
                `;
                logsBody.appendChild(row);
            });
        }

        // 4. Render and Update Charts
        renderCharts(data.threat_distribution, logs);

    } catch (err) {
        console.error("Dashboard error: ", err);
    }
}

function renderCharts(threatDistribution, logs) {
    const categories = Object.keys(threatDistribution);
    const counts = Object.values(threatDistribution);

    const threatOptions = {
        series: counts.length > 0 ? counts : [1],
        chart: {
            type: 'donut',
            height: 250,
            foreColor: '#94a3b8'
        },
        labels: counts.length > 0 ? categories : ["No Data"],
        colors: ['#10b981', '#6366f1', '#a855f7', '#f43f5e', '#f59e0b'],
        theme: { mode: 'dark' },
        legend: { position: 'bottom' },
        dataLabels: { enabled: false },
        plotOptions: {
            pie: {
                donut: {
                    size: '70%',
                    labels: { show: false }
                }
            }
        }
    };

    if (threatChart) {
        threatChart.updateOptions(threatOptions);
    } else {
        threatChart = new ApexCharts(document.querySelector("#threatChart"), threatOptions);
        threatChart.render();
    }

    const latencyData = logs.map(l => l.latency_ms).reverse();
    const timeLabels = logs.map(l => {
        const dateObj = new Date(l.timestamp);
        return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }).reverse();

    const latencyOptions = {
        series: [{
            name: 'Latency (ms)',
            data: latencyData.length > 0 ? latencyData : [0]
        }],
        chart: {
            type: 'area',
            height: 250,
            toolbar: { show: false },
            foreColor: '#94a3b8'
        },
        stroke: { curve: 'smooth', width: 2 },
        colors: ['#a855f7'],
        xaxis: {
            categories: timeLabels.length > 0 ? timeLabels : ["No Logs"],
            labels: { show: false }
        },
        grid: { borderColor: 'rgba(255, 255, 255, 0.05)' },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.3,
                opacityTo: 0.05,
                stops: [0, 90, 100]
            }
        },
        theme: { mode: 'dark' }
    };

    if (latencyChart) {
        latencyChart.updateOptions(latencyOptions);
    } else {
        latencyChart = new ApexCharts(document.querySelector("#latencyChart"), latencyOptions);
        latencyChart.render();
    }
}

// ----------------------------------------------------
// TUNING PANEL CONFIG MANAGEMENT
// ----------------------------------------------------
async function loadCalibrationConfig() {
    try {
        const res = await fetch('/api/v1/config');
        const config = await res.json();
        
        // Populate Sliders and Text labels
        document.getElementById('threshold-slider').value = config.decision_threshold;
        document.getElementById('valDecisionThreshold').innerText = config.decision_threshold;
        
        document.getElementById('dampen-len-slider').value = config.dampening.length_threshold;
        document.getElementById('valDampenLen').innerText = config.dampening.length_threshold;
        
        document.getElementById('dampen-caps-slider').value = config.dampening.caps_threshold;
        document.getElementById('valDampenCaps').innerText = (config.dampening.caps_threshold * 100).toFixed(0) + '%';
        
        document.getElementById('dampen-spec-slider').value = config.dampening.special_threshold;
        document.getElementById('valDampenSpec').innerText = (config.dampening.special_threshold * 100).toFixed(0) + '%';
        
        document.getElementById('boost-caps-slider').value = config.boosting.caps_threshold;
        document.getElementById('valBoostCaps').innerText = (config.boosting.caps_threshold * 100).toFixed(0) + '%';
        
        document.getElementById('boost-spec-slider').value = config.boosting.special_threshold;
        document.getElementById('valBoostSpec').innerText = (config.boosting.special_threshold * 100).toFixed(0) + '%';
        
    } catch (err) {
        console.error("Failed to load calibration configuration parameters: ", err);
    }
}

function updateSliderLabel(sliderId, labelId, isPercentage = false) {
    const val = document.getElementById(sliderId).value;
    const label = document.getElementById(labelId);
    if (isPercentage) {
        label.innerText = (parseFloat(val) * 100).toFixed(0) + '%';
    } else {
        label.innerText = val;
    }
}

async function saveCalibrationConfig() {
    const btn = document.getElementById('btnSaveConfig');
    btn.innerText = 'Saving Config...';
    btn.disabled = true;

    const payload = {
        decision_threshold: parseFloat(document.getElementById('threshold-slider').value),
        dampening: {
            length_threshold: parseInt(document.getElementById('dampen-len-slider').value),
            caps_threshold: parseFloat(document.getElementById('dampen-caps-slider').value),
            special_threshold: parseFloat(document.getElementById('dampen-spec-slider').value),
            max_raw_prob: 0.55,
            factor: 0.5
        },
        boosting: {
            caps_threshold: parseFloat(document.getElementById('boost-caps-slider').value),
            special_threshold: parseFloat(document.getElementById('boost-spec-slider').value),
            factor: 1.3
        }
    };

    try {
        const res = await fetch('/api/v1/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            const statusLabel = document.getElementById('configStatusMsg');
            statusLabel.style.display = 'inline';
            setTimeout(() => { statusLabel.style.display = 'none'; }, 3000);
        } else {
            alert("Failed to save configuration settings.");
        }
    } catch (err) {
        alert("Configuration save communication error: " + err);
    } finally {
        btn.innerText = 'Save Active Config';
        btn.disabled = false;
    }
}

// ----------------------------------------------------
// MODEL EVALUATION MANAGEMENT
// ----------------------------------------------------
async function runPerformanceEvaluation() {
    const evalBtn = document.getElementById('btnRunEvaluation');
    const loadingPanel = document.getElementById('evalLoading');
    const resultsPanel = document.getElementById('evalResultsPanel');

    evalBtn.disabled = true;
    loadingPanel.style.display = 'block';
    resultsPanel.style.display = 'none';

    try {
        const res = await fetch('/api/v1/evaluate', { method: 'POST' });
        const data = await res.json();

        loadingPanel.style.display = 'none';
        resultsPanel.style.display = 'block';

        // 1. Render Metrics summary
        document.getElementById('valEvalAccuracy').innerText = (data.accuracy * 100).toFixed(2) + '%';
        
        const metricsBody = document.getElementById('tblEvalMetricsBody');
        metricsBody.innerHTML = '';
        
        Object.keys(data.class_metrics).forEach(clsName => {
            const m = data.class_metrics[clsName];
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${clsName}</strong></td>
                <td>${(m.precision * 100).toFixed(1)}%</td>
                <td>${(m.recall * 100).toFixed(1)}%</td>
                <td>${(m.f1 * 100).toFixed(1)}%</td>
            `;
            metricsBody.appendChild(row);
        });

        // 2. Render Heatmap Confusion Matrix Grid
        const classes = ["Clean", "Override", "Roleplay", "Leakage"];
        const matrix = data.confusion_matrix;
        
        const matrixBody = document.getElementById('tblConfusionMatrixBody');
        matrixBody.innerHTML = '';

        // Generate headers dynamically
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = '<th>Actual \\ Predicted</th>';
        classes.forEach(c => {
            headerRow.innerHTML += `<th>${c}</th>`;
        });
        matrixBody.appendChild(headerRow);

        for (let i = 0; i < 4; i++) {
            const row = document.createElement('tr');
            row.innerHTML = `<td><strong>${classes[i]}</strong></td>`;
            
            // Calculate row total for shading percentages
            const rowTotal = matrix[i].reduce((a, b) => a + b, 0) || 1;
            
            for (let j = 0; j < 4; j++) {
                const count = matrix[i][j];
                const pct = (count / rowTotal) * 100;
                
                let cellColor = 'rgba(255, 255, 255, 0.02)';
                let textColor = '#94a3b8';
                
                if (i === j) { // True Positives (Diagonal)
                    if (count > 0) {
                        cellColor = `rgba(16, 185, 129, ${0.1 + (pct / 100) * 0.75})`;
                        textColor = '#10b981';
                    }
                } else { // Errors / Off-diagonals
                    if (count > 0) {
                        cellColor = `rgba(244, 63, 94, ${0.1 + (pct / 100) * 0.75})`;
                        textColor = '#f43f5e';
                    }
                }

                row.innerHTML += `
                    <td style="background-color: ${cellColor}; color: ${textColor}; font-weight: bold; text-align: center; font-size: 1.1rem; transition: background 0.3s;" title="Percentage: ${pct.toFixed(0)}%">
                        ${count}
                    </td>
                `;
            }
            matrixBody.appendChild(row);
        }

    } catch (err) {
        alert("Evaluation API communication error: " + err);
        loadingPanel.style.display = 'none';
    } finally {
        evalBtn.disabled = false;
    }
}

// Initial stats fetching and configuration load
document.addEventListener('DOMContentLoaded', () => {
    fetchSystemStats();
    loadCalibrationConfig();
    setInterval(fetchSystemStats, 10000); // refresh telemetry every 10s
});
