from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="先行研究の3D散布図", layout="wide")
st.title("遊びの発達状況（3D散布図）")

EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"
TODAY = pd.Timestamp("2026-09-23")
WEEK_AGO = TODAY - pd.Timedelta(days=7)
TARGET_ID = "C001"
MIN_AGE = 42
AGE_POINTS = [33, 36, 39, 42]
STAGE_MAX = {"ボール": 5, "お絵描き": 4, "ぬいぐるみ": 3}
STAGE_COLORS = {1: "#456CB3", 2: "#43A0A6", 3: "#E1B04D", 4: "#9469C4", 5: "#D784A3"}
CAMERA = dict(eye=dict(x=1.7, y=-1.7, z=0.9))


def calculate_age(dates, birthdays):
    """満月齢を計算する。"""
    return ((dates.dt.year - birthdays.dt.year) * 12
            + dates.dt.month - birthdays.dt.month
            - (dates.dt.day < birthdays.dt.day).astype(int))


@st.cache_data
def load_data(path, modified_time):
    obs = pd.read_excel(path, sheet_name="観測データ")
    children = pd.read_excel(path, sheet_name="子ども基本情報")
    return obs, children


if not EXCEL_PATH.exists():
    st.error("同じフォルダに『デモデータ.xlsx』を置いてください。")
    st.stop()

try:
    df, children = load_data(str(EXCEL_PATH), EXCEL_PATH.stat().st_mtime)
except Exception as exc:
    st.error(f"Excelの読み込みに失敗しました：{exc}")
    st.stop()

required_obs = {"子どもID", "観測日", "おもちゃの種類", "発達段階", "観測回数"}
required_children = {"子どもID", "誕生年月"}
if not required_obs.issubset(df.columns) or not required_children.issubset(children.columns):
    st.error("Excelのシート名・列名を確認してください。")
    st.stop()

df["観測日"] = pd.to_datetime(df["観測日"], errors="coerce")
children["誕生年月"] = pd.to_datetime(children["誕生年月"], errors="coerce")
df["発達段階"] = pd.to_numeric(df["発達段階"], errors="coerce")
df["観測回数"] = pd.to_numeric(df["観測回数"], errors="coerce").fillna(0).clip(lower=0).astype(int)
children = children.drop_duplicates("子どもID").dropna(subset=["子どもID", "誕生年月"]).copy()
children["現在月齢"] = calculate_age(pd.Series(TODAY, index=children.index), children["誕生年月"])

eligible_peer_ids = set(children.loc[
    (children["子どもID"] != TARGET_ID) & (children["現在月齢"] >= MIN_AGE), "子どもID"
])
child_ids = sorted(children["子どもID"].unique())
id_map = {cid: i + 1 for i, cid in enumerate(child_ids)}

df = df.merge(children[["子どもID", "誕生年月"]], on="子どもID", how="left")
df = df.dropna(subset=["観測日", "誕生年月", "発達段階"]).copy()
df["月齢"] = calculate_age(df["観測日"], df["誕生年月"])
df["識別番号"] = df["子どもID"].map(id_map)


def get_peer_history(toy):
    """比較児の33・36・39・42か月時点の記録。各月齢で最新観測日を使用。"""
    result = df.loc[
        df["子どもID"].isin(eligible_peer_ids)
        & (df["おもちゃの種類"] == toy)
        & df["月齢"].isin(AGE_POINTS)
        & (df["観測日"] <= TODAY)
        & df["発達段階"].between(1, STAGE_MAX[toy])
        & (df["観測回数"] > 0)
    ].copy()
    if result.empty:
        return result
    latest = result.groupby(["子どもID", "月齢"])["観測日"].transform("max")
    return result.loc[result["観測日"] == latest].copy()


def get_target_snapshot(toy, day):
    """対象児の指定日だけの記録。"""
    return df.loc[
        (df["子どもID"] == TARGET_ID)
        & (df["おもちゃの種類"] == toy)
        & (df["観測日"] == day)
        & df["発達段階"].between(1, STAGE_MAX[toy])
        & (df["観測回数"] > 0)
    ].copy()


def get_target_history(toy):
    """対象児の33・36・39・42か月時点の履歴。"""
    result = df.loc[
        (df["子どもID"] == TARGET_ID)
        & (df["おもちゃの種類"] == toy)
        & df["月齢"].isin(AGE_POINTS)
        & (df["観測日"] <= TODAY)
        & df["発達段階"].between(1, STAGE_MAX[toy])
        & (df["観測回数"] > 0)
    ].copy()
    if result.empty:
        return result
    latest = result.groupby(["子どもID", "月齢"])["観測日"].transform("max")
    return result.loc[result["観測日"] == latest].copy()


