from configparser import ConfigParser
import argparse
import time
import os
import openai
import concurrent.futures
from knowledge_handler.knowledge_update import KGUpdate
from dbms.postgres import PgDBMS
from dbms.mysql import  MysqlDBMS
from config_recommender.coarse_stage import CoarseStage
from config_recommender.fine_stage import FineStage
from knowledge_handler.knowledge_preparation import KGPre
from knowledge_handler.knowledge_transformation import KGTrans
from space_optimizer.knob_selection import KnobSelection

def process_knob(knob, knowledge_pre, knowledge_trans, knowledge_update):
    try:
        knowledge_pre.pipeline(knob)
        knowledge_trans.pipeline(knob)
        new_structure = knowledge_update.pipeline(knob)
        if new_structure is False:
            return f"Skipped processing for {knob}"
        return f"Processed {knob}"
    except openai.RateLimitError as e:
        wait_time = float(e.response.headers.get('Retry-After', 0.5))
        print(f"Rate limit hit. Waiting for {wait_time} seconds before retrying...")
        time.sleep(wait_time)
        return process_knob(knob, knowledge_pre, knowledge_trans, knowledge_update)  # Retry recursively after waiting

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=str)
    parser.add_argument("test", type=str)
    parser.add_argument("timeout", type=int)
    parser.add_argument("-seed", type=int, default=1)
    args = parser.parse_args()
    print(f'Input arguments: {args}')
    time.sleep(2)
    config = ConfigParser()


    if args.db == 'postgres':
        config_path = "./configs/postgres.ini"
        config.read(config_path)
        dbms = PgDBMS.from_file(config)
    elif args.db == 'mysql':
        config_path = "./configs/mysql.ini"
        config.read(config_path)
        dbms = MysqlDBMS.from_file(config)
    else:
        raise ValueError("Illegal dbms!")


    # Select target knobs, write your api_base and api_key
    dbms._connect("benchbase")
    knob_selection = KnobSelection(db=args.db, dbms=dbms, benchmark=args.test, api_base="your_api_base", api_key="your_api_key", model="gpt-4o")
    knob_selection.select_interdependent_all_knobs()


    # prepare tuning lake and structured knowledge
    target_knobs_path = f"/home/knob/revision/GPTuner/knowledge_collection/{args.db}/target_knobs.txt"
    with open(target_knobs_path, 'r') as file:
        lines = file.readlines()
        target_knobs = [line.strip() for line in lines]


    # write your api_base and api_key
    knowledge_pre = KGPre(db=args.db, api_base="your_api_base", api_key="your_api_key", model="gpt-4o")
    knowledge_trans = KGTrans(db=args.db, api_base="your_api_base", api_key="your_api_key", model="gpt-4o")
    knowledge_update = KGUpdate(db=args.db, api_base="your_api_base", api_key="your_api_key", model="gpt-4o")
    for i in range(1, 6):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_knob, knob, knowledge_pre, knowledge_trans, knowledge_update): knob for knob in target_knobs}
            for future in concurrent.futures.as_completed(futures):
                print(future.result())
        print(f"Update {i} completed")


    if args.db == 'postgres':
        config_path = "./configs/postgres.ini"
        config.read(config_path)
        dbms = PgDBMS.from_file(config)
    elif args.db == 'mysql':
        config_path = "./configs/mysql.ini"
        config.read(config_path)
        dbms = MysqlDBMS.from_file(config)
    else:
        raise ValueError("Illegal dbms!")
    
    # store the optimization results
    folder_path = "../optimization_results/"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)  

    gptuner_coarse = CoarseStage(
        dbms=dbms, 
        target_knobs_path=target_knobs_path, 
        test=args.test, 
        timeout=args.timeout, 
        seed=args.seed,
    )

    gptuner_coarse.optimize(
        name = f"../optimization_results/{args.db}/coarse/", 
        trials_number=30, 
        initial_config_number=10)
    time.sleep(20)

    
    gptuner_fine = FineStage(
        dbms=dbms, 
        target_knobs_path=target_knobs_path, 
        test=args.test, 
        timeout=args.timeout, 
        seed=args.seed
    )

    gptuner_fine.optimize(
        name = f"../optimization_results/{args.db}/fine/",
        trials_number=110 # history trials + new tirals
    )   

