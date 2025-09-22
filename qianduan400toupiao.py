import pandas as pd
import streamlit as st
from collections import Counter
import plotly.express as px
import os
import re
import json
import uuid
from datetime import datetime
import requests
from io import BytesIO

# 页面设置
st.set_page_config(
    page_title="口号评选系统",
    page_icon="🏆",
    layout="wide"
)

# 初始化session state
if 'votes' not in st.session_state:
    st.session_state.votes = {}
if 'slogan_df' not in st.session_state:
    st.session_state.slogan_df = None
if 'voter_id' not in st.session_state:
    st.session_state.voter_id = ""
if 'voted' not in st.session_state:
    st.session_state.voted = False
if 'max_votes' not in st.session_state:
    st.session_state.max_votes = 10
if 'current_selections' not in st.session_state:
    st.session_state.current_selections = set()
if 'votes_df' not in st.session_state:
    st.session_state.votes_df = pd.DataFrame()
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = None


def load_slogan_data_from_github():
    """从GitHub Raw URL加载口号数据"""
    try:
        # 替换为您的GitHub Raw URL
        github_raw_url = "https://raw.githubusercontent.com/cadyjko/slogan/main/slogans.xlsx"

        response = requests.get(github_raw_url)
        response.raise_for_status()

        # 从字节流读取Excel文件
        df = pd.read_excel(BytesIO(response.content))

        if '序号' not in df.columns or '口号' not in df.columns:
            st.error("Excel文件必须包含'序号'和'口号'列")
            return None

        return df
    except Exception as e:
        st.error(f"从GitHub加载数据失败: {e}")
        return None


def update_selections(selected_options):
    """更新选择状态"""
    current_selection = set(st.session_state.votes.get(st.session_state.voter_id, []))
    
    # 移除取消选择的
    for slogan_id in list(current_selection):
        if slogan_id not in selected_options:
            current_selection.remove(slogan_id)
    
    # 添加新选择的
    for slogan_id in selected_options:
        current_selection.add(slogan_id)
    
    # 保存到session state
    st.session_state.votes[st.session_state.voter_id] = list(current_selection)
    st.session_state.current_selections = current_selection


def save_votes_to_file():
    """保存投票数据到文件"""
    try:
        votes_data = []
        for voter, votes in st.session_state.votes.items():
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for slogan_id in votes:
                votes_data.append({
                    "投票人": voter,
                    "口号序号": slogan_id,
                    "投票时间": current_time
                })

        # 转换为DataFrame并存储在session state中
        votes_df = pd.DataFrame(votes_data)
        st.session_state.votes_df = votes_df
        st.session_state.last_updated = datetime.now()

        # 尝试保存到文件（在本地运行时有效）
        try:
            votes_df.to_excel("votes.xlsx", index=False)
        except:
            pass  # 在Streamlit Cloud中可能无法写入文件

    except Exception as e:
        st.error(f"保存投票数据时出错: {e}")


def main():
    st.title("🏆 宣传口号评选系统")

    # 检查用户是否已投票
    if st.session_state.voter_id and st.session_state.voted:
        st.success("您已完成投票，感谢参与！")
        if st.button("重新投票"):
            st.session_state.voted = False
            st.session_state.votes[st.session_state.voter_id] = []
            st.session_state.current_selections = set()
            st.rerun()
        return

    # 用户标识输入
    if not st.session_state.voter_id:
        st.subheader("请输入您的标识")
        voter_id = st.text_input("姓名", placeholder="请输入您的姓名")
        if st.button("开始投票"):
            if voter_id.strip():
                st.session_state.voter_id = voter_id.strip()
                # 加载数据
                if st.session_state.slogan_df is None:
                    st.session_state.slogan_df = load_slogan_data_from_github()
                st.rerun()
            else:
                st.error("请输入有效的标识")
        return

    # 显示投票界面
    display_voting_interface()


