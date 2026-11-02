import os
import sys
import pandas as pd
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DANANG_DIR = r"f:\dss\DSS_repo\data\danang"

def test_split():
    print("=== KIỂM THỬ TƯƠNG THÍCH VỚI HUẤN LUYỆN MÔ HÌNH DYNAMIC GNN / CPR ===")
    ck = pd.read_csv(os.path.join(DANANG_DIR, "checkins.csv"))
    pois = pd.read_csv(os.path.join(DANANG_DIR, "pois.csv"))
    social = pd.read_csv(os.path.join(DANANG_DIR, "social.csv"))

    print(f"Check-ins shape: {ck.shape}")
    print(f"POIs shape:      {pois.shape}")
    print(f"Social shape:    {social.shape}")

    # Temporal split 70% train, 10% tune, 20% test
    ck = ck.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tr = np.floor(size * 0.7).astype(int)
    n_tu = np.floor(size * 0.8).astype(int)
    ck["part"] = np.where(pos < n_tr, 0, np.where(pos < n_tu, 1, 2))

    train = ck[ck["part"] == 0]
    tune = ck[ck["part"] == 1]
    test = ck[ck["part"] == 2]

    print(f"Train set: {len(train)} tương tác ({len(train)/len(ck)*100:.1f}%)")
    print(f"Tune set:  {len(tune)} tương tác ({len(tune)/len(ck)*100:.1f}%)")
    print(f"Test set:  {len(test)} tương tác ({len(test)/len(ck)*100:.1f}%)")

    # Kiểm tra xem có user nào rỗng trong train không
    assert train["u"].nunique() == ck["u"].nunique(), "Có user bị thiếu trong tập train!"
    print("✅ TOÀN BỘ 100% USERS ĐỀU XUẤT HIỆN TRONG TẬP TRAIN!")
    print("✅ TẬP DỮ LIỆU ĐÀ NẴNG HOÀN TOÀN TƯƠNG THÍCH VÀ SẴN SÀNG CHO MÔ HÌNH HỌC!")

if __name__ == "__main__":
    test_split()
