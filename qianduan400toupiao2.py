import pandas as pd
import streamlit as st
import plotly.express as px
import os
import json
import requests
from io import BytesIO
from datetime import datetime
import time
import copy
from supabase import create_client, Client
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 页面设置
st.set_page_config(
    page_title="口号评选系统",
    page_icon="🏆",
    layout="wide"
)

# Supabase配置
@st.cache_resource
def init_supabase():
    """初始化Supabase客户端"""
    try:
        # 从环境变量或Secrets获取配置
        supabase_url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
        supabase_key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
        
        if not supabase_url or not supabase_key:
            st.error("Supabase配置缺失，请设置SUPABASE_URL和SUPABASE_KEY")
            return None
        
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Supabase初始化失败: {e}")
        return None

# 初始化session state
def initialize_session_state():
    """初始化session state"""
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
    if 'supabase' not in st.session_state:
        st.session_state.supabase = init_supabase()
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

# 调用初始化
initialize_session_state()

def load_slogan_data_from_github():
    """从GitHub Raw URL加载口号数据"""
    try:
        github_raw_url = st.secrets.get("GITHUB_RAW_URL", "https://raw.githubusercontent.com/cadyjko/slogan/main/slogans.xlsx")
        response = requests.get(github_raw_url)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content))

        if '序号' not in df.columns or '口号' not in df.columns:
            st.error("Excel文件必须包含'序号'和'口号'列")
            return None
        
        df['序号'] = df['序号'].astype(int)
        return df
    except Exception as e:
        st.error(f"从GitHub加载数据失败: {e}")
        return None

def load_all_votes_data():
    """从Supabase加载所有投票数据"""
    try:
        supabase = st.session_state.supabase
        if not supabase:
            st.error("数据库连接失败")
            return {}
        
        # 从votes_data表加载数据
        response = supabase.table("votes_data").select("*").execute()
        
        if hasattr(response, 'error') and response.error:
            st.error(f"数据库查询错误: {response.error}")
            return {}
        
        all_data = {}
        for record in response.data:
            voter_id = record['voter_id']
            all_data[voter_id] = {
                "votes": record['votes'],
                "voted": record['voted']
            }
        
        logger.info(f"从数据库加载了 {len(all_data)} 位用户的投票数据")
        return all_data
        
    except Exception as e:
        st.error(f"加载投票数据失败: {e}")
        return {}

def save_voter_data(voter_id, votes, voted):
    """保存单个用户的投票数据到Supabase"""
    try:
        supabase = st.session_state.supabase
        if not supabase:
            return False
        
        data = {
            "voter_id": voter_id,
            "votes": votes,
            "voted": voted,
            "updated_at": datetime.now().isoformat()
        }
        
        # 检查用户是否已存在
        check_response = supabase.table("votes_data").select("voter_id").eq("voter_id", voter_id).execute()
        
        if check_response.data:  # 用户已存在，更新数据
            response = supabase.table("votes_data").update(data).eq("voter_id", voter_id).execute()
        else:  # 新用户，插入数据
            response = supabase.table("votes_data").insert(data).execute()
        
        if hasattr(response, 'error') and response.error:
            logger.error(f"保存数据失败: {response.error}")
            return False
        
        # 如果已投票，同时保存到投票记录表
        if voted and votes:
            records_data = []
            for slogan_id in votes:
                records_data.append({
                    "voter_id": voter_id,
                    "slogan_id": slogan_id
                })
            
            # 先删除该用户旧的投票记录
            supabase.table("votes_records").delete().eq("voter_id", voter_id).execute()
            
            # 插入新的投票记录
            if records_data:
                supabase.table("votes_records").insert(records_data).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"保存投票数据失败: {e}")
        return False

def save_all_votes_data():
    """保存所有投票数据到Supabase"""
    try:
        success_count = 0
        total_count = len(st.session_state.all_votes_data)
        
        for voter_id, voter_data in st.session_state.all_votes_data.items():
            votes = voter_data.get("votes", [])
            voted = voter_data.get("voted", False)
            
            if save_voter_data(voter_id, votes, voted):
                success_count += 1
        
        logger.info(f"数据保存完成: {success_count}/{total_count}")
        return success_count == total_count
        
    except Exception as e:
        st.error(f"保存数据失败: {e}")
        return False

