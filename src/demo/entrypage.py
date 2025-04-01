import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
import os
import numpy as np
from demo.util.get_knobs import *
from configparser import ConfigParser
import argparse
import time
from io import StringIO
from streamlit_modal import Modal

import matplotlib.pyplot as plt
from dbms.postgres import PgDBMS
from dbms.mysql import  MysqlDBMS
from demo.util.coarse_stage import CoarseStage
from demo.util.fine_stage import FineStage
from knowledge_handler.utils import get_hardware_info, get_disk_type
from demo.util.knob_selection import KnobSelection
from demo.util.handle_res_page import *
from streamlit_autorefresh import st_autorefresh
from threading import Thread
from queue import Queue
from demo.util.compare_coarse import CoarseSpace_get
from demo.util.compare_fine import FineSpace_get
from demo.util.compare_space import define_search_space



def skip1():
    st.session_state.go_next = True
def next_page():
    st.session_state.next_page = True

def begin_select():
    st.session_state.begin_select=True

def regenerate_summary():
    st.session_state.regenerate_summary = True

def regenerate_structured():
    st.session_state.regenerate_structured = True

def u_gpt():
    st.session_state.u_gpt = not st.session_state.u_gpt

def u_manual():
    st.session_state.u_mamual = not st.session_state.u_manual

def u_web():
    st.session_state.u_web = not st.session_state.u_gpt

def u_add():
    st.session_state.u_add = not st.session_state.u_add

def go_filter():
    st.session_state.go_filter = True

def filter_noisy_knowledge(col, official_doc, gpt_suggestion, web_suggestion, add_suggestion, api_base, api_key, model):
    try:
        ans = gpt_filter_noisy_knowledge(official_doc, gpt_suggestion, web_suggestion, add_suggestion, api_base, api_key, model)
        st.session_state.u_gpt, st.session_state.u_add, st.session_state.u_web, st.session_state.u_manual = True, True, True, True
        print(ans)
        if  ans["gpt_suggestion"]:
            st.session_state.u_gpt = False
        if  ans["web_suggestion"]:
            st.session_state.u_web = False
        if  ans["additional_suggestion"]:
            st.session_state.u_add = False
        time.sleep(3)
    except Exception as e:
        col.markdown(f"<p style='color: red;'>Something wrong with your openai api, please check!{e}</p>", unsafe_allow_html=True)
        

def check_summary_call(col, gpt_suggestion, web_suggestion, manual_suggestion, add_suggestion, summary, api_base, api_key, model):
    suggestions_json = dict()
    suggestions_json["web_suggestion"] = web_suggestion
    suggestions_json["gpt_suggestion"] = gpt_suggestion
    suggestions_json["manual_suggestion"] = manual_suggestion
    suggestions_json["additional_suggestion"] = add_suggestion
    with st.spinner('Checking Summary...'):
        while not check_summary(summary, suggestions_json, api_base, api_key, model):
            col.write("The summary contradict the selected suggestion. Begin to revise summary...")
            summary = revise_summarize(suggestions_json, summary, api_base, api_key, model)
            st.session_state.suggestions[st.session_state.current_knob]["summary"] = summary
    st_modal = Modal(key="tan", title="Check Summary")
    with st_modal.container():
        st.write("The summary passes the contradiction check.")

