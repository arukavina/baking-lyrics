"""Conditional word level LSTM language model (AWD-LSTM family) for lyrics and titles.

Input at every timestep: word embedding (300 d, optionally GloVe initialised) concatenated with a learned artist
embedding and a learned genre embedding. Three stacked LSTM layers (hidden 1024, the last one projects to the
embedding size), output softmax tied to the input embedding.

Regularisation (Merity et al. 2017, "Regularizing and Optimizing LSTM Language Models"):

- embedding dropout: whole word types are dropped from the embedding matrix;
- locked (variational) dropout: one mask per sequence on the input, between layers and on the output;
- weight drop (DropConnect) on each layer's hidden-to-hidden matrix, applied only in training through
  `torch.func.functional_call`, so the stored parameters stay plain `nn.LSTM` weights that export as-is;
- conditioning dropout: the artist (and genre) id is replaced by the "unknown" id 0 at random, so the model also
  learns a generic style for artists it has never seen.
"""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass

import torch
import torch.nn.functional as F
from torch import nn


@dataclass
class ModelConfig:
    vocab_size: int
    n_artists: int  # including the unknown id 0
    n_genres: int  # including the unknown id 0
    emb_dim: int = 300
    artist_dim: int = 64
    genre_dim: int = 16
    hidden: int = 1024
    layers: int = 3
    dropout_emb: float = 0.05  # word type dropout on the embedding matrix
    dropout_in: float = 0.25  # locked dropout on the LSTM input
    dropout_hid: float = 0.2  # locked dropout between LSTM layers
    dropout_out: float = 0.25  # locked dropout before the softmax
    weight_drop: float = 0.3  # DropConnect on hidden-to-hidden weights
    cond_drop: float = 0.1  # probability of replacing the artist id with "unknown"
    emb_init_std: float = 0.3  # word embedding init; ~ the scale of GloVe 6B vectors (see reset_parameters)
    tie_weights: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def input_dim(self) -> int:
        return self.emb_dim + self.artist_dim + self.genre_dim

    def layer_sizes(self) -> list[tuple[int, int]]:
        """(input size, hidden size) per layer; the last hidden size equals emb_dim when weights are tied."""
        sizes = []
        for i in range(self.layers):
            n_in = self.input_dim if i == 0 else self.hidden
            n_hid = self.emb_dim if (i == self.layers - 1 and self.tie_weights) else self.hidden
            sizes.append((n_in, n_hid))
        return sizes

    @property
    def state_size(self) -> int:
        """Size of the flat recurrent state used by the exported step model: [h_0, c_0, h_1, c_1, ...]."""
        return sum(2 * h for _, h in self.layer_sizes())


State = list[tuple[torch.Tensor, torch.Tensor]]


def locked_dropout(x: torch.Tensor, p: float, training: bool) -> torch.Tensor:
    """Same dropout mask for every timestep of a sequence. x: [B, T, D]."""
    if not training or p <= 0:
        return x
    mask = x.new_empty(x.size(0), 1, x.size(2)).bernoulli_(1 - p) / (1 - p)
    return x * mask


def embedding_dropout(embed: nn.Embedding, tokens: torch.Tensor, p: float, training: bool) -> torch.Tensor:
    if not training or p <= 0:
        return embed(tokens)
    w = embed.weight
    mask = w.new_empty(w.size(0), 1).bernoulli_(1 - p) / (1 - p)
    return F.embedding(tokens, w * mask, embed.padding_idx)


