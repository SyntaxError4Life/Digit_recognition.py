import socket
import threading
import select
import json
import sys
import os
import subprocess
from datetime import datetime, timedelta
from random import randint, uniform
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from __gestion_sql__ import (
    initialize_database, insert_feedback, get_all_feedbacks, get_feedback_by_id, mark_feedback_as_deleted,
    insert_model, get_all_models, get_model_by_id, mark_model_as_deleted,
    insert_training_batch, get_all_training_batches, mark_training_batch_as_deleted, get_absolute_path,
    generate_test_grid
)
from framework import Model, Tensor

# Configuration constants for server settings
HOST = '127.0.0.1'  # Host address for the TCP server
PORT = 9999        # Port number for the TCP server
WEB_HOST = '127.0.0.1'  # Host address for the Flask web server
WEB_PORT = 20000   # Port number for the Flask web server

# Event to signal the daemon to shut down
stop_event = threading.Event()

# Flask application setup for the main process (used only for template references)
app = Flask(__name__, template_folder="../templates", static_folder="../static")
CORS(app)

# Web server state and traffic statistics
web_server_running = False
web_server_process = None
traffic_stats = {"requests": 0, "errors": 0}

# Global model instance for predictions
model = None

def daemon():
    """Start the TCP and Flask servers, initializing the database and model.

    Initializes the SQLite database using `__gestion_sql__.py`, loads the machine learning model
    from 'framework.py', and launches a Flask server in a subprocess. Listens for TCP commands
    on port 9999 until the stop event is triggered.
    """
    global model, web_server_running, web_server_process
    # Initialize the database
    initialize_database()
    print("Database initialized. Daemon started on port 9999.")

    # Load the machine learning model
    try:
        model_path = get_absolute_path("data/model_weights.json")
        model = Model(model_path)
        print("Model loaded successfully")
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return

    # Start the Flask server in a subprocess
    web_server_running = True
    flask_script = os.path.join(os.path.dirname(__file__), "flask_server.py")
    with open(flask_script, "w") as f:
        f.write("""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
import socket
sys.path.append('{script_dir}')
from __gestion_sql__ import get_absolute_path, insert_feedback, get_all_models
from framework import Model, Tensor
import json
                
app = Flask(__name__, template_folder="../templates", static_folder="../static")
CORS(app)
traffic_stats = {{"requests": 0, "errors": 0}}
model = None

def hex_to_binary(hex_string: str) -> list:
    \"\"\"Convert a hexadecimal string to a binary list for model input.

    Args:
        hex_string (str): A 64-character hexadecimal string representing a grid.

    Returns:
        list: A list of 256 floats (0.0 or 1.0) representing the grid in binary form.

    Raises:
        ValueError: If the hex string contains invalid characters.
    \"\"\"
    binary_list = []
    for char in hex_string:
        if char not in '0123456789ABCDEF':
            raise ValueError(f"Invalid hexadecimal character: {{char}}")
        binary = bin(int(char, 16))[2:].zfill(4)
        binary_list.extend(float(bit) for bit in binary)
    return binary_list

try:
    model_path = get_absolute_path("data/model_weights.json")
    model = Model(model_path)
    print("Model loaded in Flask process")
except Exception as e:
    print(f"Error loading model in Flask: {{{{str(e)}}}}")
    sys.exit(1)

@app.route('/')
def index():
    \"\"\"Serve the main index page of the web interface.\"\"\"
    traffic_stats["requests"] += 1
    return render_template('index.html')

@app.route('/admin')
def admin():
    \"\"\"Serve the admin page of the web interface.\"\"\"
    traffic_stats["requests"] += 1
    return render_template('admin.html')

@app.route('/predict', methods=['POST'])
def predict():
    \"\"\"Handle digit prediction requests from the web interface.

    Receives a hexadecimal grid in JSON format, converts it to binary, runs the model,
    and returns the predicted probabilities.

    Expects JSON with an 'image_criter' key containing a 64-character hex string.

    Returns:
        JSON response with 'probabilities' (list of 10 floats) or an 'error' message.
    \"\"\"
    traffic_stats["requests"] += 1
    try:
        if not request.is_json:
            print("Request /predict - Error: Non-JSON content")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Request must be JSON"}}), 400

        data = request.json
        if not data:
            print("Request /predict - Error: No JSON data")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "No JSON data provided"}}), 400

        image_criter = data.get('image_criter')
        if not image_criter:
            print("Request /predict - Error: Missing 'image_criter' key")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Missing 'image_criter' key"}}), 400

        if len(image_criter) != 64:
            print(f"Request /predict - Error: Invalid image_criter length ({{len(image_criter)}} instead of 64)")
            traffic_stats["errors"] += 1
            return jsonify({{"error": f"Invalid image_criter length: {{len(image_criter)}}"}}), 400

        if not all(c in '0123456789ABCDEF' for c in image_criter):
            print(f"Request /predict - Error: Non-hexadecimal characters in image_criter ({{image_criter}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "image_criter contains non-hexadecimal characters"}}), 400

        binary_list = hex_to_binary(image_criter)
        print(f"Request /predict - image_criter: {{image_criter}}, binary: {{binary_list[:10]}}... (total: {{len(binary_list)}})")

        input_tensor = Tensor({{'1': binary_list}})
        output = model.forward(input_tensor)
        probabilities = output.data['1']

        if len(probabilities) != 10 or abs(sum(probabilities) - 1.0) > 1e-5:
            print(f"Request /predict - Error: Invalid probabilities ({{probabilities}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Invalid model output"}}), 500

        print(f"Response /predict - probabilities: {{probabilities}}")
        return jsonify({{"probabilities": probabilities}})

    except Exception as e:
        print(f"Request /predict - Error: {{{{str(e)}}}}")
        traffic_stats["errors"] += 1
        return jsonify({{"error": f"Prediction failed: {{{{str(e)}}}}"}}), 500

@app.route('/feedback', methods=['POST'])
def feedback():
    \"\"\"Handle feedback submissions from the web interface.

    Stores the submitted grid and prediction in the database using `__gestion_sql__.py`.

    Expects JSON with 'image_criter' (64 hex chars) and 'prob_max' (int 0-9).

    Returns:
        JSON response with a 'message' and 'feedback_id', or an 'error' message.
    \"\"\"
    traffic_stats["requests"] += 1
    try:
        from datetime import datetime
        if not request.is_json:
            print("Request /feedback - Error: Non-JSON content")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Request must be JSON"}}), 400

        data = request.json
        if not data:
            print("Request /feedback - Error: No JSON data")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "No JSON data provided"}}), 400

        image_criter = data.get('image_criter')
        prob_max = data.get('prob_max')

        if not image_criter or prob_max is None:
            print(f"Request /feedback - Error: Invalid data (image_criter: {{image_criter}}, prob_max: {{prob_max}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Missing 'image_criter' or 'prob_max'"}}), 400

        if len(image_criter) != 64:
            print(f"Request /feedback - Error: Invalid image_criter length ({{len(image_criter)}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": f"Invalid image_criter length: {{len(image_criter)}}"}}), 400

        if not all(c in '0123456789ABCDEF' for c in image_criter):
            print(f"Request /feedback - Error: Non-hexadecimal characters in image_criter ({{image_criter}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": "image_criter contains non-hexadecimal characters"}}), 400

        if not isinstance(prob_max, int) or not 0 <= prob_max <= 9:
            print(f"Request /feedback - Error: Invalid prob_max ({{prob_max}})")
            traffic_stats["errors"] += 1
            return jsonify({{"error": f"Invalid prob_max: {{prob_max}}"}}), 400

        date = datetime.now().strftime("%Y-%m-%d")
        models = get_all_models()
        id_version_modele = models[-1][0] if models else 1

        feedback_id = insert_feedback(image_criter, prob_max, date, id_version_modele)

        print(f"Request /feedback - image_criter: {{image_criter}}, prob_max: {{prob_max}}, date: {{date}}, id_version_modele: {{id_version_modele}}")
        print(f"Feedback inserted with ID: {{feedback_id}}")

        return jsonify({{"message": "Feedback received", "feedback_id": feedback_id}})

    except Exception as e:
        print(f"Request /feedback - Error: {{{{str(e)}}}}")
        traffic_stats["errors"] += 1
        return jsonify({{"error": f"Feedback failed: {{{{str(e)}}}}"}}), 500

@app.route('/tcp_relay', methods=['POST'])
def tcp_relay():
    \"\"\"Relay a command to the TCP server and return its response.

    Expects JSON with a 'command' key containing the TCP command string.

    Returns:
        JSON response from the TCP server or an 'error' message.
    \"\"\"
    traffic_stats["requests"] += 1
    try:
        if not request.is_json:
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Request must be JSON"}}), 400
        data = request.json
        command = data.get('command')
        if not command:
            traffic_stats["errors"] += 1
            return jsonify({{"error": "Missing 'command' key"}}), 400
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('127.0.0.1', 9999))
            s.sendall(command.encode())
            response = s.recv(4096).decode()
            return jsonify(json.loads(response))
    except Exception as e:
        traffic_stats["errors"] += 1
        return jsonify({{"error": f"Command failed: {{{{str(e)}}}}"}}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=20000, debug=False)
""".format(script_dir=os.path.dirname(__file__)))
    web_server_process = subprocess.Popen([sys.executable, flask_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Web server started in separate process (PID: {web_server_process.pid})")

    # Start the TCP server to listen for commands
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, PORT))
        except OSError:
            print("Port is already in use. The daemon may already be running.")
            if web_server_running:
                web_server_process.terminate()
                web_server_running = False
            return
        server.listen()

        while not stop_event.is_set():
            readable, _, _ = select.select([server], [], [], 1)
            if readable:
                conn, addr = server.accept()
                threading.Thread(target=handle_client, args=(conn,)).start()

