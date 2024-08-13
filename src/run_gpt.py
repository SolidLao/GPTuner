# 导入 GPT 类
from knowledge_handler.gpt import GPT 
import os

# def test_gpt():
    # # 创建 GPT 实例
    # gpt_instance = GPT(api_base="https://one.aios123.com/v1", api_key="sk-Xmt8rI8NLSc9MUrm17C59c605b994f50Ab26Eb1d4f609423")

    # # 测试获取答案的功能
    # prompt = "What is the capital of France?"
    # try:
    #     response = gpt_instance.get_answer(prompt)
    #     print("Test Get Answer: Success")
    #     print("Response:", response)
    # except Exception as e:
    #     print("Test Get Answer: Failed", e)

    # # 测试令牌计算功能
    # in_text = "gykjhfdhsh hfbhfv hjrqjhreh jjjj ss csa asd as z cs x"
    # out_text = "halll dsldk"
    # try:
    #     tokens = gpt_instance.calc_token(in_text, out_text)
    #     print("Test Calc Token: Success")
    #     print("Tokens:", tokens)
    # except Exception as e:
    #     print("Test Calc Token: Failed", e)

    # # 测试费用计算功能
    # try:
    #     cost = gpt_instance.calc_money(in_text, out_text)
    #     print("Test Calc Money: Success")
    #     print("Cost:", cost)
    # except Exception as e:
    #     print("Test Calc Money: Failed", e)

    # # 测试移除 HTML 标签功能
    # html_text = "<div>Hello, <strong>world!</strong></div>"
    # try:
    #     clean_text = gpt_instance.remove_html_tags(html_text)
    #     print("Test Remove HTML Tags: Success")
    #     print("Clean Text:", clean_text)
    # except Exception as e:
    #     print("Test Remove HTML Tags: Failed", e)

    # # 测试提取 JSON 功能
    # json_text = """
    # Here is a JSON object:
    # {
    # "firstName": "John",
    # "lastName": "Doe",
    # "age": 21
    # }
    # """

    # try:
    #     json_obj = gpt_instance.extract_json_from_text(json_text)
    #     print("Test Extract JSON: Success")
    #     print("JSON Object:", json_obj)
    # except Exception as e:
    #     print("Test Extract JSON: Failed", e)

# 运行测试
if __name__ == "__main__":
    # test_gpt()


# 调用示例
    gpt_instance = GPT(api_base="https://one.aios123.com/v1", api_key="sk-Xmt8rI8NLSc9MUrm17C59c605b994f50Ab26Eb1d4f609423")

    prompt = f"""My name is Bob, return my name in json format.
    ans format:
    {{
        "name": 

    }}

    """

    ans = gpt_instance.get_GPT_response_json(prompt, json_format=True)

    print(ans, type(ans))
    # {'name': 'Bob'} <class 'dict'>
