mytools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock information for a given stock symbol. Only Stock symbol supported is IBM",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol for which to get the information. Example: IBM",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_good_feedback",
            "description": "Get good and high quality feedback examples that have been used in the past",
            "parameters": {
                "type": "object",
                "properties": {
                    "howMany": {
                        "type": "number",
                        "description": "how many good feedback items to return. Maximum is 5",
                    },
                },
                "required": ["howMany"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bad_feedback",
            "description": "Get bad and low quality feedback examples that have been used in the past",
            "parameters": {
                "type": "object",
                "properties": {
                    "howMany": {
                        "type": "number",
                        "description": "how many bad feedback items to return. Maximum is 5",
                    },
                },
                "required": ["howMany"],
            },
        },
    },
]
