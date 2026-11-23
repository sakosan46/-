from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="先行研究の3D散布図", layout="wide")
st.title("遊びの発達状況（3D散布図）")

EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"

TODAY = pd.Timestamp("2026-09-23")
TARGET_ID = "C001"
MIN_AGE = 30

# 時系列で表示する4つの観測日
TIME_POINTS = [
    TODAY - pd.DateOffset(months=9),
    TODAY - pd.DateOffset(months=6),
    TODAY - pd.DateOffset(months=3),
    TODAY,
]

STAGE_MAX = {"ボール": 5, "お絵描き": 4, "ぬいぐるみ": 3}

STAGE_COLORS = {
    1: "#456CB3",
    2: "#43A0A6",
    3: "#E1B04D",
    4: "#9469C4",
    5: "#D784A3",
}

CAMERA = dict(eye=dict(x=1.7, y=-1.7, z=0.9))


@st.cache_data
def load_data(path, modified_time):
    observations = pd.read_excel(path, sheet_name="観測データ")
    children = pd.read_excel(path, sheet_name="子ども基本情報")
    return observations, children


def calculate_age(dates, birthdays):
    """観測日・生年月日から満月齢を計算する"""
    return (
        (dates.dt.year - birthdays.dt.year) * 12
        + dates.dt.month - birthdays.dt.month
        - (dates.dt.day < birthdays.dt.day).astype(int)
    )


if not EXCEL_PATH.exists():
    st.error("デモデータ.xlsx が見つかりません。")
    st.stop()

try:
    df, children = load_data(
        str(EXCEL_PATH),
        EXCEL_PATH.stat().st_mtime
    )
except Exception as exc:
    st.error(f"Excelの読み込みに失敗しました：{exc}")
    st.stop()


required_obs = {
    "子どもID", "観測日", "おもちゃの種類",
    "発達段階", "観測回数"
}
required_children = {"子どもID", "誕生年月"}

if (
    not required_obs.issubset(df.columns)
    or not required_children.issubset(children.columns)
):
    st.error("Excelのシート名・列名を確認してください。")
    st.stop()


# データ形式を統一
df["観測日"] = pd.to_datetime(df["観測日"], errors="coerce")
children["誕生年月"] = pd.to_datetime(
    children["誕生年月"], errors="coerce"
)

df["発達段階"] = pd.to_numeric(
    df["発達段階"], errors="coerce"
)

df["観測回数"] = (
    pd.to_numeric(df["観測回数"], errors="coerce")
    .fillna(0)
    .clip(lower=0)
    .astype(int)
)

children = children.drop_duplicates("子どもID").copy()

# 基準日時点の月齢を計算
children["基準日時点の月齢"] = calculate_age(
    pd.Series(TODAY, index=children.index),
    children["誕生年月"]
)

# 比較児の抽出：9月23日時点で満30か月以上
eligible_peer_ids = set(
    children.loc[
        (children["子どもID"] != TARGET_ID)
        & (children["基準日時点の月齢"] >= MIN_AGE),
        "子どもID"
    ]
)

# 対象児と条件を満たす比較児だけを使用
display_ids = eligible_peer_ids | {TARGET_ID}

df = df.merge(
    children[["子どもID", "誕生年月"]],
    on="子どもID",
    how="left"
)

df = df.dropna(
    subset=["観測日", "誕生年月", "発達段階"]
)

df["月齢"] = calculate_age(
    df["観測日"],
    df["誕生年月"]
)

# 識別番号はクラス全体で固定
child_ids = sorted(children["子どもID"].dropna().unique())
id_map = {cid: i + 1 for i, cid in enumerate(child_ids)}

df["識別番号"] = df["子どもID"].map(id_map)


def get_day_data(toy, day):
    """指定日の対象児と条件を満たす比較児を抽出"""
    return df.loc[
        (df["子どもID"].isin(display_ids))
        & (df["おもちゃの種類"] == toy)
        & (df["観測日"].dt.normalize() == day)
        & (df["発達段階"].between(1, STAGE_MAX[toy]))
        & (df["観測回数"] > 0)
    ].copy()


def get_timeseries_data(toy):
    """21・24・27・30か月に対応する4日分を抽出"""
    parts = [
        get_day_data(toy, day)
        for day in TIME_POINTS
    ]
    return pd.concat(parts, ignore_index=True)


def make_figure(source, toy, timeseries=False, height=650):
    fig = go.Figure()

    # 観測回数分の点を表示
    expanded = source.loc[
        source.index.repeat(source["観測回数"])
    ].copy()

    peers = expanded.loc[
        expanded["子どもID"] != TARGET_ID
    ]

    target = expanded.loc[
        expanded["子どもID"] == TARGET_ID
    ]

    # 比較児：発達段階別の半透明点
    for stage in range(1, STAGE_MAX[toy] + 1):
        part = peers.loc[peers["発達段階"] == stage]

        if part.empty:
            continue

        fig.add_trace(go.Scatter3d(
            x=part["月齢"],
            y=part["識別番号"],
            z=part["発達段階"],
            mode="markers",
            name="その他の幼児",
            showlegend=False,
            marker=dict(
                size=4,
                color=STAGE_COLORS[stage],
                opacity=0.35
            ),
            hoverinfo="skip"
        ))

    # 対象児：赤色
    if not target.empty:
        fig.add_trace(go.Scatter3d(
            x=target["月齢"],
            y=target["識別番号"],
            z=target["発達段階"],
            mode="markers",
            name="対象児",
            showlegend=False,
            marker=dict(
                size=7,
                color="red",
                opacity=1
            ),
            hoverinfo="skip"
        ))

    # 月齢軸
     if timeseries:
        age_axis = dict(
            title="月齢",
            range=[20, 31],
            tickmode="array",
            tickvals=[21, 24, 27, 30],
            ticktext=["21", "24", "27", "30"]
        )
    else:
        max_age = max(30, int(source["月齢"].max()))
        age_axis = dict(
            title="月齢",
            range=[29, max_age + 1],
            dtick=1
        )

    fig.update_layout(
        scene=dict(
            xaxis=age_axis,
            yaxis=dict(
                title="識別番号",
                range=[0.5, len(child_ids) + 0.5],
                dtick=1
            ),
            zaxis=dict(
                title="発達段階",
                range=[0.5, STAGE_MAX[toy] + 0.5],
                tickvals=list(
                    range(1, STAGE_MAX[toy] + 1)
                )
            ),
            aspectmode="cube",
            camera=CAMERA
        ),
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False
    )

    return fig

# 画面
toy = st.selectbox(
    "おもちゃを選択",
    list(STAGE_MAX)
)

config = {
    "displayModeBar": False,
    "scrollZoom": False
}

# 4時点の観測データを取得
plot_data = get_timeseries_data(toy)

st.subheader("遊びの発達状況（21～30か月）")

if plot_data.empty:
    st.info("表示できる観測データがありません。")
else:
    st.plotly_chart(
        make_figure(
            plot_data,
            toy,
            timeseries=True,
            height=650
        ),
        use_container_width=True,
        config=config
    )

st.caption(
    "赤：対象児／その他：発達段階ごとの色分け（半透明）。"
    "ドラッグで3D回転できます。"
)

st.caption(
    f"比較児は2026年9月23日時点で満30か月以上の"
    f"{len(eligible_peer_ids)}人を抽出しています。"
)

st.caption(
    "観測日：2025/12/23・2026/03/23・"
    "2026/06/23・2026/09/23"
)