def handle_client(conn):
    """Handle an incoming client connection for TCP commands.

    Receives command data from the client, processes it, and sends back a response.

    Args:
        conn: The socket connection object for the client.
    """
    with conn:
        while True:
            data = conn.recv(4096).decode()
            if not data:
                break
            command, *args = data.split(maxsplit=3)
            response = process_command(command, args)
            conn.sendall(json.dumps(response).encode())

def process_command(command: str, args: list) -> dict:
    """Process incoming TCP commands and interact with the database or web server.

    Supports commands for managing feedbacks, models, training batches, web server status,
    and model testing.

    Args:
        command (str): The command to process (e.g., 'list_feedbacks', 'test_model').
        args (list): A list of arguments provided with the command.

    Returns:
        dict: A dictionary containing the response data or an error message.
    """
    global web_server_running, web_server_process, WEB_HOST, model
    try:
        if command == "list_feedbacks":
            feedbacks = get_all_feedbacks()
            return {"data": [{"id": f[0], "image_criter": f[1], "prob_max": f[2], "date": f[3], "id_version_modele": f[4]} for f in feedbacks]}

        elif command == "get_feedback":
            feedback_id = int(args[0])
            feedback = get_feedback_by_id(feedback_id)
            if feedback:
                return {"data": {"id": feedback[0], "image_criter": feedback[1], "prob_max": feedback[2], "date": feedback[3], "id_version_modele": feedback[4]}}
            return {"error": "Feedback not found"}

        elif command == "delete_feedback":
            feedback_id = int(args[0])
            mark_feedback_as_deleted(feedback_id)
            return {"message": f"Feedback {feedback_id} marked as deleted"}

        elif command == "add_feedback":
            hex_chars = "0123456789ABCDEF"
            image_criter = ''.join(hex_chars[randint(0, 15)] for _ in range(64))
            prob_max = randint(0, 9)
            date = (datetime.now() - timedelta(days=randint(0, 10))).strftime("%Y-%m-%d")
            models = get_all_models()
            id_version_modele = models[randint(0, len(models)-1)][0] if models else 1
            feedback_id = insert_feedback(image_criter, prob_max, date, id_version_modele)
            feedback = get_feedback_by_id(feedback_id)
            return {"data": {"id": feedback[0], "image_criter": feedback[1], "prob_max": feedback[2], "date": feedback[3], "id_version_modele": feedback[4]}}

        elif command == "list_training_batches":
            batches = get_all_training_batches()
            return {"data": [{"id": b[0], "id_min_feedback": b[1], "id_max_feedback": b[2], "id_modele_genere": b[3]} for b in batches]}

        elif command == "add_training_batch":
            id_min, id_max = int(args[0]), int(args[1])
            models = get_all_models()
            id_modele_genere = models[randint(0, len(models)-1)][0] if models else 1
            batch_id = insert_training_batch(id_min, id_max, id_modele_genere)
            return {"message": f"Batch created: ID={batch_id}, min={id_min}, max={id_max}"}

        elif command == "delete_training_batch":
            batch_id = int(args[0])
            mark_training_batch_as_deleted(batch_id)
            return {"message": f"Batch {batch_id} marked as deleted"}

        elif command == "list_models":
            models = get_all_models()
            return {"data": [{"id_version": m[0], "perte_moyenne": m[1], "date": m[2]} for m in models]}

        elif command == "get_model":
            model_id = int(args[0])
            model_data = get_model_by_id(model_id)
            if model_data:
                return {"data": {"id_version": model_data[0], "perte_moyenne": model_data[1], "date": model_data[2]}}
            return {"error": "Model not found"}

        elif command == "add_model":
            id_min, id_max = int(args[0]), int(args[1])
            loss = round(uniform(0.1, 2.0), 2)
            date = (datetime.now() - timedelta(days=randint(0, 10))).strftime("%Y-%m-%d")
            model_id = insert_model(loss, date)
            return {"message": f"Model created: ID={model_id}, Loss={loss}"}

        elif command == "delete_model":
            model_id = int(args[0])
            mark_model_as_deleted(model_id)
            return {"message": f"Model {model_id} marked as deleted"}

        elif command == "web_status":
            return {"message": f"Web server {'running' if web_server_running else 'stopped'} on {WEB_HOST}:{WEB_PORT}"}

        elif command == "start_web":
            if not web_server_running:
                web_server_running = True
                flask_script = os.path.join(os.path.dirname(__file__), "flask_server.py")
                web_server_process = subprocess.Popen([sys.executable, flask_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"Web server restarted in separate process (PID: {web_server_process.pid})")
                return {"message": f"Web server started on {WEB_HOST}:{WEB_PORT}"}
            return {"message": "Web server already running"}

        elif command == "test_model":
            try:
                if not model:
                    return {"error": "Model not loaded"}
                image_criter = generate_test_grid()
                binary_list = hex_to_binary(image_criter)
                input_tensor = Tensor({'1': binary_list})
                output = model.forward(input_tensor)
                probabilities = output.data['1']
                predicted_digit = probabilities.index(max(probabilities))
                return {"image_criter": image_criter, "predicted_digit": predicted_digit}
            except Exception as e:
                return {"error": f"Model test failed: {str(e)}"}

        elif command == "stop_web":
            if web_server_running:
                web_server_process.terminate()
                web_server_running = False
                print("Web server stopped")
                return {"message": "Web server stopped"}
            return {"message": "Web server already stopped"}

        elif command == "web_traffic":
            return {"data": traffic_stats}

        elif command == "set_web_host":
            mode = args[0]
            if mode in ["local", "lan"]:
                WEB_HOST = "127.0.0.1" if mode == "local" else "0.0.0.0"
                if web_server_running:
                    web_server_process.terminate()
                    web_server_running = False
                    flask_script = os.path.join(os.path.dirname(__file__), "flask_server.py")
                    web_server_process = subprocess.Popen([sys.executable, flask_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Web server restarted with new host {WEB_HOST} (PID: {web_server_process.pid})")
                return {"message": f"Web host set to {WEB_HOST}"}
            return {"error": "Invalid mode (use 'local' or 'lan')"}

        elif command == "model_status":
            if model:
                return {"message": "Model is loaded"}
            else:
                return {"message": "Model is not loaded"}

        elif command == "predict_test":
            if not model:
                return {"error": "Model not loaded"}
            image_criter = args[0]
            if len(image_criter) != 64 or not all(c in '0123456789ABCDEF' for c in image_criter):
                return {"error": "Invalid image_criter"}
            binary_list = hex_to_binary(image_criter)
            input_tensor = Tensor({'1': binary_list})
            output = model.forward(input_tensor)
            probabilities = output.data['1']
            print(f"Command predict_test - image_criter: {image_criter}, probabilities: {probabilities}")
            return {"probabilities": probabilities}

        elif command == "stop":
            stop_event.set()
            if web_server_running:
                web_server_process.terminate()
                web_server_running = False
                print("Web server stopped")
            return {"message": "Daemon stopped"}

        else:
            return {"error": "Unknown command"}

    except (IndexError, ValueError):
        return {"error": "Invalid command arguments"}

def hex_to_binary(hex_string: str) -> list:
    """Convert a hexadecimal string to a binary list for model input.

    Args:
        hex_string (str): A 64-character hexadecimal string representing a grid.

    Returns:
        list: A list of 256 floats (0.0 or 1.0) representing the grid in binary form.

    Raises:
        ValueError: If the hex string contains invalid characters.
    """
    binary_list = []
    for char in hex_string:
        if char not in '0123456789ABCDEF':
            raise ValueError(f"Invalid hexadecimal character: {char}")
        binary = bin(int(char, 16))[2:].zfill(4)
        binary_list.extend(float(bit) for bit in binary)
    return binary_list

if __name__ == "__main__":
    daemon()