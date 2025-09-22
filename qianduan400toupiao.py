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
    st.session_state.max_votes = 20
if 'all_votes_data' not in st.session_state:
    st.session_state.all_votes_data = {}
if 'votes_df' not in st.session_state:
    st.session_state.votes_df = pd.DataFrame()


def load_slogan_data_from_github():
    """从GitHub Raw URL加载口号数据"""
    try:
        github_raw_url = "https://raw.githubusercontent.com/cadyjko/slogan/main/slogans.xlsx"
        response = requests.get(github_raw_url)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content))

        if '序号' not in df.columns or '口号' not in df.columns:
            st.error("Excel文件必须包含'序号'和'口号'列")
            return None
        return df
    except Exception as e:
        st.error(f"从GitHub加载数据失败: {e}")
        return None


def load_all_votes_data():
    """加载所有投票数据"""
    try:
        if os.path.exists("all_votes.json"):
            with open("all_votes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                converted_data = {}
                for voter, votes in data.items():
                    converted_data[voter] = [int(vote) if isinstance(vote, (int, str)) and str(vote).isdigit() else vote 
                                           for vote in votes]
                return converted_data
        return {}
    except:
        return {}


def save_all_votes_data():
    """保存所有投票数据到文件"""
    try:
        with open("all_votes.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.all_votes_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存投票数据时出错: {e}")


def update_votes_dataframe():
    """更新投票DataFrame"""
    try:
        votes_data = []
        for voter, votes in st.session_state.all_votes_data.items():
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for slogan_id in votes:
                votes_data.append({
                    "投票人": voter,
                    "口号序号": slogan_id,
                    "投票时间": current_time
                })

        if votes_data:
            st.session_state.votes_df = pd.DataFrame(votes_data)
        else:
            st.session_state.votes_df = pd.DataFrame(columns=["投票人", "口号序号", "投票时间"])
    except Exception as e:
        st.error(f"更新投票数据框时出错: {e}")


def main():
    st.title("🏆 宣传口号评选系统")

    # 初始化投票数据
    if not st.session_state.all_votes_data:
        st.session_state.all_votes_data = load_all_votes_data()
        update_votes_dataframe()

    # 检查用户是否已投票
    if st.session_state.voter_id and st.session_state.voted:
        st.success("您已完成投票，感谢参与！")
        if st.button("重新投票"):
            st.session_state.voted = False
            st.session_state.voter_id = ""
            st.rerun()
        return

    # 用户标识输入
    if not st.session_state.voter_id:
        st.subheader("请输入您的标识")
        voter_id = st.text_input("姓名", placeholder="请输入您的姓名")
        if st.button("开始投票"):
            if voter_id.strip():
                if voter_id.strip() in st.session_state.all_votes_data:
                    st.warning("该姓名已投过票，请使用其他姓名或联系管理员")
                    return
                
                st.session_state.voter_id = voter_id.strip()
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
    
    # 获取当前用户的选择
    current_selection = set(st.session_state.all_votes_data.get(st.session_state.voter_id, []))
    current_count = len(current_selection)
    max_votes = st.session_state.max_votes
    
    # 显示选择状态 - 根据是否超过限制显示不同颜色
    if current_count <= max_votes:
        st.info(f"您最多可以选择 {max_votes} 条口号，当前已选择 **{current_count}** 条")
        progress_color = "normal"
    else:
        st.error(f"❌ 您已选择 {current_count} 条口号，超过限制 {max_votes} 条！请取消部分选择")
        progress_color = "red"
    
    # 显示选择进度条
    progress = min(current_count / max_votes, 1.0)
    st.progress(progress, text=f"{current_count}/{max_votes}")

    # 搜索筛选
    search_term = st.text_input("搜索口号", placeholder="输入关键词筛选口号")

    # 分页显示
    page_size = 50
    total_pages = (len(df) + page_size - 1) // page_size

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    # 显示已选口号详情
    if current_count > 0:
        selected_slogans = df[df['序号'].isin(current_selection)]
        with st.expander(f"查看已选口号 ({current_count}条)"):
            for _, row in selected_slogans.iterrows():
                st.write(f"{row['序号']}. {row['口号']}")
            
            if st.button("清空所有选择"):
                st.session_state.all_votes_data[st.session_state.voter_id] = []
                update_votes_dataframe()
                save_all_votes_data()
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

    # 显示口号和选择框
    st.write("### 请选择您喜欢的口号（可多选）：")
    
    # 创建当前页的选择状态
    current_page_selections = []
    
    for _, row in current_page_df.iterrows():
        slogan_id = row['序号']
        slogan_text = row['口号']

        unique_key = f"{st.session_state.voter_id}_page{st.session_state.current_page}_slogan{slogan_id}"
        
        # 检查是否已达到最大选择限制
        is_disabled = current_count >= max_votes and slogan_id not in current_selection
        
        # 显示选择框，如果已满且未选中则禁用
        if is_disabled:
            # 显示禁用的选择框
            is_selected = st.checkbox(
                f"**{slogan_id}.** {slogan_text} 🔒",
                value=False,
                key=unique_key,
                disabled=True
            )
            st.caption("已达到最大选择数量，请取消其他选择后再选择此项")
        else:
            # 正常选择框
            is_selected = st.checkbox(
                f"**{slogan_id}.** {slogan_text}",
                value=slogan_id in current_selection,
                key=unique_key
            )

        if is_selected:
            current_page_selections.append(slogan_id)

    # 实时更新选择状态
    if st.session_state.voter_id:
        current_selection_set = set(st.session_state.all_votes_data.get(st.session_state.voter_id, []))
        
        # 处理当前页的选择变化
        for slogan_id in current_page_selections:
            if slogan_id not in current_selection_set and len(current_selection_set) < max_votes:
                current_selection_set.add(slogan_id)
        
        # 处理取消选择（需要检查所有当前页的口号）
        for _, row in current_page_df.iterrows():
            slogan_id = row['序号']
            unique_key = f"{st.session_state.voter_id}_page{st.session_state.current_page}_slogan{slogan_id}"
            if slogan_id in current_selection_set and slogan_id not in current_page_selections:
                current_selection_set.remove(slogan_id)
        
        # 更新全局数据（确保不超过限制）
        if len(current_selection_set) <= max_votes:
            st.session_state.all_votes_data[st.session_state.voter_id] = list(current_selection_set)
            update_votes_dataframe()
        else:
            # 如果超过限制，只保留前max_votes条
            st.session_state.all_votes_data[st.session_state.voter_id] = list(current_selection_set)[:max_votes]
            update_votes_dataframe()
            st.error(f"选择数量超过限制，已自动保留前{max_votes}条选择")
            st.rerun()

    # 提交投票按钮
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit_disabled = current_count == 0 or current_count > max_votes
        
        if submit_disabled:
            if current_count == 0:
                st.error("请至少选择一条口号")
            else:
                st.error(f"选择数量超过限制，请调整到{max_votes}条以内")
        
        if st.button("提交投票", 
                    type="primary", 
                    use_container_width=True,
                    disabled=submit_disabled):
            
            current_selection = st.session_state.all_votes_data.get(st.session_state.voter_id, [])
            
            # 最终检查
            if len(current_selection) > max_votes:
                st.error(f"选择数量超过限制，请调整到{max_votes}条以内")
            elif len(current_selection) == 0:
                st.error("请至少选择一条口号")
            else:
                st.session_state.voted = True
                save_all_votes_data()
                st.success(f"投票成功！您选择了 {len(current_selection)} 条口号。感谢您的参与。")
                st.balloons()
                
                # 显示投票结果摘要
                selected_slogans = df[df['序号'].isin(current_selection)]
                with st.expander("您的投票结果"):
                    for _, row in selected_slogans.iterrows():
                        st.write(f"{row['序号']}. {row['口号']}")
                
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

    st.success("管理员登录成功！")
    
    # 刷新数据按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 刷新数据", type="primary"):
            st.session_state.all_votes_data = load_all_votes_data()
            st.session_state.slogan_df = load_slogan_data_from_github()
            update_votes_dataframe()
            st.success("数据刷新成功！")
            st.rerun()

    # 确保数据加载
    if st.session_state.slogan_df is None:
        st.session_state.slogan_df = load_slogan_data_from_github()
        if st.session_state.slogan_df is None:
            st.error("口号数据加载失败")
            return

    df = st.session_state.slogan_df
    
    if not st.session_state.all_votes_data:
        st.session_state.all_votes_data = load_all_votes_data()
        update_votes_dataframe()

    votes_df = st.session_state.votes_df

    # 统计信息
    st.header("投票统计")
    if not votes_df.empty:
        total_voters = votes_df["投票人"].nunique()
        total_votes = len(votes_df)
        avg_votes = total_votes / total_voters if total_voters > 0 else 0
    else:
        total_voters = 0
        total_votes = 0
        avg_votes = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("总参与人数", total_voters)
    col2.metric("总投票数", total_votes)
    col3.metric("人均投票数", f"{avg_votes:.1f}")

    # 显示参与投票人员列表
    if total_voters > 0:
        with st.expander(f"查看参与投票人员 ({total_voters}人)"):
            voters = votes_df["投票人"].unique()
            for i, voter in enumerate(voters, 1):
                voter_votes = len(votes_df[votes_df["投票人"] == voter])
                status = "✅" if voter_votes <= 20 else "⚠️"
                st.write(f"{i}. {voter} - 投票数: {voter_votes} {status}")

    # 投票结果
    st.header("投票结果")
    
    if votes_df.empty:
        st.info("暂无投票数据")
        return

    vote_counts = votes_df["口号序号"].value_counts().reset_index()
    vote_counts.columns = ["口号序号", "得票数"]

    result_df = pd.merge(vote_counts, df, left_on="口号序号", right_on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

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
    if len(result_df) > 0:
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
        st.dataframe(votes_df if not votes_df.empty else "暂无数据")

    # 管理员功能
    with st.expander("管理员高级功能", expanded=False):
        st.warning("危险操作区域")
        if st.button("清空所有投票数据"):
            st.session_state.all_votes_data = {}
            st.session_state.votes_df = pd.DataFrame()
            save_all_votes_data()
            st.success("所有投票数据已清空")
            st.rerun()


# 运行应用
if __name__ == "__main__":
    query_params = st.query_params
    if "admin" in query_params and query_params["admin"] == "true":
        admin_interface()
    else:
        main()

