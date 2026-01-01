import torch
import torch.nn as nn
import numpy as np
from qlib.contrib.model.pytorch_utils import count_parameters
from qlib.contrib.model.pytorch_lstm import LSTM
from qlib.log import get_module_logger

class ALSTMEmbeddingModel(nn.Module):
    def __init__(self, d_feat, hidden_size, num_layers, dropout, rnn_type, num_embeddings, embedding_dim):
        super().__init__()
        self.d_feat = d_feat
        self.hidden_size = hidden_size
        self.embedding_dim = embedding_dim
        
        # Feature processing (minus 1 for ID)
        self.input_dim = d_feat - 1
        
        if rnn_type.upper() == 'GRU':
            self.rnn = nn.GRU(self.input_dim, hidden_size, num_layers, batch_first=True, dropout=dropout)
        else:
            self.rnn = nn.LSTM(self.input_dim, hidden_size, num_layers, batch_first=True, dropout=dropout)
            
        self.inst_embedding = nn.Embedding(num_embeddings, embedding_dim)
        
        # Simple Attention Mechanism
        self.att_linear = nn.Linear(hidden_size, hidden_size)
        self.att_ctx = nn.Linear(hidden_size, 1, bias=False)
        
        # Output FC
        # Fusing hidden_state + embedding
        self.fc_out = nn.Linear(hidden_size + embedding_dim, 1)

    def forward(self, x):
        # x: [Batch, Seq, d_feat]
        # x_feat: [Batch, Seq, d_feat-1] -> Dynamic features
        x_feat = x[:, :, :-1]
        
        # x_id: [Batch, Seq, 1] -> Instrument ID (Last column)
        # It is repeated across sequence, take first step
        x_id = x[:, 0, -1].long()
        # Ensure within bounds (defensive)
        x_id = torch.clamp(x_id, 0, self.inst_embedding.num_embeddings - 1)
        
        # RNN Forward
        out, _ = self.rnn(x_feat) # [Batch, Seq, Hidden]
        
        # Attention
        # 1. Transform: u = tanh(W*h + b)
        u = torch.tanh(self.att_linear(out))
        # 2. Score: a = softmax(u * context)
        att_scores = self.att_ctx(u) # [Batch, Seq, 1]
        att_weights = torch.softmax(att_scores, dim=1)
        # 3. Aggregate
        context_vec = torch.sum(out * att_weights, dim=1) # [Batch, Hidden]
        
        # Embedding
        emb_vec = self.inst_embedding(x_id) # [Batch, Emb]
        
        # Fusion
        fused = torch.cat([context_vec, emb_vec], dim=1) # [Batch, Hidden+Emb]
        
        return self.fc_out(fused).squeeze(-1)

class ALSTMWithEmbedding(LSTM):
    """
    ALSTM with Instrument Embedding
    Inherits from Qlib's LSTM wrapper to reuse training loop logic (fit, predict, etc.)
    """
    def __init__(self, d_feat=6, hidden_size=64, num_layers=2, dropout=0.0, n_epochs=200, lr=0.001, metric='', batch_size=2000, early_stop=20, loss='mse', optimizer='adam', GPU=0, seed=None, rnn_type='GRU', num_embeddings=100, embedding_dim=16, **kwargs):
        self.rnn_type = rnn_type
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        # Initialize base
        super().__init__(d_feat, hidden_size, num_layers, dropout, n_epochs, lr, metric, batch_size, early_stop, loss, optimizer, GPU, seed, **kwargs)

    def _init_model(self):
        self.model = ALSTMEmbeddingModel(
            d_feat=self.d_feat, 
            hidden_size=self.hidden_size, 
            num_layers=self.num_layers, 
            dropout=self.dropout, 
            rnn_type=self.rnn_type,
            num_embeddings=self.num_embeddings,
            embedding_dim=self.embedding_dim
        ).to(self.device)
        self.logger.info(f"ALSTMWithEmbedding Initialized: d_feat={self.d_feat}, hidden={self.hidden_size}, emb={self.embedding_dim}")
        self.logger.info(f"Model Parameter Count: {count_parameters(self.model)}")
