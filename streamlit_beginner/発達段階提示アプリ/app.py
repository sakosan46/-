
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
