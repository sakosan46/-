from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="先行研究の3D散布図", layout="wide")
st.title("遊びの発達状況（3D散布図）")

EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"
TODAY = pd.Timestamp("2026-09-23")
TARGET_ID = 16
MIN_AGE = 42
AGE_POINTS = [33, 36, 39, 41, 42]
STAGE_MAX = {"ボール": 5, "お絵描き": 4, "ぬいぐるみ": 3}
STAGE_COLORS = {1: "#456CB3", 2: "#43A0A6", 3: "#E1B04D", 4: "#9469C4", 5: "#D784A3"}
CAMERA = dict(eye=dict(x=1.7, y=-1.7, z=0.9))


def calculate_age(dates, birthdays):
    """観測日・基準日時点の満月齢を計算。"""
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

required_obs = {"識別番号", "観測日", "おもちゃの種類", "発達段階", "観測回数"}
required_children = {"識別番号", "誕生年月"}
if not required_obs.issubset(df.columns) or not required_children.issubset(children.columns):
    st.error("Excelのシート名・列名を確認してください。識別番号の列が必要です。")
    st.stop()

df["識別番号"] = pd.to_numeric(df["識別番号"], errors="coerce")
children["識別番号"] = pd.to_numeric(children["識別番号"], errors="coerce")
df["観測日"] = pd.to_datetime(df["観測日"], errors="coerce")
children["誕生年月"] = pd.to_datetime(children["誕生年月"], errors="coerce")
df["発達段階"] = pd.to_numeric(df["発達段階"], errors="coerce")
df["観測回数"] = pd.to_numeric(df["観測回数"], errors="coerce").fillna(0).clip(lower=0).astype(int)
children = children.dropna(subset=["識別番号", "誕生年月"]).drop_duplicates("識別番号").copy()
children["識別番号"] = children["識別番号"].astype(int)
df = df.dropna(subset=["識別番号"]).copy()
df["識別番号"] = df["識別番号"].astype(int)

children["現在月齢"] = calculate_age(pd.Series(TODAY, index=children.index), children["誕生年月"])
eligible_peer_ids = set(children.loc[
    (children["識別番号"] != TARGET_ID) & (children["現在月齢"] >= MIN_AGE), "識別番号"
].astype(int))
all_ids = sorted(children["識別番号"].unique())

# Excelの識別番号を変更せず、そのまま散布図に使用する。
df = df.merge(children[["識別番号", "誕生年月"]], on="識別番号", how="left")
df = df.dropna(subset=["観測日", "誕生年月", "発達段階"]).copy()
df["月齢"] = calculate_age(df["観測日"], df["誕生年月"])


def get_display_data(toy, display_mode, months_before=1):

    # 選択したおもちゃの有効な観測データ
    valid = df.loc[
        (df["おもちゃの種類"] == toy)
        & (df["観測日"] <= TODAY)
        & df["発達段階"].between(1, STAGE_MAX[toy])
        & (df["観測回数"] > 0)
    ].copy()

    # 対象児の今日のデータ
    target_today = valid.loc[
        (valid["識別番号"] == TARGET_ID)
        & (valid["観測日"].dt.normalize() == TODAY)
    ].copy()

    # 現在
    if display_mode == "現在":
        return target_today

    # 時系列
    elif display_mode == "時系列":

        past_date = TODAY - pd.DateOffset(
            months=months_before
        )

        target_past = valid.loc[
            (valid["識別番号"] == TARGET_ID)
            & (valid["観測日"].dt.normalize() == past_date)
        ].copy()

        return pd.concat(
            [target_past, target_today],
            ignore_index=True
        )

    # 同月齢
    elif display_mode == "同月齢":

        peers = valid.loc[
            valid["識別番号"].isin(eligible_peer_ids)
            & (valid["月齢"] == MIN_AGE)
        ].copy()

        # 比較児1人につき1件
        # 最新日、観測回数の多い記録を優先
        peers["元の行順"] = peers.index

        peers = peers.sort_values(
            ["識別番号", "観測日", "観測回数", "元の行順"],
            ascending=[True, False, False, True]
        ).drop_duplicates(
            "識別番号",
            keep="first"
        )

        # 比較児は1人につき1点
        peers["観測回数"] = 1

        return pd.concat(
            [target_today, peers],
            ignore_index=True
        )


def spread_points(source):
    """観測回数分の点を作り、X・Y方向に少しずらす。"""
    if source.empty:
        return source.copy()
    expanded = source.loc[source.index.repeat(source["観測回数"])].reset_index(drop=True)
    groups = ["識別番号", "観測日", "月齢", "発達段階"]
    expanded["点番号"] = expanded.groupby(groups).cumcount()
    expanded["点数"] = expanded.groupby(groups)["点番号"].transform("count")
    angle = 2 * np.pi * expanded["点番号"] / expanded["点数"].clip(lower=1)
    radius = np.where(expanded["点数"] > 1, 0.22, 0.0)
    expanded["表示月齢"] = expanded["月齢"].astype(float) + radius * np.cos(angle)
    expanded["表示識別番号"] = expanded["識別番号"].astype(float) + radius * np.sin(angle)
    expanded["表示発達段階"] = expanded["発達段階"].astype(float)
    return expanded


