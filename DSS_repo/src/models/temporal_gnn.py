import torch
import torch.nn as nn
import torch.nn.functional as F
import scipy.sparse as sp
import numpy as np
import math

class ContinuousTimeEncoder(nn.Module):
    """
    Mã hóa thời gian liên tục dựa trên định lý Bochner (Fourier Time Embedding / TGAT)
    Phi(t) = [cos(w_1 * t + b_1), sin(w_1 * t + b_1), ...]
    Kết hợp nhúng giờ trong ngày (0-23) và ngày trong tuần (0-6).
    """
    def __init__(self, time_dim=32):
        super(ContinuousTimeEncoder, self).__init__()
        self.time_dim = time_dim
        self.half_dim = time_dim // 2

        # Tham số học tần số và pha
        self.weights = nn.Parameter(torch.randn(self.half_dim))
        self.bias = nn.Parameter(torch.zeros(self.half_dim))

        # Discrete Time Embeddings
        self.hour_embedding = nn.Embedding(24, time_dim)
        self.weekday_embedding = nn.Embedding(7, time_dim)

        self.proj = nn.Sequential(
            nn.Linear(time_dim * 2, time_dim),
            nn.ReLU(),
            nn.Linear(time_dim, time_dim)
        )

    def forward(self, timestamps, hours=None, weekdays=None):
        """
        timestamps: (B,) epoch timestamp dạng float
        hours: (B,) 0-23
        weekdays: (B,) 0-6
        """
        # Chuẩn hóa timestamp về đơn vị ngày (86400s)
        t = (timestamps / 86400.0).unsqueeze(-1) # (B, 1)
        freq = t * self.weights.unsqueeze(0) + self.bias.unsqueeze(0) # (B, half_dim)
        fourier_time = torch.cat([torch.cos(freq), torch.sin(freq)], dim=-1) # (B, time_dim)

        if hours is not None and weekdays is not None:
            discrete_time = self.hour_embedding(hours) + self.weekday_embedding(weekdays) # (B, time_dim)
            combined = torch.cat([fourier_time, discrete_time], dim=-1)
            return self.proj(combined)
        return fourier_time

class SpatialEncoder(nn.Module):
    """
    Mã hóa đặc trưng không gian địa lý:
    Tọa độ GPS (lat, lon) -> MLP -> Vector không gian d_dim
    """
    def __init__(self, spatial_dim=32):
        super(SpatialEncoder, self).__init__()
        self.mlp = nn.Sequential(
            nn.Linear(2, spatial_dim),
            nn.ReLU(),
            nn.Linear(spatial_dim, spatial_dim)
        )

    def forward(self, coords):
        """
        coords: Tensor (N, 2) [lat, lon]
        """
        return self.mlp(coords)