class LyricsLSTM(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.embed = nn.Embedding(cfg.vocab_size, cfg.emb_dim, padding_idx=0)
        self.artist_embed = nn.Embedding(cfg.n_artists, cfg.artist_dim)
        self.genre_embed = nn.Embedding(cfg.n_genres, cfg.genre_dim)
        self.rnns = nn.ModuleList(nn.LSTM(n_in, n_hid, batch_first=True) for n_in, n_hid in cfg.layer_sizes())
        out_dim = cfg.layer_sizes()[-1][1]
        if cfg.tie_weights and out_dim != cfg.emb_dim:
            raise ValueError("weight tying needs the last LSTM size to equal emb_dim")
        self.decoder = nn.Linear(out_dim, cfg.vocab_size)
        if cfg.tie_weights:
            self.decoder.weight = self.embed.weight
        self.reset_parameters()

    def reset_parameters(self) -> None:
        # Xavier input weights and orthogonal recurrent weights per gate: with PyTorch's default init a 3 layer
        # stack sat on a unigram plateau for ~450 steps in the smoke run; this keeps early gradients larger.
        # With tied weights the context logits are hidden . embedding: the AWD-LSTM default uniform(-0.1, 0.1)
        # kept a 3 layer stack on the unigram plateau for 1,000+ steps in the smoke run; std 0.3 left it in ~300.
        nn.init.normal_(self.embed.weight, std=self.cfg.emb_init_std)
        with torch.no_grad():
            self.embed.weight[0].zero_()  # <pad>
        nn.init.normal_(self.artist_embed.weight, std=0.1)
        nn.init.normal_(self.genre_embed.weight, std=0.1)
        nn.init.zeros_(self.decoder.bias)
        for rnn in self.rnns:
            for name, p in rnn.named_parameters():
                if name.startswith("weight_ih"):
                    for gate in p.data.chunk(4, dim=0):
                        nn.init.xavier_uniform_(gate)
                elif name.startswith("weight_hh"):
                    for gate in p.data.chunk(4, dim=0):
                        nn.init.orthogonal_(gate)
                elif "bias" in name:
                    nn.init.zeros_(p)
                    if name.startswith("bias_ih"):
                        n = p.numel() // 4
                        p.data[n:2 * n] = 1.0  # forget gate bias 1 (PyTorch gate order i, f, g, o)

    def load_pretrained_embeddings(self, vectors: torch.Tensor, mask: torch.Tensor) -> None:
        """Copy pretrained rows (e.g. GloVe) where `mask` is True."""
        with torch.no_grad():
            self.embed.weight[mask] = vectors[mask].to(self.embed.weight)

    def init_state(self, batch: int, device=None) -> State:
        return [(torch.zeros(1, batch, h, device=device), torch.zeros(1, batch, h, device=device))
                for _, h in self.cfg.layer_sizes()]

    def _run_rnn(self, rnn: nn.LSTM, x: torch.Tensor, state):
        if self.training and self.cfg.weight_drop > 0:
            params = dict(rnn.named_parameters())
            params["weight_hh_l0"] = F.dropout(params["weight_hh_l0"], self.cfg.weight_drop, training=True)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*not part of single contiguous chunk.*")
                return torch.func.functional_call(rnn, params, (x, state))
        return rnn(x, state)

    def forward(self, tokens: torch.Tensor, artist: torch.Tensor, genre: torch.Tensor,
                state: State | None = None) -> tuple[torch.Tensor, State]:
        """tokens [B, T] int64, artist [B], genre [B] -> logits [B, T, V], new state."""
        cfg = self.cfg
        B, T = tokens.shape
        if self.training and cfg.cond_drop > 0:
            drop = torch.rand(B, device=tokens.device) < cfg.cond_drop
            artist = artist.masked_fill(drop, 0)
            genre = genre.masked_fill(torch.rand(B, device=tokens.device) < cfg.cond_drop / 2, 0)
        emb = embedding_dropout(self.embed, tokens, cfg.dropout_emb, self.training)
        cond = torch.cat([self.artist_embed(artist), self.genre_embed(genre)], dim=-1)
        x = torch.cat([emb, cond.unsqueeze(1).expand(B, T, cond.size(-1))], dim=-1)
        x = locked_dropout(x, cfg.dropout_in, self.training)
        if state is None:
            state = self.init_state(B, tokens.device)
        new_state: State = []
        for i, rnn in enumerate(self.rnns):
            x, s = self._run_rnn(rnn, x, state[i])
            new_state.append(s)
            p = cfg.dropout_hid if i < len(self.rnns) - 1 else cfg.dropout_out
            x = locked_dropout(x, p, self.training)
        return self.decoder(x), new_state

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


class StepDecoder(nn.Module):
    """Single step inference graph for export: explicit LSTM gate math over a flat state tensor.

    Inputs: token [B] int64, artist [B] int64, genre [B] int64, state [B, S] float32.
    Outputs: logits [B, V] float32, state_out [B, S] float32. S = ModelConfig.state_size, laid out as
    [h_0, c_0, h_1, c_1, ...]. Writing the cell out (MatMul, Sigmoid, Tanh) keeps the ONNX graph to basic ops
    that every exporter and runtime supports, instead of relying on the ONNX LSTM op conversion.
    """

    def __init__(self, model: LyricsLSTM):
        super().__init__()
        self.model = model
        self.sizes = [h for _, h in model.cfg.layer_sizes()]

    def forward(self, token, artist, genre, state):
        m = self.model
        x = torch.cat([m.embed(token), m.artist_embed(artist), m.genre_embed(genre)], dim=-1)
        out_states = []
        offset = 0
        for rnn, h_size in zip(m.rnns, self.sizes, strict=True):
            h = state[:, offset:offset + h_size]
            c = state[:, offset + h_size:offset + 2 * h_size]
            offset += 2 * h_size
            gates = x @ rnn.weight_ih_l0.t() + rnn.bias_ih_l0 + h @ rnn.weight_hh_l0.t() + rnn.bias_hh_l0
            i, f, g, o = gates.chunk(4, dim=-1)
            c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
            h = torch.sigmoid(o) * torch.tanh(c)
            out_states += [h, c]
            x = h
        return m.decoder(x), torch.cat(out_states, dim=-1)


def flatten_state(state: State) -> torch.Tensor:
    """nn.LSTM state list -> flat [B, S] in StepDecoder layout."""
    return torch.cat([t for h, c in state for t in (h[0], c[0])], dim=-1)
