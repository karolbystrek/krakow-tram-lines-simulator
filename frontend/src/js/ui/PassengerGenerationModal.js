import { debounce } from '../utils/debounce.js';

export class PassengerGenerationModal {
  constructor(client, simulation) {
    this.client = client;
    this.simulation = simulation;
    this.isOpen = false;
    this.chart = null;
    
    // Default configuration (will be used if nothing loaded)
    this.config = {
        baseRate: 50,
        peaks: [
            { id: 1, time: 450, width: 90, height: 700 },   // Morning
            { id: 2, time: 810, width: 150, height: 420 },  // Midday
            { id: 3, time: 1020, width: 120, height: 700 }  // Evening
        ]
    };

    this.initUI();
  }

  initUI() {
    // Create Modal HTML
    this.modal = document.createElement('div');
    this.modal.id = 'passenger-gen-modal';
    this.modal.className = 'modal hidden';
    this.modal.innerHTML = `
      <div class="modal-content large-modal">
        <div class="modal-header">
          <h2>Passenger Demand Configuration</h2>
          <button class="close-modal-btn">&times;</button>
        </div>
        
        <div class="modal-body">
          <div class="modal-section chart-section">
            <div class="chart-container-large">
               <canvas id="scenario-chart"></canvas>
            </div>
          </div>
          
          <div class="modal-section controls-section">
            <div class="base-rate-control">
                <label>Base Demand Rate (pax/min):</label>
                <input type="number" id="base-rate-input" min="0" max="500" value="50">
                <input type="range" id="base-rate-slider" min="0" max="500" value="50">
            </div>
            
            <div class="peaks-header">
                <h3>Demand Peaks</h3>
                <button id="add-peak-btn" class="btn btn-secondary">+ Add Peak</button>
            </div>
            
            <div id="peaks-list" class="peaks-list">
                <!-- Peaks injected here -->
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <div class="warning-text">
            <i class="fas fa-exclamation-triangle"></i> Applying changes will restart the simulation.
          </div>
          <div class="action-buttons">
            <button id="cancel-gen-btn" class="btn btn-secondary">Cancel</button>
            <button id="apply-gen-btn" class="btn btn-primary">Apply & Restart</button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(this.modal);

    // Bind Elements
    this.closeBtn = this.modal.querySelector('.close-modal-btn');
    this.cancelBtn = document.getElementById('cancel-gen-btn');
    this.applyBtn = document.getElementById('apply-gen-btn');
    this.addPeakBtn = document.getElementById('add-peak-btn');
    this.peaksList = document.getElementById('peaks-list');
    this.baseRateInput = document.getElementById('base-rate-input');
    this.baseRateSlider = document.getElementById('base-rate-slider');

    // Events
    this.closeBtn.addEventListener('click', () => this.close());
    this.cancelBtn.addEventListener('click', () => this.close());
    this.applyBtn.addEventListener('click', () => this.apply());
    this.addPeakBtn.addEventListener('click', () => this.addPeak());
    
    // Save button
    this.saveBtn = document.createElement('button');
    this.saveBtn.className = 'btn btn-secondary';
    this.saveBtn.style.marginRight = 'auto'; // Push others to right
    this.saveBtn.textContent = 'Save as Default';
    this.saveBtn.onclick = () => this.save();
    this.modal.querySelector('.action-buttons').prepend(this.saveBtn);

    this.baseRateInput.addEventListener('input', (e) => {
        this.config.baseRate = parseFloat(e.target.value) || 0;
        this.baseRateSlider.value = this.config.baseRate;
        this.updateChart();
    });
    
    this.baseRateSlider.addEventListener('input', (e) => {
        this.config.baseRate = parseFloat(e.target.value);
        this.baseRateInput.value = this.config.baseRate;
        this.updateChart();
    });

    this.initEvents();
  }

  initEvents() {
    this.modal.addEventListener('click', (e) => {
      if (e.target === this.modal) {
        this.close();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
  }

  setParams(params) {
      if (params.base_demand_rate !== undefined) {
          this.config.baseRate = params.base_demand_rate;
          this.baseRateInput.value = this.config.baseRate;
          this.baseRateSlider.value = this.config.baseRate;
      }
      
      if (params.peaks && Array.isArray(params.peaks)) {
          this.config.peaks = params.peaks.map((p, i) => ({
              id: Date.now() + i, // Generate temporary ID for UI
              time: p.time,
              width: p.width,
              height: p.height
          }));
      }
      
      this.renderPeaksList();
      this.updateChart();
      this.hideLoading();
  }

  open() {
    this.isOpen = true;
    this.modal.classList.remove('hidden');
    
    // Pause simulation
    this.client.sendCommand('pause');
    
    // Fetch current params from server
    this.showLoading();
    this.client.sendCommand('get_generation_params');
    
    // Initialize chart if needed
    if (!this.chart) {
        this.initChart();
    } else {
        this.updateChart();
    }
  }

  showLoading() {
      // Optional: Add loading state to modal
      this.peaksList.innerHTML = '<div style="text-align:center; padding: 20px;">Loading configuration...</div>';
  }

  hideLoading() {
      // Handled by renderPeaksList
  }

  close() {
    this.isOpen = false;
    this.modal.classList.add('hidden');
    // Resume simulation if valid
    // Note: We might want to check if it was running before, but standard behavior is resume
    this.client.sendCommand('resume');
  }

  save() {
      // Apply current config to server first to ensure state is consistent
      const payload = {
        base_demand_rate: this.config.baseRate,
        peaks: this.config.peaks.map(p => ({
            time: p.time,
            width: p.width,
            height: p.height
        }))
      };
      
      // Update runtime params (silent update, no restart needed for save action strictly speaking,
      // but good to ensure what we save is what we have)
      this.client.sendCommand('update_generation_params', { params: payload });
      
      // Trigger save
      this.client.sendCommand('save_generation_params');
      
      // Feedback
      const originalText = this.saveBtn.textContent;
      this.saveBtn.textContent = 'Saved!';
      this.saveBtn.disabled = true;
      setTimeout(() => {
          this.saveBtn.textContent = originalText;
          this.saveBtn.disabled = false;
      }, 2000);
  }

  apply() {
    // 1. Construct payload
    const payload = {
        base_demand_rate: this.config.baseRate,
        peaks: this.config.peaks.map(p => ({
            time: p.time,
            width: p.width,
            height: p.height
        }))
    };

    // 2. Send update command
    this.client.sendCommand('update_generation_params', { params: payload });

    // 3. Restart simulation
    this.client.sendCommand('restart');

    // 4. Close modal (without resuming, since restart handles state)
    this.isOpen = false;
    this.modal.classList.add('hidden');
  }

  addPeak() {
    const newId = Date.now();
    this.config.peaks.push({
        id: newId,
        time: 720, // 12:00
        width: 60,
        height: 500
    });
    this.renderPeaksList();
    this.updateChart();
  }

  removePeak(id) {
    this.config.peaks = this.config.peaks.filter(p => p.id !== id);
    this.renderPeaksList();
    this.updateChart();
  }

  updatePeak(id, field, value) {
    const peak = this.config.peaks.find(p => p.id === id);
    if (peak) {
        peak[field] = parseFloat(value);
        this.updateChart();
        // Update specific input if needed, but usually handled by event target
    }
  }

  renderPeaksList() {
    this.peaksList.innerHTML = '';
    
    this.config.peaks.forEach((peak, index) => {
        const el = document.createElement('div');
        el.className = 'peak-item';
        el.innerHTML = `
            <div class="peak-header">
                <span class="peak-title">Peak ${index + 1}</span>
                <button class="remove-peak-btn" data-id="${peak.id}">&times;</button>
            </div>
            <div class="peak-controls">
                <div class="control-group">
                    <label>Time: <span class="val-display">${this.formatTime(peak.time)}</span></label>
                    <input type="range" class="peak-time-slider" min="0" max="1439" value="${peak.time}" data-id="${peak.id}">
                </div>
                <div class="control-group">
                    <label>Intensity: <span class="val-display">${peak.height}</span></label>
                    <input type="range" class="peak-height-slider" min="0" max="2000" value="${peak.height}" step="10" data-id="${peak.id}">
                </div>
                <div class="control-group">
                    <label>Width: <span class="val-display">${peak.width}</span></label>
                    <input type="range" class="peak-width-slider" min="10" max="300" value="${peak.width}" step="5" data-id="${peak.id}">
                </div>
            </div>
        `;
        this.peaksList.appendChild(el);
    });

    // Bind events for this render
    this.peaksList.querySelectorAll('.remove-peak-btn').forEach(btn => {
        btn.addEventListener('click', (e) => this.removePeak(parseInt(e.target.dataset.id)));
    });

    this.peaksList.querySelectorAll('input[type="range"]').forEach(input => {
        input.addEventListener('input', (e) => {
            const id = parseInt(e.target.dataset.id);
            const val = parseFloat(e.target.value);
            
            // Update display
            const display = e.target.parentElement.querySelector('.val-display');
            if (e.target.classList.contains('peak-time-slider')) {
                display.textContent = this.formatTime(val);
                this.updatePeak(id, 'time', val);
            } else if (e.target.classList.contains('peak-height-slider')) {
                display.textContent = val;
                this.updatePeak(id, 'height', val);
            } else if (e.target.classList.contains('peak-width-slider')) {
                display.textContent = val;
                this.updatePeak(id, 'width', val);
            }
        });
    });
  }

  formatTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = Math.floor(minutes % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  // --- Chart Logic ---
  gaussian(x, mu, sigma) {
      if (sigma === 0) return 0;
      return Math.exp(-Math.pow(x - mu, 2) / (2 * Math.pow(sigma, 2)));
  }

  calculateRate(t) {
      const time = t % 1440;
      let total = this.config.baseRate;
      
      this.config.peaks.forEach(p => {
          total += p.height * this.gaussian(time, p.time, p.width);
      });
      return total;
  }

  initChart() {
      const ctx = document.getElementById('scenario-chart').getContext('2d');
      const labels = [];
      const data = [];
      for(let i = 0; i < 1800; i += 30) {
          const h = Math.floor(i / 60);
          const validHour = h % 24;
          const timeStr = `${validHour.toString().padStart(2,'0')}:00`;
          const label = h >= 24 ? `${timeStr} (+1)` : timeStr;
          labels.push(label);
          data.push(this.calculateRate(i));
      }

      this.chart = new Chart(ctx, {
          type: 'line',
          data: {
              labels: labels,
              datasets: [{
                  label: 'Projected Demand',
                  data: data,
                  borderColor: '#2196F3',
                  backgroundColor: 'rgba(33, 150, 243, 0.1)',
                  borderWidth: 2,
                  pointRadius: 0,
                  fill: true,
                  tension: 0.4
              }]
          },
          options: {
              responsive: true,
              maintainAspectRatio: false,
              interaction: {
                  mode: 'index',
                  intersect: false,
              },
              scales: {
                  y: {
                      beginAtZero: true,
                      title: { display: true, text: 'Passengers / min' }
                  },
                  x: {
                      grid: { display: false }
                  }
              }
          }
      });
  }

  updateChart() {
      if (!this.chart) return;
      
      const newData = [];
      for(let i = 0; i < 1800; i += 30) {
          newData.push(this.calculateRate(i));
      }
      
      this.chart.data.datasets[0].data = newData;
      this.chart.update('none');
  }
}
