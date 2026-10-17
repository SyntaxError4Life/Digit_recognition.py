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