def make_figure(source, toy, height=700):
    fig = go.Figure()
    expanded = spread_points(source)
    peers = expanded.loc[expanded["識別番号"] != TARGET_ID]
    target = expanded.loc[expanded["識別番号"] == TARGET_ID]

    for stage in range(1, STAGE_MAX[toy] + 1):
        part = peers.loc[peers["発達段階"] == stage]
        if not part.empty:
            fig.add_trace(go.Scatter3d(
                x=part["表示月齢"], y=part["表示識別番号"], z=part["表示発達段階"],
                mode="markers", name=f"比較児・段階{stage}",
                marker=dict(size=4, color=STAGE_COLORS[stage], opacity=0.25),
                customdata=np.column_stack([part["識別番号"], part["月齢"]]),
                hovertemplate="比較児・識別番号%{customdata[0]}<br>月齢：%{customdata[1]}<br>段階：%{z:.0f}<extra></extra>"
            ))

    if not target.empty:
        fig.add_trace(go.Scatter3d(
            x=target["表示月齢"], y=target["表示識別番号"], z=target["表示発達段階"],
            mode="markers", name="対象児", marker=dict(size=7, color="red", opacity=1),
            customdata=np.column_stack([target["識別番号"], target["月齢"]]),
            hovertemplate="対象児・識別番号%{customdata[0]}<br>月齢：%{customdata[1]}<br>段階：%{z:.0f}<extra></extra>"
        ))

    # 目盛りは対象児と実際に抽出された比較児の識別番号のみ。
    shown_ids = sorted(set(source["識別番号"].astype(int)))
    fig.update_layout(
        scene=dict(
           xaxis=dict(
        title="月齢",
        range=[32, 43],
        tickmode="array",
        tickvals=sorted(
            source["月齢"].unique().tolist()
            )
        ),
            yaxis=dict(title="識別番号", range=[0.5, max(all_ids) + 0.5],
                       tickmode="array", tickvals=shown_ids,
                       ticktext=[str(n) for n in shown_ids]),
            zaxis=dict(title="発達段階", range=[0.5, STAGE_MAX[toy] + 0.5],
                       tickmode="array", tickvals=list(range(1, STAGE_MAX[toy] + 1))),
            aspectmode="cube", camera=CAMERA,
        ),
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True, legend=dict(orientation="h", y=-0.06, x=0),
    )
    return fig


# -------------------------
# おもちゃの選択
# -------------------------
toy = st.segmented_control(
    "おもちゃを選択",
    ["ボール", "お絵描き", "ぬいぐるみ"],
    default="ボール"
)

# -------------------------
# 表示方法の切り替え
# -------------------------
display_mode = st.segmented_control(
    "表示する情報",
    ["現在", "時系列", "同月齢"],
    default="現在"
)

months_before = 1

# -------------------------
# 時系列の比較時期の選択
# -------------------------
if display_mode == "時系列":

    selected_period = st.selectbox(
        "現在と比較する時期",
        ["1か月前", "3か月前", "6か月前", "9か月前"],
        index=0,
        key="history_period"
    )

    months_before = {
        "1か月前": 1,
        "3か月前": 3,
        "6か月前": 6,
        "9か月前": 9
    }[selected_period]

    past_date = TODAY - pd.DateOffset(
        months=months_before
    )

# -------------------------
# 散布図の表示
# -------------------------
st.subheader(f"{toy}の発達状況")

plot_data = get_display_data(
    toy,
    display_mode,
    months_before
)

if plot_data.empty:
    st.info("表示できる観測データがありません。")

else:
    st.plotly_chart(
        make_figure(plot_data, toy),
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False
        }
    )

# -------------------------
# 表示方法ごとの説明
# -------------------------
if display_mode == "現在":

    st.caption("赤：対象児")

    st.info(
        f"今日（{TODAY:%Y/%m/%d}）の"
        "遊びの発達状況を表示しています。"
    )

elif display_mode == "時系列":

    st.caption("赤：対象児")

    st.info(
        f"今日（{TODAY:%Y/%m/%d}）と"
        f"{months_before}か月前"
        f"（{past_date:%Y/%m/%d}）の"
        "遊びの発達状況を表示しています。"
    )

elif display_mode == "同月齢":

    st.caption(
        "赤：対象児／半透明：比較児（発達段階別の色）"
    )

    peer_count = plot_data.loc[
        plot_data["識別番号"] != TARGET_ID,
        "識別番号"
    ].nunique()

    st.info(
        f"対象児と比較児{peer_count}人の"
        f"{MIN_AGE}か月時点の記録を表示しています。"
        "発達の進み方には個人差があります。"
    )

st.caption(
    "ドラッグで3D散布図を回転できます。"
)
