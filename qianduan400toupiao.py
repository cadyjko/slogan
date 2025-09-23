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
import threading
import time

# 页面设置
st.set_page_config(
    page_title="口号评选系统",
    page_icon="🏆",
    layout="wide"
)

# 文件锁用于线程安全
file_lock = threading.Lock()

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
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False


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
    """加载所有投票数据 - 线程安全版本"""
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with file_lock:
                if os.path.exists("all_votes.json"):
                    with open("all_votes.json", "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content:
                            return {}
                        data = json.loads(content)
                        converted_data = {}
                        for voter, votes in data.items():
                            converted_data[voter] = [int(vote) if isinstance(vote, (int, str)) and str(vote).isdigit() else vote 
                                                   for vote in votes]
                        return converted_data
                return {}
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                st.error(f"JSON解析失败: {e}")
                return {}
            time.sleep(retry_delay)
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"加载投票数据失败: {e}")
                return {}
            time.sleep(retry_delay)


def save_all_votes_data():
    """保存所有投票数据到文件 - 线程安全版本"""
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with file_lock:
                # 先加载现有数据，避免覆盖
                existing_data = load_all_votes_data()
                
                # 合并数据（以当前session state为主）
                merged_data = {**existing_data, **st.session_state.all_votes_data}
                
                # 确保目录存在
                os.makedirs(os.path.dirname("all_votes.json") or ".", exist_ok=True)
                
                with open("all_votes.json", "w", encoding="utf-8") as f:
                    json.dump(merged_data, f, ensure_ascii=False, indent=2)
                
                # 更新session state为合并后的数据
                st.session_state.all_votes_data = merged_data
                update_votes_dataframe()
                return True
                
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"保存投票数据时出错: {e}")
                return False
            time.sleep(retry_delay)


def update_votes_dataframe():
    """更新投票DataFrame"""
    try:
        votes_data = []
        for voter, votes in st.session_state.all_votes_data.items():
            # 为每个投票人生成投票时间
            vote_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for slogan_id in votes:
                votes_data.append({
                    "投票人": voter,
                    "口号序号": int(slogan_id),
                    "投票时间": vote_time
                })

        if votes_data:
            st.session_state.votes_df = pd.DataFrame(votes_data)
        else:
            st.session_state.votes_df = pd.DataFrame(columns=["投票人", "口号序号", "投票时间"])
    except Exception as e:
        st.error(f"更新投票数据框时出错: {e}")


def initialize_data():
    """初始化数据加载"""
    if not st.session_state.data_loaded:
        # 加载投票数据
        votes_data = load_all_votes_data()
        if votes_data is not None:
            st.session_state.all_votes_data = votes_data
        else:
            st.session_state.all_votes_data = {}
        
        # 加载口号数据
        if st.session_state.slogan_df is None:
            st.session_state.slogan_df = load_slogan_data_from_github()
        
        # 更新DataFrame
        update_votes_dataframe()
        
        st.session_state.data_loaded = True


def main():
    st.title("🏆 宣传口号评选系统")

    # 初始化数据
    initialize_data()

    # 检查用户是否已投票
    if st.session_state.voter_id and st.session_state.voted:
        st.success("您已完成投票，感谢参与！")
        
        # 显示用户投票结果
        if st.session_state.slogan_df is not None:
            current_selection = st.session_state.all_votes_data.get(st.session_state.voter_id, [])
            selected_slogans = st.session_state.slogan_df[st.session_state.slogan_df['序号'].isin(current_selection)]
            
            st.subheader("您的投票结果")
            for _, row in selected_slogans.iterrows():
                st.write(f"**{row['序号']}.** {row['口号']}")
        
        if st.button("重新投票"):
            st.session_state.voted = False
            st.session_state.voter_id = ""
            st.rerun()
        return

    # 用户标识输入
    if not st.session_state.voter_id:
        st.subheader("请输入您的姓名")
        voter_id = st.text_input("姓名", placeholder="请输入您的姓名", key="voter_input")
        
        if st.button("开始投票", key="start_vote"):
            if voter_id.strip():
                # 检查是否已投过票
                if voter_id.strip() in st.session_state.all_votes_data:
                    st.warning("该姓名已投过票，请使用其他姓名或联系管理员")
                    return
                
                st.session_state.voter_id = voter_id.strip()
                st.rerun()
            else:
                st.error("请输入有效的姓名")
        return

    # 显示投票界面
    display_voting_interface()


