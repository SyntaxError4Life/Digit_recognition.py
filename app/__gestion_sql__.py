import sqlite3
import os
from datetime import datetime
import random

# Reference grids for digits 0 to 9 in hexadecimal format (64 characters each)
INITIAL_GRIDS = {
    0: "03C007E00FF01F383E3C3E3C7C1E7C1E7C1E7C1E3E3C3E3C1F380FF007E003C0",
    1: "0180038007800F801F801F801F801F801F801F801F801F801F801F801F801F80",
    2: "07E01FF83FFC7FFE7E3E023E023E063C0E381E303E207E007FFE7FFE7FFE7FFE",
    3: "07E01FF83FFC7FFE7E3E023E023E07F807F8023E023E7E3E7FFE3FFC1FF807E0",
    4: "03E007E00FE01FE03E703C3C7C3C7C3C7FFE7FFE023C023C023C023C023C023C",
    5: "7FFE7FFE7FFE7FFE7C007C007FE07FF87C3C023E023E7C3E7FFE3FFC1FF807E0",
    6: "07E01FF83FFC7FFE7E3E7C007C007FE07C3C7C3E7C3E7C3E7FFE3FFC1FF807E0",
    7: "7FFE7FFE7FFE7FFE01F001F003F003F007E007E00FC00FC01F801F803F003F00",
    8: "07E01FF83FFC7FFE7E3E3E3C1F3807E007E01F383E3C7E3E7FFE3FFC1FF807E0",
    9: "07E01FF83FFC7FFE7E3E7E3E7E3E7FF87FE001F001F07E3E7FFE3FFC1FF807E0"
}

def get_absolute_path(relative_path: str) -> str:
    """Convert a relative path to an absolute path based on the script's directory.

    Args:
        relative_path (str): The relative path to convert (e.g., 'data/database.db').

    Returns:
        str: The absolute path to the file or directory.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_path = os.path.join(script_dir, relative_path)
    return os.path.normpath(absolute_path)

def initialize_database():
    """Initialize the SQLite database and populate it with initial data if necessary.

    Creates tables using the schema defined in 'data/schema.sql' and inserts a default model,
    feedback entry, and reference grids for digits 0-9. This function is called by `__deamon__.py`
    during the daemon's startup process.

    Raises:
        Exception: If the initial data insertion fails or cannot be verified.
    """
    db_path = get_absolute_path('data/database.db')
    schema_path = get_absolute_path('data/schema.sql')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the 'Modeles' table exists to determine if the database is initialized
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Modeles';")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        # Create the database schema from schema.sql
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        
        # Insert an initial model
        model_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO Modeles (perte_moyenne, date) VALUES (?, ?)", (0.5, model_date))
        model_id = cursor.lastrowid
        
        # Insert the first feedback entry with a placeholder grid ('F' * 64)
        cursor.execute(
            "INSERT INTO Feedbacks (image_criter, prob_max, date, id_version_modele) VALUES (?, ?, ?, ?)",
            ('F' * 64, 0, model_date, model_id)
        )
        first_feedback_id = cursor.lastrowid
        
        # Insert reference grids for digits 0-9 as initial feedback
        feedback_ids = [first_feedback_id]
        for digit, image_criter in INITIAL_GRIDS.items():
            cursor.execute(
                "INSERT INTO Feedbacks (image_criter, prob_max, date, id_version_modele) VALUES (?, ?, ?, ?)",
                (image_criter, digit, model_date, model_id)
            )
            feedback_ids.append(cursor.lastrowid)
        
        # Create an initial training batch linking the feedback range to the model
        cursor.execute(
            "INSERT INTO Lots_Entrainement (id_min_feedback, id_max_feedback, id_modele_genere) VALUES (?, ?, ?)",
            (min(feedback_ids), max(feedback_ids), model_id)
        )
        
        # Verify that the initial data was inserted correctly
        cursor.execute("SELECT id, image_criter FROM Feedbacks WHERE id = ?", (first_feedback_id,))
        result = cursor.fetchone()
        if not result or result[1] != 'F' * 64:
            conn.close()
            raise Exception("Failed to insert initial data into the database")
    else:
        # Ensure the first feedback exists, even if the database already exists
        cursor.execute("SELECT id, image_criter FROM Feedbacks WHERE id = ?", (1,))
        result = cursor.fetchone()
        if not result or result[1] != 'F' * 64:
            model_date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT id_version FROM Modeles ORDER BY id_version DESC LIMIT 1")
            model_id = cursor.fetchone()[0] if cursor.fetchone() else 1
            cursor.execute(
                "INSERT INTO Feedbacks (image_criter, prob_max, date, id_version_modele) VALUES (?, ?, ?, ?)",
                ('F' * 64, 0, model_date, model_id)
            )
    
    conn.commit()
    conn.close()

def insert_feedback(image_criter: str, prob_max: int, date: str, id_version_modele: int) -> int:
    """Insert a new feedback entry into the Feedbacks table.

    Args:
        image_criter (str): A 64-character hexadecimal string representing a 16x16 grid.
        prob_max (int): The predicted digit (0-9) from the model.
        date (str): The submission date in 'YYYY-MM-DD' format.
        id_version_modele (int): The ID of the model version used for the prediction.

    Returns:
        int: The ID of the newly inserted feedback entry.

    Note:
        This function is called by `__deamon__.py` in the '/feedback' endpoint and by the generated
        'flask_server.py' script to store user feedback.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Feedbacks (image_criter, prob_max, date, id_version_modele) VALUES (?, ?, ?, ?)",
        (image_criter, prob_max, date, id_version_modele)
    )
    conn.commit()
    feedback_id = cursor.lastrowid
    conn.close()
    return feedback_id