def basic_info_page():
    if st.session_state.next_page:
        st.session_state.current_page = "Knob Selection"
        st.session_state.sider_select = 1
        st.session_state.next_page = False
        st.rerun()
    st.markdown("# Basic Info")
    pre_db_select = st.session_state.db_select
    st.session_state.db_select = st.selectbox('Select DBMS', ['Postgres 14.9', 'MySQL 8.0'], 
            index=['Postgres 14.9', 'MySQL 8.0'].index(st.session_state.db_select))
    print(st.session_state.db_select)


    if st.session_state.db_select == 'Postgres 14.9':
        config_path = "./configs/postgres.ini"
        config.read(config_path)
        st.session_state.system_view = get_system_view("./knowledge_collection/postgres/knob_info/system_view.json")
    elif st.session_state.db_select == 'MySQL 8.0':
        config_path = "./configs/mysql.ini"
        config.read(config_path)
        st.session_state.system_view = get_system_view("./knowledge_collection/mysql/knob_info/system_view.json")

    st.session_state.suggestions = get_suggestions(st.session_state.db_select)
    st.session_state.structured_knowledge, st.session_state.suggested_values = get_structured_knowledge(st.session_state.db_select)


    if pre_db_select != st.session_state.db_select:
        st.session_state.knobs = get_knobs(st.session_state.db_select)
        st.session_state.target_knobs = get_target_knobs(st.session_state.db_select)
        st.session_state.knob_selection = pd.DataFrame(
            {
                "Knobs": st.session_state.knobs,
                "desc": [st.session_state.system_view[i]["short_desc"][0] for i in st.session_state.knobs],
                "gpt": [True if i in st.session_state.target_knobs else False for i in st.session_state.knobs],
            },
            )
        st.session_state.knob_selection = st.session_state.knob_selection.sort_values(by=['gpt', 'Knobs'], ascending=[False, True])

    # st.session_state.db = config['DATABASE']["db"]
    # st.session_state.user = config['DATABASE']['user']
    # st.session_state.password = config['DATABASE']['password']
    # st.session_state.restart_cmd = config['DATABASE']['restart_cmd']
    st.session_state.knob_info_path = config['DATABASE']['knob_info_path']
    st.session_state.recover_script = config['DATABASE']['recover_script']

    form = st.form("form1")
    db = form.text_input('Database Name', value=st.session_state.db)
    user = form.text_input('Database User', value=st.session_state.user)
    password = form.text_input(
        'Database Password', value=st.session_state.password, type='password')
    restart_cmd = form.text_input('Database Restart Command', value=st.session_state.restart_cmd)
    st.session_state.db, st.session_state.user, st.session_state.password, st.session_state.restart_cmd = db, user, password, restart_cmd
    
    available_cpu_cores = form.text_input('Number of CPU Cores', value=st.session_state.hardware_info[0])
    total_memory = form.text_input('Total Memory', value=st.session_state.hardware_info[1])
    total_disk_space = form.text_input('Total Disk Space', value=st.session_state.hardware_info[2])
    disk_type = form.selectbox("Disk Type", ['SSD', "HDD", "Unknown"],
            index=['SSD', "HDD", "Unknown"].index(st.session_state.hardware_info[3]))
    st.session_state.hardware_info = (available_cpu_cores, total_memory, total_disk_space, disk_type)
    form.form_submit_button(label='Save and Connect', on_click=skip1)

    if st.session_state.go_next:
        try:
            "Connecting to your database..."
            os.system(restart_cmd)
            if st.session_state.db_select == 'Postgres 14.9':
                st.session_state.dbms = PgDBMS(db, user, password, restart_cmd, st.session_state.recover_script, st.session_state.knob_info_path)
            elif st.session_state.db_select == 'MySQL 8.0':
                st.session_state.dbms = MysqlDBMS(db, user, password, restart_cmd, st.session_state.recover_script, st.session_state.knob_info_path)
            if not st.session_state.dbms._connect(db):
                raise ValueError("Wrong Info, please check your Info!")
            "Connected!"
            st.button("Next Step", type="primary", on_click=next_page)
        except Exception as e:
            "Wrong Info"
            print(e)
            st.session_state.go_next = False
    
    st.write("Provide OpenAI api-key and api-base. (Optional)")
    form = st.form("col_form3")
    model = form.selectbox('Select Model', ["gpt-4-1106-preview", 'gpt-4', "gpt-3.5-turbo"])
    base = form.text_input(label='Your api-base', value=st.session_state.api_base, type='default')
    key = form.text_input(label='Your api-key', value=st.session_state.api_key, type='password')
    st.session_state.api_base, st.session_state.api_key, st.session_state.model = base, key, model
    print(base)
    form.form_submit_button("Save")


