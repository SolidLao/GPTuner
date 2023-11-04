from configparser import ConfigParser
from dbms.postgres import PgDBMS
from dbms.mysql import  MysqlDBMS
from config_recommender.coarse_stage import CoarseStage
from config_recommender.fine_stage import FineStage
from knowledge_handler.knowledge_preparation import KGPre
from knowledge_handler.knowledge_transformation import KGTrans
import argparse
import time

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

    # prepare tuning lake and structured knowledge
    target_knobs_path = f"./knowledge_collection/{args.db}/target_knobs.txt"
    with open(target_knobs_path, 'r') as file:
        lines = file.readlines()
        target_knobs = [line.strip() for line in lines]

    # write your api_base and api_key
    knowledge_pre = KGPre(db=args.db, api_base="your_api_base", api_key="your_api_key", model="your_model")
    knowledge_trans = KGTrans(db=args.db, api_base="your_api_base", api_key="your_api_key", model="your_model")
    for knob in target_knobs:
        knowledge_pre.pipeline(knob)
        knowledge_trans.pipeline(knob)

    if args.db == 'postgres':
        config_path = "./configs/postgres.ini"
        config.read(config_path)
        dbms = PgDBMS.from_file(config)
        target_knobs_path = target_knobs_path
    elif args.db == 'mysql':
        config_path = "./configs/mysql.ini"
        config.read(config_path)
        dbms = MysqlDBMS.from_file(config)
        target_knobs_path = target_knobs_path
    else:
        raise ValueError("No implementation for your dbms now...")
    
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