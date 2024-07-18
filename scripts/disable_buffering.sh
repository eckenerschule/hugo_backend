#!/bin/bash
# NOTE: This file adds nginx configurations to disable buffering for the streaming endpoint: get_response

# Define the content you want to add
new_content="location /get_response {
    proxy_buffering off;
}"

# File to edit
file_path="/etc/nginx/conf.d/nginx.conf"

# Check if the file exists
if [ -f "$file_path" ]; then
    # Use sed to edit the file and append the new content before the last '}' character
    sed -i -e '/}/i '"$new_content" "$file_path"
    echo "Content added to $file_path"
else
    echo "File not found: $file_path"
fi