def display_voting_interface():
    """显示投票界面"""
    if st.session_state.slogan_df is None:
        st.error("数据加载失败，请刷新页面重试")
        return

    df = st.session_state.slogan_df

    st.header(f"欢迎 {st.session_state.voter_id}，请选出最符合南岳衡山全球旅游品牌宣传的口号")
    
    # 获取当前用户的选择
    current_selection = set(st.session_state.all_votes_data.get(st.session_state.voter_id, []))
    current_count = len(current_selection)
    max_votes = st.session_state.max_votes
    
    # 显示选择状态
    if current_count <= max_votes:
        st.info(f"您最多可以选择 {max_votes} 条口号，当前已选择 **{current_count}** 条")
    else:
        st.error(f"❌ 您已选择 {current_count} 条口号，超过限制 {max_votes} 条！请取消部分选择")
    
    # 显示选择进度条
    progress = min(current_count / max_votes, 1.0)
    st.progress(progress, text=f"{current_count}/{max_votes}")

    # 搜索筛选
    search_term = st.text_input("搜索口号", placeholder="输入关键词筛选口号", key="search_slogan")

    # 分页显示
    page_size = 50
    total_pages = (len(df) + page_size - 1) // page_size

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    # 显示已选口号详情
    if current_count > 0:
        selected_slogans = df[df['序号'].isin(current_selection)]
        with st.expander(f"📋 查看已选口号 ({current_count}条)", expanded=False):
            st.write("**您已选择的口号：**")
            for _, row in selected_slogans.iterrows():
                st.write(f"✅ {row['序号']}. {row['口号']}")
            
            if st.button("🗑️ 清空所有选择", key="clear_all"):
                st.session_state.all_votes_data[st.session_state.voter_id] = []
                update_votes_dataframe()
                save_all_votes_data()
                st.rerun()

    # 分页控件
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ 上一页", key="prev_page") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        st.write(f"**第 {st.session_state.current_page} 页，共 {total_pages} 页**")
    with col3:
        if st.button("下一页 ➡️", key="next_page") and st.session_state.current_page < total_pages:
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

        unique_key = f"checkbox_{st.session_state.voter_id}_page{st.session_state.current_page}_slogan{slogan_id}"
        
        # 检查是否已达到最大选择限制
        is_disabled = current_count >= max_votes and slogan_id not in current_selection
        
        # 显示选择框
        if is_disabled:
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                is_selected = st.checkbox(
                    "",
                    value=slogan_id in current_selection,
                    key=unique_key,
                    disabled=True
                )
            with col2:
                st.write(f"**{slogan_id}.** {slogan_text} 🔒")
                st.caption("已达到最大选择数量")
        else:
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
            if slogan_id not in current_selection_set:
                current_selection_set.add(slogan_id)
        
        # 处理取消选择
        for _, row in current_page_df.iterrows():
            slogan_id = row['序号']
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

    # 自动保存机制（每10次操作自动保存一次）
    if 'save_counter' not in st.session_state:
        st.session_state.save_counter = 0
    
    st.session_state.save_counter += 1
    if st.session_state.save_counter % 10 == 0:
        save_all_votes_data()

    # 提交投票按钮
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        current_selection = st.session_state.all_votes_data.get(st.session_state.voter_id, [])
        current_count = len(current_selection)
        
        submit_disabled = current_count == 0 or current_count > max_votes
        
        if submit_disabled:
            if current_count == 0:
                st.error("请至少选择一条口号")
            else:
                st.error(f"选择数量超过限制，请调整到{max_votes}条以内")
        
        if st.button("✅ 提交投票", 
                    type="primary", 
                    use_container_width=True,
                    disabled=submit_disabled,
                    key="submit_vote"):
            
            # 最终检查
            if len(current_selection) > max_votes:
                st.error(f"选择数量超过限制，请调整到{max_votes}条以内")
            elif len(current_selection) == 0:
                st.error("请至少选择一条口号")
            else:
                # 保存投票数据
                success = save_all_votes_data()
                if success:
                    st.session_state.voted = True
                    st.success(f"投票成功！您选择了 {len(current_selection)} 条口号。感谢您的参与。")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("投票保存失败，请重试或联系管理员")


