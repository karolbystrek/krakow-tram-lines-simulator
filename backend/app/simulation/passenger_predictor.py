
import math
from typing import Dict

class PassengerPredictor:

    def __init__(self):
        self.peak1 = 8 * 60
        self.peak2 = 16 * 60
        self.width = 90
        self.base = 0.15

        self.max_capacity = 1.0

    def gaussian(self, x: float, mu: float, sigma: float):
        return math.exp(-((x - mu) ** 2) / (2 * sigma * sigma))

    def predict_occupancy(self, time_minutes: float) -> float:

        g1 = self.gaussian(time_minutes, self.peak1, self.width)
        g2 = self.gaussian(time_minutes, self.peak2, self.width)

        occupancy = self.base + 0.7 * (g1 + g2)
        normalised = math.floor(min(1.0, max(0.0, occupancy))*130)
        return normalised
