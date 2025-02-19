from flask import Flask, request, redirect, url_for, send_file, abort
import pandas as pd
import matplotlib.pyplot as plt
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)


# Folder to store uploaded files and generated charts
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'csv'}

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route: Home Page (File Upload)
@app.route('/')
def upload_page():
    return '''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CSV Visualization</title>
        <style>
            /* Import fonts */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400&family=Plus+Jakarta+Sans:wght@700&display=swap');
            @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css');

            /* General body styling */
            body {
                font-family: 'Inter', sans-serif;
                background-color: #e8f5e9; /* Light green background */
                color: #333;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                flex-direction: column;
            }

            h1 {
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: bold;
                color: #2e7d32; /* Dark green text */
            }

            p {
                font-family: 'Inter', sans-serif;
                color: #555;
                text-align: center;
                max-width: 600px;
            }

            .icon-list {
                display: flex;
                justify-content: center;
                margin: 20px 0;
            }

            .icon-list div {
                margin: 0 15px;
                text-align: center;
            }

            .icon-list i {
                font-size: 30px;
                color: #2e7d32;
                margin-bottom: 10px;
            }

            form {
                text-align: center;
                margin-top: 20px;
            }

            input[type="file"] {
                display: none;
            }

            label {
                background-color: #ffffff; /* White button */
                color: #2e7d32; /* Green text */
                border: 2px solid #2e7d32;
                padding: 10px 20px;
                font-size: 16px;
                border-radius: 5px;
                cursor: pointer;
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: bold;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }

            label:hover {
                background-color: #f1f8e9; /* Light green hover */
            }

            label i {
                font-size: 18px;
            }

            input[type="submit"] {
                background: linear-gradient(90deg, #4caf50, #81c784, #66bb6a); /* Gradient */
                background-size: 200%;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                border-radius: 5px;
                cursor: pointer;
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: bold;
                position: relative;
                overflow: hidden;
                animation: gradientAnimation 2s linear infinite; /* Animation */
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }

            input[type="submit"]:hover {
                background-position: right;
            }

            input[type="submit"] i {
                font-size: 18px;
            }

            @keyframes gradientAnimation {
                0% {
                    background-position: left;
                }
                100% {
                    background-position: right;
                }
            }

            footer {
                margin-top: 40px;
                font-size: 14px;
                color: #666;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <h1>Visualize Your CSV Data</h1>
        <p>Transform your boring spreadsheets into beautiful, insightful visualizations in just a few clicks.</p>

        <div class="icon-list">
            <div>
                <i class="fas fa-chart-line"></i>
                <p>Interactive Charts</p>
            </div>
            <div>
                <i class="fas fa-upload"></i>
                <p>Easy Uploads</p>
            </div>
            <div>
                <i class="fas fa-file-download"></i>
                <p>Quick Downloads</p>
            </div>
        </div>

        <form action="/process" method="post" enctype="multipart/form-data">
            <label for="file">
                <i class="fas fa-file-upload"></i>
                Choose File
            </label>
            <input type="file" name="file" id="file" accept=".csv">
            <input type="submit" value="Visualise Now">
        </form>

        <footer>
            Powered by <strong>codingwithsagar</strong>
        </footer>
    </body>
    </html>
    '''

# Route: Process CSV File
@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return "No file part in the request.", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected.", 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            # Generate the chart and save it
            chart_path = generate_chart(file_path)
            return redirect(url_for('show_chart', chart_file=os.path.basename(chart_path)))
        except Exception as e:
            return f"Error processing the file: {e}", 500

    return "Invalid file format. Please upload a CSV file.", 400

