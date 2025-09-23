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
    """加载所有投票数据 - 修复版本"""
    try:
        if os.path.exists("all_votes.json"):
            with open("all_votes.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                
                data = json.loads(content)
                # 确保数据格式正确
                converted_data = {}
                
                if isinstance(data, dict):
                    for voter, votes in data.items():
                        if isinstance(votes, list):
                            # 确保所有投票ID都是整数
                            converted_data[str(voter)] = [int(vote) if isinstance(vote, (int, str)) and str(vote).isdigit() else vote for vote in votes]
                        else:
                            converted_data[str(voter)] = []
                else:
                    st.error("投票数据格式错误，将使用空数据")
                    return {}
                
                return converted_data
        return {}
    except json.JSONDecodeError as e:
        st.error(f"JSON解析错误: {e}")
        # 尝试恢复数据
        return try_recover_votes_data()
    except Exception as e:
        st.error(f"加载投票数据失败: {e}")
        # 创建新的空文件
        try:
            with open("all_votes.json", "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        except:
            pass
        return {}

def try_recover_votes_data():
    """尝试从备份文件恢复数据"""
    try:
        # 查找最新的备份文件
        backup_files = [f for f in os.listdir(".") if f.startswith("all_votes_backup_") and f.endswith(".json")]
        if backup_files:
            latest_backup = max(backup_files)
            with open(latest_backup, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    st.info(f"从备份文件 {latest_backup} 恢复数据")
                    return data
    except Exception as e:
        st.error(f"恢复备份数据失败: {e}")
    
    return {}

def save_all_votes_data():
    """保存所有投票数据到文件 - 修复版本"""
    try:
        # 先保存到临时文件
        temp_file = "all_votes_temp.json"
        
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(st.session_state.all_votes_data, f, ensure_ascii=False, indent=2)
        
        # 创建备份
        if os.path.exists("all_votes.json"):
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                os.rename("all_votes.json", f"all_votes_backup_{backup_time}.json")
            except Exception as e:
                st.error(f"创建备份失败: {e}")
        
        # 重命名临时文件为主文件
        os.rename(temp_file, "all_votes.json")
        
        st.session_state.last_save_time = time.time()
        return True
    except Exception as e:
        st.error(f"保存投票数据时出错: {e}")
        # 尝试恢复操作
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        return False

def atomic_save_votes_data():
    """原子操作保存投票数据，防止数据丢失"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 深度复制当前数据
            current_data = copy.deepcopy(st.session_state.all_votes_data)
            
            # 保存到临时文件
            temp_filename = f"all_votes_{int(time.time())}_{attempt}.tmp"
            with open(temp_filename, "w", encoding="utf-8") as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
            
            # 备份原文件
            if os.path.exists("all_votes.json"):
                backup_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_filename = f"all_votes_backup_{backup_time}.json"
                try:
                    import shutil
                    shutil.copy2("all_votes.json", backup_filename)
                except Exception as e:
                    st.warning(f"创建备份失败: {e}")
            
            # 替换原文件
            if os.path.exists("all_votes.json"):
                os.remove("all_votes.json")
            os.rename(temp_filename, "all_votes.json")
            
            # 清理旧的临时文件
            cleanup_old_files()
            
            st.session_state.last_save_time = time.time()
            return True
            
        except Exception as e:
            st.error(f"保存尝试 {attempt + 1} 失败: {e}")
            time.sleep(0.1)  # 短暂等待后重试
    
    return False

def cleanup_old_files():
    """清理旧的临时文件和备份文件"""
    try:
        # 清理临时文件
        for file in os.listdir("."):
            if file.startswith("all_votes_") and (file.endswith(".tmp") or "backup" in file):
                # 保留最近5个备份文件，删除旧的
                if "backup" in file:
                    file_time = os.path.getctime(file)
                    if time.time() - file_time > 86400:  # 保留1天内的备份
                        try:
                            os.remove(file)
                        except:
                            pass
                elif file.endswith(".tmp"):
                    # 删除所有临时文件
                    try:
                        os.remove(file)
                    except:
                        pass
    except Exception as e:
        # 清理失败不影响主流程
        pass

def update_votes_dataframe():
    """更新投票DataFrame"""
    try:
        votes_data = []
        for voter, votes in st.session_state.all_votes_data.items():
            if votes:  # 只处理有投票的记录
                vote_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for slogan_id in votes:
                    try:
                        votes_data.append({
                            "投票人": voter,
                            "口号序号": int(slogan_id),
                            "投票时间": vote_time
                        })
                    except (ValueError, TypeError):
                        # 跳过无效的投票ID
                        continue

        if votes_data:
            st.session_state.votes_df = pd.DataFrame(votes_data)
        else:
            st.session_state.votes_df = pd.DataFrame(columns=["投票人", "口号序号", "投票时间"])
    except Exception as e:
        st.error(f"更新投票数据框时出错: {e}")

def initialize_data():
    """初始化数据加载"""
    if not st.session_state.data_loaded:
        # 加载口号数据
        if st.session_state.slogan_df is None:
            st.session_state.slogan_df = load_slogan_data_from_github()
        
        # 加载投票数据
        if not st.session_state.all_votes_data:
            loaded_data = load_all_votes_data()
            if loaded_data is not None:
                st.session_state.all_votes_data = loaded_data
                # 清理空记录
                st.session_state.all_votes_data = {k: v for k, v in st.session_state.all_votes_data.items() if v is not None and len(v) > 0}
                update_votes_dataframe()
        
        st.session_state.data_loaded = True

def validate_votes_data():
    """验证投票数据的完整性"""
    try:
        if not st.session_state.all_votes_data:
            return True
        
        valid_count = 0
        invalid_voters = []
        
        for voter, votes in st.session_state.all_votes_data.items():
            if voter and isinstance(votes, list):
                # 验证投票ID都是有效的数字
                valid_votes = []
                for vote in votes:
                    try:
                        if vote is not None:
                            valid_votes.append(int(vote))
                    except (ValueError, TypeError):
                        continue
                
                if valid_votes:
                    st.session_state.all_votes_data[voter] = valid_votes
                    valid_count += 1
                else:
                    invalid_voters.append(voter)
            else:
                invalid_voters.append(voter)
        
        # 删除无效的投票记录
        for voter in invalid_voters:
            if voter in st.session_state.all_votes_data:
                del st.session_state.all_votes_data[voter]
        
        if invalid_voters:
            st.warning(f"清理了 {len(invalid_voters)} 条无效投票记录")
        
        return True
    except Exception as e:
        st.error(f"数据验证失败: {e}")
        return False

def main():
    st.title("🏆 宣传口号评选系统")

    # 初始化数据
    initialize_data()
    
    # 验证数据完整性
    validate_votes_data()

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
                    # 立即保存一次
                    atomic_save_votes_data()
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
                atomic_save_votes_data()
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
                
                # 原子保存
                if atomic_save_votes_data():
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
                if atomic_save_votes_data():
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
    
    # 直接从all_votes_data统计，更准确
    total_voters = len(st.session_state.all_votes_data)
    total_votes = sum(len(votes) for votes in st.session_state.all_votes_data.values() if votes)
    avg_votes = total_votes / total_voters if total_voters > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("总参与人数", total_voters)
    col2.metric("总投票数", total_votes)
    col3.metric("人均投票数", f"{avg_votes:.1f}")

    # 显示数据完整性信息
    st.info(f"数据文件记录数: {len(st.session_state.all_votes_data)}")
    
    # 显示所有投票人
    if total_voters > 0:
        with st.expander(f"👥 查看所有投票人员 ({total_voters}人)", expanded=True):
            voters = sorted(st.session_state.all_votes_data.keys())
            for i, voter in enumerate(voters, 1):
                voter_votes = len(st.session_state.all_votes_data[voter])
                status = "✅" if voter_votes <= 20 else "⚠️"
                st.write(f"{i}. {voter} - 投票数: {voter_votes} {status}")

    # 投票结果
    st.header("🏅 投票结果")
    
    if total_votes == 0:
        st.info("暂无投票数据")
        return

    # 从原始数据计算投票结果
    vote_counts = {}
    for votes in st.session_state.all_votes_data.values():
        for slogan_id in votes:
            try:
                slogan_id_int = int(slogan_id)
                vote_counts[slogan_id_int] = vote_counts.get(slogan_id_int, 0) + 1
            except (ValueError, TypeError):
                continue

    if not vote_counts:
        st.info("暂无有效的投票数据")
        return

    # 创建结果DataFrame
    vote_counts_df = pd.DataFrame(list(vote_counts.items()), columns=["口号序号", "得票数"])
    result_df = pd.merge(vote_counts_df, df, left_on="口号序号", right_on="序号", how="left")
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
        if not votes_df.empty:
            st.dataframe(votes_df, use_container_width=True)
        else:
            st.write("暂无投票记录数据")

    # 数据管理功能
    with st.expander("🔧 数据管理", expanded=False):
        st.subheader("数据备份与恢复")
        
        # 显示备份文件
        backup_files = [f for f in os.listdir(".") if f.startswith("all_votes_backup_") and f.endswith(".json")]
        if backup_files:
            st.write("可用备份文件:")
            for backup in sorted(backup_files, reverse=True)[:5]:  # 显示最近5个备份
                file_time = os.path.getctime(backup)
                st.write(f"- {backup} (创建时间: {datetime.fromtimestamp(file_time)})")
                
                if st.button(f"从{backup}恢复", key=f"restore_{backup}"):
                    try:
                        with open(backup, "r", encoding="utf-8") as f:
                            backup_data = json.load(f)
                        st.session_state.all_votes_data = backup_data
                        update_votes_dataframe()
                        atomic_save_votes_data()
                        st.success(f"已从 {backup} 恢复数据")
                        st.rerun()
                    except Exception as e:
                        st.error(f"恢复失败: {e}")
        
        # 手动备份
        if st.button("创建手动备份"):
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"all_votes_manual_backup_{backup_time}.json"
            try:
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.all_votes_data, f, ensure_ascii=False, indent=2)
                st.success(f"手动备份创建成功: {backup_file}")
            except Exception as e:
                st.error(f"备份失败: {e}")

    # 管理员功能
    with st.expander("⚙️ 管理员高级功能", expanded=False):
        st.warning("危险操作区域")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ 清空所有投票数据", key="clear_all_data"):
                st.session_state.all_votes_data = {}
                st.session_state.votes_df = pd.DataFrame()
                if atomic_save_votes_data():
                    st.success("所有投票数据已清空")
                    st.rerun()
                else:
                    st.error("清空操作失败")
        
        with col2:
            if st.button("🔍 验证数据完整性", key="validate_data"):
                if validate_votes_data():
                    st.success("数据验证完成")
                    st.rerun()
                else:
                    st.error("数据验证失败")

# 运行应用
if __name__ == "__main__":
    query_params = st.query_params
    if "admin" in query_params and query_params["admin"] == "true":
        admin_interface()
    else:
        main()
