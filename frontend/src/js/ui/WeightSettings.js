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
      <div class="modal-content">
        <div class="modal-header">
          <h2>Stop Weights Configuration</h2>
          <button class="close-modal-btn">&times;</button>
        </div>
        
        <div class="modal-body">
            <div class="weights-search-container">
                <input type="text" id="weights-search" placeholder="Search stops..." class="form-control" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;">
            </div>
            <div class="weights-list-header">
                <span>Stop Name</span>
                <span>Weight (0.1 - 20.0)</span>
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

  async open() {
    this.isOpen = true;
    this.modal.classList.remove('hidden');
    await this.fetchWeights();
    this.renderList();
  }

  close() {
    this.isOpen = false;
    this.modal.classList.add('hidden');
  }

  async fetchWeights() {
    try {
      const response = await fetch('/api/simulation/weights');
      const data = await response.json();
      
      this.weightsMap = {};
      this.displayList = [];
      
      if (Array.isArray(data)) {
        this.displayList = data;
        data.forEach(item => {
          this.weightsMap[item.id] = item.weight;
        });
      } else {
        this.weightsMap = data;
        this.displayList = Object.entries(data).map(([id, weight]) => ({
          id, name: id, weight
        }));
      }
      
      this.displayList.sort((a, b) => b.weight - a.weight);
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
    
    this.filteredList.forEach(item => {
      const el = document.createElement('div');
      el.className = 'weight-item';
      el.innerHTML = `
        <span class="weight-name" title="${item.name} (${item.id})">${item.name}</span>
        <div class="weight-control">
          <input type="range" min="0.1" max="20.0" step="0.1" value="${item.weight}" data-id="${item.id}">
          <span class="weight-value">${item.weight.toFixed(1)}</span>
        </div>
      `;
      this.listContainer.appendChild(el);
    });

    this.listContainer.querySelectorAll('input[type="range"]').forEach(input => {
      input.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        e.target.nextElementSibling.textContent = val.toFixed(1);
        this.weightsMap[e.target.dataset.id] = val;
      });
    });
  }

  async save() {
    try {
      const response = await fetch('/api/simulation/weights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.weightsMap)
      });
      
      if (response.ok) {
        const originalText = this.saveBtn.textContent;
        this.saveBtn.textContent = 'Saved!';
        this.saveBtn.disabled = true;
        setTimeout(() => {
          this.saveBtn.textContent = originalText;
          this.saveBtn.disabled = false;
          this.close();
        }, 1000);
      }
    } catch (e) {
      console.error("Error saving weights", e);
    }
  }
}