def get_all_feedbacks() -> list:
    """Retrieve all feedback entries from the Feedbacks table.

    Returns:
        list: A list of tuples, each containing feedback data:
              (id, image_criter, prob_max, date, id_version_modele).
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, image_criter, prob_max, date, id_version_modele FROM Feedbacks")
    feedbacks = cursor.fetchall()
    conn.close()
    return feedbacks

def get_feedback_by_id(feedback_id: int) -> tuple:
    """Retrieve a specific feedback entry by its ID.

    Args:
        feedback_id (int): The ID of the feedback entry to retrieve.

    Returns:
        tuple: Feedback data (id, image_criter, prob_max, date, id_version_modele), or None if not found.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, image_criter, prob_max, date, id_version_modele FROM Feedbacks WHERE id = ?",
        (feedback_id,)
    )
    feedback = cursor.fetchone()
    conn.close()
    return feedback

def mark_feedback_as_deleted(feedback_id: int):
    """Mark a feedback entry as deleted by resetting its values to defaults.

    Sets image_criter to '0'*64, prob_max to 0, date to '1970-01-01', and id_version_modele to 0.
    The entry with ID 1 (initial placeholder) is protected from modification.

    Args:
        feedback_id (int): The ID of the feedback entry to mark as deleted.

    Note:
        This function updates the record instead of deleting it to preserve ID integrity.
    """
    if feedback_id != 1:  # Protect the initial feedback entry
        db_path = get_absolute_path('data/database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Feedbacks SET image_criter = ?, prob_max = ?, date = ?, id_version_modele = ? WHERE id = ?",
            ('0' * 64, 0, '1970-01-01', 0, feedback_id)
        )
        conn.commit()
        conn.close()

def insert_model(loss: float, date: str) -> int:
    """Insert a new model entry into the Modeles table.

    Args:
        loss (float): The average loss value of the model.
        date (str): The creation date of the model in 'YYYY-MM-DD' format.

    Returns:
        int: The ID of the newly inserted model.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Modeles (perte_moyenne, date) VALUES (?, ?)",
        (loss, date)
    )
    conn.commit()
    model_id = cursor.lastrowid
    conn.close()
    return model_id

def get_all_models() -> list:
    """Retrieve all model entries from the Modeles table.

    Returns:
        list: A list of tuples, each containing model data:
              (id_version, perte_moyenne, date).
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id_version, perte_moyenne, date FROM Modeles")
    models = cursor.fetchall()
    conn.close()
    return models

def get_model_by_id(model_id: int) -> tuple:
    """Retrieve a specific model entry by its ID.

    Args:
        model_id (int): The ID of the model to retrieve.

    Returns:
        tuple: Model data (id_version, perte_moyenne, date), or None if not found.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_version, perte_moyenne, date FROM Modeles WHERE id_version = ?",
        (model_id,)
    )
    model = cursor.fetchone()
    conn.close()
    return model

def mark_model_as_deleted(model_id: int):
    """Mark a model entry as deleted by resetting its values to defaults.

    Sets perte_moyenne to 0.0 and date to '1970-01-01'.

    Args:
        model_id (int): The ID of the model to mark as deleted.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Modeles SET perte_moyenne = ?, date = ? WHERE id_version = ?",
        (0.0, '1970-01-01', model_id)
    )
    conn.commit()
    conn.close()

