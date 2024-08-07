import matplotlib.pyplot as plt
from networks.dataLoader import SimulationDataset
from networks.early_stopping import EarlyStopper
import numpy as np
from networks.architecture import Net
from torch.utils.data import DataLoader
import torch
import torch.nn as nn
import os
import pandas as pd
from torchinfo import summary

try:
    from tkinter import *
except ModuleNotFoundError:
    pass

# Random Seed
np.random.seed(2990)
torch.manual_seed(2990)

# Parameters
RESULTS_FOLDER = "results"


class Network:
    """
    A class that describe the instantiation, the training and the evaluation of the model

    Parameters:
        param (dict): the parameters of the dataset, the model and the training

    Attributes:
        img_types (list): List containing all the image types that we want to use
        n_draws (int): Number of draws
        parameter_of_interest (list): List of parameters of interest that we want to predict
        batch_size (int): Batch size
        epochs (int): Number of epochs
        name (string): Name of the configuration, will be used for the result folder
        path_weight (string): Path to the weights of the model
        path_performance_curve (string): Path to the performance curve of the training
        path_test_data (string): Path to the result for each parameter
        train_dataset (SimulationDataset): Training dataset
        val_dataset (SimulationDataset): Validation dataset
        test_dataset (SimulationDataset): Testing dataset
        train_dataloader (DataLoader): Training dataloader
        val_dataloader (DataLoader): Validation dataloader
        test_dataloader (DataLoader): Testing dataloader
        param_architecture (dict): Parameters of the architecture
        network (Net): Instance of the architecture
        optimizer (Optimizer): Optimizer (Adams)
        criterion (Loss): Loss function

    Methods:
        load_weights(): Load the weights if any are present
        train(): Train the model and save the weight
        evaluate(): Evaluate the model
    """

    def __init__(self, param):
        # USEFUL VARIABLES
        self.img_types = param["DATASET"]["IMG_TYPES"]
        self.n_draws = param["DATASET"]["N_DRAWS"]
        self.parameter_of_interest = param["DATASET"]["PARAMETERS_OF_INTEREST"]
        self.batch_size = param["TRAINING"]["BATCH_SIZE"]
        self.epochs = param["TRAINING"]["EPOCH"]
        self.learning_rate = param["TRAINING"]["LEARNING_RATE"]
        self.name = param["NAME"]

        # CREATE FOLDER FOR SAVING
        folder_path = os.path.join(RESULTS_FOLDER, self.name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.path_weight = os.path.join(folder_path, "weight.pkl")
        self.path_performance_curve = os.path.join(folder_path, "performance_curve.png")
        self.path_evaluation_data = os.path.join(folder_path, "evaluation_data.csv")
        self.path_evaluation_stats = os.path.join(folder_path, "evaluation_stats.csv")

        # LOAD DATASET
        self.train_dataset = SimulationDataset("train", param["DATASET"]["FOLDER_NAME"],
                                               self.n_draws, self.parameter_of_interest, self.img_types)
        self.val_dataset = SimulationDataset("val", param["DATASET"]["FOLDER_NAME"],
                                             self.n_draws, self.parameter_of_interest, self.img_types)
        self.test_dataset = SimulationDataset("test", param["DATASET"]["FOLDER_NAME"],
                                              self.n_draws, self.parameter_of_interest, self.img_types)
        self.train_dataloader = DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=param["TRAINING"]["NUM_WORKERS"])
        self.val_dataloader = DataLoader(self.val_dataset, batch_size=self.batch_size, shuffle=False, num_workers=param["TRAINING"]["NUM_WORKERS"])
        self.test_dataloader = DataLoader(self.test_dataset, batch_size=self.batch_size, shuffle=False, num_workers=param["TRAINING"]["NUM_WORKERS"])

        # ARCHITECTURE INITIALIZATION
        self.param_architecture = {
            "N_DRAWS": self.n_draws,
            "N_TYPES": len(self.img_types),
            "INPUT_LSTM": param["MODEL"]["INPUT_LSTM"],
            "OUTPUT_LSTM": param["MODEL"]["INPUT_LSTM"],
            "BATCH_SIZE": self.batch_size,
            "HEIGHT": self.train_dataset.get_height(),
            "WIDTH": self.train_dataset.get_width(),
            "N_PARAMS": len(param["DATASET"]["PARAMETERS_OF_INTEREST"]),
            "LSTM_LAYERS": param["MODEL"]["LSTM_LAYERS"],
            "CONV_LAYERS": param["MODEL"]["CONV_LAYERS"],
            "FEED_FORWARD": param["MODEL"]["FEED_FORWARD"]
        }

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.network = Net(self.param_architecture).to(self.device)

        # TRAINING
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=self.learning_rate, weight_decay=param["TRAINING"]["L2_REGULARIZATION"])
        self.criterion = nn.MSELoss()
        self.early_stopper = EarlyStopper(patience=param["TRAINING"]["EARLY_STOPPING_PATIENCE"], min_delta=param["TRAINING"]["EARLY_STOPPING_MIN_DELTA"])

    def __str__(self):
        # (Batch Size, n_draws, n_types, Height,  Width)
        model_stats = summary(self.network, (
            self.batch_size, self.n_draws, len(self.img_types), self.train_dataset.get_height(),
            self.train_dataset.get_width()), verbose=0)
        return str(model_stats)

    def load_weights(self):
        self.network.load_state_dict(torch.load(self.path_weight))

    def train(self, verbose=False, epoch_variable=None):
        validation_losses = np.zeros(self.epochs)
        losses = np.zeros(self.epochs)

        # EPOCHS ITERATIONS
        for iter_epoch in range(self.epochs):
            if verbose: print("Epoch {}/{}".format(iter_epoch, self.epochs))

            # TRAINING
            running_loss = 0
            for iter_train, data in enumerate(self.train_dataloader):
                inputs, outputs, outputs_scaled = data
                inputs, outputs, outputs_scaled = inputs.to(self.device), outputs.to(self.device), outputs_scaled.to(self.device)
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
                    validation_inputs, validation_outputs, validation_outputs_scaled = validation_inputs.to(self.device), validation_outputs.to(self.device), validation_outputs_scaled.to(self.device)

                    # Forward Pass
                    predicted = self.network.forward(validation_inputs)
                    validation_loss = self.criterion(predicted, validation_outputs_scaled)

                    # Validation Loss data
                    running_validation_loss += validation_loss.item()

            validation_losses[iter_epoch] = running_validation_loss / (iter_val + 1)

            if epoch_variable is not None: epoch_variable.set((iter_epoch + 1) / self.epochs * 100)

            if self.early_stopper.early_stop(validation_losses[iter_epoch]):
                print("Early stopped")
                break
        print("Finished")
        # SAVE WEIGHT
        torch.save(self.network.state_dict(), self.path_weight)

        # PLOT PERFORMANCE CURVE
        plt.switch_backend('agg')
        plt.cla()
        X = np.arange(iter_epoch + 1)
        plt.plot(X, losses[:iter_epoch + 1], label="Training Loss")
        plt.plot(X, validation_losses[:iter_epoch + 1], label="Validation Loss")
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.legend()
        plt.savefig(self.path_performance_curve)

    def evaluate(self):
        self.network.train(False)
        self.network.eval()

        columns = [f"predicted_{p}" for p in self.parameter_of_interest] + [f"true_{p}" for p in self.parameter_of_interest]
        evaluation_data = pd.DataFrame(columns=columns)

        # EVALUATION LOOP
        differences = None
        for iter_test, data in enumerate(self.test_dataloader):
            test_inputs, test_outputs, test_outputs_scaled = data
            test_inputs, test_outputs, test_outputs_scaled = test_inputs.to(self.device), test_outputs.to(self.device), test_outputs_scaled.to(self.device)

            # Forward Pass
            predicted = self.network.forward(test_inputs)

            # Add evaluation data
            predicted, test_outputs_scaled = predicted.cpu(), test_outputs_scaled.cpu()
            for i in range(len(test_outputs_scaled)):
                evaluation_data.loc[len(evaluation_data.index)] = np.concatenate((predicted.detach().numpy()[i], test_outputs_scaled.numpy()[i]))

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
        df.to_csv(self.path_evaluation_stats, index=False)
        evaluation_data.to_csv(self.path_evaluation_data, index=False)

        return np.mean(differences)