def knob_select_page():

    st.title("Dimensionality Optimization (Knob Selection)")
    
    st.session_state.workload = st.selectbox("Target Workload", ['TPC-C', "TPC-H", "Customized Workload"],
            index=['TPC-C', "TPC-H", "Customized Workload"].index(st.session_state.workload))
    st.session_state.timeout = st.number_input("Timeout for each interation (s)", value=st.session_state.timeout, placeholder="If exceed this time, return the penalty")

    if st.session_state.next_page:
        st.session_state.current_page = "Knowledge Handler and Space Optimizer"
        st.session_state.sider_select = 2
        st.session_state.next_page = False
        st.rerun()
        return

    if st.session_state.workload == "Customized Workload":
        form1 = st.form("f")

        uploaded_files = form1.file_uploader("Drag to upload files of your workload", accept_multiple_files=True)

        form1.text_area(
            "Workload characteristics",
            placeholder = "Provide the key attributes of your workload in nature language for better knob selection.", key="workload_description"
            )
        if form1.form_submit_button("Save"):
            st.session_state.workload_queries = ""
            for uploaded_file in uploaded_files:
                stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
                string_data = stringio.read()
                st.session_state.workload_queries += string_data
    else:
        st.session_state.workload_description = st.session_state.workload
        

    st.button("Begin Selection", type="primary", on_click=begin_select)

    if st.session_state.begin_select:
        knob_selection = KnobSelection(db=st.session_state.db, dbms=st.session_state.dbms, candidate_knobs=get_knobs(st.session_state.db_select), api_base=st.session_state.api_base, workload_description=st.session_state.workload_description, api_key=st.session_state.api_key, model=st.session_state.model)
        try:
            "GPT selecting...It will take a few minutes..."
            st.session_state.target_knobs = knob_selection.select_interdependent_all_knobs()
            st.session_state.knob_selection = pd.DataFrame(
                {
                    "Knobs": st.session_state.knobs,
                    "desc": [st.session_state.system_view[i]["short_desc"][0] for i in st.session_state.knobs],
                    "gpt": [True if i in st.session_state.target_knobs else False for i in st.session_state.knobs],

                }
                )
            st.session_state.knob_selection = st.session_state.knob_selection.sort_values(by=['gpt', 'Knobs'], ascending=[False, True])

            "GPT selecting process finished!"
            st.session_state.begin_select = False

        except Exception as e:
            print(e)
            st.markdown(f"<p style='color: red;'>Something wrong with your openai api, please check!</p>{e}", unsafe_allow_html=True)

        "You can add more knobs or cancle GPT's suggestion"
    edited_df = st.data_editor(
        st.session_state.knob_selection,
        hide_index=True,
        column_config={
            "desc": st.column_config.TextColumn(
                "Description",
                help="Short description of knobs",

            ),
            "gpt": st.column_config.CheckboxColumn(
                "Knob Selection",
                help="Select knobs to tune",
                default=False,
            ),
        },
        disabled=["desc"],
        height = 200,
    )


    try:
        if edited_df is not None and True in list(edited_df["gpt"]):
            if st.button("Save", key="save2"):
                st.session_state.knob_selection = edited_df
                st.session_state.selected_knobs = [i["Knobs"] for index, i in edited_df.iterrows() if i["gpt"]==True]
                st.button("Next Step", type="primary", on_click=next_page)

    except:
        pass


