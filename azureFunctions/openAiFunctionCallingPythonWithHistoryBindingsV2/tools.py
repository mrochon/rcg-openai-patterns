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
            "name": "get_good_emails",
            "description": "Get good and high quality email examples that have been used in the past",
            "parameters": {
                "type": "object",
                "properties": {
                    "howMany": {
                        "type": "number",
                        "description": "how many good emails to return",
                    },
                },
                "required": ["howMany"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bad_emails",
            "description": "Get bad and low quality email examples that have been used in the past",
            "parameters": {
                "type": "object",
                "properties": {
                    "howMany": {
                        "type": "number",
                        "description": "how many bad emails to return",
                    },
                },
                "required": ["howMany"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_segments",
            "description": "this function will return the definition of customer segments",
            "parameters": {
                "type": "object",
                "properties": {
                    "CustomerSegment": {
                        "type": "string",
                        "description": "Allowed values are: 'High Potential', 'Low Potential', 'High Risk'",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]
