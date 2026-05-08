import os
from flask import Flask, jsonify, request, render_template_string
from collections import defaultdict
import webbrowser
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Folder Scanner</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 1400px;
            box-sizing: border-box;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .input-group {
            margin: 20px 0;
            display: flex;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
            outline: none;
        }
        input[type="text"]:focus {
            border-color: #4CAF50;
        }
        button {
            padding: 12px 24px;
            font-size: 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background-color: #45a049;
        }
        .results {
            margin-top: 30px;
        }
        .section {
            margin: 20px 0;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 4px;
        }
        .section h2 {
            color: #555;
            margin-top: 0;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
            word-break: break-all;
            overflow-wrap: break-word;
        }
        li:last-child {
            border-bottom: none;
        }
        .error {
            color: #d32f2f;
            background-color: #ffebee;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 Folder Scanner</h1>
        <form id="scanForm" class="input-group">
            <input type="text" id="folderPath" placeholder="Enter folder path (e.g., C:\\Users\\Documents)" required>
            <button type="submit">CALCULATE</button>
        </form>
        <div id="results" class="results"></div>
    </div>

    <script>
        document.getElementById('scanForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const path = document.getElementById('folderPath').value;
            const resultsDiv = document.getElementById('results');
            
            resultsDiv.innerHTML = '<p class="loading">Scanning folder...</p>';
            
            try {
                const response = await fetch(`/scan?path=${encodeURIComponent(path)}`);
                const data = await response.json();
                
                if (data.error) {
                    resultsDiv.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                    return;
                }
                
                let html = '';
                
                if (data.top_files && data.top_files.length > 0) {
                    html += '<div class="section"><h2>📄 Top 10 Files</h2><ul>';
                    data.top_files.forEach(file => {
                        html += `<li><strong>${file.path}</strong>: ${file.size} GB</li>`;
                    });
                    html += '</ul></div>';
                }
                
                if (data.top_folders && data.top_folders.length > 0) {
                    html += '<div class="section"><h2>📂 Top 10 Folders</h2><ul>';
                    data.top_folders.forEach(folder => {
                        html += `<li><strong>${folder.name}</strong>: ${folder.size} GB</li>`;
                    });
                    html += '</ul></div>';
                }
                
                if (!html) {
                    html = '<p class="loading">No files or folders found.</p>';
                }
                
                resultsDiv.innerHTML = html;
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });
    </script>
</body>
</html>
"""

def get_folder_size(path):
    """Calculates the total size of a directory in bytes."""
    total_size = 0
    for root, dirs, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                total_size += os.path.getsize(file_path)
            except OSError:
                continue
    return total_size

def bytes_to_gb(size_in_bytes):
    """Converts bytes to gigabytes."""
    return round(size_in_bytes / (1024 ** 3), 2)

def analyze_folder(root_path):
    """Scans the folder and collects file and folder sizes."""
    if not os.path.isdir(root_path):
        return {"error": "Invalid directory path"}, None

    file_sizes = []
    immediate_subdirs = {}
    
    # First pass: collect all file sizes and calculate sizes of immediate subdirectories
    for root, dirs, files in os.walk(root_path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                size = os.path.getsize(file_path)
                file_sizes.append((file_path, size))
            except OSError:
                continue

        # If we are at the root level, track immediate subdirectories
        if root == root_path:
            for d in dirs:
                subdir_path = os.path.join(root_path, d)
                # Calculate size of the subdirectory
                subdir_size = get_folder_size(subdir_path)
                immediate_subdirs[d] = subdir_size

    # Sort and get top 10 files
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    top_files = file_sizes[:10]
    
    # Sort and get top 10 folders
    top_folders_list = []
    for name, size in immediate_subdirs.items():
        top_folders_list.append((name, size))
    
    top_folders_list.sort(key=lambda x: x[1], reverse=True)
    top_folders = top_folders_list[:10]

    return {
        "top_files": [{"path": f[0], "size": bytes_to_gb(f[1])} for f in top_files],
        "top_folders": [{"name": f[0], "size": bytes_to_gb(f[1])} for f in top_folders]
    }

def _generate_list(items):
    """Generates an HTML list string from a list of file/folder dictionaries."""
    if not items:
        return "<p>No items found.</p>"
    
    list_items = []
    for item in items:
        if "path" in item: # File
            list_items.append(f'<li><strong>{item["path"]}</strong>: {item["size"]} bytes</li>')
        elif "name" in item: # Folder
            list_items.append(f'<li><input type="text" value="{item["name"]}">{item["size"]} bytes</li>')
    
    return "\n".join(list_items)


@app.route('/')
def index():
    """Serves the HTML page with input field and calculate button."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/scan', methods=['GET'])
def scan_folder():
    """Endpoint to scan the specified folder."""
    # Get the folder path from query parameters
    folder_path = request.args.get('path')
    
    if not folder_path:
        return jsonify({"error": "Please provide a 'path' query parameter."}), 400

    # Ensure the path is absolute and exists
    absolute_path = os.path.abspath(folder_path)
    
    try:
        results = analyze_folder(absolute_path)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"An error occurred during scanning: {str(e)}"}), 500

if __name__ == '__main__':
    # Run the Flask application for web access
    app.run(debug=True)