def knowledge_transformation():
    if st.session_state.next_page:
        st.session_state.current_page = "Result Visualization"
        st.session_state.sider_select = 3
        st.session_state.next_page = False
        st.rerun()
        return

    st.title("Knowledge Handler and Search Space Optimizer")
    
    try:
        st.selectbox(label="Selected Knobs", options=st.session_state.selected_knobs, key="current_knob")
        st.markdown("#### System View:")
        knob_view = st.session_state.system_view[st.session_state.current_knob]
        st.dataframe(knob_view, width=1200, hide_index=True, column_order=("vartype", "unit", "max_val", "min_val", "reset_val", "enumvals", "short_desc"))
    except:
        "Please Finish Knob Selection First"
        return
    col2, col3 = st.columns([10, 10])
    col2.markdown("#### Multi-Source Knowledge")
    form = col2.form("col_form")
    form.text_area("GPT's Suggestion:", st.session_state.suggestions[st.session_state.current_knob]["gpt"], key="gpt_suggestion", height=get_txt_height(st.session_state.suggestions[st.session_state.current_knob]["gpt"]))
    form.toggle("Use GPT's Suggestion", key="u_gpt", value=st.session_state.u_gpt)
    form.text_area("Manual's Suggestion:", st.session_state.suggestions[st.session_state.current_knob]["manual"], key="manual_suggestion", height=get_txt_height(st.session_state.suggestions[st.session_state.current_knob]["manual"]))
    form.toggle("Use Manual's Suggestion", key="u_manual", value=st.session_state.u_manual)
    form.text_area("Web's Suggestion:", st.session_state.suggestions[st.session_state.current_knob]["web"], key="web_suggestion", height=get_txt_height(st.session_state.suggestions[st.session_state.current_knob]["web"]))
    form.toggle("Use Web's Suggestion", key="u_web", value=st.session_state.u_web)
    form.text_area("Additional Suggestion (You can provide in natural language):", st.session_state.suggestions[st.session_state.current_knob]["add"], height=100, key="add_suggestion")
    form.toggle("Use Additional Suggestion", key="u_add", value=st.session_state.u_add)

    form.form_submit_button(label='Save')
    st.session_state.suggestions[st.session_state.current_knob]["web"] = st.session_state.web_suggestion
    st.session_state.suggestions[st.session_state.current_knob]["manual"] = st.session_state.manual_suggestion
    st.session_state.suggestions[st.session_state.current_knob]["gpt"] = st.session_state.gpt_suggestion
    st.session_state.suggestions[st.session_state.current_knob]["add"] = st.session_state.add_suggestion


    col2.button("Filter Noisy Knowledge", type="primary", help="GPTuner helps to toggle knowledge consistent with  the system view",on_click=filter_noisy_knowledge, args=(col2, knob_view, st.session_state.gpt_suggestion, st.session_state.web_suggestion, st.session_state.add_suggestion, st.session_state.api_base, st.session_state.api_key, st.session_state.model))
    
    col3.markdown("#### Summary")
    col3.text_area(label="Summarize the multi-source knowledge:", value = st.session_state.suggestions[st.session_state.current_knob]["summary"], key="summary", height=get_txt_height(st.session_state.suggestions[st.session_state.current_knob]["summary"]))

    st.session_state.suggestions[st.session_state.current_knob]["summary"] = st.session_state.summary

    col3.button("Generate Summary", type="primary", on_click=regenerate_summary)
    if st.session_state.regenerate_summary:
        try:
            with st.spinner('Generating Summary...'):
                st.session_state.suggestions[st.session_state.current_knob]["summary"] = re_summary(
                    st.session_state.gpt_suggestion, st.session_state.manual_suggestion, st.session_state.web_suggestion, st.session_state.add_suggestion, 
                    st.session_state.u_gpt, st.session_state.u_manual, st.session_state.u_web, st.session_state.u_add, model=st.session_state.model, 
                    api_key=st.session_state.api_key, api_base=st.session_state.api_base)
                st.session_state.regenerate_summary = False
                st.rerun()
        except Exception as e:
            col3.markdown(f"<p style='color: red;'>Something wrong with your openai api, please check!</p>{e}", unsafe_allow_html=True)
            print(e)


    col3.button("Check Summary", type="primary", on_click=check_summary_call, args=(col3, st.session_state.gpt_suggestion, st.session_state.web_suggestion, st.session_state.manual_suggestion, st.session_state.add_suggestion, st.session_state.suggestions[st.session_state.current_knob]["summary"], st.session_state.api_base, st.session_state.api_key, st.session_state.model))


    col3.markdown("#### Knowledge Transformation")
    col3.write("Structured Knowledge:")
    show = st.session_state.structured_knowledge[st.session_state.current_knob]
    show['suggested_values'] = ",".join(st.session_state.suggested_values[st.session_state.current_knob])
    edited_df = col3.data_editor(
            show,
            hide_index=True,
            column_order=("min_value", "max_value", "suggested_values", "special_knob", "special_value")
        )

    if edited_df['suggested_values'][0].split(",")[0] == "":
        st.session_state.suggested_values[st.session_state.current_knob] = []
    else:
        st.session_state.suggested_values[st.session_state.current_knob] = edited_df['suggested_values'][0].split(",")

    edited_df.drop('suggested_values', axis=1)
    st.session_state.structured_knowledge[st.session_state.current_knob] = edited_df
    if not edited_df.equals(show):
        if edited_df['suggested_values'][0].split(",")[0] == "":
            st.session_state.suggested_values[st.session_state.current_knob] = []
        else:
            st.session_state.suggested_values[st.session_state.current_knob] = edited_df['suggested_values'][0].split(",")

        edited_df.drop('suggested_values', axis=1)
        st.session_state.structured_knowledge[st.session_state.current_knob] = edited_df
        st.rerun()
    
    col3.button("Generate Structured Knowledge", type="primary", on_click=regenerate_structured)
    if st.session_state.regenerate_structured:
        with st.spinner('Generating Structured Knowledge...'):
            st.session_state.structured_knowledge[st.session_state.current_knob].loc[0, ["min_value", "max_value", "special_knob", "special_value"]], st.session_state.suggested_values[st.session_state.current_knob] = re_structured(st.session_state.current_knob, 
                                st.session_state.summary, model=st.session_state.model,
                                api_key=st.session_state.api_key, api_base=st.session_state.api_base,
                                hardware_info=st.session_state.hardware_info)
        st.session_state.regenerate_structured = False
        st.rerun()


    col3.markdown("#### Range Optimization")
    coarse_space = define_search_space(st.session_state.current_knob, st.session_state.structured_knowledge, st.session_state.suggested_values,st.session_state.dbms, st.session_state.system_view, 1)

    fine_space = define_search_space(st.session_state.current_knob, st.session_state.structured_knowledge, st.session_state.suggested_values,st.session_state.dbms, st.session_state.system_view, 0)

    coarse_space_ls = {"discrete values":coarse_space["choices"], "special value":coarse_space["special"]}

    coarse_space_ls = pd.DataFrame([coarse_space_ls])
    

    if st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "string":
        fine_space_ls = {"special value":str(fine_space["special"][0])}
        fine_space_ls = pd.DataFrame([fine_space_ls])
    elif st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "bool" or st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "enum":
        fine_space_ls = {"choices":fine_space["choices"][0]}
        fine_space_ls = pd.DataFrame([fine_space_ls])
    else:
        fine_space_ls = {"lower":fine_space["lower"],"upper":fine_space["upper"],"special value":str(fine_space["special"][0])}
        print(fine_space_ls)
        fine_space_ls = pd.DataFrame([fine_space_ls])


    col3.markdown("##### _Coarse Stage:_")
    col3.dataframe(
        coarse_space_ls,
        hide_index=True,
    )

    
    if st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "real" or st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "integer":
        col3.caption(":blue[Blue dots] represent search space of the **Coarse Stage**, :red[red line] represents search space of the **Fine Stage**:")

        y = [0 for i in  coarse_space["choices"]]
        plt.figure(figsize=(10, 0.3))
        plt.scatter(coarse_space["choices"], y)
        plt.plot([fine_space["lower"], fine_space["upper"]], [0, 0], color='red', label="line") 

        plt.yticks([])
        plt.tight_layout()
        col3.pyplot(plt)

    col3.markdown("##### _Fine Stage:_")
    col3.dataframe(
        fine_space_ls,
        hide_index=True,
    )
    
    if st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "real" or st.session_state.system_view[st.session_state.current_knob]["vartype"][0] == "integer":

        col3.caption(":blue[Blue line] reprents **default search space**, :red[red line] represents **Optimized Space**:")
        y = [0 for i in coarse_space["choices"]]
        plt.clf()
        plt.figure(figsize=(10, 0.3))
        plt.plot([float(knob_view["min_val"][0]), float(knob_view["max_val"][0])], [0, 0], color='blue') 
        plt.plot([fine_space["lower"], fine_space["upper"]], [0, 0], color='red') 
        plt.yticks([])
        plt.tight_layout()
        col3.pyplot(plt)
    

    st.divider()
    st.button("Next Step", type="primary", on_click=next_page)
        
        
