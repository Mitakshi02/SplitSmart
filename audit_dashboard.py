import re

with open('app/templates/groups/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Check all getElementById calls
get_els = re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)", content)
print(f"Total getElementById calls: {len(get_els)}")
missing_ids = []
for el_id in set(get_els):
    # Check if id="<el_id>" or id='<el_id>' exists in HTML
    if not re.search(r'id=[\'"]' + re.escape(el_id) + r'[\'"]', content):
        missing_ids.append(el_id)

print(f"MISSING IDs referenced in JS: {missing_ids}")

# 2. Check all querySelector/querySelectorAll
q_selectors = re.findall(r"document\.querySelectorAll\(['\"]([^'\"]+)['\"]\)", content)
print(f"querySelectorAll: {set(q_selectors)}")

# 3. Check all on* event attributes
on_events = re.findall(r'on\w+=[\'"]([^\'"]+)[\'"]', content)
print(f"on* events count: {len(on_events)}")
for ev in set(on_events):
    print(f"  Event: {ev}")

# 4. Check all fetch calls
fetches = re.findall(r'fetch\([`\'"]([^`\'"]+)[`\'"]', content)
print(f"Fetch calls: {set(fetches)}")