def display_voting_interface():
    """显示投票界面"""
    if st.session_state.slogan_df is None:
        st.error("数据加载失败，请刷新页面重试")
        return

    df = st.session_state.slogan_df

    st.header(f"欢迎 {st.session_state.voter_id}，请选出您喜欢的口号")
    st.info(f"您最多可以选择 {st.session_state.max_votes} 条口号")

    # 搜索筛选
    search_term = st.text_input("搜索口号", placeholder="输入关键词筛选口号")

    # 分页显示
    page_size = 50
    total_pages = (len(df) + page_size - 1) // page_size

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    # 获取当前用户的选择
    current_selection = set(st.session_state.votes.get(st.session_state.voter_id, []))
    
    # 实时显示已选中口号数量
    st.write(f"当前已选择 **{len(current_selection)}/{st.session_state.max_votes}** 条口号")
    
    # 显示选择进度条
    progress = len(current_selection) / st.session_state.max_votes
    st.progress(progress)

    # 显示已选口号详情
    if len(current_selection) > 0:
        selected_slogans = df[df['序号'].isin(current_selection)]
        with st.expander(f"查看已选口号 ({len(current_selection)}条)"):
            for _, row in selected_slogans.iterrows():
                st.write(f"{row['序号']}. {row['口号']}")
            
            # 添加清空选择按钮
            if st.button("清空所有选择"):
                st.session_state.votes[st.session_state.voter_id] = []
                st.session_state.current_selections = set()
                st.rerun()

    # 分页控件
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("上一页") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        st.write(f"第 {st.session_state.current_page} 页，共 {total_pages} 页")
    with col3:
        if st.button("下一页") and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
            st.rerun()

    # 过滤数据
    filtered_df = df
    if search_term:
        filtered_df = df[df['口号'].str.contains(search_term, case=False, na=False)]

    # 当前页数据
    start_idx = (st.session_state.current_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(filtered_df))
    current_page_df = filtered_df.iloc[start_idx:end_idx]

    # 显示口号和选择框 - 使用form来批量处理选择
    with st.form(f"vote_form_page_{st.session_state.current_page}"):
        selected_options = []
        
        for _, row in current_page_df.iterrows():
            slogan_id = row['序号']
            slogan_text = row['口号']

            # 检查是否已选择
            is_selected = st.checkbox(
                f"{slogan_id}. {slogan_text}",
                value=slogan_id in current_selection,
                key=f"checkbox_{st.session_state.current_page}_{slogan_id}"
            )

            if is_selected:
                selected_options.append(slogan_id)
        
        # 修复核心问题：在翻页前自动保存选择
        if st.form_submit_button("保存当前页选择"):
            # 更新选择状态
            update_selections(selected_options)
            st.success("选择已保存！")
            st.rerun()

    # 提交投票按钮
    if st.button("提交投票", type="primary"):
        # 最终确认选择（确保当前页的选择被保存）
        update_selections(selected_options)
        current_selection = st.session_state.votes.get(st.session_state.voter_id, [])
        
        # 检查是否超过限制
        if len(current_selection) > st.session_state.max_votes:
            st.error(f"您最多只能选择 {st.session_state.max_votes} 条口号，请取消部分选择")
        elif len(current_selection) == 0:
            st.error("请至少选择一条口号")
        else:
            st.session_state.voted = True
            save_votes_to_file()
            st.success(f"投票成功！您选择了 {len(current_selection)} 条口号。感谢您的参与。")
            st.balloons()
            st.rerun()


def admin_interface():
    """管理员界面"""
    st.title("🏆 口号评选系统 - 管理员界面")

    # 密码保护
    password = st.text_input("请输入管理员密码", type="password")
    if password != "admin123":
        if password:
            st.error("密码错误")
        return

    # 成功登录后显示界面
    st.success("管理员登录成功！")
    
    # 修复问题：添加独立的数据刷新按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 刷新数据", type="primary"):
            # 强制重新加载所有数据
            st.session_state.slogan_df = load_slogan_data_from_github()
            
            # 重新加载投票数据
            try:
                if os.path.exists("votes.xlsx"):
                    st.session_state.votes_df = pd.read_excel("votes.xlsx")
                    st.session_state.last_updated = datetime.now()
                    st.success("数据刷新成功！")
                else:
                    # 从session state重建投票数据
                    save_votes_to_file()
            except Exception as e:
                st.error(f"刷新数据时出错: {e}")
            
            st.rerun()

    # 显示最后更新时间
    if st.session_state.last_updated:
        st.write(f"最后更新时间: {st.session_state.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")

    # 确保数据加载
    if st.session_state.slogan_df is None:
        st.info("正在加载口号数据...")
        st.session_state.slogan_df = load_slogan_data_from_github()
        if st.session_state.slogan_df is None:
            st.error("口号数据加载失败，请检查网络连接或数据源")
            return

    df = st.session_state.slogan_df
    st.success(f"成功加载 {len(df)} 条口号数据")

    # 检查是否有投票数据
    if st.session_state.votes_df.empty:
        # 尝试从文件加载投票数据
        try:
            if os.path.exists("votes.xlsx"):
                st.session_state.votes_df = pd.read_excel("votes.xlsx")
                st.session_state.last_updated = datetime.now()
                st.success("从文件加载投票数据成功")
            else:
                st.info("暂无投票数据，等待用户投票...")
                # 从session state的votes重建数据
                if st.session_state.votes:
                    save_votes_to_file()
                    st.success("从内存数据重建投票记录")
                else:
                    return
        except Exception as e:
            st.info("暂无投票数据，等待用户投票...")
            return

    votes_df = st.session_state.votes_df

    # 统计信息
    st.header("投票统计")
    total_voters = votes_df["投票人"].nunique()
    total_votes = len(votes_df)
    avg_votes = total_votes / total_voters if total_voters > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("总参与人数", total_voters)
    col2.metric("总投票数", total_votes)
    col3.metric("人均投票数", f"{avg_votes:.1f}")

    # 投票结果
    st.header("投票结果")
    vote_counts = votes_df["口号序号"].value_counts().reset_index()
    vote_counts.columns = ["口号序号", "得票数"]

    # 合并口号文本
    result_df = pd.merge(vote_counts, df, left_on="口号序号", right_on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

    # 显示完整结果
    st.dataframe(result_df[["排名", "序号", "口号", "得票数"]])

    # 下载按钮
    csv = result_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="下载完整结果",
        data=csv,
        file_name=f"口号评选结果_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

    # 可视化
    st.header("数据可视化")
    top_n = st.slider("显示前多少名", 10, min(100, len(result_df)), 20)

    fig = px.bar(
        result_df.head(top_n),
        x="得票数",
        y="口号",
        orientation='h',
        title=f"前{top_n}名口号得票情况"
    )
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    # 显示原始投票记录
    with st.expander("查看原始投票记录"):
        st.dataframe(votes_df)


# 运行应用
if __name__ == "__main__":
    # URL参数判断是用户界面还是管理员界面
    query_params = st.query_params
    if "admin" in query_params and query_params["admin"] == "true":
        admin_interface()
    else:
        main()
