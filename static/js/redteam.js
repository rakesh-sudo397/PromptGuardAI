let redteamChart = null;

async function runRedteamScanner() {
    const promptInput = document.getElementById('txtSystemPrompt');
    const systemPrompt = promptInput.value.trim();
    if (!systemPrompt) {
        alert("Please enter your LLM system instructions to audit.");
        return;
    }

    const btn = document.getElementById('btnRunRedteam');
    const progress = document.getElementById('pnlRedteamProgress');
    const results = document.getElementById('pnlRedteamResults');

    btn.disabled = true;
    progress.style.display = 'flex';
    results.style.display = 'none';

    try {
        const response = await fetch('/api/v1/redteam/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ system_prompt: systemPrompt })
        });

        if (response.status === 401) {
            alert("Security session expired. Please log in again.");
            window.location.href = '/logout';
            return;
        }

        const report = await response.json();
        if (!response.ok) {
            alert(report.detail || "Scanning failed.");
            return;
        }

        progress.style.display = 'none';
        results.style.display = 'block';

        // 1. Render Safety Score and Grades
        const score = report.safety_score;
        const scoreEl = document.getElementById('valRedteamScore');
        scoreEl.innerText = score.toFixed(1) + '%';

        const gradeEl = document.getElementById('valRedteamGrade');
        let gradeLabel = 'A';
        let gradeColor = '#10b981'; // Green
        let gradeClass = 'badge bg-green';

        if (score >= 90.0) {
            gradeLabel = 'GRADE: A (Excellent)';
            gradeColor = '#10b981';
            scoreEl.style.color = '#10b981';
        } else if (score >= 75.0) {
            gradeLabel = 'GRADE: B (Secure)';
            gradeColor = '#a855f7'; // Purple
            scoreEl.style.color = '#a855f7';
        } else if (score >= 50.0) {
            gradeLabel = 'GRADE: C (Vulnerable)';
            gradeColor = '#f59e0b'; // Amber
            scoreEl.style.color = '#f59e0b';
        } else {
            gradeLabel = 'GRADE: F (Critical)';
            gradeColor = '#f43f5e'; // Red
            scoreEl.style.color = '#f43f5e';
        }

        gradeEl.innerText = gradeLabel;
        gradeEl.style.backgroundColor = gradeColor;

        // 2. Render Categories Bar Chart
        renderRedteamChart(report.splits);

        // 3. Render Sample Vulnerabilities Table
        const vulnerabilitiesBody = document.getElementById('tblRedteamVulnerabilities');
        vulnerabilitiesBody.innerHTML = '';

        if (report.failed_attacks.length === 0) {
            vulnerabilitiesBody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; color: #10b981; font-weight: bold; padding: 1.5rem;">
                        ✓ Secure Prompt! No simulated attacks bypassed your safety instructions.
                    </td>
                </tr>
            `;
        } else {
            report.failed_attacks.forEach(atk => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td style="text-align: left; font-family: monospace; font-size: 0.85rem; word-break: break-all;">
                        ${atk.prompt}
                    </td>
                    <td><strong>${atk.category}</strong></td>
                    <td style="color: #f43f5e; font-weight: bold;">${(atk.risk_score * 100).toFixed(1)}%</td>
                `;
                vulnerabilitiesBody.appendChild(row);
            });
        }

    } catch (err) {
        console.error("Red-teaming client execution error:", err);
        alert("Failed to communicate with auditing server.");
    } finally {
        btn.disabled = false;
        progress.style.display = 'none';
    }
}

function renderRedteamChart(splits) {
    const categories = Object.keys(splits); // ["Override", "Roleplay", "Leakage"]
    const data = categories.map(cat => splits[cat].block_rate);

    const options = {
        series: [{
            name: 'Block Rate',
            data: data
        }],
        chart: {
            type: 'bar',
            height: 180,
            background: 'transparent',
            toolbar: { show: false },
            foreColor: '#94a3b8',
            fontFamily: 'Inter, sans-serif'
        },
        plotOptions: {
            bar: {
                borderRadius: 6,
                horizontal: true,
                barHeight: '55%',
                distributed: true
            }
        },
        colors: ['#a855f7', '#6366f1', '#f43f5e'],
        dataLabels: {
            enabled: true,
            formatter: function (val) {
                return val.toFixed(0) + "%";
            },
            style: {
                colors: ['#fff'],
                fontFamily: 'Inter',
                fontWeight: 'bold'
            }
        },
        xaxis: {
            categories: categories,
            max: 100,
            labels: { show: true, style: { colors: '#64748b' } }
        },
        yaxis: {
            labels: { style: { colors: '#64748b', fontWeight: 'bold' } }
        },
        grid: {
            borderColor: 'rgba(255, 255, 255, 0.02)',
            xaxis: { lines: { show: true } },
            yaxis: { lines: { show: false } }
        },
        legend: { show: false },
        tooltip: {
            theme: 'dark',
            x: { show: true },
            style: { fontSize: '0.9rem', fontFamily: 'Inter' }
        }
    };

    if (redteamChart) {
        redteamChart.updateOptions(options);
    } else {
        redteamChart = new ApexCharts(document.querySelector("#redteamChart"), options);
        redteamChart.render();
    }
}
