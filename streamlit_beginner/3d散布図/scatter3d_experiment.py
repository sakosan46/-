from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="先行研究の3D散布図", layout="wide")
st.title("遊びの発達状況（3D散布図）")

EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"
TODAY = pd.Timestamp("2026-09-23")
WEEK_AGO = TODAY - pd.Timedelta(days=7)
TARGET_ID = "C001"
STAGE_MAX = {"ボール": 5, "お絵描き": 4, "ぬいぐるみ": 3}
# 比較児の色は発達段階ごとに変える。対象児は常に赤色。
STAGE_COLORS = {1: "#456CB3", 2: "#43A0A6", 3: "#E1B04D", 4: "#9469C4", 5: "#D784A3"}
CAMERA = dict(eye=dict(x=1.7, y=-1.7, z=0.9))

@st.cache_data
def load_data(path, modified_time):
    observations = pd.read_excel(path, sheet_name="観測データ")
    children = pd.read_excel(path, sheet_name="子ども基本情報")
    return observations, children

if not EXCEL_PATH.exists():
    st.error("デモデータ.xlsx が見つかりません。Pythonファイルと同じフォルダに配置してください。")
    st.stop()

try:
    df, children = load_data(str(EXCEL_PATH), EXCEL_PATH.stat().st_mtime)
except Exception as exc:
    st.error(f"Excelの読み込みに失敗しました：{exc}")
    st.stop()

required_obs = {"子どもID", "観測日", "おもちゃの種類", "発達段階", "観測回数"}
required_children = {"子どもID", "誕生年月"}
if not required_obs.issubset(df.columns) or not required_children.issubset(children.columns):
    st.error("Excelの『観測データ』『子ども基本情報』シートの列名を確認してください。")
    st.stop()

df["観測日"] = pd.to_datetime(df["観測日"], errors="coerce")
children["誕生年月"] = pd.to_datetime(children["誕生年月"], errors="coerce")
df["発達段階"] = pd.to_numeric(df["発達段階"], errors="coerce")
df["観測回数"] = pd.to_numeric(df["観測回数"], errors="coerce").fillna(0).clip(lower=0).astype(int)
df = df.merge(children[["子どもID", "誕生年月"]].drop_duplicates("子どもID"), on="子どもID", how="left")
df = df.dropna(subset=["観測日", "誕生年月", "発達段階"])
df["月齢"] = ((df["観測日"].dt.year - df["誕生年月"].dt.year) * 12
            + df["観測日"].dt.month - df["誕生年月"].dt.month
            - (df["観測日"].dt.day < df["誕生年月"].dt.day).astype(int))
child_ids = sorted(children["子どもID"].dropna().unique())
id_map = {cid: i + 1 for i, cid in enumerate(child_ids)}
df["識別番号"] = df["子どもID"].map(id_map)

def target_age_at(day):
    birthday = children.loc[children["子どもID"] == TARGET_ID, "誕生年月"]
    if birthday.empty or pd.isna(birthday.iloc[0]):
        return None
    dob = birthday.iloc[0]
    return ((day.year - dob.year) * 12 + day.month - dob.month
            - int(day.day < dob.day))

def get_day_data(toy, day):
    """対象児は指定日の観測、比較児は指定日までに観測された同月齢時の記録。
    同月齢児のデータが複数日ある場合は、各児の最新観測日の記録を採用する。
    """
    age = target_age_at(day)
    if age is None:
        return df.iloc[0:0].copy(), 0
    base = df.loc[(df["おもちゃの種類"] == toy)
                  & df["発達段階"].between(1, STAGE_MAX[toy])
                  & (df["観測回数"] > 0)].copy()
    target = base.loc[(base["子どもID"] == TARGET_ID)
                      & (base["観測日"].dt.normalize() == day)]
    peers = base.loc[(base["子どもID"] != TARGET_ID)
                     & (base["月齢"] == age)
                     & (base["観測日"] <= day)].copy()
    if not peers.empty:
        latest = peers.groupby("子どもID")["観測日"].transform("max")
        peers = peers.loc[peers["観測日"] == latest]
    return pd.concat([target, peers], ignore_index=True), age

def make_figure(source, toy, age, height=570):
    fig = go.Figure()
    # 元の3D散布図の形式を維持：月齢・識別番号・発達段階。
    # 同じ座標に観測回数分の点が重なる（位置のずらしは行わない）。
    expanded = source.loc[source.index.repeat(source["観測回数"])].copy()
    peers = expanded.loc[expanded["子どもID"] != TARGET_ID]
    target = expanded.loc[expanded["子どもID"] == TARGET_ID]
    for stage in range(1, STAGE_MAX[toy] + 1):
        part = peers.loc[peers["発達段階"] == stage]
        if part.empty:
            continue
        fig.add_trace(go.Scatter3d(
            x=part["月齢"], y=part["識別番号"], z=part["発達段階"],
            mode="markers", name="その他の幼児", showlegend=False,
            marker=dict(size=4, color=STAGE_COLORS[stage], opacity=0.35),
            hoverinfo="skip", hovertemplate=None,
        ))
    if not target.empty:
        fig.add_trace(go.Scatter3d(
            x=target["月齢"], y=target["識別番号"], z=target["発達段階"],
            mode="markers", name="対象児", showlegend=False,
            marker=dict(size=6, color="red", opacity=1),
            hoverinfo="skip", hovertemplate=None,
        ))
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="月齢", range=[max(0, age - 1), age + 1], dtick=1),
            yaxis=dict(title="識別番号", range=[0.5, len(child_ids) + 0.5], dtick=1),
            zaxis=dict(title="発達段階", range=[0.5, STAGE_MAX[toy] + 0.5],
                       tickvals=list(range(1, STAGE_MAX[toy] + 1))),
            aspectmode="cube", camera=CAMERA,
        ),
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
    )
    return fig

toy = st.selectbox("おもちゃを選択", list(STAGE_MAX))
mode = st.radio("表示", ["現在・同月齢", "時系列"], horizontal=True)
config = {"displayModeBar": False, "scrollZoom": False}

if mode == "現在・同月齢":
    day_data, age = get_day_data(toy, TODAY)
    st.subheader(f"現在・同月齢（{TODAY:%Y/%m/%d}）")
    if day_data.empty:
        st.info("表示できる観測データがありません。")
    else:
        st.plotly_chart(make_figure(day_data, toy, age, height=650),
                        use_container_width=True, config=config)
else:
    left, right = st.columns(2)
    for column, day, label in [(left, WEEK_AGO, "1週間前"), (right, TODAY, "現在")]:
        day_data, age = get_day_data(toy, day)
        with column:
            st.subheader(f"{label}（{day:%Y/%m/%d}）")
            if day_data.empty:
                st.info("表示できる観測データがありません。")
            else:
                st.plotly_chart(make_figure(day_data, toy, age, height=490),
                                use_container_width=True, config=config,
                                key=f"plot_{day:%Y%m%d}_{toy}")

st.caption("赤：対象児／その他：発達段階ごとの色分け（半透明）。ドラッグで3D回転できます。")
st.caption("比較児は対象児と同じ月齢の記録を各児の最新観測日から抽出しています。観測回数分の点は同一座標に重なります。")
