"""Feature-based ranking with gradient-boosted trees: a classical supervised-ML baseline.

Each (user, POI, hour, weekday) candidate becomes one feature row; the classifier learns
P(visit). User features come only from a history that precedes the labelled events.
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

FEATURES = ["hour", "weekday", "weekend", "category", "log_popularity", "log_hour_popularity", "hour_share",
            "km_from_user_centre", "user_category_share", "log_user_events", "rating", "log_price", "catalog_popularity"]
EARTH_KM = 6371.0


def km(lat, lon, lats, lons):
    lat, lon, lats, lons = map(np.radians, (lat, lon, lats, lons))
    a = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class History:
    """Aggregates of a set of past check-ins that candidate features are computed from."""

    def __init__(self, events, pois, n_users):
        n_items = len(pois)
        self.coords = pois[["lat", "lon"]].to_numpy(float)
        self.category = pois["category_id"].to_numpy(int)
        self.static = np.column_stack([pois["rating"].to_numpy(float), np.log1p(pois["price_avg"].to_numpy(float)),
                                       pois["popularity"].to_numpy(float)])
        u, l, h = events["u"].to_numpy(int), events["l"].to_numpy(int), events["hour"].to_numpy(int)
        hourly = np.zeros((24, n_items))
        np.add.at(hourly, (h, l), 1)
        self.popularity = hourly.sum(0)
        # Rates per 10,000 events, not raw counts: the history used to fit is shorter than the one
        # used to score test events, and raw counts would shift between the two.
        scale = 1e4 / max(len(events), 1)
        self.log_popularity = np.log1p(self.popularity * scale)
        self.log_hourly = np.log1p(hourly * scale)
        self.hour_share = hourly / np.maximum(self.popularity, 1)
        self.seen = np.zeros((n_users, n_items), dtype=bool)
        self.seen[u, l] = True
        counts = np.bincount(u, minlength=n_users).astype(float)
        self.log_user_events = np.log1p(counts / max(counts.mean(), 1e-9))  # activity relative to the average user
        safe = np.maximum(counts, 1)[:, None]
        centre = np.zeros((n_users, 2))
        np.add.at(centre, u, self.coords[l])
        self.centre = np.where(counts[:, None] > 0, centre / safe, self.coords.mean(0))
        share = np.zeros((n_users, 4))
        np.add.at(share, (u, self.category[l]), 1)
        self.category_share = share / safe

    def rows(self, user, items, hour, weekday):
        """Feature matrix for one user/context against an array of candidate items."""
        items = np.asarray(items)
        n = len(items)
        distance = km(self.centre[user, 0], self.centre[user, 1], self.coords[items, 0], self.coords[items, 1])
        return np.column_stack([
            np.full(n, hour), np.full(n, weekday), np.full(n, int(weekday >= 5)), self.category[items],
            self.log_popularity[items], self.log_hourly[hour, items], self.hour_share[hour, items], distance,
            self.category_share[user, self.category[items]], np.full(n, self.log_user_events[user]), self.static[items]])


def training_set(history, positives, negatives_per_positive=4, seed=42):
    rng = np.random.default_rng(seed)
    n_items = len(history.popularity)
    X, y = [], []
    for u, l, h, w in positives[["u", "l", "hour", "day_of_week"]].to_numpy(int):
        negatives = rng.integers(n_items, size=negatives_per_positive * 2)
        negatives = negatives[(negatives != l) & ~history.seen[u, negatives]][:negatives_per_positive]
        items = np.r_[l, negatives]
        X.append(history.rows(u, items, h, w))
        y.append(np.r_[1, np.zeros(len(negatives))])
    return np.vstack(X), np.concatenate(y)


def fit_gbm(X, y, max_depth, seed=42):
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_depth=max_depth,
                                           categorical_features=[FEATURES.index("category")], random_state=seed)
    return model.fit(X, y)
