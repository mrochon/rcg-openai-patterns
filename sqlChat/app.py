import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objs as go
from analyze import AnalyzeGPT, SQL_Query, ChatGPT_Handler
import openai
from pathlib import Path
from dotenv import load_dotenv
import os
import datetime

# Only load the settings if they are running local and not in Azure
if os.getenv("WEBSITE_SITE_NAME") is None:
    load_dotenv()


def load_setting(setting_name, session_name, default_value=""):
    """
    Function to load the setting information from session
    """
    if session_name not in st.session_state:
        if os.environ.get(setting_name) is not None:
            st.session_state[session_name] = os.environ.get(setting_name)
        else:
            st.session_state[session_name] = default_value


load_setting("AZURE_OPENAI_CHATGPT_DEPLOYMENT", "chatgpt", "gpt-35-turbo")
load_setting("AZURE_OPENAI_GPT4_DEPLOYMENT", "gpt4", "gpt-35-turbo")
load_setting(
    "AZURE_OPENAI_ENDPOINT", "endpoint", "https://resourcenamehere.openai.azure.com/"
)
load_setting("AZURE_OPENAI_API_KEY", "apikey")


if "show_settings" not in st.session_state:
    st.session_state["show_settings"] = False


def saveOpenAI():
    st.session_state.chatgpt = st.session_state.txtChatGPT
    st.session_state.gpt4 = st.session_state.txtGPT4
    st.session_state.endpoint = st.session_state.txtEndpoint
    st.session_state.apikey = st.session_state.txtAPIKey


    # We can close out the settings now
    st.session_state["show_settings"] = False


def toggleSettings():
    st.session_state["show_settings"] = not st.session_state["show_settings"]


openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"
openai.api_key = st.session_state.apikey
openai.api_base = st.session_state.endpoint
max_response_tokens = 1500
token_limit = 6000
temperature = 0.2

st.set_page_config(
    page_title="Microsoft SQL OpenAI Assistant", page_icon=":chart:", layout="wide"
)

st.markdown(
    '<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous">',
    unsafe_allow_html=True,
)

