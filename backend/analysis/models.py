"""Predictive modelling with a strict chronological protocol.

Protocol
* Split POOLED BY DATE: unique trading dates sorted, first 70% -> train, next 15% -> validation,
  last 15% -> test. A date never appears in two splits; no shuffling anywhere.
* Purge/embargo: a training row at date d has a label that uses prices up to d+h sessions. Rows
  whose label window reaches into the next split are dropped (the last h train dates and the
  last h validation dates), so no label overlaps a later split.
* Standardisation statistics (mean/std) are fit on TRAIN rows only and applied to val/test.
* Baselines first: (a) naive zero return, (b) historical mean of training returns,
  (c) Ridge regression (alpha chosen on validation). Only then a small LSTM, which is skipped
  with a logged reason when there are fewer than ``min_train_sequences`` training sequences.
* Metrics on the test split: MAE, RMSE, directional accuracy (share of test days where
  sign(prediction) == sign(actual); undefined for the always-zero model).
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from analysis import config as C

log = logging.getLogger(__name__)

MODEL_FEATURES = ["ret", "ret_lag1", "ret_lag2", "ret_lag3", "ret_lag4", "vol20", "vol30", "px_sma20",
                  "px_sma50", "px_sma200", "rsi14", "volume_change", "volume_z", "news_count",
                  "sentiment_filled", "has_news"]
HORIZONS = {"target_next_1d": 1, "target_fwd_5d": 5}


def chronological_split(dates: pd.Series, train: float = 0.70, val: float = 0.15, embargo: int = 0
                        ) -> dict[str, np.ndarray]:
    """Boolean masks for train/val/test by unique date, with an optional embargo (in sessions)."""
    dv = pd.to_datetime(dates).to_numpy(dtype="datetime64[ns]")
    uniq = np.unique(dv)  # sorted ascending
    n = len(uniq)
    if n < 3:
        raise ValueError("need at least 3 distinct dates to split")
    n_tr = max(1, int(round(n * train)))
    n_va = max(1, int(round(n * val)))
    n_tr = min(n_tr, n - 2)
    n_va = min(n_va, n - n_tr - 1)
    tr_dates = uniq[: max(0, n_tr - embargo)]
    va_dates = uniq[n_tr: max(n_tr, n_tr + n_va - embargo)]
    te_dates = uniq[n_tr + n_va:]
    return {"train": np.isin(dv, tr_dates), "val": np.isin(dv, va_dates), "test": np.isin(dv, te_dates)}


def metrics(y_true: np.ndarray, y_pred: np.ndarray, directional: bool = True) -> dict:
    y_true = np.asarray(y_true, float); y_pred = np.asarray(y_pred, float)
    err = y_pred - y_true
    da = None
    if directional:
        mask = y_true != 0
        da = float(np.mean(np.sign(y_pred[mask]) == np.sign(y_true[mask]))) if mask.any() else None
    return {"mae": float(np.mean(np.abs(err))), "rmse": float(math.sqrt(np.mean(err ** 2))),
            "directional_accuracy": da, "n_test": int(len(y_true))}


def prepare(features: pd.DataFrame, target: str) -> pd.DataFrame:
    df = features.copy()
    df["sentiment_filled"] = df["sentiment_mean"].fillna(0.0)  # no news -> neutral; has_news flags it
    df = df.dropna(subset=MODEL_FEATURES + [target])
    return df.sort_values(["date", "ticker"]).reset_index(drop=True)


class Ridge:
    """Closed-form ridge regression (intercept unpenalised).

    Implemented with numpy instead of scikit-learn because sklearn's compiled extensions are
    blocked by Windows Application Control on this machine; the maths matches
    ``sklearn.linear_model.Ridge(fit_intercept=True)``.
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Ridge":
        xm, ym = X.mean(axis=0), y.mean()
        Xc, yc = X - xm, y - ym
        A = Xc.T @ Xc + self.alpha * np.eye(X.shape[1])
        self.coef_ = np.linalg.solve(A, Xc.T @ yc)
        self.intercept_ = float(ym - xm @ self.coef_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return X @ self.coef_ + self.intercept_


class Standardizer:
    def fit(self, X: np.ndarray) -> "Standardizer":
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mu) / self.sd


