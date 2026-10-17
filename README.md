# Digit Recognition Web Application in Python
Resumption of a computer science course project from 2024-25. Updated and maintained.

>60% was created with the help of AI (such as the JS code).
Our goal is not to recreate everything from scratch, but rather to implement missing features and improve deployment.

At the time, I was trying to code without external libraries, and I didn't know JS (which is still the case as of this commit in 2026).
Using NumPy for the ML component is an option, as is revisiting the JS code.

---
---

## Overview

This web application recognizes digits (0-9) drawn on a 16x16 binary grid using a custom machine learning model implemented in native Python. It features a public interface for drawing and predicting digits, and an admin interface for managing feedback, training batches, and models. The application uses Flask for the web backend, SQLite for data storage, and a TCP socket daemon for handling requests. The daemon runs autonomously, initializing the database and serving web interfaces.

## Dependencies

- Flask==3.1.0
- flask-cors==5.0.1
- Python 3.10+ (standard libraries: sqlite3, json, os, subprocess, threading, socket, datetime, random, curses)

## Installation

1. Clone the repo.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
3. Ensure `app/data/model_weights.json` (280.8 KB) is present in the `app/data/` directory.

## Usage

1. Start the daemon (auto-initializes database and web server):

   ```bash
   python app
   ```
2. Access web interfaces:
   - Public: `http://127.0.0.1:20000/`
   - Admin: `http://127.0.0.1:20000/admin`
3. Use the CLI for management:
   - Connect: `python app connect`
   - Stop: `python app stop`

## Database Management

The application uses an SQLite database (`app/data/database.db`) to store feedback, models, and training batches. The database is automatically initialized when the daemon starts (`python app`) using the `app/data/schema.sql` script.

### Features

- **Tables**:
  - `Modeles`: Stores model versions with loss (`perte_moyenne`) and creation date.
  - `Feedbacks`: Stores user-submitted 16x16 grids (`image_criter`, hex-encoded), predicted digit (`prob_max`), submission date, and model version.
  - `Lots_Entrainement`: Tracks training batches with feedback ranges and generated model.
- **Initialization**:
  - Creates tables and inserts initial data: one default model, a default feedback (`F*64`), and 10 reference grids for digits 0-9.
  - Verifies data integrity on startup.
- **Operations**:
  - CRUD functions for feedbacks, models, and batches, accessible via CLI (`python app connect`) and admin interface (`http://127.0.0.1:20000/admin`).
  - Logical deletion (e.g., sets feedback to `0*64` instead of removing it).
- **Testing**:
  - Generates noisy grids for model testing based on reference digit patterns.

## Daemon and Web Server

The daemon (`app/__deamon__.py`) handles TCP requests (port 9999) and hosts a Flask web server (port 20000). It coordinates database operations, model predictions, and web interfaces.

### Features

- **TCP Server**:
  - Processes commands like `list_feedbacks`, `add_model`, `test_model`, and `stop`.
  - Accessible via CLI (`python app connect`).
- **Web Server**:
  - Serves public interface (`http://127.0.0.1:20000/`) for drawing/predicting digits.
  - Serves admin interface (`http://127.0.0.1:20000/admin`) for managing data like the `app/__main__.py`.
  - Handles predictions (`/predict`) and feedback submission (`/feedback`).
- **Startup**:
  - Initializes the database and loads the ML model (`app/data/model_weights.json`).
  - Runs automatically with `python app`.
- **Control**:
  - Start: `python app`
  - Connect (CLI): `python app connect`
  - Stop (damon): `python app stop`

## Machine Learning Model

The neural network (`app/framework.py`) recognizes digits from 16x16 binary grids. Initially developed in C++ with pybind11, it was rewritten in native Python to resolve issues with a model layer and eliminate dependencies.

### Features

- **Structure**:
  - Input layer: 256 → 64 (ReLU).
  - 5 hidden layers: 64 → 64 (ReLU).
  - Output layer: 64 → 10 (softmax, probabilities for digits 0-9).
- **Components**:
  - `Tensor`: Handles 1D/2D tensors as nested dictionaries for matrix operations.
  - `Linear`: Implements linear layers (weights × input + bias).
  - `relu` and `softmax`: Activation functions.
- **Weights**:
  - Loaded from `app/data/model_weights.json` (280.8 KB) at startup.
- **Training**:
  - Trained externally with PyTorch 2.4 on a GPU (\~80 W) for 117.38 seconds using &gt;1M generated samples (similar to `test_model` grids).
  - Fine-tuning is simulated due to implementation complexity.