# Route: Show Chart and Provide Download Link
@app.route('/chart/<chart_file>')
def show_chart(chart_file):
    chart_path = os.path.join(app.config['UPLOAD_FOLDER'], chart_file)
    if not os.path.exists(chart_path):
        abort(404, description="Chart file not found.")

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chart Visualization</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400&family=Plus+Jakarta+Sans:wght@700&display=swap');
            @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css');

            body {{
                font-family: 'Inter', sans-serif;
                background-color: #e8f5e9;
                color: #333;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                padding: 20px;
            }}

            h1 {{
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: bold;
                color: #2e7d32;
                margin-bottom: 20px;
            }}

            p {{
                font-family: 'Inter', sans-serif;
                color: #555;
                max-width: 600px;
                margin-bottom: 20px;
            }}

            .icon-list {{
                display: flex;
                justify-content: center;
                gap: 20px;
                margin: 20px 0;
            }}

            .icon-list div {{
                text-align: center;
            }}

            .icon-list i {{
                font-size: 30px;
                color: #4caf50;
                margin-bottom: 10px;
            }}

            img {{
                max-width: 90%;
                margin: 20px 0;
                border: 2px solid #4caf50;
                border-radius: 8px;
            }}

            a {{
                text-decoration: none;
                background-color: #4caf50;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: bold;
                margin: 5px;
            }}

            a:hover {{
                background-color: #388e3c;
            }}
        </style>
    </head>
    <body>
        <h1>Your Data Visualization</h1>
        <p>This tool empowers you to transform raw data into clear, actionable insights. Explore the benefits below:</p>

        <div class="icon-list">
            <div>
                <i class="fas fa-chart-pie"></i>
                <p>Interactive Charts</p>
            </div>
            <div>
                <i class="fas fa-user-friends"></i>
                <p>User-Friendly Interface</p>
            </div>
            <div>
                <i class="fas fa-file-export"></i>
                <p>Quick Downloads</p>
            </div>
        </div>

        <img src="/static/uploads/{chart_file}" alt="Chart">

        <div>
            <a href="/download/{chart_file}"><i class="fas fa-download"></i> Download Chart as PNG</a>
            <a href="/"><i class="fas fa-arrow-left"></i> Go Back</a>
        </div>
    </body>
    </html>
    """

# Route: Download Chart
@app.route('/download/<chart_file>')
def download_chart(chart_file):
    chart_path = os.path.join(app.config['UPLOAD_FOLDER'], chart_file)
    return send_file(chart_path, as_attachment=True)

# Function to generate a chart from the CSV file
def generate_chart(file_path):
    # Read the CSV file
    df = pd.read_csv(file_path)

    # Ensure the file has at least one numeric column and one non-numeric column (e.g., Month)
    numeric_columns = df.select_dtypes(include=['number']).columns
    non_numeric_columns = df.select_dtypes(exclude=['number']).columns

    if len(numeric_columns) < 2:
        raise ValueError("The uploaded file must have at least two numeric columns for visualization.")
    if len(non_numeric_columns) == 0:
        raise ValueError("The uploaded file must have at least one non-numeric column (e.g., Month).")

    # Assume the first non-numeric column is the X-axis (e.g., Month)
    x_column = non_numeric_columns[0]

    # Plot the numeric columns against the X-axis
    plt.figure(figsize=(10, 6))
    for column in numeric_columns:
        plt.plot(df[x_column], df[column], marker='o', label=column)

    # Add chart details
    plt.title(f"Visualization of {', '.join(numeric_columns)} Over {x_column}")
    plt.xlabel(x_column)
    plt.ylabel("Values")
    plt.legend(title="Metrics")
    plt.grid(True)

    # Rotate X-axis labels for better readability (if it's a categorical axis like Month)
    plt.xticks(rotation=45)

    # Save the plot as a PNG file
    chart_path = os.path.join(app.config['UPLOAD_FOLDER'], 'chart.png')
    plt.savefig(chart_path)
    plt.close()

    return chart_path

# Static route to serve chart images
@app.route('/static/uploads/<filename>')
def static_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return f"Error: File {filename} not found.", 404
    return send_file(file_path)

if __name__ == '__main__':
    app.run(debug=True)
