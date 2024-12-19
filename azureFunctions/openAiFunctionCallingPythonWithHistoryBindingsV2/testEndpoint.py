from flask import Flask, jsonify
import re
import json

app = Flask(__name__)


@app.route("/api/data", methods=["GET"])
def get_data():
    try:
        with open("sampledata.txt", "r") as file:
            # Read the content of the file
            content = file.read()

            # Fix invalid JSON format
            # 1. Replace single quotes with double quotes
            fixed_content = re.sub(r"'", '"', content)

            # 2. Handle multi-line strings (ensure JSON format stays valid)
            fixed_content = re.sub(r"\n", "", fixed_content)

            # Parse the cleaned-up content as JSON
            data = json.loads(fixed_content)

    except (FileNotFoundError, json.JSONDecodeError) as e:
        return jsonify({"error": f"Unable to load data: {str(e)}"}), 500

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