def show_result_figure_and_knobls():
    # v1
    # Customized Workload :temporily support latency only
    if st.session_state.workload=="TPC-H" or st.session_state.workload=="Customized Workload":
        y_label = "95th %-tile Latency (s)"
        title_= "Latency"
    else:
        y_label = "Throughput (tx/s)"
        title_ = "Throughput"
    # pg or my    
    if st.session_state.db_select == 'Postgres 14.9':    
        coarse_directory_path = "/optimization_results/postgres/coarse/" 
        fine_directory_path = "/optimization_results/postgres/fine/"   
    else:
        coarse_directory_path = "/optimization_results/mysql/coarse/"
        fine_directory_path = "/optimization_results/mysql/fine/"        

    root_dir = os.path.abspath(os.path.join(os.getcwd()))
    # get seed dir
    contents1 = os.listdir(root_dir+coarse_directory_path)
    if len(contents1) > 0:
        folder_name1 = contents1[0]
    else:
        folder_name1 = "0"
    data_coarse_dir = coarse_directory_path+folder_name1+"/runhistory.json"
    
    contents2 = os.listdir(root_dir+fine_directory_path)
    if len(contents2) > 0:
        folder_name2 = contents2[0]
    else:
        folder_name2 = "0"
    
    data_fine_dir = fine_directory_path+folder_name2+"/runhistory.json"
    # The refresh time intervel need raising if the allocated source is little(like 8GB)    
    count = st_autorefresh(interval=30*1000, limit=2000, key="draw_line")
    
    gpt_cost = getPerformance(st.session_state.default, st.session_state.workload,root_dir,data_coarse_dir,data_fine_dir)
    
    if st.session_state.tune_ == 0:
        st.info('GPTuner havent started', icon="ℹ️")
    elif gpt_cost=="wait" and st.session_state.tune_==1: # smaller than 13 iterations
        st.info('GPTuner is under sampling stage', icon="ℹ️")
    elif len(gpt_cost) == 0:
        st.info('GPTuner is under tuning stage', icon="ℹ️")  # results havent been generated
    else: # draw pictures
        null_list = [None for i in range(19)]
        gpt_rounds = [i + 1 for i in range(len(gpt_cost))]
        best_value = min(gpt_cost)
        best_round = gpt_cost.index(best_value)
        st.info(f"The optimal performance achieved so far is {round(best_value,2)} s,\nwhich is found in the {best_round} iteration")
        option = {
            "title": {"text": "The Optimization Result of GPTuner on"+title_},
            "animationDuration": 10000,
            "legend": 
            {
            "data": ["Coarse Stage", "Fine Stage"],
            "left": '70%', 
            "top": '20%' 
            },
            "xAxis": {
                "type": "category",
                "data": gpt_rounds,  
                "name": "iteration" 
            },
            "tooltip": {
                "trigger": 'item',  
                "formatter": '({a})iteration:{b0}: value:{c0}'  
            },
            "yAxis": {"type": "value", "name": y_label},
            "series": [
                {"data": gpt_cost[:20], "type": "line", "color": "orange","name":"Coarse Stage"},  
                {"data": null_list+gpt_cost[20:], "type": "line", "color": "green", "name":"Fine Stage"}  
            ],
        }
        st_echarts(options=option, height="400px")
    # get knob list  
    st.subheader('You can check the configuration of each iteration below', divider='rainbow')
    if gpt_cost!="wait":   
        choice = [i + 1 for i in range(len(gpt_cost))]
        option = st.selectbox(
        "Select the iteration that captures your interest:",
        choice,
        index=0,
        placeholder="Select contact method...",
        )
        knob_list, knob_value = getKnobInfo(option,data_coarse_dir,data_fine_dir)
    else:
        choice = []
        option = st.selectbox(
        "Select the iteration that captures your interest:",
        choice,
        index=0,
        placeholder="Select contact method...",
        ) 
        knob_list = []
        knob_value = []   
    
    knob_data_ls = pd.DataFrame(
        {
            "Knob Name": list(knob_list),
            "Knob's value in this iteration": knob_value
        }
    )
    col1, col2 = st.columns(2)
    with col1:
        st.data_editor(
            knob_data_ls,
            column_config={
                "Your choice": st.column_config.CheckboxColumn(
                    "Your choice",
                    help="Select your **favorite** widgets",
                    default=False,
                ),
            },
            disabled=["widgets"],
            hide_index=True,
        )
    with col2:
        st.markdown('''
            You can export the satisfied knob configuration in SQL format below.''')
    col2_1,col2_2 = st.columns(2)
    with col2_1:
        generate = st.button("Generate SQL File")
    with col2_2:
        if generate:
            with st.spinner('Wait for it...'):
                get_sql_file(option,knob_list,knob_value)
            st.success('SQL File Done!')
    sqlfile_name = "iteration" + str(option) + "config.sql"
    if generate:
        with open(sqlfile_name, "rb") as file:
            btn = st.download_button(
                label="Download Knob Configuration SQL File",
                data=file,
                file_name=sqlfile_name,
                # mime="image/png"
            )    

