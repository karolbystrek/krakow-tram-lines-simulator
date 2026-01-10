export class StatisticsUI {
    constructor(onClose) {
        this.overlay = document.getElementById('statistics-overlay');
        this.closeBtn = document.getElementById('close-stats-btn');
        this.totalBoardedEl = document.getElementById('stat-total-boarded');
        this.totalAlightedEl = document.getElementById('stat-total-alighted');
        this.chartCanvas = document.getElementById('passenger-chart');
        this.chart = null;
        this.onClose = onClose;

        this.initEvents();
    }

    initEvents() {
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => {
                this.hide();
            });
        }
        
        if (this.overlay) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) {
                    this.hide();
                }
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay && !this.overlay.classList.contains('hidden')) {
                this.hide();
            }
        });
    }

    show(statistics) {
        if (!this.overlay) return;

        if (this.totalBoardedEl) this.totalBoardedEl.textContent = statistics.total_boarded.toLocaleString();
        if (this.totalAlightedEl) this.totalAlightedEl.textContent = statistics.total_alighted.toLocaleString();

        this.renderChart(statistics.hourly_stats);

        this.overlay.classList.remove('hidden');
    }

    hide() {
        if (this.overlay) {
            this.overlay.classList.add('hidden');
        }
        if (this.onClose) {
            this.onClose();
        }
    }

    renderChart(hourlyStats) {
        if (!this.chartCanvas) return;

        if (this.chart) {
            this.chart.destroy();
        }

        // Process data
        const hours = Object.keys(hourlyStats).map(Number).sort((a, b) => a - b);
        const labels = hours.map(h => {
             // Format hour index to HH:00
             // Handle > 24 hours (e.g. 25 -> 01:00 (Next Day)) if needed
             // For simple display:
             const validHour = h % 24;
             const isNextDay = h >= 24;
             const timeStr = `${validHour.toString().padStart(2, '0')}:00`;
             return isNextDay ? `${timeStr} (+1)` : timeStr;
        });

        const boardedData = hours.map(h => hourlyStats[h].boarded);
        const alightedData = hours.map(h => hourlyStats[h].alighted);

        this.chart = new Chart(this.chartCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Boarded',
                        data: boardedData,
                        backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Alighted',
                        data: alightedData,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Passengers'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Hour'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Passengers per Hour'
                    }
                }
            }
        });
    }

    async loadDetailedStats() {
        try {
            const response = await fetch('/api/simulation/stats/detailed');
            const data = await response.json();
            
            this.show(data.global);
            this.renderTopStops(data.top_stops);
            
        } catch (e) {
            console.error("Failed to load detailed stats", e);
        }
    }

    renderTopStops(stops) {
        const tbody = document.querySelector('#top-stops-table tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        stops.forEach(stop => {
            const row = document.createElement('tr');
            row.style.borderBottom = '1px solid #eee';
            row.innerHTML = `
                <td style="padding: 6px;">${stop.name}</td>
                <td style="padding: 6px;">${stop.boarded.toLocaleString()}</td>
                <td style="padding: 6px;">${stop.alighted.toLocaleString()}</td>
            `;
            tbody.appendChild(row);
        });
    }
}