# ---------------------------------------------------------------------------
# LSTM
# ---------------------------------------------------------------------------

def build_sequences(df: pd.DataFrame, Xs: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-ticker sliding windows of ``seq_len`` consecutive rows ending at row i.
    Returns (X_seq, y, end_row_index). The window only contains rows <= i (past/present)."""
    xs, ys, idx = [], [], []
    for _, g in df.groupby("ticker", sort=True):
        rows = g.sort_values("date").index.to_numpy()
        for k in range(seq_len - 1, len(rows)):
            win = rows[k - seq_len + 1: k + 1]
            xs.append(Xs[win]); ys.append(df.at[rows[k], "_y"]); idx.append(rows[k])
    if not xs:
        return np.empty((0, seq_len, Xs.shape[1])), np.empty(0), np.empty(0, dtype=int)
    return np.stack(xs), np.asarray(ys, float), np.asarray(idx, int)


def train_lstm(Xtr, ytr, Xva, yva, *, hidden: int = 32, max_epochs: int = 50, patience: int = 5,
               lr: float = 1e-3, batch_size: int = 64, seed: int = C.SEED) -> tuple[object, dict]:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    np.random.seed(seed)

    class Net(nn.Module):
        def __init__(self, n_feat: int):
            super().__init__()
            self.lstm = nn.LSTM(n_feat, hidden, batch_first=True)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    net = Net(Xtr.shape[2])
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    Xt, yt = torch.tensor(Xtr, dtype=torch.float32), torch.tensor(ytr, dtype=torch.float32)
    Xv, yv = torch.tensor(Xva, dtype=torch.float32), torch.tensor(yva, dtype=torch.float32)
    gen = torch.Generator().manual_seed(seed)
    best, best_state, bad, history = float("inf"), None, 0, []
    for epoch in range(max_epochs):
        net.train()
        perm = torch.randperm(len(Xt), generator=gen)  # shuffles mini-batches of TRAIN windows only
        for i in range(0, len(Xt), batch_size):
            b = perm[i:i + batch_size]
            opt.zero_grad()
            loss = loss_fn(net(Xt[b]), yt[b])
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vl = float(loss_fn(net(Xv), yv)) if len(Xv) else float("nan")
        history.append(vl)
        if vl < best - 1e-6:
            best, bad = vl, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        net.load_state_dict(best_state)
    return net, {"epochs_run": len(history), "best_val_mse_scaled": best if best < float("inf") else None}


def run_models(features: pd.DataFrame, *, target: str = "target_next_1d", seed: int = C.SEED,
               min_train_sequences: int = 500, seq_len: int = 20, lstm_max_epochs: int = 50,
               force_lstm: bool = False) -> dict:
    C.set_seeds(seed)
    horizon = HORIZONS.get(target, 1)
    df = prepare(features, target)
    result: dict = {"target": target, "features": MODEL_FEATURES, "models": {}, "notes": []}
    if df["date"].nunique() < 10:
        result["notes"].append(f"{target}: too few dates ({df['date'].nunique()}) to model; skipped.")
        return result
    masks = chronological_split(df["date"], embargo=horizon)
    tr, va, te = masks["train"], masks["val"], masks["test"]
    if tr.sum() < 2 or te.sum() < 1:
        result["notes"].append(f"{target}: empty train/test split after embargo; skipped.")
        return result
    result["split"] = {k: {"rows": int(m.sum()),
                           "start": str(df.loc[m, "date"].min().date()) if m.any() else None,
                           "end": str(df.loc[m, "date"].max().date()) if m.any() else None}
                       for k, m in masks.items()}
    result["split"]["embargo_sessions"] = horizon

    X = df[MODEL_FEATURES].to_numpy(float)
    y = df[target].to_numpy(float)
    scaler = Standardizer().fit(X[tr])          # fit on TRAIN only
    Xs = scaler.transform(X)
    y_te = y[te]
    preds = {"date": df.loc[te, "date"].to_numpy(), "ticker": df.loc[te, "ticker"].to_numpy(), "actual": y_te}

    # (a) naive zero
    p0 = np.zeros_like(y_te)
    result["models"]["naive_zero"] = metrics(y_te, p0, directional=False); preds["naive_zero"] = p0
    # (b) historical mean of training targets
    pm = np.full_like(y_te, y[tr].mean())
    result["models"]["historical_mean"] = metrics(y_te, pm); preds["historical_mean"] = pm
    # (c) Ridge, alpha selected on validation RMSE
    best_alpha, best_rmse = None, float("inf")
    for alpha in (0.1, 1.0, 10.0, 100.0, 1000.0):
        m = Ridge(alpha=alpha).fit(Xs[tr], y[tr])
        r = metrics(y[va], m.predict(Xs[va]))["rmse"] if va.any() else float("inf")
        if r < best_rmse:
            best_alpha, best_rmse = alpha, r
    ridge = Ridge(alpha=best_alpha or 1.0).fit(Xs[tr], y[tr])
    pr = ridge.predict(Xs[te])
    result["models"]["ridge"] = {**metrics(y_te, pr), "alpha": best_alpha}
    preds["ridge"] = pr
    result["ridge_coefficients"] = dict(zip(MODEL_FEATURES, map(float, ridge.coef_)))

    # (d) LSTM — only after baselines, only with enough data
    df["_y"] = (y - y[tr].mean()) / (y[tr].std() or 1.0)  # target scaled with TRAIN stats
    Xseq, yseq, end_idx = build_sequences(df, Xs, seq_len)
    split_of = np.select([tr, va, te], ["train", "val", "test"], "embargo")
    seq_split = split_of[end_idx] if len(end_idx) else np.array([])
    n_tr_seq = int((seq_split == "train").sum())
    result["lstm_train_sequences"] = n_tr_seq
    if n_tr_seq < min_train_sequences and not force_lstm:
        reason = (f"LSTM skipped: only {n_tr_seq} training sequences (< {min_train_sequences} required); "
                  "a neural sequence model would mostly fit noise.")
        log.info(reason)
        result["notes"].append(reason)
        result["models"]["lstm"] = {"skipped": True, "reason": reason}
    elif (seq_split == "test").sum() == 0 or n_tr_seq == 0:
        reason = "LSTM skipped: no train or test sequences after windowing."
        result["notes"].append(reason)
        result["models"]["lstm"] = {"skipped": True, "reason": reason}
    else:
        import torch

        trm, vam, tem = seq_split == "train", seq_split == "val", seq_split == "test"
        net, info = train_lstm(Xseq[trm], yseq[trm], Xseq[vam], yseq[vam], max_epochs=lstm_max_epochs, seed=seed)
        with torch.no_grad():
            p_scaled = net(torch.tensor(Xseq[tem], dtype=torch.float32)).numpy()
        p_lstm = p_scaled * (y[tr].std() or 1.0) + y[tr].mean()
        y_lstm = y[end_idx[tem]]
        result["models"]["lstm"] = {**metrics(y_lstm, p_lstm), **info, "seq_len": seq_len,
                                    "note": "evaluated on test rows with a full 20-session history"}
    result["predictions"] = pd.DataFrame(preds)
    naive = result["models"]["naive_zero"]["rmse"]
    beats = [k for k, v in result["models"].items() if "rmse" in v and k != "naive_zero" and v["rmse"] < naive]
    result["notes"].append(f"{target}: models with lower test RMSE than naive zero: {beats or 'none'}.")
    return result