- **Inference**:
  - Takes a 256-bit binary grid (as a tensor) and outputs probabilities.
  - Used in web predictions (`/predict`) and CLI tests (`python app connect`, "Test Model").
- **Example: Creating a Tensor**:

  ```python
  from framework import Tensor
  grid = [1.0, 0.0, 0.0, 1.0] + [0.0] * 252  # 16x16 grid
  tensor = Tensor({'1': grid})
  print(tensor.shape)  # Output: (256,)
  ```

## Command-Line Interface

The CLI (`app/__main__.py`) provides a remote interface to interact with the daemon via TCP (port 9999). It allows managing data, the web server, and model testing, locally or over a WAN (e.g., via SSH tunnel).

### Features

- **Daemon Control**:
  - Start: `python app`
  - Connect: `python app connect`
  - Stop: `python app stop`
- **Data Management**:
  - View/delete feedbacks, manage training batches, inspect model performance.
  - Displays 16x16 grids for feedbacks.
- **Web Server Control**:
  - Check status, start/stop, view traffic, configure host (local/LAN).
- **Model Testing**:
  - Tests the model with random noisy grids.
- **Remote Access**:
  - Supports remote management via SSH tunnel (e.g., `ssh -L 9999:localhost:9999 user@server`).
- **Note**:
  - Fine-tuning is not implemented due to implementation challenges (not computational power); new models are simulated.

### CLI Example

List and navigate feedbacks:

```bash
python app connect
# Select "Manage Data" -> "Feedbacks" -> use arrows or enter ID
```

## Web Interfaces

The application provides two web interfaces (`app/templates/index.html`, `app/templates/admin.html`) served by Flask (port 20000).

### Public Interface (`index.html`)

- **URL**: `http://127.0.0.1:20000/`
- **Features**:
  - Draw a digit on a 16x16 grid.
  - Submit for prediction (displays probabilities as a chart).
  - Send feedback to store the grid and predicted digit.
  - Reset the grid.
  - Link to the admin interface.

### Admin Interface (`admin.html`)

- **URL**: `http://127.0.0.1:20000/admin`
- **Features**:
  - **Feedbacks**: View 16x16 grids with details (ID, predicted digit, date, model), navigate, delete, create batches.
  - **Training Batches**: List batches (ID, feedback range), navigate, delete, create models.
  - **Models**: Display model losses as a chart, view details (ID, loss, date), navigate, delete.
  - Tab-based navigation with confirmation for critical actions.

## Web Interface Styling and Interactivity

The interfaces are styled by `app/static/css/styles.css` and made interactive by `app/static/js/script.js`.

### Styling (`styles.css`)

- **Features**:
  - Consistent layout with Arial font, light background, flexible design.
  - Sticky header, centered content (max 1200px), box-shadow for depth.
  - Interactive 16x16 grid (20x20px cells, toggle black/white).
  - Styled buttons, tabs, tables, SVG charts with hover effects.
  - Responsive design for small screens (&lt;600px).
- **Purpose**:
  - Ensures a clean, professional look.

### Interactivity (`script.js`)

- **Features**:
  - **Grid Management**: Initializes/toggles grids in `index.html`, displays feedback grids in `admin.html`.
  - **HTTP Requests**: Sends grids (`/predict`), submits feedback (`/feedback`), relays admin commands (`/tcp_relay`).
  - **Charts**: Generates SVG bar charts for probabilities and model losses.
  - **Admin Navigation**: Handles tabs, feedback/lot/model navigation, deletion, batch/model creation.
  - **Error Handling**: Validates inputs, displays errors.
- **Purpose**:
  - Enables dynamic user interactions.

## Project Structure

The zip (`Python_Number_recognition.zip`) contains all necessary files. Some files (e.g., `app/data/database.db`, `flask_server.py`) are generated at runtime.

**\[Placeholder for final project structure\]**

```
.
├── app
│   ├── data
│   │   ├── database.db  # Generated
│   │   ├── model_weights.json
│   │   └── schema.sql
│   ├── __deamon__.py
│   ├── framework.py
│   ├── __gestion_sql__.py
│   ├── __main__.py
├── README.md
├── requirements.txt
├── static
│   ├── css
│   │   └── styles.css
│   ├── js
│   │   └── script.js
├── templates
│   ├── admin.html
│   ├── index.html
```

## Compatibility

Tested in Ubuntu 22.04 with Python 3.10. The application runs on Python 3.10+ in a clean environment. Annexes (e.g., `specs.pdf`) are for submission, not runtime.

## Credits

- **Grok 3** (xAI) translates this `README.md` into English and writes/translates code comments and docstrings.