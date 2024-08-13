import argparse
from knowledge_handler.knowledge_preparation import KGPre
from knowledge_handler.knowledge_transformation import KGTrans
# from knowledge_handler.knowledge_update import KGUpdate

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=str)
    parser.add_argument("test", type=str)
    args = parser.parse_args()
    print(f'Input arguments: {args}')

    # Initialize knowledge handlers with placeholders for API base and API key
    knowledge_pre = KGPre(db=args.db, api_base="https://one.aios123.com/v1", api_key="sk-Xmt8rI8NLSc9MUrm17C59c605b994f50Ab26Eb1d4f609423")
    knowledge_trans = KGTrans(db=args.db, api_base="https://one.aios123.com/v1", api_key="sk-Xmt8rI8NLSc9MUrm17C59c605b994f50Ab26Eb1d4f609423")
    # knowledge_update = KGUpdate(db=args.db, api_base="https://one.aios123.com/v1", api_key="sk-Xmt8rI8NLSc9MUrm17C59c605b994f50Ab26Eb1d4f609423")

    # prepare tuning lake and structured knowledge
    target_knobs_path = f"/home/ych/GPTuner/knowledge_collection/{args.db}/target_knobs.txt"
    with open(target_knobs_path, 'r') as file:
        lines = file.readlines()
        target_knobs = [line.strip() for line in lines]
    
    # Mock-up list of knobs for demonstration
    target_knobs = ["shared_buffers"]

    # Execute the pipeline function for each knob
    for knob in target_knobs:
        print(f"Processing {knob} in Knowledge Preparation")
        knowledge_pre.pipeline(knob)

        print(f"Processing {knob} in Knowledge Transformation")
        knowledge_trans.pipeline(knob)

        # print(f"Processing {knob} in Knowledge Update")
        # knowledge_update.pipeline(knob)