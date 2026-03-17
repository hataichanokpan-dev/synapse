#!/bin/bash
# Patch graphiti_core library to fix RediSearch syntax error with group_ids
# containing reserved words like "user" or special characters like hyphens
#
# Bug: https://github.com/getzep/graphiti/issues/XXX
# Fix: Use re.escape() instead of quotes for group_ids

set -e

LIBRARY_FILE="/opt/venv/lib/python3.12/site-packages/graphiti_core/driver/falkordb_driver.py"

echo "Patching graphiti_core library..."

# Check if file exists
if [ ! -f "$LIBRARY_FILE" ]; then
    echo "ERROR: Library file not found: $LIBRARY_FILE"
    exit 1
fi

# Check if already patched
if grep -q "re.escape(gid)" "$LIBRARY_FILE"; then
    echo "Already patched, skipping."
    exit 0
fi

# Add import re if not present
if ! grep -q "^import re$" "$LIBRARY_FILE"; then
    echo "Adding 'import re'..."
    sed -i 's/^import asyncio$/import asyncio\nimport re/' "$LIBRARY_FILE"
fi

# Fix the build_fulltext_query method
# Replace: escaped_group_ids = [f'"{gid}"' for gid in group_ids]
# With:    escaped = [re.escape(gid) for gid in group_ids]
echo "Patching build_fulltext_query method..."
sed -i "s/escaped_group_ids = \[f'\"{gid}\"' for gid in group_ids\]/escaped = [re.escape(gid) for gid in group_ids]/" "$LIBRARY_FILE"

# Replace: group_values = '|'.join(escaped_group_ids)
# With:    group_values = '|'.join(escaped)
sed -i "s/group_values = '|'.join(escaped_group_ids)/group_values = '|'.join(escaped)/" "$LIBRARY_FILE"

# Update comment
sed -i 's/# Escape group_ids with quotes to prevent RediSearch syntax errors/# Escape hyphens and other special characters to avoid RediSearch errors/' "$LIBRARY_FILE"
sed -i 's/# with reserved words like "main" or special characters like hyphens/# Reserved words like "user" and hyphens can cause syntax errors/' "$LIBRARY_FILE"

# Verify the patch
if grep -q "re.escape(gid)" "$LIBRARY_FILE"; then
    echo "Patch applied successfully!"
else
    echo "ERROR: Patch failed to apply!"
    exit 1
fi
