import socket
import subprocess
import sys
import time
import curses
import json
import os

# Configuration constants for TCP communication with the daemon
HOST = '127.0.0.1'  # Localhost address for daemon connection
PORT = 9999  # Port for TCP socket communication
MIN_HEIGHT = 30  # Minimum terminal height for curses UI
MIN_WIDTH = 80  # Minimum terminal width for curses UI

def check_daemon():
    """Check if the daemon is running by attempting a TCP connection.

    Returns:
        bool: True if the daemon is reachable, False otherwise.
    """
    # Try connecting to the daemon up to 5 times
    for _ in range(5):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((HOST, PORT))
                return True
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(0.5)
    return False

def start_daemon():
    """Start the daemon process if the port is available.

    Launches __deamon__.py in a subprocess and checks if it starts successfully.
    Prints instructions or error messages based on the outcome.
    """
    # Check if port 9999 is available
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 9999))
    except OSError:
        print("Port 9999 already in use. Try: `kill -9 $(lsof -t -i:9999)`")
        return
    # Get the absolute path to the daemon script
    daemon_path = os.path.join(os.path.dirname(__file__), "__deamon__.py")
    # Start the daemon in a subprocess
    process = subprocess.Popen(
        [sys.executable, daemon_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Wait for the daemon to initialize
    time.sleep(10)
    # Verify daemon status
    if check_daemon():
        print("Daemon started, do:")
        print('- "python3 app connect" to open the CLI')
        print('- "python3 app stop" to stop the daemon')
    else:
        stdout, stderr = process.communicate(timeout=5)
        print("Failed to start daemon.")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        print("Check `ps aux | grep deamon` or logs.")

def send_command(command):
    """Send a command to the daemon via TCP and return the response.

    Args:
        command (str): The command to send (e.g., 'list_feedbacks').

    Returns:
        dict: JSON-parsed response from the daemon, or an error dict if the connection fails.
    """
    try:
        # Establish TCP connection to the daemon
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(command.encode())
            response = s.recv(4096).decode()
            return json.loads(response) if response else {}
    except (ConnectionRefusedError, json.JSONDecodeError):
        return {"error": "Failed to communicate with daemon"}

def check_window_size(stdscr):
    """Check if the terminal window size meets minimum requirements for curses UI.

    Args:
        stdscr: The curses window object.

    Returns:
        bool: True if the window size is sufficient, False otherwise.
    """
    # Get current terminal dimensions
    height, width = stdscr.getmaxyx()
    if height < MIN_HEIGHT or width < MIN_WIDTH:
        # Display error message and wait for user input
        stdscr.clear()
        stdscr.addstr(0, 0, f"Window too small! Min: {MIN_HEIGHT}x{MIN_WIDTH}, Current: {height}x{width}")
        stdscr.addstr(2, 0, "Resize and press any key...")
        stdscr.refresh()
        stdscr.getch()
        return False
    return True

def hex_to_binary(hex_string):
    """Convert a hexadecimal string to a binary list for 16x16 grid display.

    Args:
        hex_string (str): 64-character hexadecimal string representing a grid.

    Returns:
        list: List of 256 binary values (0 or 1) for the grid.
    """
    binary_list = []
    # Convert each hex character to 4 bits
    for char in hex_string:
        binary = bin(int(char, 16))[2:].zfill(4)
        binary_list.extend(int(bit) for bit in binary)
    return binary_list

def draw_grid(stdscr, binary_list, y_start, x_start):
    """Draw a 16x16 grid in the curses UI using a binary list.

    Args:
        stdscr: The curses window object.
        binary_list (list): List of 256 binary values (0 or 1) for the grid.
        y_start (int): Starting Y coordinate for drawing.
        x_start (int): Starting X coordinate for drawing.
    """
    # Draw each cell based on binary value
    for i in range(16):
        for j in range(16):
            if binary_list[i*16 + j]:
                stdscr.addstr(y_start + i, x_start + j*2, "  ", curses.color_pair(1))
            else:
                stdscr.addstr(y_start + i, x_start + j*2, "  ")

def cli_menu():
    """Initialize and run the interactive CLI menu using curses.

    Sets up the main menu and delegates to sub-menus for data management, web server control, and model testing.
    """
    def main_menu(stdscr):
        """Display and handle the main menu.

        Args:
            stdscr: The curses window object.
        """
        # Initialize curses settings
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
        options = ["Manage Data", "Manage Web Server", "Test Model", "Quit"]
        current = 0
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw menu
            stdscr.clear()
            stdscr.addstr(0, 0, "MAIN MENU", curses.A_BOLD)
            for i, opt in enumerate(options):
                if i == current:
                    stdscr.addstr(i+2, 0, f"> {opt} ", curses.color_pair(2))
                else:
                    stdscr.addstr(i+2, 0, f"  {opt} ")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_UP:
                current = (current - 1) % len(options)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(options)
            elif key == ord('\n'):
                if current == 0:
                    manage_data(stdscr)
                elif current == 1:
                    manage_web_server(stdscr)
                elif current == 2:
                    test_model(stdscr)
                elif current == 3:
                    break

    def manage_web_server(stdscr):
        """Manage the web server state and deployment options.

        Args:
            stdscr: The curses window object.
        """
        options = ["Check Status", "Start Server", "Stop Server", "View Traffic", "Configure Deployment"]
        current = 0
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw menu
            stdscr.clear()
            stdscr.addstr(0, 0, "MANAGE WEB SERVER", curses.A_BOLD)
            for i, opt in enumerate(options):
                if i == current:
                    stdscr.addstr(i+2, 0, f"> {opt} ", curses.color_pair(2))
                else:
                    stdscr.addstr(i+2, 0, f"  {opt} ")
            stdscr.addstr(14, 0, "Arrows: ↑/↓ | Enter: Select | Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_UP:
                current = (current - 1) % len(options)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(options)
            elif key == ord('\n'):
                if current == 0:  # Check Status
                    response = send_command("web_status")
                    stdscr.addstr(16, 0, response.get("message", "Error checking status"))
                    stdscr.refresh()
                    time.sleep(0.8)
                elif current == 1:  # Start Server
                    response = send_command("start_web")
                    stdscr.addstr(16, 0, response.get("message", "Error starting server"))
                    stdscr.refresh()
                    time.sleep(0.8)
                elif current == 2:  # Stop Server
                    response = send_command("stop_web")
                    stdscr.addstr(16, 0, response.get("message", "Error stopping server"))
                    stdscr.refresh()
                    time.sleep(0.8)
                elif current == 3:  # View Traffic
                    response = send_command("web_traffic")
                    stats = response.get("data", {})
                    stdscr.addstr(16, 0, f"Requests: {stats.get('requests', 0)}")
                    stdscr.addstr(17, 0, f"Errors: {stats.get('errors', 0)}")
                    stdscr.refresh()
                    stdscr.getch()
                elif current == 4:  # Configure Deployment
                    configure_deployment(stdscr)
            elif key == 27:
                break

    def configure_deployment(stdscr):
        """Configure web server deployment settings (local/LAN, ports).

        Args:
            stdscr: The curses window object.
        """
        options = ["Set Local", "Set LAN", "Open Ports", "Check Ports"]
        current = 0
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw menu
            stdscr.clear()
            stdscr.addstr(0, 0, "CONFIGURE DEPLOYMENT", curses.A_BOLD)
            for i, opt in enumerate(options):
                if i == current:
                    stdscr.addstr(i+2, 0, f"> {opt} ", curses.color_pair(2))
                else:
                    stdscr.addstr(i+2, 0, f"  {opt} ")
            stdscr.addstr(14, 0, "Arrows: ↑/↓ | Enter: Select | Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_UP:
                current = (current - 1) % len(options)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(options)
            elif key == ord('\n'):
                if current == 0:  # Set Local
                    response = send_command("set_web_host local")
                    stdscr.addstr(16, 0, response.get("message", "Error setting host"))
                    stdscr.refresh()
                    time.sleep(0.8)
                elif current == 1:  # Set LAN
                    response = send_command("set_web_host lan")
                    stdscr.addstr(16, 0, response.get("message", "Error setting host"))
                    stdscr.refresh()
                    time.sleep(0.8)
                elif current == 2:  # Open Ports
                    stdscr.addstr(16, 0, "Run manually:")
                    stdscr.addstr(17, 0, "sudo ufw allow 5000  # Web server")
                    stdscr.addstr(18, 0, "sudo ufw allow 9999  # Admin access")
                    stdscr.addstr(20, 0, "Press any key to continue")
                    stdscr.refresh()
                    stdscr.getch()
                elif current == 3:  # Check Ports
                    stdscr.addstr(16, 0, "Run manually: sudo ufw status")
                    stdscr.addstr(18, 0, "Press any key to continue")
                    stdscr.refresh()
                    stdscr.getch()
            elif key == 27:
                break

    def manage_data(stdscr):
        """Manage database entities (feedbacks, training batches, models).

        Args:
            stdscr: The curses window object.
        """
        options = ["Feedbacks", "Training Batches", "Models"]
        current = 0
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw menu
            stdscr.clear()
            stdscr.addstr(0, 0, "MANAGE DATA", curses.A_BOLD)
            for i, opt in enumerate(options):
                if i == current:
                    stdscr.addstr(i+2, 0, f"> {opt} ", curses.color_pair(2))
                else:
                    stdscr.addstr(i+2, 0, f"  {opt} ")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_UP:
                current = (current - 1) % len(options)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(options)
            elif key == ord('\n'):
                if current == 0:
                    view_feedbacks(stdscr)
                elif current == 1:
                    list_batches(stdscr)
                elif current == 2:
                    display_models(stdscr)
            elif key == 27:
                break

    def view_feedbacks(stdscr):
        """View and manage feedback entries in the SQLite database.

        Args:
            stdscr: The curses window object.
        """
        current_id = 1
        # Fetch feedback IDs
        response = send_command("list_feedbacks")
        feedback_ids = [f["id"] for f in response.get("data", [])] if "data" in response else []
        max_id = max(feedback_ids, default=0)
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw feedback view
            stdscr.clear()
            response = send_command(f"get_feedback {current_id}")
            fb = response.get("data", {})
            stdscr.addstr(0, 0, f"FEEDBACK ID: {current_id}", curses.A_BOLD)
            if not fb or fb.get("image_criter") == '0' * 64 or fb.get("prob_max") is None:
                stdscr.addstr(2, 0, "Feedback deleted")
            else:
                # Display feedback grid
                binary_list = hex_to_binary(fb["image_criter"])
                draw_grid(stdscr, binary_list, 2, 0)
                stdscr.addstr(2, 35, f"Detected digit: {fb['prob_max']}")
                stdscr.addstr(3, 35, f"Date: {fb['date']}")
                stdscr.addstr(4, 35, f"Model ID: {fb['id_version_modele']}")
            stdscr.addstr(20, 0, "Arrows: ←/→ | Enter: ID | Tab: Create batch | Del: Delete | Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_LEFT:
                current_id = max(1, current_id - 1)
            elif key == curses.KEY_RIGHT:
                current_id = min(max_id, current_id + 1)
            elif key == ord('\n'):
                # Prompt for feedback ID
                stdscr.addstr(22, 0, "Enter ID: ")
                curses.echo()
                new_id = stdscr.getstr(22, 10, 3).decode()
                curses.noecho()
                try:
                    new_id = int(new_id)
                    if 1 <= new_id <= max_id:
                        current_id = new_id
                except:
                    pass
            elif key == 9:  # Tab: Create batch
                # Prompt for batch range
                stdscr.addstr(22, 0, "Min feedback ID: ")
                curses.echo()
                id_min = stdscr.getstr(22, 15, 3).decode()
                stdscr.addstr(23, 0, "Max feedback ID: ")
                id_max = stdscr.getstr(23, 15, 3).decode()
                curses.noecho()
                try:
                    id_min, id_max = int(id_min), int(id_max)
                    if 1 <= id_min <= id_max <= max_id:
                        response = send_command(f"add_training_batch {id_min} {id_max}")
                        stdscr.addstr(24, 0, response.get("message", "Error creating batch"))
                    else:
                        stdscr.addstr(24, 0, "Error: Invalid IDs")
                except:
                    stdscr.addstr(24, 0, "Error: Invalid input")
                stdscr.refresh()
                time.sleep(0.8)
            elif key == curses.KEY_DC:  # Delete
                # Confirm deletion
                stdscr.addstr(22, 0, "Confirm deletion (y/n): ")
                confirm = stdscr.getch()
                if confirm == ord('y'):
                    response = send_command(f"delete_feedback {current_id}")
                    stdscr.addstr(23, 0, response.get("message", "Error deleting feedback"))
                    stdscr.refresh()
                    time.sleep(0.8)
            elif key == 27:
                break

    def list_batches(stdscr):
        """List and manage training batches in the SQLite database.

        Args:
            stdscr: The curses window object.
        """
        start = 0
        current = 0
        # Fetch batch data
        response = send_command("list_training_batches")
        batches = response.get("data", [])
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw batch list
            stdscr.clear()
            stdscr.addstr(0, 0, "TRAINING BATCHES", curses.A_BOLD)
            displayed = [batch for batch in batches[start:start+10] if batch["id_min_feedback"] is not None]
            for i, batch in enumerate(displayed):
                if i == current:
                    stdscr.addstr(i+2, 0, f"> ID: {batch['id']} Min: {batch['id_min_feedback']} Max: {batch['id_max_feedback']} ", curses.color_pair(2))
                else:
                    stdscr.addstr(i+2, 0, f"  ID: {batch['id']} Min: {batch['id_min_feedback']} Max: {batch['id_max_feedback']} ")
            stdscr.addstr(14, 0, "Arrows: ↑/↓ | Enter: Select | 'a': Create model | Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_UP:
                if current > 0:
                    current -= 1
                elif start > 0:
                    start -= 1
                    current = 0
            elif key == curses.KEY_DOWN:
                if current < len(displayed) - 1:
                    current += 1
                elif start + 10 < len(batches):
                    start += 1
                    current = len(displayed) - 1
            elif key == ord('a'):
                # Prompt for model creation
                stdscr.addstr(16, 0, "Min batch ID: ")
                curses.echo()
                id_min = stdscr.getstr(16, 12, 3).decode()
                stdscr.addstr(17, 0, "Max batch ID: ")
                id_max = stdscr.getstr(17, 12, 3).decode()
                curses.noecho()
                try:
                    id_min, id_max = int(id_min), int(id_max)
                    if 1 <= id_min <= id_max <= max([batch["id"] for batch in batches], default=0):
                        response = send_command(f"add_model {id_min} {id_max}")
                        stdscr.addstr(18, 0, response.get("message", "Error creating model"))
                    else:
                        stdscr.addstr(18, 0, "Error: Invalid IDs")
                except:
                    stdscr.addstr(18, 0, "Error: Invalid input")
                stdscr.refresh()
                time.sleep(0.8)
            elif key == ord('\n') and displayed:
                # Handle batch actions
                stdscr.addstr(16, 0, "1. Submit training | 2. Delete batch")
                action = stdscr.getch()
                if action == ord('1'):
                    stdscr.addstr(17, 0, "Training submitted.")
                    stdscr.refresh()
                    time.sleep(0.8)
                elif action == ord('2'):
                    batch = displayed[current]
                    response = send_command(f"delete_training_batch {batch['id']}")
                    stdscr.addstr(17, 0, response.get("message", "Error deleting batch"))
                    stdscr.refresh()
                    time.sleep(0.8)
            elif key == 27:
                break

    def display_models(stdscr):
        """Display a bar chart of model losses in the SQLite database.

        Args:
            stdscr: The curses window object.
        """
        start = 0
        # Fetch model data
        response = send_command("list_models")
        models = response.get("data", [])
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw model chart
            stdscr.clear()
            stdscr.addstr(0, 0, "MODELS", curses.A_BOLD)
            displayed = [m for m in models[start:start+10] if m["perte_moyenne"] is not None]
            if displayed:
                # Calculate scaling for bar chart
                max_loss = max(m["perte_moyenne"] for m in displayed)
                min_loss = min(m["perte_moyenne"] for m in displayed)
                for i in range(20, 0, -1):
                    loss = min_loss + (max_loss - min_loss) * (i-1) / 19 if max_loss > min_loss else min_loss
                    if i == 20:
                        stdscr.addstr(21 - i, 0, f"{max_loss:.1f} ")
                    elif i == 1:
                        stdscr.addstr(21 - i, 0, f"{min_loss:.1f} ")
                    else:
                        stdscr.addstr(21 - i, 0, " " * 4)
                    # Draw bars
                    for j, m in enumerate(displayed):
                        bar_height = int((m["perte_moyenne"] - min_loss) / (max_loss - min_loss) * 19) + 1 if max_loss > min_loss else 1
                        if i <= bar_height:
                            stdscr.addstr(21 - i, 5 + j*3, "  ", curses.color_pair(1))
                        else:
                            stdscr.addstr(21 - i, 5 + j*3, "  ")
                # Display model IDs
                ids = " ".join(str(m["id_version"]).rjust(2) for m in displayed)
                stdscr.addstr(22, 0, f"IDs {ids}")
            stdscr.addstr(24, 0, "Arrows: ←/→ | Enter: ID | Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == curses.KEY_LEFT:
                start = max(0, start - 1)
            elif key == curses.KEY_RIGHT:
                start = min(len(models) - 10, start + 1)
            elif key == ord('\n'):
                # Prompt for model ID
                stdscr.addstr(26, 0, "Enter ID: ")
                curses.echo()
                id_version = stdscr.getstr(26, 10, 3).decode()
                curses.noecho()
                try:
                    id_version = int(id_version)
                    response = send_command(f"get_model {id_version}")
                    m = response.get("data", {})
                    if m and m["perte_moyenne"] is not None:
                        stdscr.addstr(27, 0, f"Date: {m['date']} | Loss: {m['perte_moyenne']}")
                        stdscr.addstr(28, 0, "Delete? (y/n): ")
                        confirm = stdscr.getch()
                        if confirm == ord('y'):
                            response = send_command(f"delete_model {id_version}")
                            stdscr.addstr(29, 0, response.get("message", "Error deleting model"))
                            stdscr.refresh()
                            time.sleep(0.8)
                except:
                    pass
            elif key == 27:
                break

    def test_model(stdscr):
        """Test the machine learning model with a random noisy grid.

        Args:
            stdscr: The curses window object.
        """
        while True:
            # Verify window size
            if not check_window_size(stdscr):
                continue
            # Clear and draw test menu
            stdscr.clear()
            stdscr.addstr(0, 0, "TEST MODEL", curses.A_BOLD)
            stdscr.addstr(2, 0, "Press 'g' to generate and test a random grid")
            stdscr.addstr(3, 0, "Esc: Back")
            stdscr.refresh()
            # Handle user input
            key = stdscr.getch()
            if key == ord('g'):
                # Send test command to daemon
                response = send_command("test_model")
                stdscr.clear()
                stdscr.addstr(0, 0, "TEST MODEL - RESULT", curses.A_BOLD)
                if "error" in response:
                    stdscr.addstr(2, 0, response["error"])
                    stdscr.addstr(4, 0, "Press any key to continue")
                    stdscr.refresh()
                    stdscr.getch()
                    continue
                # Display test results
                image_criter = response.get("image_criter")
                predicted_digit = response.get("predicted_digit")
                if image_criter and predicted_digit is not None:
                    binary_list = hex_to_binary(image_criter)
                    draw_grid(stdscr, binary_list, 2, 0)
                    stdscr.addstr(2, 35, f"Predicted digit: {predicted_digit}")
                    stdscr.addstr(4, 35, "Is the model correct? (y/n): ")
                    stdscr.refresh()
                    # Handle validation input
                    confirm = stdscr.getch()
                    if confirm == ord('y'):
                        stdscr.addstr(5, 35, "Model validated.")
                    elif confirm == ord('n'):
                        stdscr.addstr(5, 35, "Model incorrect.")
                    stdscr.addstr(20, 0, "Press any key to continue")
                    stdscr.refresh()
                    stdscr.getch()
                else:
                    stdscr.addstr(2, 0, "Error during model test")
                    stdscr.addstr(4, 0, "Press any key to continue")
                    stdscr.refresh()
                    stdscr.getch()
            elif key == 27:  # Esc to exit
                break

    # Start the curses wrapper
    curses.wrapper(main_menu)

def main():
    """Handle command-line arguments and control the daemon or CLI.

    Supports 'connect' to open the CLI, 'stop' to stop the daemon, or no arguments to start the daemon.
    """
    if len(sys.argv) == 1:
        if check_daemon():
            print("Daemon already running, do:")
            print('- "python3 app connect" to open the CLI')
            print('- "python3 app stop" to stop the daemon')
        else:
            start_daemon()
    elif sys.argv[1] == "connect":
        if check_daemon():
            cli_menu()
        else:
            print("Daemon not running. Run 'python3 app' to start the daemon.")
    elif sys.argv[1] == "stop":
        if check_daemon():
            response = send_command("stop")
            print(response.get("message", "Error stopping daemon"))
        else:
            print("Daemon not running.")
    else:
        print("Unknown command. Use 'connect' to connect or 'stop' to stop the daemon.")

if __name__ == "__main__":
    main()