st.markdown(
    """
<nav class="navbar fixed-top navbar-expand-lg navbar-dark" style="background-color: #3498DB;">
  <p class="navbar-brand" >Microsoft SQL OpenAI Assistant</p>
</nav>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """# **Microsoft SQL OpenAI Assistant**
This is an experimental assistant that requires Azure OpenAI access. The app demonstrates the use of OpenAI to support getting insights from Microsoft SQL by just asking questions. The assistant can also generate SQL and Python code for the Questions.
"""
)

footer = """<style>
a:link , a:visited{
color: blue;
background-color: transparent;
text-decoration: underline;
}

a:hover,  a:active {
color: red;
background-color: transparent;
text-decoration: underline;
}

p {
font-size: 15px;
}

.footer {
position: fixed;
left: 0;
bottom: 0;
width: 100%;
background-color: white;
color: black;
text-align: center;
}
</style>
<div class="footer">
<p>Developed with ❤ for ❄ </p>
</div>
"""

st.markdown(footer, unsafe_allow_html=True)

col1, col2 = st.columns((3, 1))

with st.sidebar:
    options = ("SQL Assistant", "Data Analysis Assistant")
    index = st.radio(
        "Choose the app", range(len(options)), format_func=lambda x: options[x]
    )
    if index == 0:
        system_message = """
        You are an agent designed to interact with a Microsoft SQL Server with schema detail in Microsoft SQL Server.
        Given an input question, create a syntactically correct Microsoft SQL Server query to run, then look at the results of the query and return the answer.
        You can order the results by a relevant column to return the most interesting data in the database.
        Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
        You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.
        The data is for a single database called SampleDB.
        DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
        Remember to format SQL query as in ```sql\n SQL QUERY HERE ``` in your response.
        """
        few_shot_examples = ""
        extract_patterns = [("sql", r"```sql\n(.*?)```")]
        extractor = ChatGPT_Handler(extract_patterns=extract_patterns)

        faq_dict = {
            "ChatGPT": [
                "How many total deaths were there from covid?",
                "How many total deaths were there from covid for each state?",
                "what state had the highest number of covid deaths?",
            ],
            "GPT-4": [
                "How many total deaths were there from covid?",
                "How many total deaths were there from covid for each state?",
                "what state had the highest number of covid deaths?",
            ],
        }

    elif index == 1:
        system_message = """
        You are a smart AI assistant to help answer business questions based on analyzing data. 
        You can plan solving the question with one more multiple thought step. At each thought step, you can write python code to analyze data to assist you. Observe what you get at each step to plan for the next step.
        You are given following utilities to help you retrieve data and communicate your result to end user.
        1. execute_sql(sql_query: str): A Python function can query data from the Microsoft SQL given a query which you need to create. The query has to be syntactically correct for Microsoft SQL and only use tables and columns under <<data_sources>>. The execute_sql function returns a Python pandas dataframe contain the results of the query.
        2. Use plotly library for data visualization. 
        3. Use observe(label: str, data: any) utility function to observe data under the label for your evaluation. Use observe() function instead of print() as this is executed in streamlit environment. Due to system limitation, you will only see the first 10 rows of the dataset.
        4. To communicate with user, use show() function on data, text and plotly figure. show() is a utility function that can render different types of data to end user. Remember, you don't see data with show(), only user does. You see data with observe()
            - If you want to show  user a plotly visualization, then use ```show(fig)`` 
            - If you want to show user data which is a text or a pandas dataframe or a list, use ```show(data)```
            - Never use print(). User don't see anything with print()
        5. Lastly, don't forget to deal with data quality problem. You should apply data imputation technique to deal with missing data or NAN data.
        6. Always follow the flow of Thought: , Observation:, Action: and Answer: as in template below strictly. 
        """

        few_shot_examples = """
        <<Template>>
        Question: User Question
        Thought 1: Your thought here.
        Action: 
        ```python
        #Import neccessary libraries here
        import numpy as np
        #Query some data 
        sql_query = "SOME SQL QUERY"
        step1_df = execute_sql(sql_query)
        # Replace 0 with NaN. Always have this step
        step1_df['Some_Column'] = step1_df['Some_Column'].replace(0, np.nan)
        #observe query result
        observe("some_label", step1_df) #Always use observe() instead of print
        ```
        Observation: 
        step1_df is displayed here
        Thought 2: Your thought here
        Action:  
        ```python
        import plotly.express as px 
        #from step1_df, perform some data analysis action to produce step2_df
        #To see the data for yourself the only way is to use observe()
        observe("some_label", step2_df) #Always use observe() 
        #Decide to show it to user.
        fig=px.line(step2_df)
        #visualize fig object to user.  
        show(fig)
        #you can also directly display tabular or text data to end user.
        show(step2_df)
        ```
        Observation: 
        step2_df is displayed here
        Answer: Your final answer and comment for the question
        <</Template>>

        """

        extract_patterns = [
            ("Thought:", r"(Thought \d+):\s*(.*?)(?:\n|$)"),
            ("Action:", r"```python\n(.*?)```"),
            ("Answer:", r"([Aa]nswer:) (.*)"),
        ]
        extractor = ChatGPT_Handler(extract_patterns=extract_patterns)
        faq_dict = {
            "ChatGPT": [
                "Show me daily revenue trends in 1996 per region",
                "Is that true that top 20% customers generate 80% revenue from 1996 to 1998? What's their percentage of revenue contribution?",
                "Which products have most seasonality in sales quantity in 1998?",
                "Which customers are most likely to churn in 1997?",
            ],
            "GPT-4": [
                "Predict monthly revenue for next 6 months starting from May-1998. Do not use Prophet.",
                "What is the impact of discount on sales? What's optimal discount rate?",
            ],
        }

    st.button("Settings", on_click=toggleSettings)
    if st.session_state["show_settings"]:
        with st.form("AzureOpenAI"):
            st.title("Azure OpenAI Settings")
            st.text_input(
                "ChatGPT deployment name:",
                key="txtChatGPT",
                help="Enter the name of ChatGPT deployment from Azure OpenAI",
            )
            st.text_input(
                "GPT-4 deployment name",
                key="txtGPT4",
                help="Enter the GPT-4 deployment in Azure OpenAI. Defaults to above value if not specified",
            )
            st.text_input(
                "Azure OpenAI Endpoint:",
                key="txtEndpoint",
                help="Enter the Azure Open AI Endpoint",
                placeholder="https://<endpointname>.openai.azure.com/",
            )
            st.text_input(
                "Azure OpenAI Key:",
                type="password",
                key="txtAPIKey",
                help="Enter Azure OpenAI Key",
            )

            st.title("Microsoft SQL Settings")
            st.text_input(
                "Account Identifier:",
                key="txtSNOWAccount",
                help="Enter Microsoft SQL Account Identifier",
                placeholder="<orgname>-<accountname>",
            )
            st.text_input(
                "User Name:", key="txtSNOWUser", help="Enter Microsoft SQL Username"
            )
            st.text_input(
                "Password:",
                type="password",
                key="txtSNOWPasswd",
                help="Enter Microsoft SQL Password",
            )
            st.text_input("Role:", key="txtSNOWRole", help="Enter Microsoft SQL role")
            st.text_input(
                "Database:", key="txtSNOWDatabase", help="Enter Microsoft SQL Database"
            )
            st.text_input("Schema:", key="txtSNOWSchema", help="Enter Microsoft SQL Schema")
            st.text_input(
                "Warehouse:", key="txtSNOWWarehouse", help="Enter Microsoft SQL Warehouse"
            )

            st.form_submit_button("Submit", on_click=saveOpenAI)

    chat_list = []
    if st.session_state.chatgpt != "":
        chat_list.append("ChatGPT")
    if st.session_state.gpt4 != "":
        chat_list.append("GPT-4")
    gpt_engine = st.selectbox("GPT Model", chat_list)
    if gpt_engine == "ChatGPT":
        gpt_engine = st.session_state.chatgpt
        faq = faq_dict["ChatGPT"]
    else:
        gpt_engine = st.session_state.gpt4
        faq = faq_dict["GPT-4"]

    option = st.selectbox("FAQs", faq)

    show_code = st.checkbox("Show code", value=False)
    show_prompt = st.checkbox("Show prompt", value=False)
    question = st.text_area("Ask me a question", option)

    if st.button("Submit"):
        if (
            st.session_state.apikey == ""
            or st.session_state.endpoint == ""
            or st.session_state.chatgpt == ""
        ):
            st.error("You need to specify Azure Open AI Deployment Settings!")
        # elif (
        #     st.session_state.snowaccount == ""
        #     or st.session_state.snowuser == ""
        #     or st.session_state.snowpassword == ""
        #     or st.session_state.snowrole == ""
        # ):
        #     st.error("You need to specify Microsoft SQL Settings!")
        else:
            sql_query_tool = SQL_Query(
                account_identifier="st.session_state.snowaccount",
                db_user="'st.session_state.snowuser'",
                db_password="st.session_state.snowpassword",
                db_role="st.session_state.snowrole",
                db_name="st.session_state.snowdatabase",
                db_schema="st.session_state.snowschema",
                db_warehouse="st.session_state.snowwarehouse",
            )
            analyzer = AnalyzeGPT(
                content_extractor=extractor,
                sql_query_tool=sql_query_tool,
                system_message=system_message,
                few_shot_examples=few_shot_examples,
                st=st,
                gpt_deployment=gpt_engine,
                max_response_tokens=max_response_tokens,
                token_limit=token_limit,
                temperature=temperature,
                db_schema="st.session_state.snowschema",
            )
            if index == 0:
                analyzer.query_run(question, show_code, show_prompt, col1)
            elif index == 1:
                analyzer.run(question, show_code, show_prompt, col1)
            else:
                st.error("Not implemented yet!")
