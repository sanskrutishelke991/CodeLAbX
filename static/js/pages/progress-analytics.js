"use strict";

const analyticsRuntime = document.getElementById('analyticsRuntime');
    const consistency = Number(analyticsRuntime.dataset.consistency);
    const consistencyRemaining = Number(analyticsRuntime.dataset.consistencyRemaining);
    const hasTopicData = analyticsRuntime.dataset.hasTopicData === 'true';
    const hasTestData = analyticsRuntime.dataset.hasTestData === 'true';
    const weeklyActivityLabels = JSON.parse(document.getElementById('weekly-activity-labels').textContent);
    const weeklyActivityData = JSON.parse(document.getElementById('weekly-activity-data').textContent);
    const topicLabels = JSON.parse(document.getElementById('topic-labels').textContent);
    const topicData = JSON.parse(document.getElementById('topic-data').textContent);
    const testLabels = JSON.parse(document.getElementById('test-labels').textContent);
    const testData = JSON.parse(document.getElementById('test-data').textContent);
    Chart.defaults.color = '#A1A1AA';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
    Chart.defaults.font.family = "'Inter', sans-serif";

    // ========== STUDY TIME CHART - TEAL AREA ==========
    const studyCtx = document.getElementById('studyTimeChart').getContext('2d');
    const studyGradient = studyCtx.createLinearGradient(0, 0, 0, 300);
    studyGradient.addColorStop(0, 'rgba(20, 184, 166, 0.5)');
    studyGradient.addColorStop(1, 'rgba(20, 184, 166, 0)');

    new Chart(studyCtx, {
        type: 'line',
        data: {
            labels: weeklyActivityLabels,
            datasets: [{
                label: 'Minutes',
                data: weeklyActivityData,
                borderColor: '#14B8A6',
                backgroundColor: studyGradient,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#14B8A6',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 8,
                pointHoverBackgroundColor: '#14B8A6',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(20, 184, 166, 0.95)',
                    padding: 12,
                    cornerRadius: 8,
                    titleFont: { size: 12, weight: 'bold' },
                    bodyFont: { size: 14, weight: 'bold' },
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return context.parsed.y + ' minutes';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#71717A', font: { size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#71717A', font: { size: 11 }, maxRotation: 45, minRotation: 45 }
                }
            }
        }
    });

    // ========== CONSISTENCY RING - PINK GLOW ==========
    const consistencyCtx = document.getElementById('consistencyChart').getContext('2d');
    new Chart(consistencyCtx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [consistency, consistencyRemaining],
                backgroundColor: [
                    'rgba(236, 72, 153, 1)',
                    'rgba(255, 255, 255, 0.05)'
                ],
                borderWidth: 0,
                borderRadius: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            }
        },
        plugins: [{
            id: 'centerText',
            afterDraw: (chart) => {
                const { ctx, chartArea: { top, width, height } } = chart;
                ctx.save();

                // Percentage
                ctx.fillStyle = '#FAFAFA';
                ctx.font = 'bold 42px Inter Tight';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`${consistency}%`, width / 2, top + height / 2 - 8);

                // Label
                ctx.fillStyle = '#71717A';
                ctx.font = '600 11px Inter';
                ctx.fillText('CONSISTENT', width / 2, top + height / 2 + 20);

                ctx.restore();
            }
        }]
    });

    // ========== TOPIC DISTRIBUTION - RAINBOW ==========
    if (hasTopicData) {
    const topicCtx = document.getElementById('topicChart').getContext('2d');
    new Chart(topicCtx, {
        type: 'polarArea',
        data: {
            labels: topicLabels,
            datasets: [{
                data: topicData,
                backgroundColor: [
                    'rgba(168, 85, 247, 0.8)',   // Purple
                    'rgba(236, 72, 153, 0.8)',   // Pink
                    'rgba(245, 158, 11, 0.8)',   // Amber
                    'rgba(14, 165, 233, 0.8)',   // Sky
                    'rgba(20, 184, 166, 0.8)',   // Teal
                    'rgba(16, 185, 129, 0.8)',   // Green
                ],
                borderColor: [
                    '#A855F7',
                    '#EC4899',
                    '#F59E0B',
                    '#0EA5E9',
                    '#14B8A6',
                    '#10B981',
                ],
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#A1A1AA',
                        font: { size: 11, weight: '600' },
                        padding: 12,
                        boxWidth: 12,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(30, 30, 35, 0.95)',
                    padding: 12,
                    cornerRadius: 8,
                    titleFont: { size: 12, weight: 'bold' },
                    bodyFont: { size: 14, weight: 'bold' },
                }
            },
            scales: {
                r: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { display: false },
                    angleLines: { color: 'rgba(255, 255, 255, 0.05)' }
                }
            }
        }
    });
    } else {
    document.getElementById('topicChart').parentElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-tertiary);"><div style="text-align: center;"><i class="bi bi-pie-chart" style="font-size: 3rem; opacity: 0.3;"></i><p style="margin-top: 12px;">Start a learning path to see topic distribution</p></div></div>';
    }

    // ========== TEST PERFORMANCE - AMBER BARS ==========
    if (hasTestData) {
    const testCtx = document.getElementById('testChart').getContext('2d');
    const testGradient = testCtx.createLinearGradient(0, 0, 0, 220);
    testGradient.addColorStop(0, 'rgba(245, 158, 11, 1)');
    testGradient.addColorStop(1, 'rgba(245, 158, 11, 0.3)');

    new Chart(testCtx, {
        type: 'bar',
        data: {
            labels: testLabels,
            datasets: [{
                label: 'Score %',
                data: testData,
                backgroundColor: testGradient,
                borderColor: '#F59E0B',
                borderWidth: 2,
                borderRadius: 8,
                hoverBackgroundColor: '#FBBF24',
                hoverBorderColor: '#F59E0B',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(245, 158, 11, 0.95)',
                    padding: 12,
                    cornerRadius: 8,
                    titleFont: { size: 12, weight: 'bold' },
                    bodyFont: { size: 14, weight: 'bold' },
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: {
                        color: '#71717A',
                        font: { size: 11 },
                        callback: function(value) { return value + '%'; }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#71717A', font: { size: 11 } }
                }
            }
        }
    });
    } else {
    document.getElementById('testChart').parentElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-tertiary);"><div style="text-align: center;"><i class="bi bi-clipboard-check" style="font-size: 3rem; opacity: 0.3;"></i><p style="margin-top: 12px;">Take tests to see performance trends</p></div></div>';
    }
