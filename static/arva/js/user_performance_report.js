/*
 * User Performance Report Charts - Enhanced
 * =========================================
 * Enhanced Chart.js configurations with better styling and clarity
 */

// Chart.js default configuration
Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
Chart.defaults.color = '#64748b';
Chart.defaults.scale.grid.color = '#e2e8f0';
Chart.defaults.scale.grid.borderColor = '#e2e8f0';

document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.reportData === 'undefined') {
        console.error('Report data not found.');
        return;
    }

    const data = window.reportData;

    // Common chart options for bar charts
    const barChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#1e293b',
                titleColor: '#fff',
                bodyColor: '#fff',
                padding: 12,
                cornerRadius: 8,
                displayColors: false,
                callbacks: {
                    label: function(context) {
                        return context.parsed.y + (context.dataset.label.includes('%') ? '%' : '');
                    }
                }
            }
        },
        scales: {
            x: {
                grid: { display: false },
                ticks: {
                    font: { size: 11 },
                    maxRotation: 45,
                    minRotation: 0
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: '#f1f5f9',
                    drawBorder: false
                },
                ticks: {
                    font: { size: 11 },
                    padding: 8
                }
            }
        },
        interaction: {
            intersect: false,
            mode: 'index'
        }
    };

    // Completion Rate Chart
    const completionCtx = document.getElementById('completionChart');
    if (completionCtx) {
        new Chart(completionCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.userLabels,
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: data.userCompletionRates,
                    backgroundColor: 'rgba(59, 130, 246, 0.85)',
                    borderColor: '#3b82f6',
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...barChartOptions,
                scales: {
                    ...barChartOptions.scales,
                    y: {
                        ...barChartOptions.scales.y,
                        max: 100,
                        ticks: {
                            ...barChartOptions.scales.y.ticks,
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    // On-Time Delivery Chart
    const ontimeCtx = document.getElementById('ontimeChart');
    if (ontimeCtx) {
        new Chart(ontimeCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.userLabels,
                datasets: [{
                    label: 'On-Time Rate (%)',
                    data: data.userOntimeRates,
                    backgroundColor: 'rgba(16, 185, 129, 0.85)',
                    borderColor: '#10b981',
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...barChartOptions,
                scales: {
                    ...barChartOptions.scales,
                    y: {
                        ...barChartOptions.scales.y,
                        max: 100,
                        ticks: {
                            ...barChartOptions.scales.y.ticks,
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    // User Distribution Pie Chart
    const userDistCtx = document.getElementById('userDistributionChart');
    if (userDistCtx) {
        new Chart(userDistCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: data.userLabels,
                datasets: [{
                    data: data.userTaskCounts,
                    backgroundColor: [
                        '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
                        '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} tasks (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Status Distribution Chart
    const statusCtx = document.getElementById('statusChart');
    if (statusCtx) {
        new Chart(statusCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Done', 'In Progress', 'Pending', 'Infeasible'],
                datasets: [{
                    data: data.statusCounts,
                    backgroundColor: ['#10b981', '#f59e0b', '#64748b', '#ef4444'],
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '55%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Priority Breakdown
    const priorityCtx = document.getElementById('priorityChart');
    if (priorityCtx) {
        new Chart(priorityCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['P0 - Urgent', 'P1 - High', 'P2 - Medium', 'P3 - Low'],
                datasets: [{
                    data: data.priorityCounts,
                    backgroundColor: ['#ef4444', '#f97316', '#f59e0b', '#10b981'],
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '55%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} tasks (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Weekly Trend
    const weeklyCtx = document.getElementById('weeklyTrendChart');
    if (weeklyCtx) {
        new Chart(weeklyCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.weekLabels,
                datasets: [{
                    label: 'Completed Tasks',
                    data: data.weeklyCompleted,
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderColor: '#10b981',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return `${context.parsed.y} tasks completed`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f1f5f9', drawBorder: false },
                        ticks: {
                            font: { size: 11 },
                            stepSize: 1,
                            padding: 8
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    // Overdue Tasks by User Chart
    const overdueCtx = document.getElementById('overdueChart');
    if (overdueCtx) {
        new Chart(overdueCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.userLabels,
                datasets: [{
                    label: 'Overdue Tasks',
                    data: data.userOverdueCounts,
                    backgroundColor: 'rgba(239, 68, 68, 0.85)',
                    borderColor: '#ef4444',
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...barChartOptions,
                scales: {
                    ...barChartOptions.scales,
                    y: {
                        ...barChartOptions.scales.y,
                        ticks: {
                            ...barChartOptions.scales.y.ticks,
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }
});
