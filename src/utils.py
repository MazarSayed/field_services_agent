import yaml
import os

def get_prompt(key: str) -> str:
    """
    Load a prompt from the prompts.yaml file based on the key.
    
    Args:
        key: The key to lookup in the YAML file (supports nested keys with dots)
        
    Returns:
        The prompt string or empty string if not found
    """
    try:
        current_dir = os.path.dirname(__file__)
        
        parent_dir = os.path.dirname(current_dir)
        yaml_path = os.path.join(parent_dir, "prompts", "prompts.yaml")
        
        if not os.path.exists(yaml_path):
            print(f"Error: YAML file not found at {yaml_path}")
            return ""
        
        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        
        # Handle nested keys like "Time_Type_Check.Corrective.Warranty Support"
        keys = key.split('.')
        result = data
        
        for k in keys:
            if isinstance(result, dict) and k in result:
                result = result[k]
            else:
                return ""  # Key not found
        
        return str(result) if result is not None else ""
        
    except Exception as e:
        print(f"Error loading prompt '{key}': {e}")
        return ""