def update_votes_dataframe():
    """从Supabase更新投票DataFrame"""
    try:
        supabase = st.session_state.supabase
        if not supabase:
            return
        
        # 从votes_records表加载已投票的记录
        response = supabase.table("votes_records").select("voter_id, slogan_id, voted_at").execute()
        
        if hasattr(response, 'error') and response.error:
            st.error(f"查询投票记录失败: {response.error}")
            return
        
        votes_data = []
        for record in response.data:
            votes_data.append({
                "投票人": record['voter_id'],
                "口号序号": record['slogan_id'],
                "投票时间": record['voted_at']
            })
        
        if votes_data:
            st.session_state.votes_df = pd.DataFrame(votes_data)
        else:
            st.session_state.votes_df = pd.DataFrame(columns=["投票人", "口号序号", "投票时间"])
            
    except Exception as e:
        st.error(f"更新投票数据框时出错: {e}")

def initialize_data():
    """初始化数据加载"""
    if not st.session_state.data_loaded or st.session_state.slogan_df is None:
        # 加载口号数据
        if st.session_state.slogan_df is None:
            st.session_state.slogan_df = load_slogan_data_from_github()
        
        # 加载投票数据
        loaded_data = load_all_votes_data()
        if loaded_data is not None:
            st.session_state.all_votes_data = loaded_data
            
            # 同步当前用户的投票状态
            if st.session_state.voter_id in st.session_state.all_votes_data:
                voter_data = st.session_state.all_votes_data[st.session_state.voter_id]
                st.session_state.voted = voter_data.get("voted", False)
            
            update_votes_dataframe()
        
        st.session_state.data_loaded = True

def check_voter_status():
    """检查当前用户的投票状态"""
    if not st.session_state.voter_id:
        return "not_started"
    
    initialize_data()
    
    voter_id = st.session_state.voter_id
    if voter_id in st.session_state.all_votes_data:
        voter_data = st.session_state.all_votes_data[voter_id]
        votes = voter_data.get("votes", [])
        voted = voter_data.get("voted", False)
        
        if voted:
            return "voted"
        elif votes and len(votes) > 0:
            return "editing"
        else:
            return "started_but_not_voted"
    
    return "not_started"

def main():
    st.title("🏆 宣传口号评选系统")

    # 显示数据库连接状态
    if not st.session_state.supabase:
        st.error("⚠️ 数据库连接失败，请检查配置")
        return

    # 初始化数据
    initialize_data()
    
    # 检查用户状态
    voter_status = check_voter_status()

    if voter_status == "voted":
        display_voting_result()
        return
    elif voter_status == "editing":
        st.warning("⚠️ 检测到您有未提交的投票记录，可以继续编辑或最终提交")
        display_voting_interface()
        return
    elif voter_status == "started_but_not_voted":
        st.info("请继续完成投票")
        display_voting_interface()
        return

    # 用户标识输入
    if not st.session_state.voter_id:
        display_voter_login()
        return

    # 显示投票界面
    display_voting_interface()
    
def display_voter_login():
    """显示用户登录界面"""
    st.subheader("请输入您的姓名")
    voter_id = st.text_input("姓名", placeholder="请输入您的姓名", key="voter_input")
    
    if st.button("开始投票", key="start_vote"):
        if voter_id and voter_id.strip():
            clean_voter_id = voter_id.strip()
            
            # 检查投票状态
            if clean_voter_id in st.session_state.all_votes_data:
                voter_data = st.session_state.all_votes_data[clean_voter_id]
                voted = voter_data.get("voted", False)
                votes_count = len(voter_data.get("votes", []))
                
                if voted:
                    st.warning(f"该姓名已完成最终投票（投了{votes_count}条口号），请使用其他姓名或联系管理员")
                    return
                else:
                    st.session_state.voter_id = clean_voter_id
                    st.session_state.voted = False
                    st.rerun()
            else:
                st.session_state.voter_id = clean_voter_id
                st.session_state.voted = False
                st.session_state.all_votes_data[clean_voter_id] = {
                    "votes": [],
                    "voted": False
                }
                st.rerun()
        else:
            st.error("请输入有效的姓名")

