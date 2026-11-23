
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -------------------------
# ページの基本設定
# -------------------------
st.set_page_config(
    page_title="先行研究の3D散布図",
    layout="wide"
)

st.title("遊びの発達状況（3D散布図）")

# -------------------------
# 基本設定
# -------------------------
EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"

TODAY = pd.Timestamp("2026-09-23")
TARGET_ID = "C001"
MIN_AGE = 30

# 比較に使用する月齢
AGE_POINTS = [21, 24, 27, 30]

# おもちゃごとの発達段階数
STAGE_MAX = {
    "ボール": 5,
    "お絵描き": 4,
    "ぬいぐるみ": 3
}

# 比較児の発達段階別の色
STAGE_COLORS = {
    1: "#456CB3",
    2: "#43A0A6",
    3: "#E1B04D",
    4: "#9469C4",
    5: "#D784A3"
}

# 3D散布図の初期視点
CAMERA = dict(
    eye=dict(x=1.7, y=-1.7, z=0.9)
)


# -------------------------
# Excelデータの読み込み
# -------------------------
@st.cache_data
def load_data(path, modified_time):
    observations = pd.read_excel(
        path,
        sheet_name="観測データ"
    )

    children = pd.read_excel(
        path,
        sheet_name="子ども基本情報"
    )

    return observations, children


# -------------------------
# 月齢の計算
# -------------------------
def calculate_age(dates, birthdays):
    """観測日と生年月日から満月齢を計算"""

    return (
        (dates.dt.year - birthdays.dt.year) * 12
        + dates.dt.month - birthdays.dt.month
        - (dates.dt.day < birthdays.dt.day).astype(int)
    )


# -------------------------
# Excelファイルの確認
# -------------------------
if not EXCEL_PATH.exists():
    st.error("デモデータ.xlsx が見つかりません。")
    st.stop()

try:
    df, children = load_data(
        str(EXCEL_PATH),
        EXCEL_PATH.stat().st_mtime
    )

except Exception as exc:
    st.error(
        f"Excelの読み込みに失敗しました：{exc}"
    )
    st.stop()


# -------------------------
# 必要な列の確認
# -------------------------
required_obs = {
    "子どもID",
    "観測日",
    "おもちゃの種類",
    "発達段階",
    "観測回数"
}

required_children = {
    "子どもID",
    "誕生年月"
}

if (
    not required_obs.issubset(df.columns)
    or not required_children.issubset(children.columns)
):
    st.error(
        "Excelのシート名・列名を確認してください。"
    )
    st.stop()


# -------------------------
# データ形式の統一
# -------------------------
df["観測日"] = pd.to_datetime(
    df["観測日"],
    errors="coerce"
)

children["誕生年月"] = pd.to_datetime(
    children["誕生年月"],
    errors="coerce"
)

df["発達段階"] = pd.to_numeric(
    df["発達段階"],
    errors="coerce"
)

df["観測回数"] = (
    pd.to_numeric(
        df["観測回数"],
        errors="coerce"
    )
    .fillna(0)
    .clip(lower=0)
    .astype(int)
)

children = children.drop_duplicates(
    "子どもID"
).copy()

children = children.dropna(
    subset=["子どもID", "誕生年月"]
)


# -------------------------
# 基準日時点の月齢を計算
# -------------------------
children["基準日時点の月齢"] = calculate_age(
    pd.Series(TODAY, index=children.index),
    children["誕生年月"]
)


# -------------------------
# 比較児の抽出
# -------------------------
# 2026年9月23日時点で満30か月以上の子ども
# 対象児C001は除外

eligible_peer_ids = set(
    children.loc[
        (children["子どもID"] != TARGET_ID)
        & (children["基準日時点の月齢"] >= MIN_AGE),
        "子どもID"
    ]
)

# 対象児と比較児
display_ids = eligible_peer_ids | {TARGET_ID}


# -------------------------
# 観測データに生年月日を追加
# -------------------------
df = df.merge(
    children[["子どもID", "誕生年月"]],
    on="子どもID",
    how="left"
)

df = df.dropna(
    subset=[
        "観測日",
        "誕生年月",
        "発達段階"
    ]
)

# 観測時点の月齢
df["月齢"] = calculate_age(
    df["観測日"],
    df["誕生年月"]
)


# -------------------------
# 識別番号を設定
# -------------------------
# クラス全体の子どもIDをもとに番号を固定

child_ids = sorted(
    children["子どもID"].dropna().unique()
)

id_map = {
    cid: i + 1
    for i, cid in enumerate(child_ids)
}

df["識別番号"] = df["子どもID"].map(id_map)


# -------------------------
# 月齢別の観測データを抽出
# -------------------------
def get_timeseries_data(toy):
    """
    各児の21・24・27・30か月時点の
    観測記録を抽出する
    """

    # 対象児と比較児を抽出
    result = df.loc[
        (df["子どもID"].isin(display_ids))
        & (df["おもちゃの種類"] == toy)
        & (df["月齢"].isin(AGE_POINTS))
        & (df["観測日"] <= TODAY)
        & (
            df["発達段階"].between(
                1,
                STAGE_MAX[toy]
            )
        )
        & (df["観測回数"] > 0)
    ].copy()

    if result.empty:
        return result

    # 各児・各月齢の最新観測日を取得
    latest_dates = result.groupby(
        ["子どもID", "月齢"]
    )["観測日"].transform("max")

    # 最新観測日の記録を使用
    result = result.loc[
        result["観測日"] == latest_dates
    ].copy()

    return result


