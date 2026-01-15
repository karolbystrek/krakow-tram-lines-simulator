

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
        this.allTrams = [];

        // Sorting state
        this.sortColumn = 'traffic'; // Default sort by Total Traffic
        this.sortDirection = 'desc'; // Default descending

        // Chart modal elements
        this.chartModal = null;
        this.chartModalCanvas = null;

        this.initEvents();
        this.createChartModal();
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

        if (this.tramSearchInput) {
            this.tramSearchInput.addEventListener('input', () => {
                this.filterAndRenderTrams();
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

            await this.loadTramStats();

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

            const traffic = (stop.traffic || 0).toLocaleString();
            const boarded = (stop.boarded || 0).toLocaleString();
            const alighted = (stop.alighted || 0).toLocaleString();

            row.innerHTML = `
                <td style="padding: 12px;">${stop.name}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums; font-weight: bold;">${traffic}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">${boarded}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">${alighted}</td>
                <td style="padding: 12px; text-align: center;">
                    <button class="btn btn-small btn-chart" data-stop-id="${stop.id}" title="View passenger chart for ${stop.name}">
                        <i class="fas fa-chart-line"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

        const chartButtons = tbody.querySelectorAll('.btn-chart');
        chartButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const stopId = e.currentTarget.dataset.stopId;
                this.showStopChart(stopId);
            });
        });
    }

    aggregateHalfHour(historyData) {
    const buckets = new Map();

    historyData.forEach(([time, value]) => {
        const bucketStart = Math.floor(time / 30) * 30;

        if (!buckets.has(bucketStart)) {
            buckets.set(bucketStart, { sum: 0, count: 0 });
        }

        const bucket = buckets.get(bucketStart);
        bucket.sum += value;
        bucket.count += 1;
    });

    const times = [];
    const values = [];

    [...buckets.entries()]
        .sort((a, b) => a[0] - b[0])
        .forEach(([bucketStart, { sum, count }]) => {
            times.push(bucketStart);
            values.push(sum / count); // average
        });

    return { times, values };
}


    createChartModal() {
        this.chartModal = document.createElement('div');
        this.chartModal.className = 'overlay hidden';
        this.chartModal.innerHTML = `
            <div class="overlay-content chart-modal-content">
                <div class="modal-header">
                    <h2 id="chart-modal-title">Passenger Chart</h2>
                    <button id="close-chart-modal-btn" class="close-modal-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <canvas id="individual-chart-canvas" width="800" height="400"></canvas>
                </div>
            </div>
        `;
        document.body.appendChild(this.chartModal);
        const closeBtn = this.chartModal.querySelector('#close-chart-modal-btn');
        closeBtn.addEventListener('click', () => this.hideChartModal());

        this.chartModal.addEventListener('click', (e) => {
            if (e.target === this.chartModal) {
                this.hideChartModal();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.chartModal && !this.chartModal.classList.contains('hidden')) {
                this.hideChartModal();
            }
        });

        this.chartModalCanvas = this.chartModal.querySelector('#individual-chart-canvas');
    }

    async showStopChart(stopId) {
        try {
            const response = await fetch(`/api/simulation/stats/stop/${stopId}`);
            const data = await response.json();

            const stopName = this.allStops.find(s => s.id === stopId)?.name || `Stop ${stopId}`;
            this.showChartModal(`Waiting Passengers at ${stopName}`, data.history, 'Waiting Passengers', 'rgba(75, 192, 192, 1)');
        } catch (e) {
            console.error("Failed to load stop chart", e);
        }
    }

    async showTramChart(tramId) {
        try {
            const response = await fetch(`/api/simulation/stats/tram/${tramId}`);
            const data = await response.json();

            const tram = this.allTrams.find(t => t.id === tramId);
            const tramName = tram ? `Line ${tram.line} (${tramId})` : `Tram ${tramId}`;
            this.showChartModal(`Occupancy for ${tramName}`, data.history, 'Occupancy', 'rgba(255, 159, 64, 1)');
        } catch (e) {
            console.error("Failed to load tram chart", e);
        }
    }

    showChartModal(title, historyData, label, color) {
    if (!this.chartModal || !this.chartModalCanvas) return;

    const titleEl = this.chartModal.querySelector('#chart-modal-title');
    if (titleEl) titleEl.textContent = title;

    // 🔹 Aggregate into 30-minute windows
    const { times, values } = this.aggregateHalfHour(historyData);

    const labels = times.map(time => {
        const hours = Math.floor(time / 60);
        const minutes = time % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    });

    if (this.chartModalCanvas.chart) {
        this.chartModalCanvas.chart.destroy();
    }

    this.chartModalCanvas.chart = new Chart(this.chartModalCanvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: `${label} (30 min avg)`,
                data: values,
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: label
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time (30 min windows)'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: title
                }
            }
        }
    });

    this.chartModal.classList.remove('hidden');
}

    hideChartModal() {
        if (this.chartModal) {
            this.chartModal.classList.add('hidden');
        }
    }

    async loadTramStats() {
        try {
            const response = await fetch('/api/simulation/stats/trams');
            const data = await response.json();

            this.allTrams = data.trams;
            this.filterAndRenderTrams();
        } catch (e) {
            console.error("Failed to load tram stats", e);
        }
    }

    filterAndRenderTrams() {
        const searchTerm = this.tramSearchInput ? this.tramSearchInput.value.toLowerCase().trim() : '';

        let filteredTrams = this.allTrams.filter(tram =>
            tram.id.toLowerCase().includes(searchTerm) ||
            tram.line.toString().includes(searchTerm)
        );

        filteredTrams.sort((a, b) => b.occupancy_percent - a.occupancy_percent);

        const tramsToShow = searchTerm ? filteredTrams : filteredTrams.slice(0, 50);

        this.renderTrams(tramsToShow);
    }

    renderTrams(trams) {
        const tbody = document.querySelector('#trams-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        trams.forEach(tram => {
            const row = document.createElement('tr');
            row.style.borderBottom = '1px solid #eee';

            const occupancyPercent = tram.occupancy_percent.toFixed(1);
            const occupancyColor = tram.occupancy_percent > 80 ? 'color: #e74c3c;' :
                                 tram.occupancy_percent > 60 ? 'color: #f39c12;' : 'color: #27ae60;';

            row.innerHTML = `
                <td style="padding: 12px;">${tram.id}</td>
                <td style="padding: 12px; text-align: right;">${tram.line}</td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">
                    <span style="${occupancyColor}">${tram.current_occupancy}</span>
                </td>
                <td style="padding: 12px; text-align: right; font-variant-numeric: tabular-nums;">${tram.max_capacity}</td>
                <td style="padding: 12px; text-align: center;">
                    <button class="btn btn-small btn-chart" data-tram-id="${tram.id}" title="View occupancy chart for ${tram.id}">
                        <i class="fas fa-chart-line"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

        const chartButtons = tbody.querySelectorAll('.btn-chart');
        chartButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tramId = e.currentTarget.dataset.tramId;
                this.showTramChart(tramId);
            });
        });
    }
}
