import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────
# 設定・スタイル
# ──────────────────────────────────────────
st.set_page_config(page_title="マーケティング分析ダッシュボード", layout="wide", page_icon="📊")

COLORS = {
    "primary": "#1B2A4A",
    "accent": "#E8913A",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "danger": "#E74C3C",
    "bg": "#F8F9FA",
    "card": "#FFFFFF",
    "text": "#2C3E50",
    "muted": "#95A5A6",
}

FUNNEL_COLORS = ["#3498DB", "#E8913A", "#2ECC71"]
PALETTE = px.colors.qualitative.Set2

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
.stApp { background-color: #F0F2F6; }
.metric-card {
    background: white; border-radius: 12px; padding: 20px 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); text-align: center;
    border-left: 4px solid #E8913A;
}
.metric-card h3 { margin: 0; font-size: 14px; color: #95A5A6; font-weight: 400; }
.metric-card h1 { margin: 4px 0 0; font-size: 28px; color: #1B2A4A; font-weight: 700; }
.section-title {
    font-size: 20px; font-weight: 700; color: #1B2A4A;
    border-bottom: 3px solid #E8913A; padding-bottom: 8px; margin: 24px 0 16px;
}
.warning-badge {
    background: #FFF3CD; color: #856404; padding: 4px 10px;
    border-radius: 6px; font-size: 12px; display: inline-block;
}
.good-badge {
    background: #D4EDDA; color: #155724; padding: 4px 10px;
    border-radius: 6px; font-size: 12px; display: inline-block;
}
div[data-testid="stSidebar"] { background-color: #1B2A4A; }
div[data-testid="stSidebar"] .stMarkdown h1,
div[data-testid="stSidebar"] .stMarkdown h2,
div[data-testid="stSidebar"] .stMarkdown h3,
div[data-testid="stSidebar"] .stMarkdown p,
div[data-testid="stSidebar"] .stMarkdown li,
div[data-testid="stSidebar"] .stMarkdown label { color: #ECF0F1 !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────
# データ読み込み・クレンジング
# ──────────────────────────────────────────
@st.cache_data
def load_data(source):
    df = pd.read_excel(source)

    # リードソース統合
    source_map = {
        "yahoo": "Yahoo", "Yahoo": "Yahoo",
        "google": "Google", "Google": "Google",
        "Facebook": "Facebook",
        "microsoft": "Microsoft", "Bing Ad": "Microsoft",
        "nikkei": "Nikkei",
        "careNet": "CareNet",
        "line": "LINE", "Line": "LINE",
        "columnSite": "コラムサイト",
        "LinkedIn": "LinkedIn",
    }
    df["リードソース"] = df["リードソース"].map(source_map).fillna(df["リードソース"])

    # 順序付きカテゴリ
    asset_order = ["2000万円未満", "5000万円未満", "1億円未満", "5億円未満", "5億円以上"]
    age_order = ["20代", "30代", "40代", "50代", "60代", "70～74歳", "75歳以上"]
    exp_order = ["なし", "1年未満", "3年未満", "3年以上"]
    progress_order = ["未面談", "面談後", "成約"]

    df["純金融資産"] = pd.Categorical(df["純 金融資産"], categories=asset_order, ordered=True)
    df["年代"] = pd.Categorical(df["年代（資料請求時）"], categories=age_order, ordered=True)
    df["投資経験"] = pd.Categorical(df["投資経験年数"], categories=exp_order, ordered=True)
    df["進捗"] = pd.Categorical(df["リード進捗"], categories=progress_order, ordered=True)
    df["職業"] = df["VTX_職業"]
    df["月"] = df["作成日"].dt.to_period("M").astype(str)

    # 成約フラグ / 面談フラグ
    df["is_meeting"] = df["進捗"].isin(["面談後", "成約"]).astype(int)
    df["is_closed"] = (df["進捗"] == "成約").astype(int)

    return df

# ファイル読み込み: リポジトリ内 → アップロード → ファイルアップローダー
DATA_FILENAME = "マーケデータクレンジング２.xlsx"
LOCAL_PATHS = [
    DATA_FILENAME,
    os.path.join("data", DATA_FILENAME),
    os.path.join("/mnt/user-data/uploads", DATA_FILENAME),
]

data_source = None
for p in LOCAL_PATHS:
    if os.path.exists(p):
        data_source = p
        break

if data_source is None:
    st.sidebar.markdown("# 📊 マーケ分析")
    st.sidebar.markdown("---")
    uploaded = st.sidebar.file_uploader("Excelファイルをアップロード", type=["xlsx", "xls"])
    if uploaded is None:
        st.info("サイドバーからExcelファイルをアップロードしてください。")
        st.stop()
    data_source = uploaded

df = load_data(data_source)

# ──────────────────────────────────────────
# ユーティリティ関数
# ──────────────────────────────────────────
def calc_funnel(data):
    """ファネル指標を計算"""
    n = len(data)
    meeting = data["is_meeting"].sum()
    closed = data["is_closed"].sum()
    revenue = data["売り上げ"].sum()
    avg_revenue = data.loc[data["is_closed"] == 1, "売り上げ"].mean() if closed > 0 else 0
    meeting_rate = meeting / n * 100 if n > 0 else 0
    close_rate = closed / n * 100 if n > 0 else 0
    close_from_meeting = closed / meeting * 100 if meeting > 0 else 0
    return {
        "リード数": n, "面談数": meeting, "成約数": closed,
        "面談率": meeting_rate, "成約率": close_rate,
        "面談→成約率": close_from_meeting,
        "売上合計": revenue, "平均売上": avg_revenue,
    }

def funnel_table(data, group_col):
    """グループ別ファネルテーブルを作成"""
    rows = []
    for name, grp in data.groupby(group_col, observed=True):
        f = calc_funnel(grp)
        f[group_col] = name
        rows.append(f)
    result = pd.DataFrame(rows)
    if len(result) > 0:
        result = result.set_index(group_col)
    return result

def format_yen(val):
    if val >= 1e8:
        return f"¥{val/1e8:.1f}億"
    elif val >= 1e4:
        return f"¥{val/1e4:.0f}万"
    else:
        return f"¥{val:,.0f}"

def sample_warning(n):
    if n <= 10:
        return f'<span class="warning-badge">⚠ n={n} 要注意</span>'
    elif n <= 30:
        return f'<span class="warning-badge">△ n={n}</span>'
    return f'<span class="good-badge">n={n}</span>'

def metric_card(label, value, sub=""):
    sub_html = f'<p style="margin:2px 0 0;font-size:12px;color:#95A5A6;">{sub}</p>' if sub else ""
    return f"""
    <div class="metric-card">
        <h3>{label}</h3>
        <h1>{value}</h1>
        {sub_html}
    </div>"""

# ──────────────────────────────────────────
# サイドバー
# ──────────────────────────────────────────
with st.sidebar:
    st.markdown("# 📊 マーケ分析")
    st.markdown("---")
    page = st.radio(
        "ページ選択",
        ["① エグゼクティブサマリー",
         "② 単軸ファネル分析",
         "③ 二軸クロス分析",
         "④ 多軸ドリルダウン",
         "⑤ リードスコアリング"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown(f"**データ件数:** {len(df)} 件")
    st.markdown(f"**期間:** {df['作成日'].min().strftime('%Y/%m/%d')} ～ {df['作成日'].max().strftime('%Y/%m/%d')}")
    st.markdown(f"**成約数:** {df['is_closed'].sum()} 件")
    st.markdown(f"**売上合計:** {format_yen(df['売り上げ'].sum())}")


# ══════════════════════════════════════════
# ページ① エグゼクティブサマリー
# ══════════════════════════════════════════
if page == "① エグゼクティブサマリー":
    st.markdown("# 📈 エグゼクティブサマリー")
    st.markdown("事業全体のファネルパフォーマンスと月次推移を一覧します。")

    overall = calc_funnel(df)

    # KPIカード
    cols = st.columns(5)
    cards = [
        ("総リード数", f"{overall['リード数']:,}", ""),
        ("面談率", f"{overall['面談率']:.1f}%", f"{overall['面談数']}件が面談済み"),
        ("成約率", f"{overall['成約率']:.1f}%", f"{overall['成約数']}件が成約"),
        ("面談→成約率", f"{overall['面談→成約率']:.1f}%", "面談を経た後の成約率"),
        ("売上合計", format_yen(overall['売上合計']), f"平均 {format_yen(overall['平均売上'])}/件"),
    ]
    for col, (label, value, sub) in zip(cols, cards):
        col.markdown(metric_card(label, value, sub), unsafe_allow_html=True)

    st.markdown("")

    # ファネルチャート
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="section-title">コンバージョンファネル</div>', unsafe_allow_html=True)
        fig_funnel = go.Figure(go.Funnel(
            y=["リード獲得", "面談実施", "成約"],
            x=[overall["リード数"], overall["面談数"], overall["成約数"]],
            textinfo="value+percent initial",
            marker=dict(color=FUNNEL_COLORS),
            connector=dict(line=dict(color="#DDD", width=2)),
        ))
        fig_funnel.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20),
                                  font=dict(family="Noto Sans JP"))
        st.plotly_chart(fig_funnel, use_container_width=True)

    with col2:
        st.markdown('<div class="section-title">リードソース構成</div>', unsafe_allow_html=True)
        source_counts = df["リードソース"].value_counts().reset_index()
        source_counts.columns = ["ソース", "件数"]
        fig_pie = px.pie(source_counts, values="件数", names="ソース",
                         color_discrete_sequence=PALETTE, hole=0.4)
        fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20),
                               font=dict(family="Noto Sans JP"),
                               legend=dict(orientation="v", x=1.05))
        fig_pie.update_traces(textposition='inside', textinfo='label+percent')
        st.plotly_chart(fig_pie, use_container_width=True)

    # 月次推移
    st.markdown('<div class="section-title">月次推移</div>', unsafe_allow_html=True)
    monthly = df.groupby("月", observed=True).agg(
        リード数=("is_closed", "count"),
        面談数=("is_meeting", "sum"),
        成約数=("is_closed", "sum"),
        売上=("売り上げ", "sum"),
    ).reset_index()
    monthly["面談率"] = monthly["面談数"] / monthly["リード数"] * 100
    monthly["成約率"] = monthly["成約数"] / monthly["リード数"] * 100

    fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
    fig_monthly.add_trace(
        go.Bar(x=monthly["月"], y=monthly["リード数"], name="リード数",
               marker_color="#3498DB", opacity=0.7), secondary_y=False)
    fig_monthly.add_trace(
        go.Bar(x=monthly["月"], y=monthly["成約数"], name="成約数",
               marker_color="#2ECC71", opacity=0.9), secondary_y=False)
    fig_monthly.add_trace(
        go.Scatter(x=monthly["月"], y=monthly["成約率"], name="成約率",
                   mode="lines+markers", line=dict(color="#E8913A", width=3),
                   marker=dict(size=8)), secondary_y=True)
    fig_monthly.update_layout(
        height=400, barmode="group",
        margin=dict(l=40, r=40, t=20, b=40),
        font=dict(family="Noto Sans JP"),
        legend=dict(orientation="h", y=-0.15),
    )
    fig_monthly.update_yaxes(title_text="件数", secondary_y=False)
    fig_monthly.update_yaxes(title_text="成約率 (%)", secondary_y=True)
    st.plotly_chart(fig_monthly, use_container_width=True)

    # 月次売上
    st.markdown('<div class="section-title">月次売上推移</div>', unsafe_allow_html=True)
    fig_rev = go.Figure()
    fig_rev.add_trace(go.Bar(
        x=monthly["月"], y=monthly["売上"], name="売上",
        marker_color="#E8913A", opacity=0.85,
        text=[format_yen(v) for v in monthly["売上"]],
        textposition="outside"
    ))
    fig_rev.update_layout(
        height=350, margin=dict(l=40, r=40, t=20, b=40),
        font=dict(family="Noto Sans JP"),
        yaxis_title="売上 (円)",
    )
    st.plotly_chart(fig_rev, use_container_width=True)


# ══════════════════════════════════════════
# ページ② 単軸ファネル分析
# ══════════════════════════════════════════
elif page == "② 単軸ファネル分析":
    st.markdown("# 🔍 単軸ファネル分析")
    st.markdown("各ディメンション単体で、ファネル転換率と売上貢献を比較します。")

    axis_options = {
        "リードソース": "リードソース",
        "純金融資産": "純金融資産",
        "年代": "年代",
        "投資経験": "投資経験",
        "職業": "職業",
    }
    selected_axis = st.selectbox("分析軸を選択", list(axis_options.keys()))
    col_name = axis_options[selected_axis]

    ft = funnel_table(df, col_name)
    if len(ft) == 0:
        st.warning("データがありません。")
    else:
        # KPIテーブル
        st.markdown(f'<div class="section-title">{selected_axis}別 ファネル指標</div>', unsafe_allow_html=True)

        display_df = ft[["リード数", "面談数", "成約数", "面談率", "成約率", "面談→成約率", "売上合計", "平均売上"]].copy()
        display_df["面談率"] = display_df["面談率"].apply(lambda x: f"{x:.1f}%")
        display_df["成約率"] = display_df["成約率"].apply(lambda x: f"{x:.1f}%")
        display_df["面談→成約率"] = display_df["面談→成約率"].apply(lambda x: f"{x:.1f}%")
        display_df["売上合計"] = display_df["売上合計"].apply(format_yen)
        display_df["平均売上"] = display_df["平均売上"].apply(lambda x: format_yen(x) if x > 0 else "—")
        display_df["リード数"] = display_df["リード数"].astype(int)
        display_df["面談数"] = display_df["面談数"].astype(int)
        display_df["成約数"] = display_df["成約数"].astype(int)
        st.dataframe(display_df, use_container_width=True)

        # サンプルサイズ注記
        small_n = ft[ft["リード数"] <= 10]
        if len(small_n) > 0:
            st.warning(f"⚠ サンプル数が10以下のセグメント: {', '.join(small_n.index.astype(str))} — 転換率の解釈には注意が必要です。")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f'<div class="section-title">リード数と成約数</div>', unsafe_allow_html=True)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=ft.index.astype(str), y=ft["リード数"], name="リード数",
                marker_color="#3498DB", opacity=0.7
            ))
            fig_bar.add_trace(go.Bar(
                x=ft.index.astype(str), y=ft["成約数"], name="成約数",
                marker_color="#2ECC71", opacity=0.9
            ))
            fig_bar.update_layout(
                barmode="group", height=400,
                margin=dict(l=40, r=20, t=20, b=80),
                font=dict(family="Noto Sans JP"),
                xaxis_tickangle=-30,
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.markdown(f'<div class="section-title">転換率比較</div>', unsafe_allow_html=True)
            fig_rate = go.Figure()
            fig_rate.add_trace(go.Bar(
                x=ft.index.astype(str), y=ft["面談率"], name="面談率",
                marker_color="#3498DB", opacity=0.8
            ))
            fig_rate.add_trace(go.Bar(
                x=ft.index.astype(str), y=ft["成約率"], name="成約率",
                marker_color="#E8913A", opacity=0.9
            ))
            fig_rate.update_layout(
                barmode="group", height=400,
                margin=dict(l=40, r=20, t=20, b=80),
                font=dict(family="Noto Sans JP"),
                yaxis_title="%",
                xaxis_tickangle=-30,
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig_rate, use_container_width=True)

        # 売上構成
        st.markdown(f'<div class="section-title">売上構成</div>', unsafe_allow_html=True)
        rev_data = ft[ft["売上合計"] > 0].sort_values("売上合計", ascending=True)
        if len(rev_data) > 0:
            fig_rev = go.Figure(go.Bar(
                y=rev_data.index.astype(str), x=rev_data["売上合計"],
                orientation="h", marker_color="#E8913A",
                text=[format_yen(v) for v in rev_data["売上合計"]],
                textposition="outside",
            ))
            fig_rev.update_layout(
                height=max(300, len(rev_data) * 50),
                margin=dict(l=20, r=100, t=20, b=20),
                font=dict(family="Noto Sans JP"),
                xaxis_title="売上合計 (円)",
            )
            st.plotly_chart(fig_rev, use_container_width=True)


# ══════════════════════════════════════════
# ページ③ 二軸クロス分析
# ══════════════════════════════════════════
elif page == "③ 二軸クロス分析":
    st.markdown("# 🗺️ 二軸クロス分析（ヒートマップ）")
    st.markdown("2つの変数を掛け合わせて、成約率や売上をヒートマップで可視化します。")

    dim_options = {
        "リードソース": "リードソース",
        "純金融資産": "純金融資産",
        "年代": "年代",
        "投資経験": "投資経験",
        "職業": "職業",
    }

    col1, col2 = st.columns(2)
    with col1:
        axis_x = st.selectbox("行（縦軸）", list(dim_options.keys()), index=0)
    with col2:
        remaining = [k for k in dim_options.keys() if k != axis_x]
        axis_y = st.selectbox("列（横軸）", remaining, index=0)

    metric = st.radio("表示指標", ["成約率", "面談率", "リード数", "売上合計", "成約数"], horizontal=True)

    x_col = dim_options[axis_x]
    y_col = dim_options[axis_y]

    # クロス集計
    cross_data = []
    for (xv, yv), grp in df.groupby([x_col, y_col], observed=True):
        f = calc_funnel(grp)
        f[x_col] = xv
        f[y_col] = yv
        cross_data.append(f)

    if len(cross_data) == 0:
        st.warning("データがありません。")
    else:
        cross_df = pd.DataFrame(cross_data)

        pivot = cross_df.pivot_table(index=x_col, columns=y_col, values=metric, aggfunc="first")
        pivot_n = cross_df.pivot_table(index=x_col, columns=y_col, values="リード数", aggfunc="first").fillna(0)

        # カスタムテキスト（値 + n数）
        if metric in ["成約率", "面談率", "面談→成約率"]:
            text_matrix = pivot.map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
            fmt = ".1f"
            colorscale = "YlOrRd"
        elif metric == "売上合計":
            text_matrix = pivot.map(lambda x: format_yen(x) if pd.notna(x) and x > 0 else "—")
            fmt = ","
            colorscale = "YlGnBu"
        else:
            text_matrix = pivot.map(lambda x: f"{int(x)}" if pd.notna(x) else "0")
            fmt = ","
            colorscale = "Blues"

        # n数をテキストに追加
        combined_text = []
        for i in range(len(text_matrix)):
            row = []
            for j in range(len(text_matrix.columns)):
                val = text_matrix.iloc[i, j]
                n_val = int(pivot_n.iloc[i, j]) if pd.notna(pivot_n.iloc[i, j]) else 0
                if n_val <= 10 and n_val > 0:
                    row.append(f"{val}<br><b style='color:red'>n={n_val}</b>")
                elif n_val > 0:
                    row.append(f"{val}<br>n={n_val}")
                else:
                    row.append("—")
            combined_text.append(row)

        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=[str(i) for i in pivot.index],
            text=combined_text,
            texttemplate="%{text}",
            colorscale=colorscale,
            hoverongaps=False,
            showscale=True,
            colorbar=dict(title=metric),
        ))
        fig_heat.update_layout(
            height=max(400, len(pivot) * 60),
            margin=dict(l=20, r=20, t=40, b=60),
            font=dict(family="Noto Sans JP", size=12),
            xaxis_title=axis_y,
            yaxis_title=axis_x,
            xaxis=dict(tickangle=-30),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("---")
        st.markdown(f'<div class="section-title">クロス集計テーブル（{metric}）</div>', unsafe_allow_html=True)

        styled_pivot = pivot.copy()
        if metric in ["成約率", "面談率"]:
            styled_pivot = styled_pivot.map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        elif metric == "売上合計":
            styled_pivot = styled_pivot.map(lambda x: format_yen(x) if pd.notna(x) and x > 0 else "—")
        else:
            styled_pivot = styled_pivot.map(lambda x: f"{int(x)}" if pd.notna(x) else "0")
        st.dataframe(styled_pivot, use_container_width=True)


# ══════════════════════════════════════════
# ページ④ 多軸ドリルダウン
# ══════════════════════════════════════════
elif page == "④ 多軸ドリルダウン":
    st.markdown("# 🔬 多軸ドリルダウン")
    st.markdown("最大3つの軸を順にフィルタリングして、特定セグメントの詳細を深掘りします。")

    dim_map = {
        "リードソース": "リードソース",
        "純金融資産": "純金融資産",
        "年代": "年代",
        "投資経験": "投資経験",
        "職業": "職業",
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        axis1 = st.selectbox("第1軸", list(dim_map.keys()), index=0, key="dd1")
    with col2:
        rem2 = [k for k in dim_map.keys() if k != axis1]
        axis2 = st.selectbox("第2軸", rem2, index=0, key="dd2")
    with col3:
        rem3 = [k for k in dim_map.keys() if k not in [axis1, axis2]]
        axis3 = st.selectbox("第3軸（任意）", ["なし"] + rem3, index=0, key="dd3")

    # 第1軸フィルタ
    st.markdown(f'<div class="section-title">第1軸: {axis1}</div>', unsafe_allow_html=True)
    ft1 = funnel_table(df, dim_map[axis1])

    display1 = ft1[["リード数", "成約数", "成約率", "売上合計"]].copy()
    display1["成約率"] = display1["成約率"].apply(lambda x: f"{x:.1f}%")
    display1["売上合計"] = display1["売上合計"].apply(format_yen)
    display1["リード数"] = display1["リード数"].astype(int)
    display1["成約数"] = display1["成約数"].astype(int)
    st.dataframe(display1, use_container_width=True)

    options1 = df[dim_map[axis1]].dropna().unique().tolist()
    options1_str = sorted([str(o) for o in options1])
    selected1 = st.multiselect(f"{axis1}を選択（複数可）", options1_str, default=options1_str[:3] if len(options1_str) > 3 else options1_str)

    if selected1:
        filtered1 = df[df[dim_map[axis1]].astype(str).isin(selected1)]
        n_filtered = len(filtered1)
        st.info(f"フィルタ後: {n_filtered}件")

        # 第2軸
        st.markdown(f'<div class="section-title">第2軸: {axis2}（{axis1}: {", ".join(selected1)}）</div>', unsafe_allow_html=True)
        ft2 = funnel_table(filtered1, dim_map[axis2])

        if len(ft2) > 0:
            # チャート
            fig_dd = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dd.add_trace(go.Bar(
                x=ft2.index.astype(str), y=ft2["リード数"], name="リード数",
                marker_color="#3498DB", opacity=0.6
            ), secondary_y=False)
            fig_dd.add_trace(go.Bar(
                x=ft2.index.astype(str), y=ft2["成約数"], name="成約数",
                marker_color="#2ECC71", opacity=0.9
            ), secondary_y=False)
            fig_dd.add_trace(go.Scatter(
                x=ft2.index.astype(str), y=ft2["成約率"], name="成約率",
                mode="lines+markers", line=dict(color="#E8913A", width=3),
                marker=dict(size=10)
            ), secondary_y=True)
            fig_dd.update_layout(
                height=400, barmode="group",
                margin=dict(l=40, r=40, t=20, b=60),
                font=dict(family="Noto Sans JP"),
                legend=dict(orientation="h", y=-0.2),
                xaxis_tickangle=-30,
            )
            fig_dd.update_yaxes(title_text="件数", secondary_y=False)
            fig_dd.update_yaxes(title_text="成約率 (%)", secondary_y=True)
            st.plotly_chart(fig_dd, use_container_width=True)

            # 小サンプル警告
            small = ft2[ft2["リード数"] <= 10]
            if len(small) > 0:
                st.warning(f"⚠ サンプル≤10: {', '.join(small.index.astype(str))}")

            # 第3軸
            if axis3 != "なし":
                st.markdown(f'<div class="section-title">第3軸: {axis3}</div>', unsafe_allow_html=True)

                options2 = filtered1[dim_map[axis2]].dropna().unique().tolist()
                options2_str = sorted([str(o) for o in options2])
                selected2 = st.multiselect(f"{axis2}を選択", options2_str, default=options2_str[:3] if len(options2_str) > 3 else options2_str)

                if selected2:
                    filtered2 = filtered1[filtered1[dim_map[axis2]].astype(str).isin(selected2)]
                    st.info(f"フィルタ後: {len(filtered2)}件")

                    ft3 = funnel_table(filtered2, dim_map[axis3])
                    if len(ft3) > 0:
                        display3 = ft3[["リード数", "面談数", "成約数", "面談率", "成約率", "売上合計"]].copy()
                        display3["面談率"] = display3["面談率"].apply(lambda x: f"{x:.1f}%")
                        display3["成約率"] = display3["成約率"].apply(lambda x: f"{x:.1f}%")
                        display3["売上合計"] = display3["売上合計"].apply(format_yen)
                        st.dataframe(display3, use_container_width=True)

                        small3 = ft3[ft3["リード数"] <= 10]
                        if len(small3) > 0:
                            st.warning(f"⚠ サンプル≤10: {', '.join(small3.index.astype(str))} — 統計的に信頼できる結論は得にくい件数です。")
                    else:
                        st.info("該当データなし")


# ══════════════════════════════════════════
# ページ⑤ リードスコアリング
# ══════════════════════════════════════════
elif page == "⑤ リードスコアリング":
    st.markdown("# 🎯 リードスコアリング・シミュレーション")
    st.markdown("属性の組み合わせごとに期待成約率と期待売上を探索し、理想的なリードプロファイルを特定します。")

    # 各属性の成約率への寄与を計算
    st.markdown('<div class="section-title">属性別 成約率の比較</div>', unsafe_allow_html=True)

    dims = {
        "リードソース": "リードソース",
        "純金融資産": "純金融資産",
        "年代": "年代",
        "投資経験": "投資経験",
        "職業": "職業",
    }

    # 全属性の成約率を横並びで表示
    all_rates = []
    for label, col in dims.items():
        for val, grp in df.groupby(col, observed=True):
            n = len(grp)
            closed = grp["is_closed"].sum()
            rate = closed / n * 100 if n > 0 else 0
            rev = grp.loc[grp["is_closed"] == 1, "売り上げ"].mean() if closed > 0 else 0
            all_rates.append({
                "属性カテゴリ": label,
                "属性値": str(val),
                "リード数": n,
                "成約数": closed,
                "成約率": rate,
                "平均売上": rev,
            })
    rates_df = pd.DataFrame(all_rates)

    # バブルチャート: 成約率 × リード数 × 平均売上
    fig_bubble = px.scatter(
        rates_df[rates_df["成約数"] > 0],
        x="リード数", y="成約率",
        size="平均売上", color="属性カテゴリ",
        hover_name="属性値",
        hover_data={"リード数": True, "成約率": ":.1f", "平均売上": ":,.0f", "成約数": True},
        color_discrete_sequence=PALETTE,
        size_max=50,
    )
    fig_bubble.update_layout(
        height=500,
        margin=dict(l=40, r=40, t=20, b=40),
        font=dict(family="Noto Sans JP"),
        xaxis_title="リード数（母数の大きさ）",
        yaxis_title="成約率 (%)",
        legend_title="属性カテゴリ",
    )
    st.plotly_chart(fig_bubble, use_container_width=True)
    st.caption("バブルの大きさは平均売上を表します。右上に位置し、バブルが大きいほど有望なセグメントです。")

    # 属性別成約率 ランキング
    st.markdown('<div class="section-title">セグメント別 成約率ランキング</div>', unsafe_allow_html=True)
    rank_df = rates_df.sort_values("成約率", ascending=False).head(20)
    rank_display = rank_df[["属性カテゴリ", "属性値", "リード数", "成約数", "成約率", "平均売上"]].copy()
    rank_display["成約率"] = rank_display["成約率"].apply(lambda x: f"{x:.1f}%")
    rank_display["平均売上"] = rank_display["平均売上"].apply(lambda x: format_yen(x) if x > 0 else "—")
    rank_display = rank_display.reset_index(drop=True)
    rank_display.index += 1
    st.dataframe(rank_display, use_container_width=True)

    # シミュレーター
    st.markdown('<div class="section-title">プロファイル シミュレーター</div>', unsafe_allow_html=True)
    st.markdown("属性を選択すると、そのプロファイルに一致するリードの実績を表示します。")

    col1, col2 = st.columns(2)
    with col1:
        sim_source = st.multiselect("リードソース", df["リードソース"].dropna().unique().tolist(),
                                     default=["Yahoo", "Google"])
        sim_asset = st.multiselect("純金融資産", ["2000万円未満", "5000万円未満", "1億円未満", "5億円未満", "5億円以上"],
                                    default=["5億円未満", "5億円以上"])
    with col2:
        sim_age = st.multiselect("年代", ["20代", "30代", "40代", "50代", "60代", "70～74歳", "75歳以上"],
                                  default=["50代", "60代"])
        sim_exp = st.multiselect("投資経験", ["なし", "1年未満", "3年未満", "3年以上"],
                                  default=["3年以上"])

    # フィルタ適用
    sim_df = df.copy()
    if sim_source:
        sim_df = sim_df[sim_df["リードソース"].isin(sim_source)]
    if sim_asset:
        sim_df = sim_df[sim_df["純金融資産"].isin(sim_asset)]
    if sim_age:
        sim_df = sim_df[sim_df["年代"].isin(sim_age)]
    if sim_exp:
        sim_df = sim_df[sim_df["投資経験"].isin(sim_exp)]

    sim_result = calc_funnel(sim_df)

    st.markdown("### シミュレーション結果")
    cols = st.columns(4)
    sim_cards = [
        ("該当リード数", f"{sim_result['リード数']:,}件", sample_warning(sim_result['リード数'])),
        ("面談率", f"{sim_result['面談率']:.1f}%", f"面談 {sim_result['面談数']}件"),
        ("成約率", f"{sim_result['成約率']:.1f}%", f"成約 {sim_result['成約数']}件"),
        ("売上合計", format_yen(sim_result['売上合計']),
         f"平均 {format_yen(sim_result['平均売上'])}/件" if sim_result['平均売上'] > 0 else ""),
    ]
    for col, (label, value, sub) in zip(cols, sim_cards):
        col.markdown(metric_card(label, value, sub), unsafe_allow_html=True)

    # 全体との比較
    overall = calc_funnel(df)
    if sim_result["リード数"] > 0:
        st.markdown("")
        comp_data = {
            "指標": ["面談率", "成約率", "平均売上"],
            "選択プロファイル": [
                f"{sim_result['面談率']:.1f}%",
                f"{sim_result['成約率']:.1f}%",
                format_yen(sim_result['平均売上']) if sim_result['平均売上'] > 0 else "—",
            ],
            "全体平均": [
                f"{overall['面談率']:.1f}%",
                f"{overall['成約率']:.1f}%",
                format_yen(overall['平均売上']),
            ],
            "差分": [
                f"{sim_result['面談率'] - overall['面談率']:+.1f}pp",
                f"{sim_result['成約率'] - overall['成約率']:+.1f}pp",
                f"{format_yen(sim_result['平均売上'] - overall['平均売上'])}" if sim_result['平均売上'] > 0 else "—",
            ],
        }
        st.dataframe(pd.DataFrame(comp_data).set_index("指標"), use_container_width=True)
