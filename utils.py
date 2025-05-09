import random
import string
from datetime import date

def generate_license_key(plugin: str, plan: str, date_obj: date) -> str:
    prefix = "QW"
    plugin_code = plugin.upper().replace("-", "")[:6]
    plan_code = "LIFE" if plan == "life" else "YEAR"
    date_str = date_obj.strftime("%Y%m%d")
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, 
k=6))
    return f"{prefix}-{plugin_code}-{plan_code}-{date_str}-{rand_part}"

# Example use:
# key = generate_license_key("quick-edit", "year", date.today())

