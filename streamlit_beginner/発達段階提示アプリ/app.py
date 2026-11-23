import pandas as pd
import streamlit as st
from pathlib import Path
import plotly.graph_objects as go
import math
import random
from datetime import date, timedelta

TARGET_ID = 16
TODAY = date(2026, 9, 23)
EXCEL_PATH = Path(__file__).resolve().parent / "デモデータ.xlsx"

@st.cache_data
def load_demo_data(path, mtime):
    return (pd.read_excel(path, sheet_name="観測データ"),
            pd.read_excel(path, sheet_name="子ども基本情報"))

def calculate_months(birth, reference):
    return ((reference.year - birth.year) * 12 + reference.month - birth.month
            - (reference.day < birth.day))


# -------------------------
# ページの基本設定
# -------------------------
st.set_page_config(
    page_title="",
    page_icon="🌷",
    layout="centered"
)

# -------------------------
# 画面切り替えの管理
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "ホーム"

def move_page(page_name):
    st.session_state.page = page_name


# -------------------------
# ホーム画面
# -------------------------
def home_page():

    # タイトル
    st.title("")

    # 子どものプロフィール
    col1, col2 = st.columns([1, 3])

    with col1:
        show_photo("child.jpg")

    with col2:
        st.subheader("ゆいちゃん")
        st.write("3歳6か月")

    st.divider()

    # 今日のひとこと
    st.markdown("### ☀️ 今日のひとこと")

    st.info(
        "いろいろな遊びに興味を持つ時期です。"
        "好きな遊びを通して、"
        "たくさんの経験を重ねていきましょう。"
    )

    # メインメニュー
    st.markdown("### メニュー")

    if st.button(
        "📊 発達状況",
        use_container_width=True,
        key="home_development"
    ):
        move_page("発達状況")
        st.rerun()

    st.caption("遊びの発達段階や過去との変化を確認")

    if st.button(
        "🧸 遊び・興味",
        use_container_width=True,
        key="home_interest"
    ):
        move_page("遊び・興味")
        st.rerun()

    st.caption("よく遊ぶおもちゃや興味の変化を確認")

    if st.button(
        "👪 園・保護者との共有",
        use_container_width=True,
        key="home_share"
    ):
        move_page("園・保護者との共有")
        st.rerun()

    st.caption("家庭や園での様子を共有・確認")

    # 最近の様子
    st.markdown("### 🌷 最近の様子")

    col1, col2, col3 = st.columns(3)

    with col1:
        show_photo(
            "play1.jpg",
            "ブロックで遊びました"
        )

    with col2:
        show_photo(
            "play2.jpg",
            "すべり台ができました"
        )

    with col3:
        show_photo(
            "play3.jpg",
            "しゃぼん玉に夢中！"
        )


# -------------------------
# 写真を表示する関数
# -------------------------
def show_photo(filename, caption=""):

    path = Path(__file__).resolve().parent.parent / "images" / filename

    if path.exists():
        try:
            st.image(
                str(path),
                use_container_width=True
            )
        except Exception:
            st.info("📷 画像を読み込めませんでした")
    else:
        st.info("📷 写真を追加できます")

    if caption:
        st.caption(caption)


