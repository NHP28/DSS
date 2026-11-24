"""Matrix factorisation trained with Bayesian Personalised Ranking (Rendle et al., 2009)."""
import numpy as np
import torch
from torch.nn import functional as F


class BPRMF:
    def __init__(self, dim=64, epochs=30, lr=0.005, batch_size=1024, reg=1e-4, seed=42):
        self.dim, self.epochs, self.lr, self.batch_size, self.reg, self.seed = dim, epochs, lr, batch_size, reg, seed

    def fit(self, pairs, n_users, n_items):
        """pairs: (n, 2) int array of (user, item) training events; repeats are kept as weight."""
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        users = torch.nn.Embedding(n_users, self.dim)
        items = torch.nn.Embedding(n_items, self.dim)
        torch.nn.init.normal_(users.weight, std=0.1)
        torch.nn.init.normal_(items.weight, std=0.1)
        optimizer = torch.optim.Adam([*users.parameters(), *items.parameters()], lr=self.lr)
        seen = np.zeros((n_users, n_items), dtype=bool)
        seen[pairs[:, 0], pairs[:, 1]] = True
        for _ in range(self.epochs):
            order = rng.permutation(len(pairs))
            for start in range(0, len(order), self.batch_size):
                batch = pairs[order[start:start + self.batch_size]]
                u, pos = batch[:, 0], batch[:, 1]
                neg = rng.integers(n_items, size=len(u))
                clash = seen[u, neg]
                while clash.any():
                    neg[clash] = rng.integers(n_items, size=int(clash.sum()))
                    clash = seen[u, neg]
                ue, pe, ne = users(torch.as_tensor(u)), items(torch.as_tensor(pos)), items(torch.as_tensor(neg))
                loss = F.softplus(-((ue * pe).sum(-1) - (ue * ne).sum(-1))).mean()
                loss = loss + self.reg * (ue.square().sum() + pe.square().sum() + ne.square().sum()) / len(u)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        self.U, self.V = users.weight.detach().numpy(), items.weight.detach().numpy()
        return self

    def predict(self, users):
        return self.U[users] @ self.V.T
