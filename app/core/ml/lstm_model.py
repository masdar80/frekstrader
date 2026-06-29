import os
try:
    import torch
    import torch.nn as nn
except ImportError:
    torch = None
    nn = None
    
from typing import List, Dict, Any
from app.utils.logger import logger

class EntryLSTM:
    pass

if nn:
    class EntryLSTM(nn.Module):
        def __init__(self, input_size, hidden_size=64, num_layers=2):
            super(EntryLSTM, self).__init__()
            self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 32)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(32, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        out, _ = self.lstm(x, (h0, c0))
        out = out[:, -1, :] # Take last sequence step
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        return self.sigmoid(out)
        
class LSTMTimingModel:
    """
    Evaluates sequences of recent market states to determine
    the optimal micro-timing for entry.
    """
    def __init__(self, model_path="data/models/lstm_timing.pth", input_size=20):
        self.model_path = model_path
        self.input_size = input_size
        self.is_loaded = False
        
        if torch:
            self.model = EntryLSTM(input_size)
            self.device = torch.device("cpu") # User requested CPU only
            self.model.to(self.device)
            self._load()
        else:
            self.model = None
            logger.warning("torch not installed. LSTM Micro-Timing is disabled.")
        
    def _load(self):
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.eval()
                self.is_loaded = True
                logger.info("✅ Loaded LSTM Entry Timing Model.")
            except Exception as e:
                logger.error(f"Failed to load LSTM: {e}")
                
    def predict_optimal_entry(self, sequence_features: List[List[float]]) -> float:
        """
        Takes a sequence of recent indicator states (e.g. last 10 candles).
        Returns a score 0.0 - 1.0 indicating if NOW is the optimal entry time.
        """
        if not self.is_loaded or not sequence_features:
            return 0.5
            
        try:
            # sequence_features shape: (seq_length, input_size)
            seq_tensor = torch.tensor(sequence_features, dtype=torch.float32).unsqueeze(0) # add batch dim
            seq_tensor = seq_tensor.to(self.device)
            
            with torch.no_grad():
                score = self.model(seq_tensor).item()
                
            return score
        except Exception as e:
            logger.error(f"LSTM Prediction error: {e}")
            return 0.5

lstm_timer = LSTMTimingModel()