# -------------------------
# 発達状況画面
# -------------------------
def development_page():
    today = TODAY
    if not EXCEL_PATH.exists():
        st.error("同じフォルダに『デモデータ.xlsx』を置いてください。")
        return
    try:
        df, children_df = load_demo_data(str(EXCEL_PATH), EXCEL_PATH.stat().st_mtime)
    except Exception as exc:
        st.error(f"Excelの読み込みに失敗しました：{exc}")
        return
    required_obs = {"識別番号", "観測日", "おもちゃの種類", "遊び方・動作", "発達段階", "観測回数"}
    required_child = {"識別番号", "誕生年月"}
    if not required_obs.issubset(df.columns) or not required_child.issubset(children_df.columns):
        st.error("Excelの『観測データ』『子ども基本情報』の列名を確認してください。")
        return
    df["識別番号"] = pd.to_numeric(df["識別番号"], errors="coerce")
    children_df["識別番号"] = pd.to_numeric(children_df["識別番号"], errors="coerce")
    df["観測日"] = pd.to_datetime(df["観測日"], errors="coerce")
    children_df["誕生年月"] = pd.to_datetime(children_df["誕生年月"], errors="coerce")
    df["発達段階"] = pd.to_numeric(df["発達段階"], errors="coerce")
    df["観測回数"] = pd.to_numeric(df["観測回数"], errors="coerce").fillna(0)
    df = df.dropna(subset=["識別番号", "観測日", "発達段階"]).copy()
    children_df = children_df.dropna(subset=["識別番号", "誕生年月"]).drop_duplicates("識別番号")

    if st.button("← ホームに戻る", key="back_dev"):
        move_page("ホーム")
        st.rerun()

    st.title("発達状況")
    st.write("遊びを通した発達の様子を確認できます。")

    # おもちゃの選択
    toy = st.segmented_control(
        "おもちゃを選択",
        ["ボール", "お絵描き", "ぬいぐるみ"],
        default="ボール"
    )

    stage_counts = {
        "ボール": 5,
        "お絵描き": 4,
        "ぬいぐるみ": 3
    }

    count = stage_counts[toy]

    # 表示方法の切り替え
    display_mode = st.segmented_control(
        "表示する情報",
        ["現在", "時系列", "同月齢"],
        default="現在"
    )

    # 時系列では、1つの選択欄で比較する月を切り替える
    months_before = 3
    past_date = None
    if display_mode == "時系列":
        selected_period = st.selectbox(
            "現在と比較する時期",
            ["3か月前", "6か月前", "9か月前"],
            index=0,
            key="history_period",
        )
        months_before = {"3か月前": 3, "6か月前": 6, "9か月前": 9}[selected_period]
        past_date = (pd.Timestamp(today) - pd.DateOffset(months=months_before)).date()

    st.subheader(f"{toy}の発達状況")

        # Excelから対象児のおもちゃ別データを取得
    target_df = df[
        (df["識別番号"] == TARGET_ID) &
        (df["おもちゃの種類"] == toy)
    ].copy()

    # Excelの記録を円の点として使える形に変換
    records = []

    for i, (_, row) in enumerate(target_df.iterrows()):
        records.append({
            "id": i + 1,
            "child_id": TARGET_ID,
            "stage": int(row["発達段階"]),
            "date": row["観測日"].strftime("%Y-%m-%d"),
            "comment": str(row["遊び方・動作"]),
            "count": int(row["観測回数"])
        })

    
    # 基準日時点で対象児と同じ月齢に到達している比較児を抽出。
    # 比較児の観測日は各自が42か月だった過去の日付でもよい。
    target_births = children_df.loc[children_df["識別番号"] == TARGET_ID, "誕生年月"]
    if target_births.empty:
        st.error("子ども基本情報に対象児（識別番号16）がありません。")
        return
    target_age = calculate_months(target_births.iloc[0], today)
    children_df = children_df.copy()
    children_df["現在月齢"] = children_df["誕生年月"].apply(
        lambda birth: calculate_months(birth, today)
    )
    eligible_peer_ids = set(children_df.loc[
        (children_df["識別番号"] != TARGET_ID)
        & (children_df["現在月齢"] >= target_age), "識別番号"
    ])
    comparison_births = children_df.set_index("識別番号")["誕生年月"]
    peer_df = df.loc[
        df["識別番号"].isin(eligible_peer_ids)
        & (df["おもちゃの種類"] == toy)
        & (df["観測日"].dt.date <= today)
        & (df["観測回数"] > 0)
        & df["発達段階"].between(1, count)
    ].copy()
    peer_df["誕生年月"] = peer_df["識別番号"].map(comparison_births)
    peer_df = peer_df.dropna(subset=["誕生年月"])
    peer_df["観測時月齢"] = peer_df.apply(
        lambda r: calculate_months(r["誕生年月"], r["観測日"]), axis=1
    )
    same_age_df = peer_df.loc[peer_df["観測時月齢"] == target_age].copy()
    same_age_df["元の行順"] = same_age_df.index
    # 比較児1人につき1件。最新日→観測回数の多い記録を優先。
    selected_df = (
        same_age_df.sort_values(
            ["識別番号", "観測日", "観測回数", "元の行順"],
            ascending=[True, False, False, True]
        ).drop_duplicates("識別番号", keep="first")
    )
    stage_counts = selected_df["発達段階"].astype(int).value_counts()
    most_common_stages = (
        stage_counts.index[stage_counts == stage_counts.max()].tolist()
        if not stage_counts.empty else []
    )
    same_age_records = []
    for i, (_, row) in enumerate(selected_df.iterrows()):
        same_age_records.append({
            "id": 100000 + i,
            "child_id": int(row["識別番号"]),
            "stage": int(row["発達段階"]),
            "date": row["観測日"].strftime("%Y-%m-%d"),
            "comment": str(row["遊び方・動作"]),
            "count": int(row["観測回数"])
        })

       # おもちゃに合わせて段階数を調整
    records = [
        r for r in records if r["stage"] <= count
    ]

    # 表示方法に応じて日付を絞り込む
    if display_mode == "現在":
        records = [
            r for r in records
            if date.fromisoformat(r["date"]) == today
        ]

    elif display_mode == "時系列":
        records = [
            r for r in records
            if date.fromisoformat(r["date"])
            in [today, past_date]
        ]

    elif display_mode == "同月齢":
        records = [
            r for r in records
            if date.fromisoformat(r["date"]) == today
        ]

        # 比較児は42か月時点の最新記録を表示するため、今日の日付で絞らない。
    fig = go.Figure()

    # 円の層を外側から描く
    colors = [
        "#FCE8C6",
        "#DDEFE5",
        "#E8E8F7",
        "#F5DDE5",
        "#F7E9E6"
    ]

    for stage in range(count, 0, -1):
        radius = stage

        fig.add_shape(
            type="circle",
            x0=-radius,
            y0=-radius,
            x1=radius,
            y1=radius,
            fillcolor="#E2F0E6",
            line=dict(color="white", width=2),
            layer="below"
        )

    # 点の位置を作る
    
 
    # -------------------------
    # 点の位置と色を設定
    # -------------------------
    x_values = []
    y_values = []
    hover_text = []
    custom_ids = []
    point_colors = []

    # 発達段階ごとの点の配置数を管理
    stage_positions = {}

    for record in records:

        stage = record["stage"]
        count_points = max(0, int(record["count"]))

        # 観測回数だけ点を作る
        for j in range(count_points):

            # 同じ段階の点の配置数を管理
            position = stage_positions.get(stage, 0)
            stage_positions[stage] = position + 1

            # 発達段階の範囲内で点をばらけさせる
            rng = random.Random(stage * 1000 + position)

            inner_radius = stage - 1
            outer_radius = stage

            radius = rng.uniform(
                inner_radius + 0.15,
                outer_radius - 0.15
            )

            angle = rng.uniform(0, 2 * math.pi)

            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            x_values.append(x)
            y_values.append(y)

            # 点を選択したときの情報
            hover_text.append(
                f"段階{stage}<br>"
                f"日付：{record['date']}<br>"
                f"遊び方：{record['comment']}<br>"
                f"観測回数：{count_points}回"
            )

            # 同じ記録から作った点には同じIDを付ける
            custom_ids.append(record["id"])

            # 点の色分け
            if display_mode == "時系列":

                record_date = date.fromisoformat(record["date"])

                if record_date == today:
                    point_colors.append("#E68AA3")

                elif record_date == past_date:
                    point_colors.append("#769BC8")

                else:
                    point_colors.append("#AAAAAA")

            else:
                point_colors.append("#E68AA3")

    # -------------------------
    # 円の中に点を描画
    # -------------------------
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers",
            marker=dict(
                size=13,
                color=point_colors,
                line=dict(color="white", width=2)
            ),
            text=hover_text,
            customdata=custom_ids,
            hovertemplate="%{text}<extra></extra>",
            name="遊びの記録"
        )
    )

     # 同月齢の子どもの点を追加
    if display_mode == "同月齢":

        same_age_x = []
        same_age_y = []
        same_age_text = []
        same_age_ids = []

        for i, record in enumerate(same_age_records):

            stage = record["stage"]

            rng = random.Random(100000 + i)

            inner_radius = stage - 1
            outer_radius = stage

            radius = rng.uniform(
                inner_radius + 0.15,
                outer_radius - 0.15
            )

            angle = rng.uniform(0, 2 * math.pi)

            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            same_age_x.append(x)
            same_age_y.append(y)

            same_age_text.append(
                f"同月齢の子ども<br>"
                f"段階{stage}<br>"
                f"日付：{record['date']}<br>"
                f"遊び方：{record['comment']}<br>"
                f"観測回数：{record['count']}回"
            )

            same_age_ids.append(record["id"])

        fig.add_trace(
            go.Scatter(
                x=same_age_x,
                y=same_age_y,
                mode="markers",
                marker=dict(
                    size=10,
                    color="#A9B0B8",
                    line=dict(color="white", width=1)
                ),
                text=same_age_text,
                customdata=same_age_ids,
                hovertemplate="%{text}<extra></extra>",
                name="同月齢の子ども"
            )
        )

    # 拡大・縮小の倍率を保存
    if "circle_zoom" not in st.session_state:
        st.session_state.circle_zoom = 1.0

    # スマホでの列の縦積みを防ぎ、拡大・縮小・元に戻すを横一列にする
    st.markdown("""
        <style>
        @media (max-width: 640px) {
            .st-key-zoom_controls [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.35rem !important;
            }
            .st-key-zoom_controls [data-testid="stColumn"] {
                flex: 1 1 0% !important;
                width: 0 !important;
                min-width: 0 !important;
            }
            .st-key-zoom_controls [data-testid="stButton"] button {
                width: 100% !important;
                padding-left: 0.2rem !important;
                padding-right: 0.2rem !important;
                white-space: nowrap !important;
                font-size: 0.82rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # ボタンをまとめる
    with st.container(key="zoom_controls"):
        col1, col2, col3 = st.columns(3, gap="small")

        with col1:
            if st.button("＋ 拡大", key="zoom_in", use_container_width=True):
                st.session_state.circle_zoom = min(
                    st.session_state.circle_zoom * 1.25, 3.0
                )

        with col2:
            if st.button("－ 縮小", key="zoom_out", use_container_width=True):
                st.session_state.circle_zoom = max(
                    st.session_state.circle_zoom / 1.25, 0.5
                )

        with col3:
            if st.button("元に戻す", key="zoom_reset", use_container_width=True):
                st.session_state.circle_zoom = 1.0

    zoom = st.session_state.circle_zoom
    axis_limit = (count + 0.5) / zoom

    # グラフのデザイン
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            visible=False,
            range=[-axis_limit, axis_limit],
            fixedrange=True
        ),
        yaxis=dict(
            visible=False,
            range=[-axis_limit, axis_limit],
            scaleanchor="x",
            scaleratio=1,
            fixedrange=True
        ),
        dragmode=False
    )

        # スマホでのタッチ操作を制限
    st.markdown(
        """
        <style>
        div[data-testid="stPlotlyChart"] .js-plotly-plot {
            touch-action: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
       # 円の表示と点の選択
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="development_chart",
        config={
            "scrollZoom": False,
            "displayModeBar": False,
            "doubleClick": False,
            "staticPlot": False,
            "showAxisDragHandles": False,
            "showAxisRangeEntryBoxes": False,
            "editable": False
        }
    )
    st.caption(
        "円の層は発達段階を、点は遊びの記録を表しています。"
    )

    # 点が選択された場合
    selected_points = event.selection.points

    if selected_points:

        selected_id = selected_points[0].get("customdata")

        if selected_id is not None:

            selected_id = int(selected_id)

            # 対象児と同月齢児の両方から記録を探す
            all_records = records + same_age_records

            selected_record = next(
                (r for r in all_records if r["id"] == selected_id),
                None
            )

            if selected_record:
                st.session_state.selected_record = selected_record
                st.session_state.selected_toy = toy
                move_page("記録詳細")
                st.rerun()


       # 画面下の説明
    # -------------------------
    # 画面下の説明
    # -------------------------
    if display_mode == "現在":
        st.info(
            f"今日（{today:%Y/%m/%d}）の遊びの発達状況を表示しています。"
        )

    elif display_mode == "時系列":
        st.markdown(
            f"<span style='color:#769BC8; font-size:18px;'>●</span> "
            f"**{months_before}か月前（{past_date:%Y/%m/%d}）**　"
            f"<span style='color:#E68AA3; font-size:18px;'>●</span> "
            f"**今日（{today:%m/%d}）**",
            unsafe_allow_html=True
        )

        st.info(
            f"今日と{months_before}か月前に見られた遊びの動作を、"
            "点の色で区別して表示しています。"
        )

       
    else:
        st.markdown("#### 同月齢児の発達段階の傾向")
        # 点の色の説明
        st.markdown(
            "<span style='color:#E68AA3; font-size:18px;'>●</span> "
            "**対象児**　"
            "<span style='color:#A9B0B8; font-size:18px;'>●</span> "
            "**同月齢の子ども**",
            unsafe_allow_html=True
        )

        st.info(
            f"比較児{len(selected_df)}人の{target_age}か月時点の記録を表示しています。"
            "発達の進み方には個人差があります。"
        )

# -------------------------
# 記録詳細画面
# -------------------------
def record_detail_page():

    if st.button("← 発達状況に戻る", key="back_detail"):
        move_page("発達状況")
        st.rerun()

    st.title("遊びの記録")

    record = st.session_state.get("selected_record")

    if record is None:
        st.warning("記録が選択されていません。")
        return

    toy = st.session_state.get("selected_toy", "")
    child_id = record.get("child_id", TARGET_ID)

    # 観測記録を区別するためのキー
    record_key = (
        child_id,
        toy,
        record["date"],
        record["stage"],
        record["comment"]
    )

    # 追加したコメントの保存先
    if "development_comments" not in st.session_state:
        st.session_state.development_comments = {}

    # -------------------------
    # 観測記録の詳細
    # -------------------------
    st.subheader("観測記録の詳細")

    with st.container(border=True):
        st.write(f"おもちゃ：{toy}")
        st.write(f"日付：{record['date']}")
        st.write(f"発達段階：段階{record['stage']}")
        st.write(f"遊びの様子：{record['comment']}")

    st.divider()

    # -------------------------
    # 記録一覧
    # -------------------------
    st.subheader("📝 記録一覧")

    comments = st.session_state.development_comments.get(
        record_key, []
    )

    if comments:
        for item in reversed(comments):
            with st.container(border=True):
                st.caption(
                    f"{item['date']} ／ {item['author']}"
                )
                st.write(item["content"])
    else:
        st.caption("まだ記録はありません。")

    st.divider()

    # -------------------------
    # 任意の記録入力
    # -------------------------
    with st.expander("＋ 記録する"):

        with st.form(
            "development_record_form",
            clear_on_submit=True
        ):

            input_date = st.date_input(
                "記録日",
                value=date.today()
            )

            author = st.selectbox(
                "記録者",
                ["保育者", "保護者"]
            )

            content = st.text_area(
                "記録内容",
                placeholder=(
                    "遊んでいるときの様子や"
                    "気づいたことを入力してください。"
                )
            )

            submitted = st.form_submit_button(
                "記録を保存する",
                use_container_width=True
            )

        if submitted:

            if not content.strip():
                st.warning(
                    "記録内容を入力してください。"
                )

            else:
                # この観測記録のコメント一覧を取得
                if record_key not in st.session_state.development_comments:
                    st.session_state.development_comments[record_key] = []

                # コメントを追加
                st.session_state.development_comments[
                    record_key
                ].append({
                    "date": str(input_date),
                    "author": author,
                    "content": content.strip()
                })

                st.rerun()



# -------------------------
# 記録入力画面（仮）
# -------------------------
def record_input_page():

    if st.button("← 発達状況に戻る", key="back_input"):
        move_page("発達状況")
        st.rerun()

    st.title("記録を追加する")

    st.date_input("日付")
    st.selectbox(
        "おもちゃ",
        ["ボール", "お絵描き", "ぬいぐるみ"]
    )
    st.text_area("遊びの様子・コメント")
    st.file_uploader("写真を追加", type=["jpg", "png"])

    st.caption(
        "※ 保存機能は後から追加します。"
    )


# -------------------------
# 遊び・興味画面
# -------------------------
def interest_page():

    # ホームに戻る
    if st.button("← ホームに戻る", key="back_interest"):
        move_page("ホーム")
        st.rerun()

    st.title("遊び・興味")
    st.write("普段の遊びや興味の様子を確認できます。")

    # 表示内容の切り替え
    display_mode = st.segmented_control(
        "表示する情報",
        ["よく遊ぶおもちゃ", "興味の変化", "関連情報"],
        default="よく遊ぶおもちゃ",
        key="interest_mode"
    )

    # よく遊ぶおもちゃ
    if display_mode == "よく遊ぶおもちゃ":

        st.subheader("🏅 よく遊ぶおもちゃ")

        # Excelの観測データを読み込む
        df = pd.read_excel(
            EXCEL_PATH,
            sheet_name="観測データ"
        )

        df["観測日"] = pd.to_datetime(df["観測日"])

        # 対象児のデータ
        target_df = df[
            df["識別番号"] == TARGET_ID
        ].copy()

        # デモデータの基準日
        today = pd.Timestamp("2026-09-23")
        start_day = today - pd.Timedelta(days=6)

        # 直近7日間のデータ
        week_df = target_df[
            (target_df["観測日"] >= start_day) &
            (target_df["観測日"] <= today)
        ]

        # おもちゃごとに観測回数を集計
        toy_counts = (
            week_df.groupby("おもちゃの種類")["観測回数"]
            .sum()
            .sort_values(ascending=False)
        )

        # おもちゃを順番に表示
        toy_icons = {
            "ボール": "⚽",
            "お絵描き": "🎨",
            "ぬいぐるみ": "🧸"
        }

        if toy_counts.empty:
            st.info("この期間の遊びの記録はありません。")

        for toy, count in toy_counts.items():

            st.markdown(
                f"### {toy_icons.get(toy, '🧸')} {toy}"
            )

            st.write(f"遊んだ回数：{int(count)}回")

            st.progress(
                float(count / toy_counts.max())
            )

            st.divider()

        # おすすめの遊び
        st.subheader("🌼 おすすめの遊び")

        st.write("ブロック遊び")

        st.info(
            "ブロックを積んだり、並べたりして、"
            "いろいろな形を作ってみましょう。"
        )


    elif display_mode == "興味の変化":

        st.subheader("🌼 興味の変化")

        st.write(
            "おもちゃごとの遊びの頻度の変化を確認できます。"
        )

        # -------------------------
        # Excelのデータを読み込む
        # -------------------------
        df = pd.read_excel(
            EXCEL_PATH,
            sheet_name="観測データ"
        )

        # 日付を日付形式に変換
        df["観測日"] = pd.to_datetime(df["観測日"])

        # 対象児のデータだけを取り出す
        target_df = df[
            df["識別番号"] == TARGET_ID
        ].copy()

        # -------------------------
        # 表示期間を設定
        # -------------------------
        # デモデータの基準日
        today = pd.Timestamp("2026-09-23")

        # 過去6か月分を表示
        start_month = (
            today.to_period("M") - 5
        ).to_timestamp()

        target_df = target_df[
            (target_df["観測日"] >= start_month) &
            (target_df["観測日"] <= today)
        ].copy()

        # -------------------------
        # 月ごとの観測回数を集計
        # -------------------------
        # 観測日から年月を取得
        target_df["年月"] = (
            target_df["観測日"].dt.to_period("M")
        )

        # 月ごと・おもちゃごとの観測回数を合計
        monthly_counts = (
            target_df.groupby(
                ["年月", "おもちゃの種類"]
            )["観測回数"]
            .sum()
            .unstack(fill_value=0)
        )

        # 6か月分の月を用意
        months = pd.period_range(
            start=start_month,
            end=today,
            freq="M"
        )

        monthly_counts = monthly_counts.reindex(
            index=months,
            columns=["ボール", "お絵描き", "ぬいぐるみ"],
            fill_value=0
        )

        # -------------------------
        # 折れ線グラフを作成
        # -------------------------
        fig = go.Figure()

        toy_colors = {
            "ボール": "#E98BA8",
            "お絵描き": "#80B6D9",
            "ぬいぐるみ": "#E8C46B"
        }

        for toy in ["ボール", "お絵描き", "ぬいぐるみ"]:

            fig.add_trace(
                go.Scatter(
                    x=[
                        f"{month.month}月"
                        for month in monthly_counts.index
                    ],
                    y=monthly_counts[toy],
                    mode="lines+markers",
                    name=toy,
                    line=dict(
                        color=toy_colors[toy],
                        width=3
                    ),
                    marker=dict(size=9),
                    hovertemplate=(
                        "%{x}<br>"
                        + toy
                        + "：%{y}回"
                        + "<extra></extra>"
                    )
                )
            )

        # グラフの見た目
        fig.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="月",
            yaxis_title="観測回数（回）",
            yaxis=dict(rangemode="tozero"),
            legend=dict(
                orientation="h",
                y=1.15,
                x=0
            ),
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        # -------------------------
        # 興味のポイント
        # -------------------------
        st.markdown("### 💡 興味のポイント")

        if not target_df.empty:

            # 最新月の観測回数
            latest_counts = monthly_counts.iloc[-1]

            if latest_counts.sum() > 0:

                # 最も観測回数が多いおもちゃ
                favorite_toy = latest_counts.idxmax()

                st.info(
                    f"最近は「{favorite_toy}」での遊びが"
                    "多く見られています。"
                    "ほかのおもちゃとの遊びの頻度の"
                    "変化も確認してみましょう。"
                )

            else:
                st.info(
                    "最新月の遊びの記録はありません。"
                )

        else:
            st.info(
                "この期間の遊びの記録はありません。"
            )

        st.caption(
            "※ グラフはExcelの観測データをもとに"
            "作成しています。"
        )


    
    elif display_mode == "関連情報":

        st.subheader("🌷 関連情報")

        st.write(
            "お子さんの遊びに役立つ情報を確認できます。"
        )

        # -------------------------
        # 月齢に合わせた遊びのアイデア
        # -------------------------
        st.markdown("### 🧸 月齢に合わせた遊びのアイデア")

        # 1つ目の遊び
        col1, col2 = st.columns([1, 2])

        with col1:
            show_photo("blocks.jpg")

        with col2:
            st.markdown("**つみき遊び**")

            st.write(
                "つみきを積んだり、並べたりして、"
                "いろいろな形を作ってみましょう。"
            )

            st.caption("手先の動き・創造性")

        st.divider()

        # 2つ目の遊び
        col1, col2 = st.columns([1, 2])

        with col1:
            show_photo("drawing.jpg")

        with col2:
            st.markdown("**お絵描き遊び**")

            st.write(
                "好きな色を選び、自由に線や形を"
                "描いてみましょう。"
            )

            st.caption("表現する力・手先の動き")

        st.divider()

        # 3つ目の遊び
        col1, col2 = st.columns([1, 2])

        with col1:
            show_photo("ball.jpg")

        with col2:
            st.markdown("**ボール遊び**")

            st.write(
                "ボールを転がしたり、投げたりして、"
                "体を動かして遊びましょう。"
            )

            st.caption("体の動き・協調性")

        # -------------------------
        # 地域の遊び場・イベント情報
        # -------------------------
        st.markdown("### 🔗 地域の遊び場・イベント情報")

        st.write("**🌳 近くの遊び場を探す**")

        st.write(
            "公園や子育て支援施設など、"
            "親子で遊べる場所を探せます。"
        )

        st.link_button(
            "遊び場を探す ↗",
            "https://www.google.com/maps/search/?api=1&query=公園+子育て支援施設",
            use_container_width=True
        )

        st.divider()

        st.write("**🎪 子ども向けイベント情報**")

        st.write(
            "親子で参加できるイベントや"
            "地域の子育て情報を探せます。"
        )

        st.link_button(
            "イベント情報を探す ↗",
            "https://www.google.com/search?q=親子向けイベント+子育て",
            use_container_width=True
        )

        st.caption(
            "※ 外部サイトの情報が表示されます。"
        )


# -------------------------
# 園・保護者との共有画面
# -------------------------
def share_page():

    if st.button("← ホームに戻る", key="back_share"):
        move_page("ホーム")
        st.rerun()

    st.title("園・保護者との共有")
    st.caption("家庭と園での様子を共有・確認できます。")

    # 家庭と園の切り替え
    display_mode = st.segmented_control(
        "表示する情報",
        ["家庭の様子", "園の様子"],
        default="家庭の様子",
        key="share_mode"
    )

   # 家庭側からの記録
    # -------------------------
    # 家庭の様子
    # -------------------------
    if display_mode == "家庭の様子":
        if st.button("＋ 記録する", key="add_parent_record"):
            st.session_state.parent_record_type = "家庭での様子"
            move_page("保護者からの入力")
            st.rerun()

        # 家庭で保存した記録を取得
        parent_records = st.session_state.get("parent_records", [])

        # -------------------------
        # 家庭での様子
        # -------------------------
        st.subheader("🍀 家庭での様子")

        home_records = [
            r for r in parent_records
            if r["type"] == "家庭での様子"
        ]

        if home_records:
            for record in reversed(home_records):
                with st.container(border=True):
                    st.caption(record["date"])
                    st.write(record["content"])

                    if record["photo"] is not None:
                        st.image(
                            record["photo"],
                            use_container_width=True
                        )
        else:
            st.caption("4月20日（木）")

            col1, col2 = st.columns(2)

            with col1:
                show_photo("home1.jpg")

            with col2:
                show_photo("home2.jpg")

            st.write(
                "今日はブロックを高く積んで遊んでいました。"
                "「もっと高くできる！」と楽しそうにしていました。"
            )

        st.divider()

        # -------------------------
        # 最近できるようになったこと
        # -------------------------
        st.subheader("🌷 最近できるようになったこと（家庭）")

        growth_records = [
            r for r in parent_records
            if r["type"] == "最近できるようになったこと"
        ]

        if growth_records:
            for record in reversed(growth_records):
                with st.container(border=True):
                    st.caption(record["date"])
                    st.write(record["content"])

                    if record["photo"] is not None:
                        st.image(
                            record["photo"],
                            use_container_width=True
                        )
        else:
            col1, col2 = st.columns([1, 3])

            with col1:
                show_photo("growth_home.jpg")

            with col2:
                st.caption("4月15日")
                st.write(
                    "スプーンを使って一人で食べることが"
                    "できるようになった。"
                )

        st.divider()

        # -------------------------
        # 家庭でよく行う遊び・おもちゃ
        # -------------------------
        st.subheader("🌼 家庭でよく行う遊び・おもちゃ")

        toys = [
            ("ブロック", "blocks.jpg"),
            ("ままごと", "pretend.jpg"),
            ("絵本", "book.jpg"),
            ("戸外遊び", "outside.jpg")
        ]

        cols = st.columns(4)

        for i, (name, filename) in enumerate(toys):
            with cols[i]:
                show_photo(filename)
                st.caption(name)

   # 園側からの記録
    elif display_mode == "園の様子":

        if st.button("＋ 記録する", key="add_school_record"):
            st.session_state.school_record_type = "園で最近できるようになったこと"
            move_page("園からの入力")
            st.rerun()

        # 園で保存した記録を取得
        school_records = st.session_state.get("school_records", [])

        # -------------------------
        # 園でよく行う遊びやおもちゃ
        # -------------------------
        st.subheader("🧸 園でよく行う遊びやおもちゃ")

        school_toys = [
            ("ブロック", "blocks.jpg"),
            ("ままごと", "pretend.jpg"),
            ("絵本", "book.jpg"),
            ("ボール", "ball.jpg")
        ]

        cols = st.columns(4)

        for i, (name, filename) in enumerate(school_toys):
            with cols[i]:
                show_photo(filename)
                st.caption(name)

        st.divider()

        # -------------------------
        # 記録できる4つの項目
        # -------------------------
        school_sections = [
            ("🌷", "園で最近できるようになったこと"),
            ("👫", "友達との関わり"),
            ("🎨", "園での遊びの様子"),
            ("💬", "保育者からのコメント")
        ]


        for i, (icon, section_name) in enumerate(school_sections):

            st.subheader(f"{icon} {section_name}")

            # この項目に保存された記録だけを取得
            section_records = [
                r for r in school_records
                if r["type"] == section_name
            ]

            # 保存した記録を表示
            if section_records:
                for record in reversed(section_records):
                    with st.container(border=True):

                        st.caption(record["date"])
                        st.write(record["content"])

                        if record["photo"] is not None:
                            st.image(
                                record["photo"],
                                use_container_width=True
                            )

            else:
                st.caption("まだ記録がありません。")

            st.divider()




    # -------------------------
    # 入力した記録を表示
    # -------------------------
    if "share_comments" in st.session_state:

        if display_mode == "家庭の様子":
            sender = "保護者"
        else:
            sender = "保育者"

        comments = [
            c for c in st.session_state.share_comments
            if c["sender"] == sender
        ]

        if comments:
            st.divider()
            st.subheader("📝 追加した記録")

            for comment in reversed(comments):
                with st.container(border=True):
                    st.caption(comment.get("date", ""))
                    st.text(comment["message"])

# -------------------------
# 家庭の記録入力画面
# -------------------------
def parent_input_page():

    if st.button("← 共有画面に戻る", key="back_parent"):
        move_page("園・保護者との共有")
        st.rerun()

    st.title("🏠 家庭の記録を追加")

    st.write("家庭での遊びや成長の様子を記録できます。")

    with st.form("parent_record_form", clear_on_submit=True):

        record_date = st.date_input(
            "日付",
            value=date(2026, 9, 23)
        )

        record_types = [
    "家庭での様子",
    "最近できるようになったこと"
     ]

        selected_type = st.session_state.get(
    "parent_record_type",
    "家庭での様子"
      )

        record_type = st.selectbox(
    "記録する項目を選択",
    record_types,
    index=record_types.index(selected_type)
       )

        content = st.text_area(
            "記録内容",
            placeholder="家庭での様子を入力してください。"
        )

        photo = st.file_uploader(
            "写真を追加（任意）",
            type=["jpg", "jpeg", "png"]
        )

        submitted = st.form_submit_button(
            "記録を保存する",
            use_container_width=True
        )

    if submitted:

        if not content.strip():
            st.warning("記録内容を入力してください。")

        else:
            if "parent_records" not in st.session_state:
                st.session_state.parent_records = []

            # 写真を一時的に保持
            photo_data = None

            if photo is not None:
                photo_data = photo.getvalue()

            # 記録を追加
            st.session_state.parent_records.append({
                "date": str(record_date),
                "type": record_type,
                "content": content.strip(),
                "photo": photo_data
            })

            # 家庭の様子を表示
            st.session_state.share_mode = "家庭の様子"

            move_page("園・保護者との共有")
            st.rerun()


# -------------------------
# 園の記録入力画面
# -------------------------
def school_input_page():

    if st.button("← 共有画面に戻る", key="back_school"):
        st.session_state.share_mode = "園の様子"
        move_page("園・保護者との共有")
        st.rerun()

    st.title("🏫 園の記録を追加")
    st.write("園での遊びや成長の様子を記録できます。")

    with st.form("school_record_form", clear_on_submit=True):

        record_date = st.date_input(
            "日付",
            value=date.today()
        )

        record_types = [
            "園で最近できるようになったこと",
            "友達との関わり",
            "園での遊びの様子",
            "保育者からのコメント"
        ]

        # 押したボタンに対応する項目を初期選択
        selected_type = st.session_state.get(
            "school_record_type",
            "園で最近できるようになったこと"
        )

        record_type = st.selectbox(
            "記録する項目を選択",
            record_types,
            index=record_types.index(selected_type)
        )

        content = st.text_area(
            "記録内容",
            placeholder="園での子どもの様子を入力してください。"
        )

        photo = st.file_uploader(
            "写真を追加（任意）",
            type=["jpg", "jpeg", "png"]
        )

        submitted = st.form_submit_button(
            "記録を保存する",
            use_container_width=True
        )

    if submitted:

        if not content.strip():
            st.warning("記録内容を入力してください。")

        else:
            if "school_records" not in st.session_state:
                st.session_state.school_records = []

            # 写真を一時的に保持
            photo_data = None

            if photo is not None:
                photo_data = photo.getvalue()

            # 記録を保存
            st.session_state.school_records.append({
                "date": str(record_date),
                "type": record_type,
                "content": content.strip(),
                "photo": photo_data
            })

            # 園の様子に戻る
            st.session_state.share_mode = "園の様子"
            move_page("園・保護者との共有")
            st.rerun()


def detail_page(page_name):
    st.title(page_name)
    st.write("この画面はこれから作成します。")

    if st.button("← ホームに戻る"):
        move_page("ホーム")
        st.rerun()

# -------------------------
# 画面の表示
# -------------------------
if st.session_state.page == "ホーム":
    home_page()

elif st.session_state.page == "発達状況":
    development_page()

elif st.session_state.page == "記録詳細":
    record_detail_page()

elif st.session_state.page == "記録入力":
    record_input_page()

elif st.session_state.page == "遊び・興味":
    interest_page()

elif st.session_state.page == "園・保護者との共有":
    share_page()

elif st.session_state.page == "保護者からの入力":
    parent_input_page()

elif st.session_state.page == "園からの入力":
    school_input_page()

else:
    detail_page(st.session_state.page)


# -------------------------
# 下部メニュー（仮）
# -------------------------
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 ホーム"):
        move_page("ホーム")
        st.rerun()

with col2:
    if st.button("🔔 お知らせ"):
        move_page("お知らせ")
        st.rerun()

with col3:
    if st.button("⚙️ 設定"):
        move_page("設定")
        st.rerun()
