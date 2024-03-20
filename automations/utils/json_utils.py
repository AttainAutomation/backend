import re
import json

def extract_json(message):
        # Normalize newlines and remove control characters except for tab
        normalized_message = re.sub(r'[\r\n]+', ' ', message)  # Replace newlines with spaces
        sanitized_message = re.sub(r'[^\x20-\x7E\t]', '', normalized_message)  # Remove non-printable chars

        # Attempt to find JSON starting and ending points without nested checks
        start = sanitized_message.find('{')
        end = sanitized_message.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            json_str = sanitized_message[start:end+1]
            try:
                json_data = json.loads(json_str)
                return json_data
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return {}
        else:
            print("No JSON found in the message")
            return {}
        