def insert_training_batch(id_min_feedback: int, id_max_feedback: int, id_modele_genere: int) -> int:
    """Insert a new training batch entry into the Lots_Entrainement table.

    Args:
        id_min_feedback (int): The minimum feedback ID included in the batch.
        id_max_feedback (int): The maximum feedback ID included in the batch.
        id_modele_genere (int): The ID of the model generated from this batch.

    Returns:
        int: The ID of the newly inserted training batch.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Lots_Entrainement (id_min_feedback, id_max_feedback, id_modele_genere) VALUES (?, ?, ?)",
        (id_min_feedback, id_max_feedback, id_modele_genere)
    )
    conn.commit()
    batch_id = cursor.lastrowid
    conn.close()
    return batch_id

def get_all_training_batches() -> list:
    """Retrieve all training batch entries from the Lots_Entrainement table.

    Returns:
        list: A list of tuples, each containing batch data:
              (id, id_min_feedback, id_max_feedback, id_modele_genere).
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, id_min_feedback, id_max_feedback, id_modele_genere FROM Lots_Entrainement")
    batches = cursor.fetchall()
    conn.close()
    return batches

def get_training_batch_by_id(batch_id: int) -> tuple:
    """Retrieve a specific training batch entry by its ID.

    Args:
        batch_id (int): The ID of the training batch to retrieve.

    Returns:
        tuple: Batch data (id, id_min_feedback, id_max_feedback, id_modele_genere), or None if not found.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, id_min_feedback, id_max_feedback, id_modele_genere FROM Lots_Entrainement WHERE id = ?",
        (batch_id,)
    )
    batch = cursor.fetchone()
    conn.close()
    return batch

def mark_training_batch_as_deleted(batch_id: int):
    """Mark a training batch entry as deleted by resetting its values to defaults.

    Sets id_min_feedback, id_max_feedback, and id_modele_genere to 0.

    Args:
        batch_id (int): The ID of the training batch to mark as deleted.
    """
    db_path = get_absolute_path('data/database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Lots_Entrainement SET id_min_feedback = ?, id_max_feedback = ?, id_modele_genere = ? WHERE id = ?",
        (0, 0, 0, batch_id)
    )
    conn.commit()
    conn.close()

def generate_test_grid() -> str:
    """Generate a random noisy grid based on reference digits for model testing.

    Selects a random digit (0-9), retrieves its reference grid, applies random noise,
    and returns the result as a hexadecimal string.

    Returns:
        str: A 64-character hexadecimal string representing the noisy grid.

    Note:
        This function is called by `__deamon__.py` when processing the 'test_model' command.
    """
    # Select a random digit (0-9)
    label = random.randint(0, 9)
    # Retrieve the reference grid for the selected digit
    hex_grid = INITIAL_GRIDS[label]
    
    # Convert the hexadecimal string to a binary list (256 bits)
    binary_grid = []
    for char in hex_grid:
        binary = bin(int(char, 16))[2:].zfill(4)
        binary_grid.extend(int(bit) for bit in binary)
    
    # Apply random noise to the grid
    noise_rate = random.uniform(0.1, 0.25)  # Noise between 10% and 25%
    for i in range(len(binary_grid)):
        if random.random() < noise_rate:
            binary_grid[i] = 1 - binary_grid[i]  # Flip the bit
    
    # Convert the binary list back to a hexadecimal string
    hex_result = ""
    for i in range(0, len(binary_grid), 4):
        nibble = binary_grid[i:i+4]
        value = sum(bit * (2 ** (3-j)) for j, bit in enumerate(nibble))
        hex_result += hex(value)[2:].upper()
    
    return hex_result

if __name__ == "__main__":
    initialize_database()

# Database schema overview:
schema = """
CREATE TABLE Modeles (
    id_version INTEGER PRIMARY KEY AUTOINCREMENT,
    perte_moyenne FLOAT NOT NULL,
    date DATE NOT NULL
);

CREATE TABLE Feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_criter VARCHAR(64) NOT NULL,
    prob_max INTEGER NOT NULL,
    date DATE NOT NULL,
    id_version_modele INTEGER,
    FOREIGN KEY (id_version_modele) REFERENCES Modeles(id_version)
);

CREATE TABLE Lots_Entrainement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_min_feedback INTEGER NOT NULL,
    id_max_feedback INTEGER NOT NULL,
    id_modele_genere INTEGER,
    FOREIGN KEY (id_modele_genere) REFERENCES Modeles(id_version)
);
"""