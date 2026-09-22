"""Tao bo Gowalla giong het paper CPR (IJCAI 2020) / benchmark VLDB 2017 tu du lieu SNAP goc.

  python src/prepare.py

INPUT  (SNAP, https://snap.stanford.edu/data/loc-gowalla.html):
  data/loc-gowalla_totalCheckins.txt.gz : user  time(ISO, UTC)  lat  lon  location_id
  data/loc-gowalla_edges.txt.gz         : user  user   (ban be, vo huong)
Loc LAP cho den khi on dinh: user co >= 15 POI khac nhau, POI co >= 10 user khac nhau
  -> 18,737 user, 32,510 POI, 1,278,274 check-in (khop chinh xac so lieu trong paper).
OUTPUT (data/processed/):
  checkins.csv : u  l  ts(unix, UTC)      (u, l da danh so lai tu 0)
  pois.csv     : l  lat  lon
  social.csv   : u  v                    (chi giu cap ma ca hai user deu con lai, u < v)
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = os.path.join(ROOT, "data"), os.path.join(ROOT, "data", "processed")
MIN_USER_POIS, MIN_POI_USERS = 15, 10


def iterative_filter(df):
    while True:
        n = len(df)
        up = df.groupby("u").l.nunique()
        df = df[df.u.isin(up[up >= MIN_USER_POIS].index)]
        pv = df.groupby("l").u.nunique()
        df = df[df.l.isin(pv[pv >= MIN_POI_USERS].index)]
        if len(df) == n:
            return df


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(os.path.join(RAW, "loc-gowalla_totalCheckins.txt.gz"), sep="\t", header=None,
                     names=["u", "t", "lat", "lon", "l"])
    print(f"SNAP goc: {len(df):,} check-in, {df.u.nunique():,} user, {df.l.nunique():,} POI")
    df = iterative_filter(df)
    print(f"Sau khi loc: {len(df):,} check-in, {df.u.nunique():,} user, {df.l.nunique():,} POI")

    umap = {u: i for i, u in enumerate(sorted(df.u.unique()))}
    lmap = {l: i for i, l in enumerate(sorted(df.l.unique()))}
    df["ts"] = pd.to_datetime(df.t, utc=True).astype("int64") // 10**9
    out = pd.DataFrame({"u": df.u.map(umap), "l": df.l.map(lmap), "ts": df.ts})
    out.to_csv(os.path.join(OUT, "checkins.csv"), index=False)

    # Toa do POI: moi location_id co 1 toa do co dinh trong SNAP -> lay gia tri dau tien
    pois = df.groupby("l")[["lat", "lon"]].first().reset_index()
    pois["l"] = pois.l.map(lmap)
    pois.sort_values("l").to_csv(os.path.join(OUT, "pois.csv"), index=False)

    e = pd.read_csv(os.path.join(RAW, "loc-gowalla_edges.txt.gz"), sep="\t", header=None, names=["u", "v"])
    e = e[e.u.isin(umap) & e.v.isin(umap)]
    e = pd.DataFrame({"u": e.u.map(umap), "v": e.v.map(umap)})
    e = e[e.u < e.v].drop_duplicates()
    e.to_csv(os.path.join(OUT, "social.csv"), index=False)
    print(f"Ban be (vo huong) giua cac user con lai: {len(e):,} canh")


if __name__ == "__main__":
    main()
