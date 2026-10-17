import json
import math

# Classe Tensor pour tenseurs 1D/2D au format dictionnaire imbriqué
class Tensor:
    def __init__(self, data):
        """Initialise un tenseur à partir d'un dictionnaire.
        
        Args:
            data (dict): Dictionnaire imbriqué, ex. pour 1D: {'1': [1.0, 2.0]},
                        pour 2D: {'1': {'1': [1.0], '2': [2.0]}}.

        Exemple:
            Tensor({'1': [1.0, 0.0, 1.0]})  # Tenseur 1D de taille 3
        """
        self.data = data
        first_val = next(iter(data.values()))
        self.shape = (len(first_val),) if isinstance(first_val, list) else (len(data), len(next(iter(first_val.values()))))
    
    def __add__(self, other):
        """Additionne deux tenseurs de même forme.
        
        Args:
            other (Tensor): Tenseur à ajouter.

        Returns:
            Tensor: Résultat de l'addition.
        """
        result_data = {}
        for k in self.data:
            result_data[k] = [a + b for a, b in zip(self.data[k], other.data[k])]
        return Tensor(result_data)
    
    def __mul__(self, other):
        """Multiplication matricielle (2D × 1D → 1D).
        
        Args:
            other (Tensor): Tenseur 1D à multiplier.

        Returns:
            Tensor: Tenseur 1D résultant.
        """
        result_data = {}
        for i in self.data:
            row = []
            for j in range(len(other.data['1'])):
                sum_val = sum(self.data[i][k] * other.data['1'][k] for k in range(len(self.data[i])))
                row.append(sum_val)
            result_data[i] = row
        return Tensor({'1': [v for row in result_data.values() for v in row[:1]]})

# Classe Linear pour les couches linéaires
class Linear:
    def __init__(self, weights_data, bias_data):
        """Initialise une couche linéaire avec poids et biais.
        
        Args:
            weights_data (dict): Poids 2D, ex. {'1': [w11, w12, ...], '2': [w21, w22, ...]}.
            bias_data (dict): Biais 1D, ex. {'1': [b1, b2, ...]}.
        """
        self.weights = Tensor(weights_data)  # Tenseur 2D
        self.bias = Tensor(bias_data)  # Tenseur 1D
    
    def forward(self, input_tensor):
        """Effectue une projection linéaire : y = W * x + b.
        
        Args:
            input_tensor (Tensor): Tenseur 1D d'entrée, ex. {'1': [1.0, 0.0, ...]}.

        Returns:
            Tensor: Tenseur 1D de sortie.
        """
        output = self.weights * input_tensor  # Matmul
        output = output + self.bias  # Ajout biais
        return output

# Fonctions d'activation
def relu(input_tensor):
    """Applique ReLU : max(0, x) à chaque élément.
    
    Args:
        input_tensor (Tensor): Tenseur 1D, ex. {'1': [1.0, -2.0, 3.0]}.

    Returns:
        Tensor: Tenseur 1D avec valeurs ≥ 0.
    """
    result_data = {'1': [max(0.0, x) for x in input_tensor.data['1']]}
    return Tensor(result_data)

def softmax(input_tensor):
    """Applique softmax : exp(x_i) / Σ(exp(x_j)).
    
    Args:
        input_tensor (Tensor): Tenseur 1D, ex. {'1': [1.0, 2.0, 3.0]}.

    Returns:
        Tensor: Tenseur 1D de probabilités (somme = 1).
    """
    values = input_tensor.data['1']
    exp_values = [math.exp(min(max(x, -100), 100)) for x in values]
    total = sum(exp_values)
    result_data = {'1': [x / total if total > 0 else 1.0 / len(values) for x in exp_values]}
    return Tensor(result_data)

# Charger les poids depuis JSON
def load_weights_json(file):
    """Charge les poids depuis model_weights.json.
    
    Returns:
        tuple: (weights, biases), dictionnaires des poids et biais pour chaque couche.
    """
    with open(file, "r") as f:
        weights_dict = json.load(f)
    weights = {}
    biases = {}
    weights['IN'] = weights_dict['IN.weight']
    biases['IN'] = weights_dict['IN.bias']
    for i in range(5):
        weights[f'hidden.{i}'] = weights_dict[f'hidden.{i}.weight']
        biases[f'hidden.{i}'] = weights_dict[f'hidden.{i}.bias']
    weights['OUT'] = weights_dict['OUT.weight']
    biases['OUT'] = weights_dict['OUT.bias']
    return weights, biases

# Modèle
class Model:
    def __init__(self, file):
        """Initialise le modèle avec les poids chargés depuis JSON."""
        weights, biases = load_weights_json(file)
        self.IN = Linear(weights['IN'], biases['IN'])  # 256 -> 64
        self.hidden = [Linear(weights[f'hidden.{i}'], biases[f'hidden.{i}']) for i in range(5)]  # 64 -> 64
        self.OUT = Linear(weights['OUT'], biases['OUT'])  # 64 -> 10
    
    def forward(self, x):
        """Effectue une passe avant : IN -> ReLU -> 5x(hidden -> ReLU) -> OUT -> softmax.
        
        Args:
            x (Tensor): Tenseur 1D de 256 valeurs binaires (0.0 ou 1.0),
                       ex. {'1': [1.0, 0.0, 1.0, ..., 0.0]}.

        Returns:
            Tensor: Tenseur 1D de 10 probabilités (softmax),
                   ex. {'1': [0.5, 0.1, 0.05, ...]}.
        """
        x = relu(self.IN.forward(x))
        for layer in self.hidden:
            x = relu(layer.forward(x))
        x = self.OUT.forward(x)
        x = softmax(x)
        return x

# Test d'inférence
if __name__ == "__main__":
    # Exemple d'entrée : grille binaire 1D (256 valeurs)
    example_input = Tensor({'1': [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] + [0.0] * 240})
    model = Model()
    output = model.forward(example_input)
    print(output.data["1"])
