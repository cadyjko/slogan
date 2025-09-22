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


def main():
    st.title("🏆 宣传口号评选系统")

    # 检查用户是否已投票
    if st.session_state.voter_id and st.session_state.voted:
        st.success("您已完成投票，感谢参与！")
        if st.button("重新投票"):
            st.session_state.voted = False
            st.rerun()
        return

    # 用户标识输入
    if not st.session_state.voter_id:
        st.subheader("请输入您的姓名")
        voter_id = st.text_input("姓名", placeholder="请输入您的姓名")
        if st.button("开始投票"):
            if voter_id.strip():
                st.session_state.voter_id = voter_id.strip()
                st.rerun()
            else:
                st.error("请输入有效的评委标识")
        return

    # 加载口号数据
    if st.session_state.slogan_df is None:
        load_slogan_data()
        return

    # 显示投票界面
    display_voting_interface()


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


def display_voting_interface():
    """显示投票界面"""
    df = st.session_state.slogan_df

    st.header(f"欢迎 {st.session_state.voter_id}，请选出您喜欢的口号")
    st.info(f"您最多可以选择 {st.session_state.max_votes} 条口号")

    # 分页显示
    page_size = 50
    total_pages = (len(df) + page_size - 1) // page_size

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

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
        filtered_df = df[df['口号'].str.contains(search_term, case=False)]

    # 当前页数据
    start_idx = (st.session_state.current_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(filtered_df))
    current_page_df = filtered_df.iloc[start_idx:end_idx]

    # 显示口号和选择框
    selected_options = []
    for _, row in current_page_df.iterrows():
        slogan_id = row['序号']
    slogan_text = row['口号']

    # 检查是否已选择
    is_selected = st.checkbox(
        f"{slogan_id}. {slogan_text}",
        value=slogan_id in st.session_state.votes.get(st.session_state.voter_id, []),
        key=f"checkbox_{slogan_id}"
    )

    if is_selected:
        selected_options.append(slogan_id)

    # 显示当前选择情况
    current_selection = st.session_state.votes.get(st.session_state.voter_id, [])
    st.write(f"当前已选择 {len(current_selection)}/{st.session_state.max_votes} 条口号")

    if len(current_selection) > 0:
        selected_slogans = df[df['序号'].isin(current_selection)]
    with st.expander("查看已选口号"):
        for _, row in selected_slogans.iterrows():
             st.write(f"{row['序号']}. {row['口号']}")

    # 提交按钮
    if st.button("提交投票", type="primary"):
    # 更新选择
        current_selection = st.session_state.votes.get(st.session_state.voter_id, [])

    # 移除取消选择的
    for slogan_id in current_selection[:]:
        if slogan_id not in selected_options:
            current_selection.remove(slogan_id)

    # 添加新选择的
    for slogan_id in selected_options:
        if slogan_id not in current_selection:
         current_selection.append(slogan_id)

    # 检查是否超过限制
    if len(current_selection) > st.session_state.max_votes:
        st.error(f"您最多只能选择 {st.session_state.max_votes} 条口号")
    else:
        st.session_state.votes[st.session_state.voter_id] = current_selection
    st.session_state.voted = True
    save_votes_to_file()
    st.success("投票成功！感谢您的参与。")
    st.rerun()


def save_votes_to_file():
    """保存投票数据到文件"""
    try:
        # 读取现有数据或创建新文件
        try:
            votes_df = pd.read_excel("votes.xlsx")
        except:
            votes_df = pd.DataFrame(columns=["投票人", "口号序号", "投票时间"])

        # 添加新投票
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_votes = []
        for slogan_id in st.session_state.votes[st.session_state.voter_id]:
            new_votes.append({
                "投票人": st.session_state.voter_id,
                "口号序号": slogan_id,
                "投票时间": current_time
            })

        # 合并数据
        new_votes_df = pd.DataFrame(new_votes)
        votes_df = pd.concat([votes_df, new_votes_df], ignore_index=True)

        # 保存文件
        votes_df.to_excel("votes.xlsx", index=False)

    except Exception as e:
        st.error(f"保存投票数据时出错: {e}")


def admin_interface():
    """管理员界面"""
    st.title("🏆 口号评选系统 - 管理员界面")

    # 密码保护
    password = st.text_input("请输入管理员密码", type="password")
    if password != "admin123":  # 请在实际使用时更改密码
        st.error("密码错误")
        return

    # 加载数据
    if not os.path.exists("slogans.xlsx"):
        st.error("未找到口号数据文件")
        return

    if not os.path.exists("votes.xlsx"):
        st.error("暂无投票数据")
        return

    df = pd.read_excel("slogans.xlsx")
    votes_df = pd.read_excel("votes.xlsx")

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
    result_df = pd.merge(vote_counts, df, on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

    # 显示前50名
    st.dataframe(result_df[["排名", "序号", "口号", "得票数"]].head(50))

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
    top_n = st.slider("显示前多少名", 10, 100, 20)

    fig = px.bar(
        result_df.head(top_n),
        x="得票数",
        y="口号",
        orientation='h',
        title=f"前{top_n}名口号得票情况"
    )
    st.plotly_chart(fig)


# 运行应用
if __name__ == "__main__":
    # URL参数判断是用户界面还是管理员界面
    query_params = st.query_params
    if "admin" in query_params and query_params["admin"] == "true":
        admin_interface()
    else:

        main()



