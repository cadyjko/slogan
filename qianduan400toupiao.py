import pandas as pd
import streamlit as st
import plotly.express as px
import os
import json
import requests
from io import BytesIO
from datetime import datetime
import time

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
if 'last_save_time' not in st.session_state:
    st.session_state.last_save_time = 0
if 'selections_updated' not in st.session_state:
    st.session_state.selections_updated = False

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
                content = f.read().strip()
                if not content:
                    return {}
                data = json.loads(content)
                # 转换数据格式
                converted_data = {}
                for voter, votes in data.items():
                    if isinstance(votes, list):
                        converted_data[voter] = [int(vote) if str(vote).isdigit() else vote for vote in votes]
                    else:
                        converted_data[voter] = []
                return converted_data
        return {}
    except Exception as e:
        st.error(f"加载投票数据失败: {e}")
        # 如果文件损坏，创建一个新的空文件
        try:
            with open("all_votes.json", "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        except:
            pass
        return {}

def save_all_votes_data():
    """保存所有投票数据到文件"""
    try:
        # 创建备份
        if os.path.exists("all_votes.json"):
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                os.rename("all_votes.json", f"all_votes_backup_{backup_time}.json")
            except:
                pass
        
        # 保存新数据
        with open("all_votes.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.all_votes_data, f, ensure_ascii=False, indent=2)
        
        st.session_state.last_save_time = time.time()
        return True
    except Exception as e:
        st.error(f"保存投票数据时出错: {e}")
        return False

def update_votes_dataframe():
    """更新投票DataFrame"""
    try:
        votes_data = []
        for voter, votes in st.session_state.all_votes_data.items():
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
    if st.session_state.slogan_df is None:
        st.session_state.slogan_df = load_slogan_data_from_github()
    
    if not st.session_state.all_votes_data:
        loaded_data = load_all_votes_data()
        if loaded_data is not None:
            st.session_state.all_votes_data = loaded_data
            update_votes_dataframe()

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
            if current_selection:
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
            if voter_id and voter_id.strip():
                clean_voter_id = voter_id.strip()
                
                # 检查是否已投过票
                if clean_voter_id in st.session_state.all_votes_data:
                    st.warning("该姓名已投过票，请使用其他姓名或联系管理员")
                else:
                    st.session_state.voter_id = clean_voter_id
                    # 初始化该用户的投票数据
                    st.session_state.all_votes_data[clean_voter_id] = []
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
        st.success(f"您最多可以选择 {max_votes} 条口号，当前已选择 **{current_count}** 条")
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
                st.success("已清空所有选择")
                st.rerun()

    # 分页控件
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ 上一页", key="prev_page") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        st.write(f"**第 {st.session_state.current_page} 页，共 {total_pages} 页**")
        # 页面跳转
        page_input = st.number_input("跳转到页面", min_value=1, max_value=total_pages, 
                                   value=st.session_state.current_page, key="page_jump")
        if page_input != st.session_state.current_page:
            st.session_state.current_page = page_input
            st.rerun()
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

    st.write("### 请选择您喜欢的口号（可多选）：")
    
    # 使用form来管理选择状态
    with st.form("voting_form"):
        selections_changed = False
        new_selections = set(current_selection)
        
        # 显示当前页的口号选择框
        for _, row in current_page_df.iterrows():
            slogan_id = row['序号']
            slogan_text = row['口号']
            
            # 检查是否已达到最大选择限制
            is_disabled = current_count >= max_votes and slogan_id not in current_selection
            
            # 创建选择框
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.write(f"**{slogan_id}.** {slogan_text}")
            with col2:
                is_selected = st.checkbox(
                    "选择",
                    value=slogan_id in current_selection,
                    key=f"cb_{slogan_id}",
                    disabled=is_disabled
                )
            
            # 更新选择状态
            if is_selected and slogan_id not in new_selections:
                new_selections.add(slogan_id)
                selections_changed = True
            elif not is_selected and slogan_id in new_selections:
                new_selections.discard(slogan_id)
                selections_changed = True
        
        # 表单提交按钮
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_form = st.form_submit_button("💾 保存当前选择", use_container_width=True)
        
        if submit_form:
            # 检查选择数量
            if len(new_selections) > max_votes:
                st.error(f"选择数量超过限制，最多只能选择 {max_votes} 条")
            else:
                # 更新选择
                st.session_state.all_votes_data[st.session_state.voter_id] = list(new_selections)
                update_votes_dataframe()
                
                # 自动保存
                if save_all_votes_data():
                    st.success("选择已保存！")
                else:
                    st.error("保存失败，请重试")
                
                st.rerun()

    # 单独的提交投票按钮
    st.markdown("---")
    st.write("### 完成选择后提交投票")
    
    current_selection = st.session_state.all_votes_data.get(st.session_state.voter_id, [])
    current_count = len(current_selection)
    
    # 显示最终选择状态
    if current_count > 0:
        st.info(f"您当前选择了 {current_count} 条口号")
        
        with st.expander("📋 查看最终选择", expanded=False):
            selected_slogans = df[df['序号'].isin(current_selection)]
            for _, row in selected_slogans.iterrows():
                st.write(f"✅ {row['序号']}. {row['口号']}")
    
    # 提交投票按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # 检查提交条件
        can_submit = 1 <= current_count <= max_votes
        
        if not can_submit:
            if current_count == 0:
                st.error("❌ 请至少选择一条口号")
            else:
                st.error(f"❌ 选择数量超过限制（最多{max_votes}条）")
        
        if st.button("✅ 最终提交投票", 
                    type="primary", 
                    use_container_width=True,
                    disabled=not can_submit,
                    key="final_submit"):
            
            # 最终验证
            if current_count == 0:
                st.error("请至少选择一条口号")
            elif current_count > max_votes:
                st.error(f"选择数量超过限制")
            else:
                # 标记为已投票
                st.session_state.voted = True
                
                # 最终保存
                if save_all_votes_data():
                    st.success(f"🎉 投票成功！您选择了 {current_count} 条口号。感谢您的参与！")
                    st.balloons()
                    
                    # 显示投票结果
                    with st.expander("您的投票详情", expanded=True):
                        selected_slogans = df[df['序号'].isin(current_selection)]
                        for _, row in selected_slogans.iterrows():
                            st.write(f"**{row['序号']}.** {row['口号']}")
                    
                    # 3秒后刷新页面
                    time.sleep(3)
                    st.rerun()
                else:
                    st.error("投票提交失败，请重试或联系管理员")

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
            st.session_state.all_votes_data = load_all_votes_data()
            st.session_state.slogan_df = load_slogan_data_from_github()
            update_votes_dataframe()
            st.success("数据刷新成功！")
            st.rerun()

    # 确保数据加载
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

    vote_counts = votes_df["口号序号"].value_counts().reset_index()
    vote_counts.columns = ["口号序号", "得票数"]

    result_df = pd.merge(vote_counts, df, left_on="口号序号", right_on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

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
