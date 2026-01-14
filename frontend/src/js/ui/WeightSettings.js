import { debounce } from '../utils/debounce.js';

export class WeightSettings {
  constructor(client, simulation) {
    this.client = client;
    this.simulation = simulation;
    this.isOpen = false;
    this.weightsMap = {};
    this.displayList = [];
    this.filteredList = [];
    
    this.initUI();
  }

  initUI() {
    this.modal = document.createElement('div');
    this.modal.id = 'weight-settings-modal';
    this.modal.className = 'modal hidden';
    this.modal.innerHTML = `
      <div class="modal-content" style="max-width: 900px;">
        <div class="modal-header">
          <h2>Stop Weights Configuration</h2>
          <button class="close-modal-btn">&times;</button>
        </div>
        
        <div class="modal-body">
            <div class="weights-search-container">
                <input type="text" id="weights-search" placeholder="Search stops..." class="form-control" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;">
            </div>
            
            <div class="weights-list-header" style="display: grid; grid-template-columns: 2fr 2fr 1fr 1fr; gap: 10px; align-items: center;">
                <span>Stop Name</span>
                <span>Base Weight (Mass)</span>
                <span style="text-align: right;">Connectivity (%)</span>
                <span style="text-align: right;">Flow Index</span>
            </div>
            <div id="weights-list" class="weights-list">
            </div>
        </div>
        
        <div class="modal-footer">
          <div class="action-buttons">
            <button id="cancel-weights-btn" class="btn btn-secondary">Close</button>
            <button id="save-weights-btn" class="btn btn-primary">Save Changes</button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(this.modal);

    this.closeBtn = this.modal.querySelector('.close-modal-btn');
    this.cancelBtn = document.getElementById('cancel-weights-btn');
    this.saveBtn = document.getElementById('save-weights-btn');
    this.listContainer = document.getElementById('weights-list');
    this.searchInput = document.getElementById('weights-search');

    this.closeBtn.addEventListener('click', () => this.close());
    this.cancelBtn.addEventListener('click', () => this.close());
    this.saveBtn.addEventListener('click', () => this.save());
    
    this.searchInput.addEventListener('input', debounce((e) => {
        this.filterList(e.target.value);
    }, 300));

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

  async open(initialSearch = null) {
    this.isOpen = true;
    this.modal.classList.remove('hidden');
    await this.fetchWeights();
    
    if (initialSearch) {
        this.searchInput.value = initialSearch;
        this.filterList(initialSearch);
    } else {
        this.searchInput.value = '';
        this.renderList();
    }
  }

  close() {
    this.isOpen = false;
    this.modal.classList.add('hidden');
  }

  async fetchWeights() {
    try {
      const response = await fetch('/api/simulation/weights');
      const data = await response.json();
      
      this.weightsMap = {}; // Stores base weights for saving
      this.displayList = [];
      this.maxScore = 0;
      this.maxFlow = 0;
      
      if (Array.isArray(data)) {
        this.displayList = data;
        data.forEach(item => {
          this.weightsMap[item.id] = item.base_weight;
          if (item.accessibility_score > this.maxScore) this.maxScore = item.accessibility_score;
          if (item.final_weight > this.maxFlow) this.maxFlow = item.final_weight;
        });
      }
      
      // Sort by final flow (importance) by default
      this.displayList.sort((a, b) => b.final_weight - a.final_weight);
      this.filteredList = [...this.displayList];
    } catch (e) {
      console.error("Failed to fetch weights", e);
    }
  }

  filterList(query) {
    if (!query) {
      this.filteredList = [...this.displayList];
    } else {
      const lowerQ = query.toLowerCase();
      this.filteredList = this.displayList.filter(item => 
        item.name.toLowerCase().includes(lowerQ) || 
        item.id.toLowerCase().includes(lowerQ)
      );
    }
    this.renderList();
  }

  renderList() {
    this.listContainer.innerHTML = '';
    
    // Safety check for div by zero and noise
    const maxScore = this.maxScore || 1;
    const maxFlow = (this.maxFlow > 0.001) ? this.maxFlow : 1.0;

    this.filteredList.forEach(item => {
      const el = document.createElement('div');
      el.className = 'weight-item';
      // Use Grid layout matching header
      el.style.display = 'grid';
      el.style.gridTemplateColumns = '2fr 2fr 1fr 1fr';
      el.style.gap = '10px';
      el.style.alignItems = 'center';
      
      // Base Weight from map (editable), others from item (read-only snapshot)
      const currentBase = this.weightsMap[item.id];
      const estimatedFlow = currentBase * item.accessibility_score;
      
      // Normalization
      const connPercent = (item.accessibility_score / maxScore) * 100;
      const flowIndex = (estimatedFlow / maxFlow) * 100;
      
      const isTerminus = item.accessibility_score <= 0.000001;
      const connDisplay = isTerminus ? '<span style="color:#aaa; font-size:11px;">Terminus</span>' : `${connPercent.toFixed(0)}%`;
      const flowDisplay = isTerminus ? '0' : flowIndex.toFixed(0);

      el.innerHTML = `
        <span class="weight-name" title="${item.name} (${item.id})" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${item.name}</span>
        <div class="weight-control" style="display: flex; align-items: center; gap: 10px;">
          <input type="range" min="0.0" max="20.0" step="0.1" value="${currentBase}" data-id="${item.id}" class="slider-input" style="flex: 1;" ${isTerminus ? 'disabled style="opacity:0.5"' : ''}>
          <span class="weight-value" style="min-width: 40px; text-align: right;">${currentBase.toFixed(1)}</span>
        </div>
        <div style="text-align: right;">
            <div style="font-weight: bold; color: #666;">${connDisplay}</div>
            <div style="font-size: 10px; color: #999;">${isTerminus ? 'No Dest.' : 'Score'}</div>
        </div>
        <div class="weight-flow-display-container" style="text-align: right;">
            <div class="weight-flow-value" style="font-weight: bold; color: #2196F3;">${flowDisplay}</div>
            <div style="font-size: 10px; color: #999;">Index</div>
        </div>
      `;
      this.listContainer.appendChild(el);
    });

    this.listContainer.querySelectorAll('input[type="range"]').forEach(input => {
      input.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        const id = e.target.dataset.id;
        
        // Update model
        this.weightsMap[id] = val;
        
        // Update UI immediate feedback
        e.target.nextElementSibling.textContent = val.toFixed(1);
        
        // Update Flow calculation (approximate immediate feedback)
        const item = this.displayList.find(i => i.id === id);
        if (item) {
             const flowContainer = e.target.closest('.weight-item').querySelector('.weight-flow-value');
             const estFlow = val * item.accessibility_score;
             const newFlowIndex = (estFlow / maxFlow) * 100;
             if (flowContainer) {
                flowContainer.textContent = newFlowIndex.toFixed(0);
             }
        }
      });
    });
  }

  async save() {
    try {
      this.saveBtn.textContent = 'Saving...';
      this.saveBtn.disabled = true;

      const response = await fetch('/api/simulation/weights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.weightsMap)
      });
      
      if (response.ok) {
        const originalText = 'Save Changes'; // Hardcoded backup
        this.saveBtn.textContent = 'Saved!';
        setTimeout(() => {
          this.saveBtn.textContent = originalText;
          this.saveBtn.disabled = false;
          this.close();
          // Reload to refresh the exact calculated flow values
          this.fetchWeights();
        }, 1000);
      } else {
         this.saveBtn.textContent = 'Error';
         this.saveBtn.disabled = false;
      }
    } catch (e) {
      console.error("Error saving weights", e);
      this.saveBtn.textContent = 'Error';
      this.saveBtn.disabled = false;
    }
  }
}