# -------------------------
# 点を少しばらけさせる処理
# -------------------------
def spread_points(source):
    """
    同じ座標に重なる点を少しずらして
    見やすくする
    """

    if source.empty:
        return source.copy()

    # 観測回数分の点を作成
    expanded = source.loc[
        source.index.repeat(
            source["観測回数"]
        )
    ].copy()

    expanded = expanded.reset_index(drop=True)

    # ずらした後の座標
    expanded["表示月齢"] = expanded["月齢"].astype(float)
    expanded["表示識別番号"] = (
        expanded["識別番号"].astype(float)
    )
    expanded["表示発達段階"] = (
        expanded["発達段階"].astype(float)
    )

    # 同じ子ども・月齢・段階の点をばらけさせる
    group_cols = [
        "子どもID",
        "月齢",
        "発達段階"
    ]

    # グループ内での点の順番
    expanded["点番号"] = (
        expanded.groupby(group_cols).cumcount()
    )

    # グループ内の点の総数
    expanded["点数"] = (
        expanded.groupby(group_cols)["点番号"]
        .transform("count")
    )

    # 点の位置を円状にずらす
    angles = (
        2 * np.pi
        * expanded["点番号"]
        / expanded["点数"].clip(lower=1)
    )

    # 点が1つの場合はずらさない
    radius = np.where(
        expanded["点数"] > 1,
        0.22,
        0.0
    )

    # 月齢軸と識別番号軸を少しずらす
    expanded["表示月齢"] += (
        radius * np.cos(angles)
    )

    expanded["表示識別番号"] += (
        radius * np.sin(angles)
    )

    return expanded


# -------------------------
# 3D散布図の作成
# -------------------------
def make_figure(source, toy, height=650):

    fig = go.Figure()

    # 観測回数分の点を作成
    expanded = spread_points(source)

    # 比較児
    peers = expanded.loc[
        expanded["子どもID"] != TARGET_ID
    ]

    # 対象児
    target = expanded.loc[
        expanded["子どもID"] == TARGET_ID
    ]

    # -------------------------
    # 比較児の点を表示
    # -------------------------
    for stage in range(
        1,
        STAGE_MAX[toy] + 1
    ):

        part = peers.loc[
            peers["発達段階"] == stage
        ]

        if part.empty:
            continue

        fig.add_trace(
            go.Scatter3d(
                x=part["表示月齢"],
                y=part["表示識別番号"],
                z=part["表示発達段階"],
                mode="markers",
                name="その他の幼児",
                showlegend=False,
                marker=dict(
                    size=4,
                    color=STAGE_COLORS[stage],
                    opacity=0.35
                ),
                hoverinfo="skip"
            )
        )

    # -------------------------
    # 対象児の点を表示
    # -------------------------
    if not target.empty:

        fig.add_trace(
            go.Scatter3d(
                x=target["表示月齢"],
                y=target["表示識別番号"],
                z=target["表示発達段階"],
                mode="markers",
                name="対象児",
                showlegend=False,
                marker=dict(
                    size=7,
                    color="red",
                    opacity=1
                ),
                hoverinfo="skip"
            )
        )

    # -------------------------
    # 月齢軸の設定
    # -------------------------
    age_axis = dict(
        title="月齢",
        range=[20, 31],
        tickmode="array",
        tickvals=AGE_POINTS,
        ticktext=[
            str(age)
            for age in AGE_POINTS
        ]
    )

    # -------------------------
    # グラフのデザイン
    # -------------------------
    fig.update_layout(
        scene=dict(
            xaxis=age_axis,

            yaxis=dict(
                title="識別番号",
                range=[
                    0.5,
                    len(child_ids) + 0.5
                ],
                dtick=1
            ),

            zaxis=dict(
                title="発達段階",
                range=[
                    0.5,
                    STAGE_MAX[toy] + 0.5
                ],
                tickmode="array",
                tickvals=list(
                    range(
                        1,
                        STAGE_MAX[toy] + 1
                    )
                )
            ),

            aspectmode="cube",
            camera=CAMERA
        ),

        height=height,

        margin=dict(
            l=0,
            r=0,
            t=0,
            b=0
        ),

        showlegend=False
    )

    return fig


# -------------------------
# 画面の表示
# -------------------------
toy = st.selectbox(
    "おもちゃを選択",
    list(STAGE_MAX.keys())
)

# 3D散布図の操作設定
config = {
    "displayModeBar": False,
    "scrollZoom": False
}

# 観測データを取得
plot_data = get_timeseries_data(toy)

st.subheader(
    "遊びの発達状況（21～30か月）"
)

if plot_data.empty:

    st.info(
        "表示できる観測データがありません。"
    )

else:

    st.plotly_chart(
        make_figure(
            plot_data,
            toy,
            height=650
        ),
        use_container_width=True,
        config=config
    )


# -------------------------
# 画面下の説明
# -------------------------
st.caption(
    "赤：対象児／その他：発達段階ごとの色分け（半透明）。"
    "ドラッグで3D回転できます。"
)

st.caption(
    f"比較児は2026年9月23日時点で満30か月以上の"
    f"{len(eligible_peer_ids)}人を抽出しています。"
)

st.caption(
    "対象児と比較児それぞれの21・24・27・30か月時点の"
    "観測記録を表示しています。"
)