def tune_part(value_queue,queue,db_select,workload,dbms,selected_knobs,structured_knowledge,suggested_values,workload_queries,timeout):
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    if db_select == 'Postgres 14.9':
        args.db = "postgres"
    if "TPC-H" in workload:
        args.test = "tpch"
    elif "TPC-C" in workload:
        args.test = "tpcc"
    elif "Customized" in workload:
        args.test = "customized"
    else:
        raise ValueError("Workload ERROR")
    args.seed = np.random.randint(100)
    args.timeout = timeout
    
    print(f'Input arguments: {args}')
    time.sleep(2)
    try:
        gptuner_coarse = CoarseStage(
            dbms=dbms, 
            target_knobs = selected_knobs,
            structured_knowledge= structured_knowledge,
            suggested_values= suggested_values,
            test=args.test, 
            timeout=args.timeout, 
            workload_queries=workload_queries,
            seed=args.seed,
        )
        default = gptuner_coarse.penalty 
        value_queue.put(default) 
        gptuner_coarse.optimize(
            name = f"../optimization_results/{args.db}/coarse/", 
            trials_number=30, 
            initial_config_number=10)
        time.sleep(20)        
        gptuner_fine = FineStage(
            dbms=dbms, 
            target_knobs = selected_knobs,
            structured_knowledge= structured_knowledge,
            suggested_values= suggested_values,
            test=args.test, 
            timeout=args.timeout, 
            workload_queries=workload_queries,
            seed=args.seed
        )
        gptuner_fine.optimize(
            name = f"../optimization_results/{args.db}/fine/",
            trials_number=110 # history trials + new tirals
        )
    except Exception as e:
        queue.put(str(e))   
        