class TemporalGNN(nn.Module):
    """
    Mô hình đề xuất: Temporal Graph Neural Network for POI Recommendation (TGNN_POIRec)
    Tích hợp:
    1. Đồ thị tương tác User-POI qua LightGCN backbone.
    2. Continuous & Discrete Time Embedding (Giờ trong ngày, khoảng cách thời gian).
    3. Spatial Coordinates Embedding (Tọa độ không gian Đà Nẵng).
    4. Temporal Gating Mechanism: Điều chỉnh biểu diễn User/POI động theo thời gian truy vấn.
    """
    def __init__(
        self,
        num_users,
        num_items,
        coords=None, # np.ndarray (num_items, 2)
        category_ids=None, # np.ndarray (num_items,)
        num_categories=4,
        embedding_dim=64,
        time_dim=32,
        num_layers=3,
        reg_weight=1e-4,
        use_time=True,
        use_spatial=True
    ):
        super(TemporalGNN, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embedding_dim = embedding_dim
        self.time_dim = time_dim
        self.num_layers = num_layers
        self.reg_weight = reg_weight
        self.use_time = use_time
        self.use_spatial = use_spatial

        # 1. Base Static Embeddings
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)

        # 2. Time Encoder
        if self.use_time:
            self.time_encoder = ContinuousTimeEncoder(time_dim=time_dim)
            self.time_proj_user = nn.Linear(time_dim, embedding_dim)
            self.time_proj_item = nn.Linear(time_dim, embedding_dim)
            # Gating mechanism
            self.user_gate = nn.Sequential(
                nn.Linear(embedding_dim * 2, embedding_dim),
                nn.Sigmoid()
            )

        # 3. Spatial & Category Encoder
        if coords is not None:
            self.coords = torch.from_numpy(coords).float()
        else:
            self.coords = torch.zeros((num_items, 2), dtype=torch.float32)

        if self.use_spatial:
            self.spatial_encoder = SpatialEncoder(spatial_dim=embedding_dim)
            self.category_embedding = nn.Embedding(num_categories, embedding_dim)
            if category_ids is not None:
                self.category_ids = torch.from_numpy(category_ids).long()
            else:
                self.category_ids = torch.zeros(num_items, dtype=torch.long)

        self.norm_adj = None

    def build_normalized_adj(self, user_item_pairs):
        """Xây dựng ma trận kề chuẩn hóa giống LightGCN."""
        u = user_item_pairs[:, 0]
        i = user_item_pairs[:, 1]
        val = np.ones(len(u), dtype=np.float32)
        R = sp.coo_matrix((val, (u, i)), shape=(self.num_users, self.num_items))
        adj = sp.bmat([[None, R], [R.T, None]], format="csr")

        rowsum = np.array(adj.sum(1)).flatten()
        d_inv_sqrt = np.power(rowsum, -0.5, where=rowsum > 0)
        d_inv_sqrt[rowsum == 0] = 0.0
        d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
        norm_adj = d_mat_inv_sqrt.dot(adj).dot(d_mat_inv_sqrt).tocoo()

        indices = torch.from_numpy(np.vstack((norm_adj.row, norm_adj.col)).astype(np.int64))
        values = torch.from_numpy(norm_adj.data.astype(np.float32))
        shape = torch.Size(norm_adj.shape)
        self.norm_adj = torch.sparse_coo_tensor(indices, values, shape).coalesce()

    def get_graph_embeddings(self):
        """Lan truyền qua đồ thị tương tác bằng Graph Convolution."""
        all_embeddings = [torch.cat([self.user_embedding.weight, self.item_embedding.weight], dim=0)]
        current_emb = all_embeddings[0]

        device = self.user_embedding.weight.device
        if self.norm_adj.device != device:
            self.norm_adj = self.norm_adj.to(device)

        for _ in range(self.num_layers):
            current_emb = torch.sparse.mm(self.norm_adj, current_emb)
            all_embeddings.append(current_emb)

        final_embeddings = torch.stack(all_embeddings, dim=1).mean(dim=1)
        users_emb, items_emb = torch.split(final_embeddings, [self.num_users, self.num_items], dim=0)

        # Kết hợp thông tin không gian vào item embedding
        if self.use_spatial:
            device = items_emb.device
            coords = self.coords.to(device)
            cat_ids = self.category_ids.to(device)
            spatial_feat = self.spatial_encoder(coords) + self.category_embedding(cat_ids)
            items_emb = items_emb + spatial_feat

        return users_emb, items_emb

    def compute_bpr_loss(self, users, pos_items, neg_items, timestamps, hours=None, weekdays=None):
        """
        Hàm mất mát BPR kết hợp Dynamic Temporal Context
        """
        users_emb, items_emb = self.get_graph_embeddings()

        u_e = users_emb[users]
        pos_e = items_emb[pos_items]
        neg_e = items_emb[neg_items]

        # Tích hợp Time Context động nếu use_time=True
        if self.use_time:
            t_emb = self.time_encoder(timestamps, hours, weekdays) # (B, time_dim)
            t_user_ctx = self.time_proj_user(t_emb) # (B, embedding_dim)
            
            # Gating: Sở thích user tại thời điểm t
            gate = self.user_gate(torch.cat([u_e, t_user_ctx], dim=-1))
            u_e = u_e + gate * t_user_ctx

            # Context POI theo thời gian
            t_item_ctx = self.time_proj_item(t_emb)
            pos_e = pos_e + t_item_ctx
            neg_e = neg_e + t_item_ctx

        pos_scores = torch.sum(u_e * pos_e, dim=1)
        neg_scores = torch.sum(u_e * neg_e, dim=1)

        bpr_loss = -torch.mean(F.logsigmoid(pos_scores - neg_scores))

        # L2 Regularization
        reg_loss = self.reg_weight * (
            self.user_embedding(users).norm(2).pow(2)
            + self.item_embedding(pos_items).norm(2).pow(2)
            + self.item_embedding(neg_items).norm(2).pow(2)
        ) / float(len(users))

        return bpr_loss + reg_loss

    def predict_for_user_at_time(self, user_idx, timestamp=None, hour=None, weekday=None, users_emb=None, items_emb=None):
        """
        Dự đoán Top-K POIs cho user tại thời điểm cụ thể (Time-aware Personalized Recommendation)
        """
        if users_emb is None or items_emb is None:
            users_emb, items_emb = self.get_graph_embeddings()

        u_e = users_emb[user_idx] # (embedding_dim,)

        if self.use_time and timestamp is not None and hour is not None and weekday is not None:
            device = u_e.device
            ts_tensor = torch.tensor([timestamp], dtype=torch.float32, device=device)
            h_tensor = torch.tensor([hour], dtype=torch.long, device=device)
            w_tensor = torch.tensor([weekday], dtype=torch.long, device=device)

            t_emb = self.time_encoder(ts_tensor, h_tensor, w_tensor)
            t_user_ctx = self.time_proj_user(t_emb).squeeze(0)
            gate = self.user_gate(torch.cat([u_e, t_user_ctx], dim=-1))
            u_e = u_e + gate * t_user_ctx

            t_item_ctx = self.time_proj_item(t_emb) # (1, embedding_dim)
            items_repr = items_emb + t_item_ctx
        else:
            items_repr = items_emb

        scores = torch.matmul(items_repr, u_e) # (num_items,)
        return scores