def display_voting_result():
    """显示投票结果"""
    st.success("🎉 您已完成投票，感谢参与！")
    
    voter_id = st.session_state.voter_id
    voter_data = st.session_state.all_votes_data.get(voter_id, {"votes": [], "voted": False})
    current_selection = voter_data.get("votes", [])
    
    if st.session_state.slogan_df is not None and current_selection:
        selected_slogans = st.session_state.slogan_df[st.session_state.slogan_df['序号'].isin(current_selection)]
        
        st.subheader("您的投票结果")
        for _, row in selected_slogans.iterrows():
            st.write(f"**{row['序号']}.** {row['口号']}")
    
    st.info("💫 您的投票已成功提交，无法再次修改。如需帮助请联系管理员。")

def display_voting_interface():
    """显示投票界面"""
    if st.session_state.slogan_df is None:
        st.error("数据加载失败，请刷新页面重试")
        return

    df = st.session_state.slogan_df
    voter_id = st.session_state.voter_id
    
    voter_data = st.session_state.all_votes_data.get(voter_id, {"votes": [], "voted": False})
    current_selection = set(voter_data.get("votes", []))
    current_count = len(current_selection)
    voted = voter_data.get("voted", False)
    max_votes = st.session_state.max_votes

    if voted:
        st.header(f"欢迎 {voter_id}，您已完成投票")
    else:
        st.header(f"欢迎 {voter_id}，请选出最符合南岳衡山全球旅游品牌宣传的口号")
    
    status_col1, status_col2 = st.columns([2, 1])
    with status_col1:
        if voted:
            st.success(f"您已完成投票，选择了 **{current_count}** 条口号")
        else:
            if current_count <= max_votes:
                st.info(f"您最多可以选择 {max_votes} 条口号，当前已选择 **{current_count}** 条")
            else:
                st.error(f"❌ 您已选择 {current_count} 条口号，超过限制 {max_votes} 条！请取消部分选择")
    
    with status_col2:
        if st.button("🔄 刷新数据状态", key="refresh_status"):
            initialize_data()
            st.rerun()

    if voted:
        display_voting_result()
        return

    progress = min(current_count / max_votes, 1.0)
    st.progress(progress, text=f"{current_count}/{max_votes}")

    search_term = st.text_input("搜索口号", placeholder="输入关键词筛选口号", key="search_slogan")

    page_size = 50
    total_pages = (len(df) + page_size - 1) // page_size

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    if current_count > 0:
        selected_slogans = df[df['序号'].isin(current_selection)]
        with st.expander(f"📋 查看已选口号 ({current_count}条)", expanded=False):
            st.write("**您已选择的口号：**")
            for _, row in selected_slogans.iterrows():
                st.write(f"✅ {row['序号']}. {row['口号']}")
            
            if st.button("🗑️ 清空所有选择", key="clear_all"):
                st.session_state.all_votes_data[voter_id]["votes"] = []
                if save_voter_data(voter_id, [], False):
                    st.success("已清空所有选择")
                    st.rerun()
                else:
                    st.error("清空失败，请重试")

    # 分页控件
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ 上一页", key="prev_page") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        st.write(f"**第 {st.session_state.current_page} 页，共 {total_pages} 页**")
        page_input = st.number_input("跳转到页面", min_value=1, max_value=total_pages, 
                                   value=st.session_state.current_page, key="page_jump")
        if page_input != st.session_state.current_page:
            st.session_state.current_page = page_input
            st.rerun()
    with col3:
        if st.button("下一页 ➡️", key="next_page") and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
            st.rerun()

    filtered_df = df
    if search_term:
        filtered_df = df[df['口号'].str.contains(search_term, case=False, na=False)]

    start_idx = (st.session_state.current_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(filtered_df))
    current_page_df = filtered_df.iloc[start_idx:end_idx]

    st.write("### 请选择您喜欢的口号（可多选）：")
    
    with st.form("voting_form"):
        new_selections = set(current_selection)
        
        for _, row in current_page_df.iterrows():
            slogan_id = row['序号']
            slogan_text = row['口号']
            
            is_disabled = (current_count >= max_votes and slogan_id not in current_selection)
            
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.write(f"**{slogan_id}.** {slogan_text}")
            with col2:
                is_selected = st.checkbox(
                    "选择",
                    value=slogan_id in current_selection,
                    key=f"cb_{slogan_id}_{st.session_state.current_page}",
                    disabled=is_disabled
                )
            
            if is_selected and slogan_id not in new_selections:
                new_selections.add(slogan_id)
            elif not is_selected and slogan_id in new_selections:
                new_selections.discard(slogan_id)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_form = st.form_submit_button("💾 保存当前选择", use_container_width=True)
        
        if submit_form:
            if len(new_selections) > max_votes:
                st.error(f"选择数量超过限制，最多只能选择 {max_votes} 条")
            else:
                st.session_state.all_votes_data[voter_id]["votes"] = list(new_selections)
                if save_voter_data(voter_id, list(new_selections), False):
                    st.success("选择已保存！")
                    st.rerun()
                else:
                    st.error("保存失败，请重试")

    st.markdown("---")
    st.write("### 完成选择后提交投票")
    
    current_selection = st.session_state.all_votes_data.get(voter_id, {"votes": []})["votes"]
    current_count = len(current_selection)
    
    if current_count > 0:
        st.info(f"您当前选择了 {current_count} 条口号")
        
        with st.expander("📋 查看最终选择", expanded=False):
            selected_slogans = df[df['序号'].isin(current_selection)]
            for _, row in selected_slogans.iterrows():
                st.write(f"✅ {row['序号']}. {row['口号']}")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
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
            
            if current_count == 0:
                st.error("请至少选择一条口号")
            elif current_count > max_votes:
                st.error(f"选择数量超过限制")
            else:
                st.session_state.all_votes_data[voter_id]["voted"] = True
                st.session_state.voted = True
                
                if save_voter_data(voter_id, current_selection, True):
                    st.success(f"🎉 投票成功！您选择了 {current_count} 条口号。感谢您的参与！")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("投票提交失败，请重试或联系管理员")

