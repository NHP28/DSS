import torch
import torch.nn as nn
import torch.nn.functional as F
import scipy.sparse as sp
import numpy as np

class LightGCN(nn.Module):
    """
    LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation (SIGIR 2020)
    He et al.
    """
    def __init__(self, num_users, num_items, embedding_dim=64, num_layers=3, reg_weight=1e-4):
        super(LightGCN, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.reg_weight = reg_weight

        # Khởi tạo embedding cho Users và POIs (Items)
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)

        # Khởi tạo trọng số Xavier
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)

        self.norm_adj = None

    def build_normalized_adj(self, user_item_pairs):
        """
        Xây dựng ma trận kề chuẩn hóa đối xứng: A_hat = D^{-1/2} A D^{-1/2}
        """
        u = user_item_pairs[:, 0]
        i = user_item_pairs[:, 1]
        
        # Ma trận tương tác R (m x n)
        val = np.ones(len(u), dtype=np.float32)
        R = sp.coo_matrix((val, (u, i)), shape=(self.num_users, self.num_items))
        
        # Ma trận liên kết lớn: A = [[0, R], [R^T, 0]]
        adj = sp.bmat([[None, R], [R.T, None]], format="csr")
        
        # Chuẩn hóa đối xứng
        rowsum = np.array(adj.sum(1)).flatten()
        d_inv_sqrt = np.power(rowsum, -0.5, where=rowsum > 0)
        d_inv_sqrt[rowsum == 0] = 0.0
        d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
        norm_adj = d_mat_inv_sqrt.dot(adj).dot(d_mat_inv_sqrt).tocoo()
        
        # Chuyển sang PyTorch Sparse Tensor
        indices = torch.from_numpy(np.vstack((norm_adj.row, norm_adj.col)).astype(np.int64))
        values = torch.from_numpy(norm_adj.data.astype(np.float32))
        shape = torch.Size(norm_adj.shape)
        
        self.norm_adj = torch.sparse_coo_tensor(indices, values, shape).coalesce()

    def forward(self):
        """
        Lan truyền đồ thị qua K lớp (Graph Convolution mà không có hàm kích hoạt phi tuyến tính)
        """
        all_embeddings = [torch.cat([self.user_embedding.weight, self.item_embedding.weight], dim=0)]
        current_emb = all_embeddings[0]

        device = self.user_embedding.weight.device
        if self.norm_adj.device != device:
            self.norm_adj = self.norm_adj.to(device)

        for _ in range(self.num_layers):
            current_emb = torch.sparse.mm(self.norm_adj, current_emb)
            all_embeddings.append(current_emb)

        # Trung bình cộng qua các lớp (Layer Combination)
        final_embeddings = torch.stack(all_embeddings, dim=1).mean(dim=1)
        users_emb, items_emb = torch.split(final_embeddings, [self.num_users, self.num_items], dim=0)
        return users_emb, items_emb

    def compute_bpr_loss(self, users, pos_items, neg_items):
        """
        Hàm mất mát BPR (Bayesian Personalized Ranking)
        """
        users_emb, items_emb = self.forward()

        u_e = users_emb[users]
        pos_e = items_emb[pos_items]
        neg_e = items_emb[neg_items]

        # Tích vô hướng điểm dự đoán
        pos_scores = torch.sum(u_e * pos_e, dim=1)
        neg_scores = torch.sum(u_e * neg_e, dim=1)

        # BPR Loss = -ln(sigmoid(pos - neg))
        bpr_loss = -torch.mean(F.logsigmoid(pos_scores - neg_scores))

        # L2 Regularization trên embedding gốc
        u_e_0 = self.user_embedding(users)
        pos_e_0 = self.item_embedding(pos_items)
        neg_e_0 = self.item_embedding(neg_items)
        reg_loss = self.reg_weight * (u_e_0.norm(2).pow(2) + pos_e_0.norm(2).pow(2) + neg_e_0.norm(2).pow(2)) / float(len(users))

        return bpr_loss + reg_loss

    def predict_for_user(self, user_idx, users_emb=None, items_emb=None):
        """
        Dự đoán điểm xếp hạng cho toàn bộ các POIs đối với một user
        """
        if users_emb is None or items_emb is None:
            users_emb, items_emb = self.forward()
        u_e = users_emb[user_idx] # (D,)
        scores = torch.matmul(items_emb, u_e) # (num_items,)
        return scores
