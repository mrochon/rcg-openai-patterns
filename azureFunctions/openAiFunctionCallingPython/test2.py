import os
from openai import AzureOpenAI
import json
import random
import requests
from dotenv import load_dotenv
from tools import mytools


def get_stock_price(symbol):
    """Get the current stock information for a given stock symbol. Only Stock symbol supported is IBM"""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"
    r = requests.get(url)
    data = r.json()
    return data

print(get_stock_price("IBM"))