def admin_interface():
    """管理员界面"""
    st.title("🏆 口号评选系统 - 管理员界面")

    # 密码保护
    password = st.text_input("请输入管理员密码", type="password", key="admin_password")
    if password != "admin123":
        if password:
            st.error("密码错误")
        return

    st.success("管理员登录成功！")
    
    # 初始化数据
    initialize_data()
    
    # 刷新数据按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 刷新数据", type="primary", key="refresh_data"):
            # 使用线程安全的方式加载数据
            votes_data = load_all_votes_data()
            if votes_data is not None:
                st.session_state.all_votes_data = votes_data
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
    
    votes_df = st.session_state.votes_df

    # 统计信息
    st.header("📊 投票统计")
    if not votes_df.empty:
        total_voters = votes_df["投票人"].nunique()
        total_votes = len(votes_df)
        avg_votes = total_votes / total_voters if total_voters > 0 else 0
        
        # 统计有效投票（不超过20票）
        valid_voters = 0
        for voter in votes_df["投票人"].unique():
            voter_votes = len(votes_df[votes_df["投票人"] == voter])
            if voter_votes <= 20:
                valid_voters += 1
    else:
        total_voters = 0
        total_votes = 0
        avg_votes = 0
        valid_voters = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总参与人数", total_voters)
    col2.metric("总投票数", total_votes)
    col3.metric("人均投票数", f"{avg_votes:.1f}")
    col4.metric("有效投票人数", valid_voters)

    # 显示参与投票人员列表
    if total_voters > 0:
        with st.expander(f"👥 查看参与投票人员 ({total_voters}人)", expanded=False):
            voters = sorted(votes_df["投票人"].unique())
            for i, voter in enumerate(voters, 1):
                voter_votes = len(votes_df[votes_df["投票人"] == voter])
                status = "✅" if voter_votes <= 20 else "⚠️"
                st.write(f"{i}. {voter} - 投票数: {voter_votes} {status}")

    # 投票结果
    st.header("🏅 投票结果")
    
    if votes_df.empty:
        st.info("暂无投票数据")
        return

    # 只统计有效投票（不超过20票的投票人）
    valid_votes_df = pd.DataFrame()
    for voter in votes_df["投票人"].unique():
        voter_votes = votes_df[votes_df["投票人"] == voter]
        if len(voter_votes) <= 20:
            valid_votes_df = pd.concat([valid_votes_df, voter_votes])

    if not valid_votes_df.empty:
        vote_counts = valid_votes_df["口号序号"].value_counts().reset_index()
    else:
        vote_counts = votes_df["口号序号"].value_counts().reset_index()
    
    vote_counts.columns = ["口号序号", "得票数"]

    result_df = pd.merge(vote_counts, df, left_on="口号序号", right_on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

    # 显示结果表格
    st.dataframe(result_df[["排名", "序号", "口号", "得票数"]], use_container_width=True)

    # 下载按钮
    csv = result_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 下载完整结果",
        data=csv,
        file_name=f"口号评选结果_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="download_results"
    )

    # 可视化
    st.header("📈 数据可视化")
    if len(result_df) > 0:
        top_n = st.slider("显示前多少名", 10, min(100, len(result_df)), 20, key="top_n_slider")

        fig = px.bar(
            result_df.head(top_n),
            x="得票数",
            y="口号",
            orientation='h',
            title=f"前{top_n}名口号得票情况"
        )
        fig.update_layout(height=600, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

    # 显示原始投票记录
    with st.expander("📋 查看原始投票记录", expanded=False):
        st.dataframe(votes_df if not votes_df.empty else "暂无数据", use_container_width=True)

    # 管理员功能
    with st.expander("⚙️ 管理员高级功能", expanded=False):
        st.warning("危险操作区域")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 重新加载数据", key="reload_data"):
                st.session_state.all_votes_data = load_all_votes_data()
                update_votes_dataframe()
                st.success("数据重新加载成功")
                st.rerun()
                
        with col2:
            if st.button("🗑️ 清空所有投票数据", key="clear_all_data"):
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
