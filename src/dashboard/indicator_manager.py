"""
指标管理页面
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any

def show_indicator_manager():
    """显示指标管理界面"""
    
    st.markdown("### 🛠️ 指标管理")
    
    # 导入必要的模块
    try:
        from src.data_fetcher.data_manager import data_manager
        from src.utils.config import config_manager
        from src.data_fetcher.akshare_fetcher import AKSHARE_INDICATORS
        from src.data_fetcher.openbb_fetcher import OPENBB_INDICATORS
    except ImportError as e:
        st.error(f"导入模块失败: {e}")
        return
    
    # 标签页
    tab1, tab2, tab3 = st.tabs(["📋 已配置指标", "➕ 添加指标", "🔍 预定义指标"])
    
    with tab1:
        show_configured_indicators()
    
    with tab2:
        show_add_indicator_form()
    
    with tab3:
        show_predefined_indicators()

def show_configured_indicators():
    """显示已配置的指标"""
    try:
        from src.utils.config import config_manager
        from src.database.db_manager import db_manager
        
        indicators = config_manager.get_indicators()
        
        if not indicators:
            st.info("暂无已配置的指标")
            return
        
        # 创建指标表格
        indicator_data = []
        for key, config in indicators.items():
            # 获取数据库信息
            table_name = config.get('table_name', key)
            table_info = db_manager.get_table_info(table_name)
            
            indicator_data.append({
                "指标键": key,
                "指标名称": config.get('name', ''),
                "数据源": config.get('source', ''),
                "状态": "✅ 启用" if config.get('enabled', True) else "❌ 禁用",
                "更新频率": config.get('update_frequency', ''),
                "数据行数": table_info.get('row_count', 0),
                "最新日期": table_info.get('max_date', '无数据')
            })
        
        df = pd.DataFrame(indicator_data)
        st.dataframe(df, use_container_width=True)
        
        # 指标操作
        st.markdown("#### 指标操作")
        selected_indicator = st.selectbox(
            "选择要操作的指标",
            list(indicators.keys()),
            format_func=lambda x: f"{x} - {indicators[x].get('name', '')}"
        )
        
        if selected_indicator:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 更新数据"):
                    with st.spinner("正在更新..."):
                        data = data_manager.fetch_indicator_data(selected_indicator, force_update=True)
                        if data is not None:
                            st.success("更新成功!")
                        else:
                            st.error("更新失败!")
            
            with col2:
                current_status = indicators[selected_indicator].get('enabled', True)
                new_status = not current_status
                action = "禁用" if current_status else "启用"
                
                if st.button(f"{'❌' if current_status else '✅'} {action}"):
                    # 这里需要实现启用/禁用功能
                    st.info(f"指标已{action}")
            
            with col3:
                if st.button("🗑️ 删除指标", type="secondary"):
                    # 这里需要实现删除功能
                    st.warning("删除功能待实现")
                    
    except Exception as e:
        st.error(f"加载指标配置失败: {e}")

def show_add_indicator_form():
    """显示添加指标表单"""
    st.markdown("#### ➕ 添加新指标")
    
    with st.form("add_indicator_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            indicator_key = st.text_input(
                "指标键 *",
                help="唯一标识符，建议使用英文和下划线"
            )
            
            indicator_name = st.text_input(
                "指标名称 *",
                help="指标的中文名称"
            )
            
            data_source = st.selectbox(
                "数据源 *",
                ["akshare", "openbb"]
            )
            
            function_name = st.text_input(
                "函数名 *",
                help="API函数名称，如: macro_china_cpi"
            )
        
        with col2:
            description = st.text_area(
                "描述",
                help="指标的详细描述"
            )
            
            update_frequency = st.selectbox(
                "更新频率",
                ["daily", "weekly", "monthly"]
            )
            
            table_name = st.text_input(
                "数据表名",
                value=indicator_key,
                help="数据库表名，默认使用指标键"
            )
        
        # 参数配置
        st.markdown("##### 函数参数")
        params_text = st.text_area(
            "参数 (JSON格式)",
            value="{}",
            help="函数调用参数，JSON格式，如: {\"symbol\": \"000001\"}"
        )
        
        submitted = st.form_submit_button("✅ 添加指标", type="primary")
        
        if submitted:
            # 验证输入
            if not indicator_key or not indicator_name or not function_name:
                st.error("请填写所有必需字段 (*)")
                return
            
            try:
                import json
                params = json.loads(params_text) if params_text.strip() else {}
                
                indicator_config = {
                    "name": indicator_name,
                    "description": description,
                    "source": data_source,
                    "function": function_name,
                    "params": params,
                    "update_frequency": update_frequency,
                    "table_name": table_name or indicator_key,
                    "enabled": True
                }
                
                # 添加指标
                from src.data_fetcher.data_manager import data_manager
                success = data_manager.add_indicator(indicator_key, indicator_config)
                
                if success:
                    st.success(f"✅ 指标 '{indicator_name}' 添加成功!")
                    st.rerun()
                else:
                    st.error("❌ 添加指标失败")
                    
            except json.JSONDecodeError:
                st.error("参数格式错误，请使用正确的JSON格式")
            except Exception as e:
                st.error(f"添加指标失败: {e}")

def show_predefined_indicators():
    """显示预定义指标"""
    st.markdown("#### 🔍 预定义指标模板")
    
    try:
        from src.data_fetcher.akshare_fetcher import AKSHARE_INDICATORS
        from src.data_fetcher.openbb_fetcher import OPENBB_INDICATORS
        
        # AkShare 指标
        st.markdown("##### 📈 AkShare 指标")
        
        akshare_data = []
        for key, config in AKSHARE_INDICATORS.items():
            akshare_data.append({
                "指标键": key,
                "指标名称": config.get('name', ''),
                "描述": config.get('description', ''),
                "函数": config.get('function', '')
            })
        
        if akshare_data:
            akshare_df = pd.DataFrame(akshare_data)
            st.dataframe(akshare_df, use_container_width=True)
            
            # 快速添加按钮
            selected_ak = st.selectbox(
                "选择 AkShare 指标",
                list(AKSHARE_INDICATORS.keys()),
                format_func=lambda x: f"{x} - {AKSHARE_INDICATORS[x].get('name', '')}"
            )
            
            if st.button("➕ 添加 AkShare 指标"):
                config = AKSHARE_INDICATORS[selected_ak].copy()
                config.update({
                    "source": "akshare",
                    "table_name": f"akshare_{selected_ak}",
                    "update_frequency": "daily",
                    "enabled": True
                })
                
                from src.data_fetcher.data_manager import data_manager
                success = data_manager.add_indicator(f"akshare_{selected_ak}", config)
                
                if success:
                    st.success(f"✅ 已添加 AkShare 指标: {config['name']}")
                    st.rerun()
                else:
                    st.error("❌ 添加失败")
        
        st.markdown("---")
        
        # OpenBB 指标
        st.markdown("##### 🌍 OpenBB 指标")
        
        openbb_data = []
        for key, config in OPENBB_INDICATORS.items():
            openbb_data.append({
                "指标键": key,
                "指标名称": config.get('name', ''),
                "描述": config.get('description', ''),
                "函数": config.get('function', '')
            })
        
        if openbb_data:
            openbb_df = pd.DataFrame(openbb_data)
            st.dataframe(openbb_df, use_container_width=True)
            
            # 快速添加按钮
            selected_obb = st.selectbox(
                "选择 OpenBB 指标",
                list(OPENBB_INDICATORS.keys()),
                format_func=lambda x: f"{x} - {OPENBB_INDICATORS[x].get('name', '')}"
            )
            
            if st.button("➕ 添加 OpenBB 指标"):
                config = OPENBB_INDICATORS[selected_obb].copy()
                config.update({
                    "source": "openbb",
                    "table_name": f"openbb_{selected_obb}",
                    "update_frequency": "daily", 
                    "enabled": True
                })
                
                from src.data_fetcher.data_manager import data_manager
                success = data_manager.add_indicator(f"openbb_{selected_obb}", config)
                
                if success:
                    st.success(f"✅ 已添加 OpenBB 指标: {config['name']}")
                    st.rerun()
                else:
                    st.error("❌ 添加失败")
                    
    except Exception as e:
        st.error(f"加载预定义指标失败: {e}")
