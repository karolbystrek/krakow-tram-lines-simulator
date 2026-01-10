export class StatisticsUI {
    constructor(onClose) {
        this.overlay = document.getElementById('statistics-overlay');
        this.closeBtn = document.getElementById('close-stats-btn');
        this.totalBoardedEl = document.getElementById('stat-total-boarded');
        this.totalAlightedEl = document.getElementById('stat-total-alighted');
        this.chartCanvas = document.getElementById('passenger-chart');
        this.stopSearchInput = document.getElementById('stop-search-input');
        
        this.chart = null;
        this.onClose = onClose;
        this.allStops = [];

        // Sorting state
        this.sortColumn = 'traffic'; // Default sort by Total Traffic
        this.sortDirection = 'desc'; // Default descending

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

        if (this.stopSearchInput) {
            this.stopSearchInput.addEventListener('input', () => {
                this.filterAndRenderStops();
            });
        }

        // Add sorting listeners
        const sortHeaders = document.querySelectorAll('.sort-header');
        sortHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                if (column) {
                    this.handleSort(column);
                }
            });
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay && !this.overlay.classList.contains('hidden')) {
                this.hide();
            }
        });
    }

    handleSort(column) {
        if (this.sortColumn === column) {
            // Toggle direction if clicking same column
            this.sortDirection = this.sortDirection === 'desc' ? 'asc' : 'desc';
        } else {
            // New column, default to descending
            this.sortColumn = column;
            this.sortDirection = 'desc';
        }
        
        this.updateSortIcons();
        this.filterAndRenderStops();
    }

    updateSortIcons() {
        const sortHeaders = document.querySelectorAll('.sort-header');
        sortHeaders.forEach(header => {
            const icon = header.querySelector('i');
            if (icon) {
                // Reset icon
                icon.className = 'fas fa-sort';
                
                // Update active icon
                if (header.dataset.column === this.sortColumn) {
                    icon.className = this.sortDirection === 'desc' ? 'fas fa-sort-down' : 'fas fa-sort-up';
                }
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

            // Store stops and pre-calculate traffic
            this.allStops = data.top_stops.map(stop => ({
                ...stop,
                traffic: (stop.boarded || 0) + (stop.alighted || 0)
            }));

            // Initial sort and render
            this.updateSortIcons();
            this.filterAndRenderStops();
            
        } catch (e) {
            console.error("Failed to load detailed stats", e);
        }
    }

    filterAndRenderStops() {
        const searchTerm = this.stopSearchInput ? this.stopSearchInput.value.toLowerCase().trim() : '';
        
        // 1. Filter
        let filteredStops = this.allStops.filter(stop => 
            stop.name.toLowerCase().includes(searchTerm)
        );

        // 2. Sort
        filteredStops.sort((a, b) => {
            const valA = a[this.sortColumn] || 0;
            const valB = b[this.sortColumn] || 0;
            
            if (this.sortDirection === 'desc') {
                return valB - valA;
            } else {
                return valA - valB;
            }
        });

        // 3. Limit (only if no search term, to keep initial view light)
        // If user searches, show all matches.
        const stopsToShow = searchTerm ? filteredStops : filteredStops.slice(0, 50);

        this.renderTopStops(stopsToShow);
    }

    renderTopStops(stops) {
        const tbody = document.querySelector('#top-stops-table tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        stops.forEach(stop => {
            const row = document.createElement('tr');
            row.style.borderBottom = '1px solid #eee';
            
            // Format numbers
            const traffic = (stop.traffic || 0).toLocaleString();
            const boarded = (stop.boarded || 0).toLocaleString();
            const alighted = (stop.alighted || 0).toLocaleString();

            row.innerHTML = `
                <td style="padding: 12px;">${stop.name}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums; font-weight: bold;">${traffic}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">${boarded}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">${alighted}</td>
            `;
            tbody.appendChild(row);
        });
    }
}