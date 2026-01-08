import { debounce } from '../utils/debounce.js';
import { getDefaultService } from '../utils/time.js';

export class SimulationUI {
  constructor(client) {
    this.client = client;
    this.timeDisplay = document.getElementById('simulation-time');
    this.timeSlider = document.getElementById('time-slider');
    this.speedSlider = document.getElementById('speed-slider');
    this.speedDisplay = document.getElementById('speed-display');
    this.pauseBtn = document.getElementById('btn-pause');
    this.restartBtn = document.getElementById('btn-restart');
    this.serviceSelector = document.getElementById('service-selector');

    this.isDraggingTimeSlider = false;
    this.isDraggingSpeedSlider = false;

    this.loadingOverlay = document.getElementById('loading-overlay');
    this.connectionErrorOverlay = document.getElementById('connection-error-overlay');

    this.initializeControls();
  }

  initializeControls() {
    this.showLoading();

    this.initializeTimeSlider();
    this.initializeSpeedSlider();
    this.initializeButtons();
    this.initializeServiceSelector();
  }

  initializeTimeSlider() {
    if (!this.timeSlider) return;

    const debouncedSetTime = debounce((time) => {
      this.client.sendCommand('set_time', { time: time });
    }, 100);

    this.timeSlider.addEventListener('input', (e) => {
      this.isDraggingTimeSlider = true;
      const time = parseFloat(e.target.value);
      this.renderTime(time);
      debouncedSetTime(time);
    });

    this.timeSlider.addEventListener('change', (e) => {
      this.isDraggingTimeSlider = false;
      this.client.sendCommand('set_time', { time: parseFloat(e.target.value) });
    });

    const clearDrag = () => { this.isDraggingTimeSlider = false; };
    this.timeSlider.addEventListener('mouseup', clearDrag);
    this.timeSlider.addEventListener('mouseleave', clearDrag);
    this.timeSlider.addEventListener('touchend', clearDrag);
  }

  initializeSpeedSlider() {
    if (!this.speedSlider) return;

    this.speedSlider.addEventListener('input', (e) => {
      this.isDraggingSpeedSlider = true;
      this.updateSpeedDisplayValue(parseFloat(e.target.value));
    });

    this.speedSlider.addEventListener('change', (e) => {
      this.isDraggingSpeedSlider = false;
      const val = parseFloat(e.target.value);
      const speed = Math.pow(10, val);
      this.updateSpeedDisplayValue(val);
      this.client.sendCommand('set_speed', { speed: speed });
    });

    const clearDrag = () => { this.isDraggingSpeedSlider = false; };
    this.speedSlider.addEventListener('mousedown', () => { this.isDraggingSpeedSlider = true; });
    this.speedSlider.addEventListener('touchstart', () => { this.isDraggingSpeedSlider = true; });
    this.speedSlider.addEventListener('mouseup', clearDrag);
    this.speedSlider.addEventListener('mouseleave', clearDrag);
    this.speedSlider.addEventListener('touchend', clearDrag);
  }

  initializeButtons() {
    if (this.pauseBtn) {
      // Clone to remove old listeners if any (though usually we are initing once)
      const newPauseBtn = this.pauseBtn.cloneNode(true);
      this.pauseBtn.parentNode.replaceChild(newPauseBtn, this.pauseBtn);
      this.pauseBtn = newPauseBtn;

      this.pauseBtn.addEventListener('click', () => {
        const isPaused = this.pauseBtn.textContent.includes('Resume');
        this.client.sendCommand(isPaused ? 'resume' : 'pause');
      });
    }

    if (this.restartBtn) {
      const newRestartBtn = this.restartBtn.cloneNode(true);
      this.restartBtn.parentNode.replaceChild(newRestartBtn, this.restartBtn);
      this.restartBtn = newRestartBtn;

      this.restartBtn.addEventListener('click', () => {
        this.client.sendCommand('restart');
      });
    }
  }

  initializeServiceSelector() {
    if (!this.serviceSelector) return;
    
    this.serviceSelector.value = getDefaultService();
    this.serviceSelector.addEventListener('change', (e) => {
      this.client.sendCommand('change_service', { service_id: e.target.value });
      this.showLoading();
    });
  }

  renderTime(timeMinutes) {
    if (!this.timeDisplay) return;
    const hours = Math.floor(timeMinutes / 60);
    const minutes = Math.floor(timeMinutes % 60);
    this.timeDisplay.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:00`;
  }

  updateSpeedDisplayValue(val) {
    const speed = Math.pow(10, val);
    const displaySpeed = speed >= 1 ? speed.toFixed(1) : speed.toFixed(2);
    
    if (this.speedDisplay) {
        this.speedDisplay.textContent = `${displaySpeed}x`;
    }
    if (this.speedSlider) {
        this.speedSlider.title = `1 real second = ${displaySpeed} simulation minutes`;
    }
  }

  update(data) {
    if (data.time) {
      this.updateTimeDisplay(data.time);
      this.hideLoading();
    }

    if (this.pauseBtn && data.status) {
        if (data.status === 'paused') {
            this.pauseBtn.innerHTML = '<i class="fas fa-play"></i> Resume';
        } else {
            this.pauseBtn.innerHTML = '<i class="fas fa-pause"></i> Pause';
        }
    }
  }

  updateTimeDisplay(timeData) {
      if (this.timeDisplay && !this.isDraggingTimeSlider) {
        this.timeDisplay.textContent = timeData.time_str;
      }

      if (this.timeSlider) {
        if (timeData.start_time_minutes !== undefined) this.timeSlider.min = timeData.start_time_minutes;
        if (timeData.end_time_minutes !== undefined) this.timeSlider.max = timeData.end_time_minutes;
        
        if (!this.isDraggingTimeSlider) {
          this.timeSlider.value = timeData.time_minutes;
        }
      }

      if (timeData.speed !== undefined && this.speedSlider && !this.isDraggingSpeedSlider) {
        const serverSpeed = parseFloat(timeData.speed);
        const sliderVal = Math.log10(serverSpeed);
        if (Math.abs(parseFloat(this.speedSlider.value) - sliderVal) > 0.05) {
          this.speedSlider.value = sliderVal;
          this.updateSpeedDisplayValue(sliderVal);
        }
      }
  }

  setConnected(isConnected) {
    if (isConnected) {
        this.hideConnectionError();
    } else {
        this.showConnectionError();
    }
  }

  showLoading() {
      if (this.loadingOverlay) {
          this.loadingOverlay.classList.remove('hidden');
      }
  }

  hideLoading() {
      if (this.loadingOverlay) {
          this.loadingOverlay.classList.add('hidden');
      }
  }

  showConnectionError() {
      if (this.connectionErrorOverlay) {
          this.hideLoading();
          this.connectionErrorOverlay.classList.remove('hidden');
      }
  }

  hideConnectionError() {
      if (this.connectionErrorOverlay) {
          this.connectionErrorOverlay.classList.add('hidden');
      }
  }
}