def start_tuning():
    st.session_state.show = 1
    st.title("Result Visualization")
    # print("st.session_state.tune_=",st.session_state.tune_)
    if st.session_state.db_select == 'Postgres 14.9':
        data_coarse_dir = "/optimization_results/postgres/coarse"
        data_fine_dir = "/optimization_results/postgres/fine"
    else:
        data_coarse_dir = "/optimization_results/mysql/coarse"
        data_fine_dir = "/optimization_results/mysql/fine"
    # The run-histoty dir is cleared if user haven't tuned
    if "tune_" not in st.session_state:     
        clear_history(data_coarse_dir,data_fine_dir)
        st.session_state.tune_ = 0    
        
    # Initialize t2 if not already in session state
    error_queue = Queue()
    value_queue = Queue()
    t2 = Thread(target=tune_part,args=(value_queue,error_queue,st.session_state.db_select,st.session_state.workload,st.session_state.dbms,st.session_state.selected_knobs,st.session_state.structured_knowledge,st.session_state.suggested_values,st.session_state.workload_queries,st.session_state.timeout))
    if st.button('Result Visualization') and ("tuning_run" not in st.session_state):
        st.session_state.tune_ = 1
        print("st.session_state.tune_=",st.session_state.tune_)
        st.session_state.tuning_run = t2
        t2.start()
   
    if ("tuning_run" in st.session_state) and st.session_state.tuning_run.is_alive():
        if st.session_state.get_default == 0:
            if not value_queue.empty(): 
                st.session_state.default = value_queue.get()
                st.session_state.get_default = 1
            
        while not error_queue.empty():
            error_message = error_queue.get()
            print("Error occurred:", error_message)
            st.error('Error:please make sure that you have finished the steps before or check the console' , icon="🚨")
            
    # auto-refresh    
    show_result_figure_and_knobls()
        

