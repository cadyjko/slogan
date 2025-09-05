import pandas as pd
import streamlit as st
import json
import time
from datetime import datetime
from collections import Counter

# 页面设置
st.set_page_config(
    page_title="文旅口号手机评选",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 初始化session state
if 'judge_data' not in st.session_state:
    st.session_state.judge_data = {}
if 'current_judge' not in st.session_state:
    st.session_state.current_judge = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'slogan_df' not in st.session_state:
    st.session_state.slogan_df = None

# 手机友好的CSS样式
st.markdown("""
<style>
    .main > div {
        padding: 1rem;
    }
    .stButton > button {
        width: 100%;
        height: 3rem;
        font-size: 1.1rem;
    }
    .slogan-card {
        padding: 1rem;
        margin: 0.5rem 0;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        background: white;
    }
    .slogan-card.selected {
        border-color: #ff4b4b;
        background-color: #fff5f5;
    }
    .progress-bar {
        background: #f0f2f6;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .progress-fill {
        background: #ff4b4b;
        height: 10px;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    .result-table {
        font-size: 0.9rem;
    }
    .top-slogan {
        background-color: #fff5f5 !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def judge_login():
    """评委登录界面"""
    st.markdown("<h1 style='text-align: center;'>🏆 文旅宣传口号评选</h1>", unsafe_allow_html=True)

    with st.form("login_form"):
        judge_name = st.text_input("👤 请输入您的姓名", placeholder="例如：张三")
        judge_id = st.text_input("🔢 评委编号（可选）", placeholder="例如：001")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.form_submit_button("开始评选", use_container_width=True):
                if judge_name.strip():
                    identifier = f"{judge_name}_{judge_id}" if judge_id else judge_name
                    st.session_state.current_judge = identifier
                    st.session_state.current_page = 1
                    if identifier not in st.session_state.judge_data:
                        st.session_state.judge_data[identifier] = {}
                    st.rerun()
                else:
                    st.error("请输入姓名")


def display_voting_page(df):
    """显示投票页面"""
    total_pages = (len(df) + 39) // 40
    current_page = st.session_state.current_page

    # 顶部导航
    st.markdown(f"### 👤 评委: {st.session_state.current_judge.split('_')[0]}")

    # 进度条
    progress = current_page / total_pages
    st.markdown(f"""
    <div class="progress-bar">
        <div class="progress-fill" style="width: {progress * 100}%;"></div>
    </div>
    <div style="text-align: center; margin: 0.5rem 0;">
        第 <strong>{current_page}</strong> / {total_pages} 页 • 已完成 {int(progress * 100)}%
    </div>
    """, unsafe_allow_html=True)

    # 导航按钮
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("◀", disabled=current_page <= 1, help="上一页"):
            st.session_state.current_page -= 1
            st.rerun()
    with col5:
        if st.button("▶", disabled=current_page >= total_pages, help="下一页"):
            st.session_state.current_page += 1
            st.rerun()

    # 显示当前页口号
    display_slogans(df, current_page)

    # 底部操作按钮
    if st.button("💾 保存进度", type="primary", use_container_width=True):
        st.success("进度已保存！")

    if st.button("🚪 退出登录", type="secondary", use_container_width=True):
        st.session_state.current_judge = None
        st.rerun()


def display_slogans(df, page_num):
    """显示当前页的口号"""
    start_idx = (page_num - 1) * 40
    end_idx = min(page_num * 40, len(df))

    st.markdown(f"**📄 本页序号: {start_idx + 1} - {end_idx}**")
    st.markdown("✅ 请选择3个最佳口号（点击选择/取消）")

    # 获取当前选择
    judge_key = st.session_state.current_judge
    page_key = f"page_{page_num}"
    if page_key not in st.session_state.judge_data[judge_key]:
        st.session_state.judge_data[judge_key][page_key] = []

    current_selections = st.session_state.judge_data[judge_key][page_key]

    # 显示口号
    for i in range(start_idx, end_idx):
        idx = i + 1
        slogan = df.iloc[i]['口号']

        # 创建卡片
        is_selected = idx in current_selections
        card_class = "slogan-card selected" if is_selected else "slogan-card"

        col1, col2 = st.columns([1, 10])
        with col1:
            # 选择框
            selected = st.checkbox(
                "",
                value=is_selected,
                key=f"select_{idx}_{page_num}",
                label_visibility="collapsed"
            )
        with col2:
            st.markdown(f"""
            <div class="{card_class}">
                <b>#{idx}</b> - {slogan}
            </div>
            """, unsafe_allow_html=True)

        # 更新选择
        if selected != is_selected:
            if selected:
                if len(current_selections) < 3:
                    current_selections.append(idx)
                else:
                    st.warning("每页最多选择3个口号")
                    time.sleep(0.5)
                    st.rerun()
            else:
                current_selections.remove(idx)
            st.rerun()

    # 显示当前选择状态
    if current_selections:
        st.info(f"已选择: {', '.join(map(str, sorted(current_selections)))}")
    else:
        st.warning("尚未选择任何口号")


def calculate_vote_results(df, top_n=300):
    """计算投票结果并排序"""
    # 收集所有投票
    all_votes = []
    for judge, pages in st.session_state.judge_data.items():
        for page, selections in pages.items():
            all_votes.extend(selections)

    # 统计每个序号的得票数
    vote_counter = Counter(all_votes)

    # 创建结果DataFrame
    results = []
    for slogan_idx, votes in vote_counter.most_common():
        if 1 <= slogan_idx <= len(df):
            slogan_text = df.iloc[slogan_idx - 1]['口号']
            results.append({
                '排名': len(results) + 1,
                '口号序号': slogan_idx,
                '口号内容': slogan_text,
                '得票数': votes,
                '得票率': f"{(votes / len(st.session_state.judge_data) * 100):.1f}%"
            })

    # 转换为DataFrame
    results_df = pd.DataFrame(results)

    # 只保留前top_n个
    if len(results_df) > top_n:
        results_df = results_df.head(top_n)

    return results_df


def display_final_results(results_df, top_n):
    """显示最终排名结果"""
    st.subheader(f"🏅 前{top_n}个入选口号排名")

    # 显示统计信息
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总口号数", len(st.session_state.slogan_df))
    with col2:
        st.metric("评委人数", len(st.session_state.judge_data))
    with col3:
        st.metric("入选口号数", len(results_df))
    with col4:
        st.metric("最高得票", results_df['得票数'].max())

    # 显示结果表格
    st.dataframe(
        results_df,
        use_container_width=True,
        height=600,
        column_config={
            "排名": st.column_config.NumberColumn(width="small"),
            "口号序号": st.column_config.NumberColumn(width="small"),
            "口号内容": st.column_config.TextColumn(width="large"),
            "得票数": st.column_config.NumberColumn(width="small"),
            "得票率": st.column_config.TextColumn(width="small")
        }
    )

    # 可视化图表
    tab1, tab2 = st.tabs(["得票分布", "前20名口号"])

    with tab1:
        if not results_df.empty:
            fig = px.histogram(results_df, x='得票数',
                               title='口号得票分布图',
                               nbins=20)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if len(results_df) >= 20:
            top20 = results_df.head(20)
            fig = px.bar(top20, x='得票数', y='口号内容',
                         orientation='h',
                         title='得票数前20名口号',
                         text='得票数')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)


def main():
    st.sidebar.title("管理面板")

    # 文件上传
    uploaded_file = st.sidebar.file_uploader("上传口号Excel文件", type=['xlsx', 'xls'])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            if '口号' not in df.columns:
                st.error("文件必须包含'口号'列")
                return

            st.session_state.slogan_df = df
            st.sidebar.success(f"已加载 {len(df)} 条口号")

            # 显示投票界面或登录界面
            if st.session_state.current_judge:
                display_voting_page(df)
            else:
                judge_login()

            st.sidebar.markdown("---")
            st.sidebar.subheader("结果统计")

            # 设置入选数量
            top_n = st.sidebar.slider("入选口号数量", 100, 500, 300, 50)

            if st.sidebar.button("📊 统计最终结果", type="primary"):
                if st.session_state.judge_data:
                    results_df = calculate_vote_results(df, top_n)
                    display_final_results(results_df, top_n)

                    # 提供下载
                    csv = results_df.to_csv(index=False, encoding='utf-8-sig')
                    st.sidebar.download_button(
                        label="📥 下载排名结果",
                        data=csv,
                        file_name=f"口号排名结果_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.sidebar.warning("暂无评选数据")

            # 导出原始数据
            if st.sidebar.button("📋 导出原始投票数据"):
                export_raw_data()

            # 数据管理
            if st.sidebar.button("🔄 重置所有数据", type="secondary"):
                st.session_state.judge_data = {}
                st.session_state.current_judge = None
                st.sidebar.success("数据已重置")

        except Exception as e:
            st.error(f"文件读取错误: {e}")
    else:
        st.info("👈 请在左侧上传Excel文件开始评选")
        st.markdown("""
        ## 📊 统计功能说明：

        ### 最终排名计算：
        1. 系统会统计每个口号的得票数
        2. 按得票数从高到低排序
        3. 显示前200-300个入选口号
        4. 包含得票数和得票率

        ### 输出内容：
        - ✅ 完整排名（从第1名到第300名）
        - ✅ 每个口号的得票数
        - ✅ 得票率（得票数/评委数）
        - ✅ 可视化图表展示

        ## 💡 使用流程：
        1. 上传Excel文件
        2. 评委完成评选
        3. 点击"统计最终结果"
        4. 查看排名并下载结果
        """)


def export_raw_data():
    """导出原始投票数据"""
    if st.session_state.judge_data and st.session_state.slogan_df:
        raw_data = []
        for judge, pages in st.session_state.judge_data.items():
            for page, selections in pages.items():
                page_num = int(page.split('_')[1])
                for selection in selections:
                    if 1 <= selection <= len(st.session_state.slogan_df):
                        slogan_text = st.session_state.slogan_df.iloc[selection - 1]['口号']
                        raw_data.append({
                            '评委': judge,
                            '页码': page_num,
                            '选择序号': selection,
                            '口号内容': slogan_text,
                            '时间戳': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })

        if raw_data:
            df_raw = pd.DataFrame(raw_data)
            csv = df_raw.to_csv(index=False, encoding='utf-8-sig')

            st.sidebar.download_button(
                label="📥 下载原始数据",
                data=csv,
                file_name=f"原始投票数据_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.sidebar.warning("暂无投票数据")


if __name__ == "__main__":
    main()