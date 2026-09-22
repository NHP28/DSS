"""Giao dien demo CPR (IJCAI 2020) - Contextualized POI Recommendation, so sanh voi USG.

  streamlit run app.py
Can chay truoc: src/prepare.py, src/run_cpr.py, src/run_usg.py (tao outputs/*_top50.npz, *_results.json).
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs")
sys.path.insert(0, os.path.join(ROOT, "src"))
from data import build                                  # noqa: E402
from graphs import local_hour, poi_graph, user_graph    # noqa: E402

st.set_page_config(page_title="CPR - Gợi ý POI", page_icon="🧭", layout="wide")
GRAY, ORANGE, BLUE, GREEN = [150, 150, 145], [235, 104, 52], [42, 120, 214], [27, 175, 122]

PAPER = {  # Bang 1 cua paper (Gowalla)
    "USG": [0.0605, 0.0490, 0.0384, 0.0274, 0.0431, 0.0685, 0.1059, 0.1828],
    "IRenMF": [0.0662, 0.0538, 0.0429, 0.0303, 0.0462, 0.0742, 0.1163, 0.1991],
    "GeoMF": [0.0644, 0.0520, 0.0415, 0.0292, 0.0454, 0.0719, 0.1121, 0.1906],
    "CPR (Ours)": [0.0722, 0.0586, 0.0462, 0.0322, 0.0491, 0.0789, 0.1224, 0.2073],
}
COLS = ["P@5", "P@10", "P@20", "P@50", "R@5", "R@10", "R@20", "R@50"]


# ---------------- Tai du lieu (cache) ----------------
def need(path):
    if not os.path.exists(path):
        st.error(f"Chưa có `{os.path.relpath(path, ROOT)}`. Hãy chạy `python src/run_cpr.py` và `python src/run_usg.py` trước.")
        st.stop()
    return path


@st.cache_resource(show_spinner="Đang đọc dữ liệu Gowalla (train + tune → test) ...")
def load_data():
    return build("test")


@st.cache_resource(show_spinner="Đang dựng đồ thị user và POI (Eq. 7–10) ...")
def load_graphs(cfg_json):
    c = json.loads(cfg_json)
    ds = load_data()
    Wu = user_graph(ds.train, ds.m, ds.n, ds.social, ds.coords, k=c["k_user"], alpha=c["alpha_user"])
    Wp = poi_graph(ds.train, ds.n, ds.coords, k=c["k_poi"], alpha=c["alpha_poi"], sigma=c["sigma"])
    return Wu.tocsr(), Wp.tocsr()


@st.cache_resource
def load_outputs():
    cpr = json.load(open(need(os.path.join(OUT, "cpr_results.json"))))
    usg = json.load(open(need(os.path.join(OUT, "usg_results.json"))))
    top_c = np.load(need(os.path.join(OUT, "cpr_top50.npz")))
    top_u_path = os.path.join(OUT, "usg_top50.npz")
    top_u = np.load(top_u_path)["top"] if os.path.exists(top_u_path) else None
    return cpr, usg, top_c["top"], top_c["score"], top_u


ds = load_data()
cpr_res, usg_res, top_cpr, score_cpr, top_usg = load_outputs()
cfg = cpr_res["config"]
Wu, Wp = load_graphs(json.dumps(cfg, sort_keys=True))
friends = {}
for a, b in ds.social:
    friends.setdefault(int(a), set()).add(int(b)); friends.setdefault(int(b), set()).add(int(a))
users = np.array(sorted(ds.truth))
c = ds.coords


@st.cache_resource
def y_csc():
    return ds.Y.tocsc()


# ---------------- Sidebar ----------------
st.sidebar.title("🧭 CPR")
st.sidebar.caption("Han et al., *Contextualized Point-of-Interest Recommendation*, IJCAI 2020")
@st.cache_data
def demo_user():
    """User minh hoa: CPR trung nhieu POI trong top-10, lich su vua phai (de nhin tren ban do)."""
    best, best_key = int(users[0]), (-1, 0)
    for uu in users:
        nv = ds.Y[uu].nnz
        if not 20 <= nv <= 80:
            continue
        hc = sum(int(p) in ds.truth[uu] for p in top_cpr[uu, :10])
        hu = sum(int(p) in ds.truth[uu] for p in top_usg[uu, :10]) if top_usg is not None else 0
        key = (hc, hc - hu)
        if key > best_key:
            best, best_key = int(uu), key
    return best


st.session_state.setdefault("user", demo_user())


def random_user():
    st.session_state.user = int(np.random.choice(users))


c1, c2 = st.sidebar.columns([3, 1])
u = int(c1.number_input("User ID", 0, ds.m - 1, step=1, key="user"))
c2.button("🎲", help="Chọn user ngẫu nhiên", on_click=random_user)
K = st.sidebar.slider("Số POI gợi ý (Top-K)", 5, 50, 10)
show = st.sidebar.multiselect("Hiện trên bản đồ", ["CPR", "USG"], default=["CPR", "USG"] if top_usg is not None else ["CPR"])
st.sidebar.markdown("**Cấu hình CPR tốt nhất** (chọn trên tập tune)")
st.sidebar.json(cfg, expanded=False)

visited = ds.Y[u].indices
truth = ds.truth.get(u, set())
rec_c = top_cpr[u, :K]
rec_u = top_usg[u, :K] if top_usg is not None and top_usg[u, 0] >= 0 else None


def pr(rec):
    if rec is None or not truth:
        return None, None
    h = sum(int(p) in truth for p in rec)
    return h / K, h / len(truth)


st.title("Gợi ý POI với CPR — Contextualized POI Recommendation")
if u == demo_user():
    st.info("User mặc định được chọn để minh hoạ (CPR gợi ý đúng nhiều). Kết quả trung bình trên toàn bộ "
            "18.640 user nằm ở tab “Kết quả thí nghiệm”; bấm 🎲 để xem user ngẫu nhiên.", icon="ℹ️")
st.caption("**INPUT**: check-in (user, giờ, POI) + bạn bè + toạ độ → **XỬ LÝ**: đồ thị user/POI + tối ưu R "
           "(Laplacian + group lasso) → **OUTPUT**: top-K POI mới")

m = st.columns(6)
m[0].metric("POI đã ghé (train+tune)", len(visited))
m[1].metric("Bạn bè", len(friends.get(u, ())))
m[2].metric("POI mới trong test", len(truth))
pc, rc = pr(rec_c); pu, ru = pr(rec_u)
m[3].metric(f"CPR P@{K} / R@{K}", "—" if pc is None else f"{pc:.2f} / {rc:.2f}")
m[4].metric(f"USG P@{K} / R@{K}", "—" if pu is None else f"{pu:.2f} / {ru:.2f}")
m[5].metric("Láng giềng trên đồ thị user", Wu[u].nnz)

tab_rec, tab_in, tab_how, tab_exp = st.tabs(["🎯 Gợi ý (Output)", "📥 Dữ liệu vào (Input)",
                                             "⚙️ Vì sao gợi ý? (Xử lý)", "📊 Kết quả thí nghiệm"])

# ---------------- Tab 1 ----------------
with tab_rec:
    def pts(ids, color, kind):
        ids = np.asarray(list(ids), dtype=int)
        return pd.DataFrame({"lat": c[ids, 0], "lon": c[ids, 1], "poi": ids, "kind": kind, "color": [color] * len(ids)})

    layers = [pdk.Layer("ScatterplotLayer", pts(visited, GRAY, "Đã ghé"), get_position="[lon, lat]",
                        get_fill_color="color", get_radius=60, radius_min_pixels=3, pickable=True, opacity=0.7),
              pdk.Layer("ScatterplotLayer", pts(sorted(truth), GREEN, "POI mới trong test"), get_position="[lon, lat]",
                        get_line_color="color", filled=False, stroked=True, line_width_min_pixels=2,
                        get_radius=120, radius_min_pixels=9, pickable=True)]
    if "USG" in show and rec_u is not None:
        layers.append(pdk.Layer("ScatterplotLayer", pts(rec_u, BLUE, "Gợi ý USG"), get_position="[lon, lat]",
                                get_fill_color="color", get_radius=80, radius_min_pixels=5, pickable=True))
    if "CPR" in show:
        layers.append(pdk.Layer("ScatterplotLayer", pts(rec_c, ORANGE, "Gợi ý CPR"), get_position="[lon, lat]",
                                get_fill_color="color", get_radius=60, radius_min_pixels=4, pickable=True,
                                stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1))
    ctr = np.median(c[rec_c], axis=0)                     # can giua theo POI duoc goi y
    col_map, col_tab = st.columns([3, 2])
    with col_map:
        st.pydeck_chart(pdk.Deck(layers=layers, map_style="light", tooltip={"text": "{kind} — POI #{poi}"},
                                 initial_view_state=pdk.ViewState(latitude=float(ctr[0]), longitude=float(ctr[1]),
                                                                  zoom=10)), height=520)
        st.caption("⚪ Xám: đã ghé · 🟠 Cam: gợi ý CPR · 🔵 Xanh dương: gợi ý USG · 🟢 Vòng xanh lá: POI mới user "
                   "thật sự ghé trong giai đoạn test (chấm nằm trong vòng = gợi ý đúng)")
    with col_tab:
        vis_xyz = c[visited]
        dmin = [float(np.min(np.hypot(vis_xyz[:, 0] - c[p, 0], (vis_xyz[:, 1] - c[p, 1]) * np.cos(np.radians(c[p, 0]))))
                      * 111.2) for p in rec_c]
        in_u = set(rec_u.tolist()) if rec_u is not None else set()
        st.dataframe(pd.DataFrame({
            "Hạng": np.arange(1, K + 1), "POI": rec_c, "Điểm R*": score_cpr[u, :K],
            "Gần nhất (km)": dmin, "USG cũng gợi ý": ["✓" if int(p) in in_u else "" for p in rec_c],
            "Đúng?": ["✅" if int(p) in truth else "" for p in rec_c]}).style.format(
            {"Điểm R*": "{:.4f}", "Gần nhất (km)": "{:.2f}"}), hide_index=True, height=520, use_container_width=True)

# ---------------- Tab 2 ----------------
with tab_in:
    tr = ds.train[ds.train.u == u]
    hrs = local_hour(tr.ts.values, c[tr.l.values, 1])
    a1, a2 = st.columns(2)
    with a1:
        st.markdown(f"**Check-in của user {u} theo giờ địa phương** (đặc trưng thời gian trong Eq. 7)")
        st.bar_chart(pd.Series(np.bincount(hrs, minlength=24), name="Số check-in"), height=260)
        cnt = tr.groupby("l").size().sort_values(ascending=False)
        st.markdown("**POI đã ghé nhiều nhất**")
        st.dataframe(pd.DataFrame({"POI": cnt.index, "Số lần": cnt.values, "Vĩ độ": c[cnt.index, 0],
                                   "Kinh độ": c[cnt.index, 1]}).head(50), hide_index=True, height=260,
                     use_container_width=True)
    with a2:
        fr = sorted(friends.get(u, ()))
        st.markdown(f"**Bạn bè ({len(fr)})** — có nằm trong k-NN của đồ thị user không?")
        st.dataframe(pd.DataFrame({"Bạn": fr, "Trọng số cạnh W_user": [float(Wu[u, f]) for f in fr],
                                   "Số POI đã ghé": [ds.Y[f].nnz for f in fr]}).sort_values(
            "Trọng số cạnh W_user", ascending=False), hide_index=True, height=560, use_container_width=True)
    st.info(f"Toàn bộ: {ds.m:,} user · {ds.n:,} POI · {len(ds.train):,} check-in (train+tune) · "
            f"{len(ds.social):,} cặp bạn bè · {len(ds.truth):,} user có POI mới trong test")

# ---------------- Tab 3 ----------------
with tab_how:
    st.markdown("### 1️⃣ Đồ thị user — ai giống user này? (Eq. 7, 8)")
    st.latex(r"S^{user}=\frac{(\alpha_{user}+S^{SR})\odot S^{ST}}{1+\alpha_{user}}")
    row = Wu[u]
    nb = pd.DataFrame({"User": row.indices, "Trọng số": row.data}).sort_values("Trọng số", ascending=False).head(10)
    nb["Là bạn bè?"] = ["✓" if int(v) in friends.get(u, ()) else "" for v in nb.User]
    nb["POI chung"] = [len(set(ds.Y[v].indices) & set(visited)) for v in nb.User]
    st.dataframe(nb, hide_index=True, use_container_width=True)

    st.markdown("### 2️⃣ Vì sao POI này được gợi ý?")
    p = st.selectbox("Chọn một POI trong top-K của CPR", rec_c.tolist(),
                     format_func=lambda x: f"POI #{x}" + ("  ✅ đúng" if x in truth else ""))
    nbu = set(Wu[u].indices.tolist())
    visitors = set(y_csc()[:, p].indices.tolist())
    pn = Wp[p]
    near = pd.DataFrame({"POI láng giềng": pn.indices, "Trọng số W_poi": pn.data})
    near["User đã ghé?"] = ["✓" if int(q) in set(visited.tolist()) else "" for q in near["POI láng giềng"]]
    e1, e2 = st.columns(2)
    e1.metric("User láng giềng đã ghé POI này", len(nbu & visitors),
              help="Lan truyền qua đồ thị USER: user giống bạn đã ghé → điểm của bạn tăng")
    e2.metric("POI láng giềng mà user đã ghé", int((near["User đã ghé?"] == "✓").sum()),
              help="Lan truyền qua đồ thị POI: POI gần / cùng khung giờ với nơi bạn đã ghé → điểm tăng")
    st.dataframe(near.sort_values("Trọng số W_poi", ascending=False).head(15), hide_index=True,
                 use_container_width=True)

    st.markdown("### 3️⃣ Tối ưu (Eq. 6, Algorithm 1)")
    st.latex(r"\min_R \tfrac12\left[\lambda_1\,\mathrm{tr}(R^\top L_{user}R)+\lambda_2\,\mathrm{tr}(RL_{poi}R^\top)"
             r"+\lambda_3\|R-Y\|_F^2+\lambda_4\sum_g\sum_j\sqrt{n_g}\,\|R_{(g),j}\|_2\right]")
    st.write(f"λ1 = {cfg['lam1']}, λ2 = {cfg['lam2']}, λ3 = 1, λ4 = {cfg['lam4']}, G = {cfg['G']} cụm, "
             f"{cfg['outer']} vòng lặp xen kẽ (User step: APG · POI step: Conjugate Gradient)")
    lg = pd.DataFrame(cpr_res["log"], columns=["Vòng", "Thay đổi tương đối", "User step (s)", "POI step (s)"])
    lg["Vòng"] += 1
    st.dataframe(lg.style.format({"Thay đổi tương đối": "{:.4f}", "User step (s)": "{:.0f}", "POI step (s)": "{:.0f}"}),
                 hide_index=True, use_container_width=True)

# ---------------- Tab 4 ----------------
with tab_exp:
    st.markdown("#### Tập test Gowalla — tái lập so với Bảng 1 của paper")
    ks = ["5", "10", "20", "50"]

    def row_of(d):
        return [d[k][0] for k in ks] + [d[k][1] for k in ks]

    rows = [["USG — paper", *PAPER["USG"]], ["USG — tái lập", *row_of(usg_res["test"]["USG"])],
            ["CPR — paper", *PAPER["CPR (Ours)"]], ["CPR — tái lập", *row_of(cpr_res["test"])],
            ["IRenMF — paper (tham khảo)", *PAPER["IRenMF"]], ["GeoMF — paper (tham khảo)", *PAPER["GeoMF"]]]
    df = pd.DataFrame(rows, columns=["Phương pháp", *COLS])
    st.dataframe(df.style.format({k: "{:.4f}" for k in COLS}), hide_index=True, use_container_width=True)
    st.caption("Recall của bản tái lập chỉ tính POI mới (chưa ghé trong train) nên có thể cao hơn paper một chút; "
               "precision so sánh trực tiếp được.")
    tpath = os.path.join(OUT, "cpr_tuning.csv")
    if os.path.exists(tpath):
        st.markdown("#### Quá trình tìm tham số trên tập tune (P@10)")
        tdf = pd.read_csv(tpath)
        st.dataframe(tdf.sort_values("P@10", ascending=False).style.format(
            {k: "{:.4f}" for k in tdf.columns if "@" in k}).highlight_max(subset=["P@10"], color="#d6e6fa"),
            hide_index=True, use_container_width=True, height=380)
    fig = os.path.join(OUT, "fig_compare.png")
    if os.path.exists(fig):
        st.image(fig, use_container_width=True)