def admin_interface():
    """管理员界面"""
    st.title("🏆 口号评选系统 - 管理员界面")

    password = st.text_input("请输入管理员密码", type="password", key="admin_password")
    if password != "admin123":
        if password:
            st.error("密码错误")
        return

    st.success("管理员登录成功！")
    
    if not st.session_state.supabase:
        st.error("数据库连接失败")
        return

    initialize_data()
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 刷新数据", type="primary", key="refresh_data"):
            st.session_state.all_votes_data = load_all_votes_data()
            st.session_state.slogan_df = load_slogan_data_from_github()
            update_votes_dataframe()
            st.success("数据刷新成功！")
            st.rerun()

    if st.session_state.slogan_df is None:
        st.error("口号数据加载失败")
        return

    df = st.session_state.slogan_df

    # 统计信息
    st.header("📊 投票统计")
    
    total_voters = len([v for v in st.session_state.all_votes_data.values() if v.get("voted", False)])
    total_votes = sum(len(v.get("votes", [])) for v in st.session_state.all_votes_data.values() if v.get("voted", False))
    avg_votes = total_votes / total_voters if total_voters > 0 else 0

    total_registered = len(st.session_state.all_votes_data)
    pending_voters = len([v for v in st.session_state.all_votes_data.values() if not v.get("voted", False) and len(v.get("votes", [])) > 0])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总参与人数", total_voters)
    col2.metric("总投票数", total_votes)
    col3.metric("人均投票数", f"{avg_votes:.1f}")
    col4.metric("待提交人数", pending_voters)

    # 数据库信息
    st.subheader("🗃️ 数据库信息")
    try:
        supabase = st.session_state.supabase
        votes_count = supabase.table("votes_data").select("count", count="exact").execute()
        records_count = supabase.table("votes_records").select("count", count="exact").execute()
        
        col1, col2 = st.columns(2)
        col1.metric("用户数据记录", votes_count.count if hasattr(votes_count, 'count') else 'N/A')
        col2.metric("投票记录数", records_count.count if hasattr(records_count, 'count') else 'N/A')
    except Exception as e:
        st.error(f"获取数据库信息失败: {e}")

        # 显示所有投票人 - 添加删除功能
    if total_registered > 0:
        with st.expander(f"👥 投票人员管理 ({total_registered}人)", expanded=True):
            st.subheader("评委投票记录")
            
            # 搜索筛选
            search_voter = st.text_input("搜索评委姓名", placeholder="输入评委姓名搜索", key="search_voter")
            
            voters = sorted(st.session_state.all_votes_data.keys())
            
            if search_voter:
                voters = [v for v in voters if search_voter.lower() in v.lower()]
            
            if not voters:
                st.info("未找到匹配的评委")
            else:
                st.write(f"找到 {len(voters)} 位评委")
                
                for i, voter in enumerate(voters, 1):
                    voter_data = st.session_state.all_votes_data[voter]
                    votes = voter_data.get("votes", [])
                    voted = voter_data.get("voted", False)
                    vote_count = len(votes)
                    
                    # 状态标识
                    if voted:
                        status = "✅ 已投票"
                        status_color = "green"
                    elif vote_count > 0:
                        status = "⏸️ 未提交"
                        status_color = "orange"
                    else:
                        status = "⏸️ 未投票"
                        status_color = "gray"
                    
                    # 创建卡片式布局
                    with st.container():
                        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                        
                        with col1:
                            st.write(f"**{voter}**")
                        
                        with col2:
                            st.write(f"投票数: **{vote_count}**")
                        
                        with col3:
                            st.markdown(f"<span style='color: {status_color}'>{status}</span>", 
                                      unsafe_allow_html=True)
                        
                        with col4:
                            # 删除按钮
                            delete_key = f"delete_{voter}_{i}"
                            if st.button("🗑️", key=delete_key, help=f"删除 {voter} 的投票记录"):
                                # 确认删除
                                if st.session_state.get(f"confirm_delete_{voter}") != True:
                                    st.session_state[f"confirm_delete_{voter}"] = True
                                    st.rerun()
                                else:
                                    # 执行删除
                                    del st.session_state.all_votes_data[voter]
                                    update_votes_dataframe()
                                    if atomic_save_votes_data():
                                        st.success(f"已删除评委 {voter} 的投票记录")
                                        st.session_state[f"confirm_delete_{voter}"] = False
                                        st.rerun()
                                    else:
                                        st.error("删除失败")
                        
                        # 确认删除提示
                        if st.session_state.get(f"confirm_delete_{voter}") == True:
                            st.warning(f"确定要删除评委 **{voter}** 的投票记录吗？此操作不可恢复！")
                            col1, col2, col3 = st.columns([1, 1, 2])
                            with col1:
                                if st.button("✅ 确认删除", key=f"confirm_{voter}"):
                                    # 执行删除
                                    del st.session_state.all_votes_data[voter]
                                    update_votes_dataframe()
                                    if atomic_save_votes_data():
                                        st.success(f"已删除评委 {voter} 的投票记录")
                                        st.session_state[f"confirm_delete_{voter}"] = False
                                        st.rerun()
                                    else:
                                        st.error("删除失败")
                            with col2:
                                if st.button("❌ 取消", key=f"cancel_{voter}"):
                                    st.session_state[f"confirm_delete_{voter}"] = False
                                    st.rerun()
                        
                        # 显示投票详情（可展开）
                        with st.expander("查看投票详情", expanded=False):
                            if vote_count > 0:
                                selected_slogans = df[df['序号'].isin(votes)]
                                for _, row in selected_slogans.iterrows():
                                    st.write(f"**{row['序号']}.** {row['口号']}")
                            else:
                                st.write("暂无投票记录")
                        
                        st.markdown("---")

    # 投票结果统计
    st.header("🏅 投票结果")
    
    if total_votes == 0:
        st.info("暂无投票数据")
        return

    vote_counts = {}
    for voter_data in st.session_state.all_votes_data.values():
        if voter_data.get("voted", False):
            votes = voter_data.get("votes", [])
            for slogan_id in votes:
                try:
                    slogan_id_int = int(slogan_id)
                    vote_counts[slogan_id_int] = vote_counts.get(slogan_id_int, 0) + 1
                except (ValueError, TypeError):
                    continue

    if not vote_counts:
        st.info("暂无有效的投票数据")
        return

    vote_counts_df = pd.DataFrame(list(vote_counts.items()), columns=["口号序号", "得票数"])
    result_df = pd.merge(vote_counts_df, df, left_on="口号序号", right_on="序号", how="left")
    result_df = result_df.sort_values("得票数", ascending=False)
    result_df["排名"] = range(1, len(result_df) + 1)

    st.dataframe(result_df[["排名", "序号", "口号", "得票数"]], use_container_width=True)

    # 下载功能
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

    with st.expander("📋 查看原始投票记录", expanded=False):
        if not st.session_state.votes_df.empty:
            st.dataframe(st.session_state.votes_df, use_container_width=True)
        else:
            st.write("暂无投票记录数据")

# 运行应用
if __name__ == "__main__":
    query_params = st.query_params
    if "admin" in query_params and query_params["admin"] == "true":
        admin_interface()
    else:
        main()

