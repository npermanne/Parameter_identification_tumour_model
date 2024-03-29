import matplotlib.pyplot as plt
from networks.dataLoader import SimulationDataset
import numpy as np
from networks.architecture import Net
from torch.utils.data import DataLoader
import torch
import torch.nn as nn
import os
import pandas as pd

# Random Seed
np.random.seed(2990)
torch.manual_seed(2990)

# Parameters
RESULTS_FOLDER = "results"


######################################################################################
#
# CLASS DESCRIBING THE INSTANTIATION, TRAINING AND EVALUATION OF THE MODEL
#
######################################################################################

class Network:
    # --------------------------------------------------------------------------------
    # INITIALISATION OF THE MODEL
    # INPUTS:
    #     - param (dic): dictionary containing the parameters defined in the
    #                    configuration (yaml) file
    # --------------------------------------------------------------------------------
    def __init__(self, param):
        # USEFUL VARIABLES
        self.img_types = param["DATASET"]["IMG_TYPES"]
        self.n_draws = param["DATASET"]["N_DRAWS"]
        self.parameter_of_interest = param["DATASET"]["PARAMETERS_OF_INTEREST"]
        self.batch_size = param["TRAINING"]["BATCH_SIZE"]
        self.epochs = param["TRAINING"]["EPOCH"]
        self.name = param["NAME"]

        # CREATE FOLDER FOR SAVING
        folder_path = os.path.join(RESULTS_FOLDER, self.name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.path_weight = os.path.join(folder_path, "weight.pkl")
        self.path_performance_curve = os.path.join(folder_path, "performance_curve.png")
        self.path_test_data = os.path.join(folder_path, "test_data.csv")

        # LOAD DATASET
        self.train_dataset = SimulationDataset("train", param["DATASET"]["FOLDER_NAME"],
                                               self.n_draws, self.parameter_of_interest, self.img_types)
        self.val_dataset = SimulationDataset("val", param["DATASET"]["FOLDER_NAME"],
                                             self.n_draws, self.parameter_of_interest, self.img_types)
        self.test_dataset = SimulationDataset("test", param["DATASET"]["FOLDER_NAME"],
                                              self.n_draws, self.parameter_of_interest, self.img_types)
        self.train_dataloader = DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=4)
        self.val_dataloader = DataLoader(self.val_dataset, batch_size=self.batch_size, shuffle=False, num_workers=4)
        self.test_dataloader = DataLoader(self.test_dataset, batch_size=self.batch_size, shuffle=False, num_workers=4)

        # ARCHITECTURE INITIALIZATION
        self.param_architecture = {
            "N_DRAWS": self.n_draws,
            "N_TYPES": len(self.img_types),
            "INPUT_LSTM": param["MODEL"]["INPUT_LSTM"],
            "OUTPUT_LSTM": param["MODEL"]["INPUT_LSTM"],
            "BATCH_SIZE": self.batch_size,
            "HEIGHT": self.train_dataset.get_height(),
            "WIDTH": self.train_dataset.get_width(),
            "N_PARAMS": len(param["DATASET"]["PARAMETERS_OF_INTEREST"])
        }
        self.network = Net(self.param_architecture).to(param["TRAINING"]["DEVICE"])

        # TRAINING PARAMETERS
        self.optimizer = torch.optim.Adam(self.network.parameters())
        self.criterion = nn.MSELoss()

    ###############################
    # LOAD WEIGHTS
    ###############################
    def load_weights(self):
        self.network.load_state_dict(torch.load(self.path_weight))

    ###############################
    # TRAINING LOOP
    ###############################
    def train(self):
        validation_losses = np.zeros(self.epochs)
        losses = np.zeros(self.epochs)

        # EPOCHS ITERATIONS
        for iter_epoch in range(self.epochs):
            print("Epoch {}/{}".format(iter_epoch, self.epochs), end='\r')

            # TRAINING
            running_loss = 0
            for iter_train, data in enumerate(self.train_dataloader):
                inputs, outputs, outputs_scaled = data
                # Forward Pass
                predicted = self.network.forward(inputs)
                loss = self.criterion(predicted, outputs_scaled)

                # Backpropagation
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                # Loss data
                running_loss += loss.item()

            losses[iter_epoch] = running_loss / (iter_train + 1)

            # VALIDATION
            running_validation_loss = 0
            with torch.no_grad():
                for iter_val, data in enumerate(self.val_dataloader):
                    validation_inputs, validation_outputs, validation_outputs_scaled = data

                    # Forward Pass
                    predicted = self.network.forward(validation_inputs)
                    validation_loss = self.criterion(predicted, validation_outputs_scaled)

                    # Validation Loss data
                    running_validation_loss += validation_loss.item()

            validation_losses[iter_epoch] = running_loss / (iter_val + 1)

        # SAVE WEIGHT
        torch.save(self.network.state_dict(), self.path_weight)

        # PLOT PERFORMANCE CURVE
        X = np.arange(self.epochs)
        plt.plot(X, losses, label="Training Loss")
        plt.plot(X, validation_losses, label="Validation Loss")
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.legend()
        plt.savefig(self.path_performance_curve)

    ###############################
    # EVALUATION
    ###############################
    def evaluate(self):
        self.network.train(False)
        self.network.eval()

        # EVALUATION LOOP
        differences = None
        for iter_test, data in enumerate(self.test_dataloader):
            test_inputs, test_outputs, test_outputs_scaled = data

            # Forward Pass
            predicted = self.network.forward(test_inputs)

            # Compute individual differences
            if differences is None:
                differences = np.absolute((test_outputs_scaled.numpy() - predicted.detach().numpy()))
            else:
                differences = np.concatenate(
                    (differences, np.absolute((test_outputs_scaled.numpy() - predicted.detach().numpy()))), axis=0)

        data = {
            "Parameters": self.parameter_of_interest,
            "Means": np.mean(differences, axis=0),
            "Standard Deviation": np.std(differences, axis=0)
        }

        df = pd.DataFrame(data)
        df.to_csv(self.path_test_data, index=False)