config = ConfigParser()


st.set_page_config(layout="wide", page_title="GPTuner demo")
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Basic Info"
    st.session_state.sider_select = None
    st.session_state.sider_option = "Basic Info"
    st.session_state.next_page = False
    st.session_state.i=0
    st.session_state.db_select = 'Postgres 14.9'
    st.session_state.knobs = get_knobs(st.session_state.db_select)
    st.session_state.target_knobs = get_target_knobs(st.session_state.db_select)
    st.session_state.system_view = get_system_view("./knowledge_collection/postgres/knob_info/system_view.json")
    st.session_state.knob_selection = pd.DataFrame(
        {
            "Knobs": st.session_state.knobs,
            "desc": [st.session_state.system_view[i]["short_desc"][0] for i in st.session_state.knobs],
            "gpt": [True if i in st.session_state.target_knobs else False for i in st.session_state.knobs],
        }
        )
    st.session_state.knob_selection = st.session_state.knob_selection.sort_values(by=['gpt', 'Knobs'], ascending=[False, True])
    st.session_state.go_next = False
    st.session_state.begin_select = False
    st.session_state.db, st.session_state.user, st.session_state.password, st.session_state.restart_cmd, st.session_state.knob_info_path, st.session_state.dbms, st.session_state.api_base, st.session_state.api_key, st.session_state.model = None, None, None, None, None, None, None, None, None
    st.session_state.workload_queries = ""

    st.session_state.selected_knobs = []

    st.session_state.suggestions = get_suggestions(st.session_state.db_select)
    st.session_state.structured_knowledge, st.session_state.suggested_values = get_structured_knowledge(st.session_state.db_select)
    st.session_state.regenerate_summary = False
    st.session_state.regenerate_structured = False
    st.session_state.start = False
    st.session_state.workload = "TPC-H"
    st.session_state.default = None
    st.session_state.hardware_info = (*get_hardware_info(), get_disk_type())
    st.session_state.u_gpt, st.session_state.u_manual, st.session_state.u_web, st.session_state.u_add = True, True, True, False
    st.session_state.go_filter = False
    st.session_state.get_default = 0 

    config_path = "./configs/postgres.ini"
    config.read(config_path)

    st.session_state.db, st.session_state.user, st.session_state.password, st.session_state.restart_cmd = config['DATABASE']["db"], config['DATABASE']['user'], config['DATABASE']['password'], config['DATABASE']['restart_cmd']
    st.session_state.timeout = 300


st.session_state.i+=1


pages = {
    "Basic Info": basic_info_page,
    "Knob Selection": knob_select_page, 
    "Knowledge Handler and Space Optimizer": knowledge_transformation, 
    "Result Visualization": start_tuning
}


with st.sidebar:
    pre_selected = st.session_state.sider_option
    selected = option_menu("Main Menu", ["Basic Info", "Knob Selection", "Knowledge Handler and Space Optimizer", "Result Visualization"], icons=['1-square', '2-square', '3-square', '4-square'], menu_icon="cast", manual_select=st.session_state.sider_select, key="main_menu")
    st.session_state.sider_option = selected
    st.session_state.sider_select = None
    if pre_selected != selected:
        st.session_state.current_page = selected

pages[st.session_state.current_page]()