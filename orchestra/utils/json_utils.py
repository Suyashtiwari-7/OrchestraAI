import json
import logging

logger = logging.getLogger("orchestra.utils.json_utils")

def extract_json(response: str) -> dict:
    """
    Robustly extract and parse a JSON block from a string response.
    Handles markdown blocks, literal newlines, invalid escapes, etc.
    """
    try:
        # Extract balanced JSON block from the response
        json_str = None
        start = response.find('{')
        if start != -1:
            brace_count = 0
            in_string = False
            escape = False
            for i in range(start, len(response)):
                char = response[i]
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response[start:i+1]
                            break
        
        if not json_str:
            raise ValueError("No JSON found in response")

        # Robustly parse JSON (handling literal newlines and invalid escapes inside string values)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            cleaned = []
            in_string = False
            i = 0
            n = len(json_str)
            while i < n:
                char = json_str[i]
                if not in_string:
                    if char == '"':
                        in_string = True
                    cleaned.append(char)
                    i += 1
                    continue
                
                if char == '"':
                    in_string = False
                    cleaned.append(char)
                    i += 1
                    continue
                
                if char == '\\':
                    # Check for valid escape
                    if i + 1 < n:
                        next_char = json_str[i + 1]
                        if next_char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                            cleaned.append('\\')
                            cleaned.append(next_char)
                            i += 2
                            continue
                        elif next_char == 'u':
                            if i + 5 < n and all(c in '0123456789abcdefABCDEF' for c in json_str[i+2:i+6]):
                                cleaned.append('\\')
                                cleaned.append('u')
                                cleaned.extend(json_str[i+2:i+6])
                                i += 6
                                continue
                    # Not a valid escape sequence: escape the backslash itself
                    cleaned.append('\\\\')
                    i += 1
                elif char in ('\n', '\r'):
                    cleaned.append('\\n')
                    i += 1
                else:
                    cleaned.append(char)
                    i += 1
            return json.loads("".join(cleaned))

    except Exception as e:
        logger.error(f"Failed to extract JSON: {e}")
        raise ValueError(f"Failed to extract JSON: {e}")