def spread_points(source):
    """観測回数分の点を生成し、月齢と識別番号方向だけ少しずらす。"""
    if source.empty:
        return source.copy()
    expanded = source.loc[source.index.repeat(source["観測回数"])].reset_index(drop=True)
    groups = ["子どもID", "観測日", "月齢", "発達段階"]
    expanded["点番号"] = expanded.groupby(groups).cumcount()
    expanded["点数"] = expanded.groupby(groups)["点番号"].transform("count")
    angle = 2 * np.pi * expanded["点番号"] / expanded["点数"].clip(lower=1)
    radius = np.where(expanded["点数"] > 1, 0.22, 0.0)
    expanded["表示月齢"] = expanded["月齢"].astype(float) + radius * np.cos(angle)
    expanded["表示識別番号"] = expanded["識別番号"].astype(float) + radius * np.sin(angle)
    expanded["表示発達段階"] = expanded["発達段階"].astype(float)
    return expanded


def make_figure(source, toy, height=620):
    fig = go.Figure()
    expanded = spread_points(source)
    peers = expanded.loc[expanded["子どもID"] != TARGET_ID]
    target = expanded.loc[expanded["子どもID"] == TARGET_ID]

    for stage in range(1, STAGE_MAX[toy] + 1):
        part = peers.loc[peers["発達段階"] == stage]
        if not part.empty:
            fig.add_trace(go.Scatter3d(
                x=part["表示月齢"], y=part["表示識別番号"], z=part["表示発達段階"],
                mode="markers", name="比較児", showlegend=False,
                marker=dict(size=4, color=STAGE_COLORS[stage], opacity=0.35),
                hoverinfo="skip"
            ))
    if not target.empty:
        fig.add_trace(go.Scatter3d(
            x=target["表示月齢"], y=target["表示識別番号"], z=target["表示発達段階"],
            mode="markers", name="対象児", showlegend=False,
            marker=dict(size=7, color="red", opacity=1), hoverinfo="skip"
        ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="月齢", range=[32, 43], tickmode="array", tickvals=AGE_POINTS),
            yaxis=dict(title="識別番号", range=[0.5, len(child_ids) + 0.5], dtick=1),
            zaxis=dict(title="発達段階", range=[0.5, STAGE_MAX[toy] + 0.5],
                       tickmode="array", tickvals=list(range(1, STAGE_MAX[toy] + 1))),
            aspectmode="cube", camera=CAMERA
        ),
        height=height, margin=dict(l=0, r=0, t=0, b=0), showlegend=False
    )
    return fig


def show_chart(source, toy, key):
    if source.empty:
        st.info("表示できる観測データがありません。")
    else:
        st.plotly_chart(make_figure(source, toy), use_container_width=True,
                        key=key, config={"displayModeBar": False, "scrollZoom": False})


toy = st.selectbox("おもちゃを選択", list(STAGE_MAX.keys()), index=1)
view = st.radio("表示する情報", ["現在・同月齢", "時系列", "月齢別の履歴"], horizontal=True)
peer_history = get_peer_history(toy)

if view == "現在・同月齢":
    st.subheader("現在の発達状況と同月齢児の比較")
    current = get_target_snapshot(toy, TODAY)
    plot_data = pd.concat([peer_history, current], ignore_index=True)
    show_chart(plot_data, toy, "current_scatter")
    st.caption("赤：対象児の2026年9月23日の記録。半透明：比較児の33・36・39・42か月時点の履歴。")
    st.caption("同月齢の比較は、各比較児の42か月時点の点を見て判断します。")

elif view == "時系列":
    st.subheader("1週間前と今日の比較")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1週間前（2026年9月16日）**")
        old_data = pd.concat([peer_history, get_target_snapshot(toy, WEEK_AGO)], ignore_index=True)
        show_chart(old_data, toy, "week_scatter")
    with col2:
        st.markdown("**今日（2026年9月23日）**")
        new_data = pd.concat([peer_history, get_target_snapshot(toy, TODAY)], ignore_index=True)
        show_chart(new_data, toy, "today_scatter")
    st.caption("両図とも比較児の背景データは共通で、赤い対象児の点だけが各日付の記録に切り替わります。")

else:
    st.subheader("33・36・39・42か月の観測履歴")
    history = pd.concat([peer_history, get_target_history(toy)], ignore_index=True)
    show_chart(history, toy, "history_scatter")
    st.caption("各児・各月齢の最新観測日の記録を表示しています。")

st.caption("赤：対象児／その他：発達段階ごとの色分け（半透明）。ドラッグで3D回転できます。")
st.caption(f"比較候補児29人のうち、2026年9月23日時点で42か月以上の{len(eligible_peer_ids)}人を使用。")
st.caption("点はExcelの『観測回数』分表示しています。『使用回数』列は使用していません。")
