import re

with open('/Users/phandangvu/Desktop/SE/docs/database-design.md', 'r') as f:
    content = f.read()

# ERD
content = content.replace('id (PK, UUID)', 'id (PK)')

# Update tables
content = re.sub(r'\|\s*UUID\s*\|', '| INT |', content)
content = re.sub(r'Auto-generated', 'Auto Increment', content)

# Add username to users table if not exists
if '| `username`' not in content:
    content = content.replace(
        '| `email`         | VARCHAR(255) | UNIQUE NOT NULL        | Dùng làm username |',
        '| `username`      | VARCHAR(100) | UNIQUE NOT NULL        |                   |\n| `email`         | VARCHAR(255) | UNIQUE NOT NULL        |                   |'
    )

with open('/Users/phandangvu/Desktop/SE/docs/database-design.md', 'w') as f:
    f.write(content)

