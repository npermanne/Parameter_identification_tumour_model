import re
from collections import Counter
from simulation import Simulation
from simulation import DEFAULT_PARAMETERS
from enum import Enum
from multiprocessing import Pool
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import time
import os

# PATH (should be the same that in networks/dataLoader.py
DATASET_FOLDER_PATH = "datasets"
DATASET_FOLDER_NAME = "{}_start={}_interval={}_ndraw={}_size=({},{})"
DATASET_FILE_NAME = "dataset.csv"
DATA_NAME = "image{}_type={}_time={}.npy"
CELLS_TYPES = "cells_types"
CELLS_DENSITIES = "cells_densities"
OXYGEN = "oxygen"
GLUCOSE = "glucose"


class DatasetGenerator:
    """
    Class to generate a dataset of simulations images and their respective target parameters

    Parameters:
        img_size (tuple): size of the image
        start_draw (int): time of the first draw
        interval (int): interval between 2 consecutive draws  (in hours)
        n_draw (int): number of draw in the total sequence
        parameter_data_file (string): name of the csv file where the range of parameter is stored
        parameters_of_interest (list): list of the varying parameters of the dataset
        n_samples (int): number of samples in the dataset
        name (sting): name of the dataset to create

    Attributes:
        img_size (tuple): size of the image
        start_draw (int): time of the first draw
        interval (int): interval between 2 consecutive draws  (in hours)
        n_draw (int): number of draw in the total sequence
        parameter_data (Dataframe): dataframe containing the range of parameter
        parameters_of_interest (list): list of the varying parameters of the dataset
        n_samples (int): number of samples in the dataset
        name (sting): name of the dataset folder to create

    Methods:
        generate_sample(parameter, color_type=True): generate a single sample with a specific set of parameter
        plot_sample(parameter): plot a single sample with a specific set of parameter
        generate_parameters(): generate randomly n_sample different parameter
        generate_dataset(): generate randomly an entire dataset
        generate_dataset_multi_process(process_number: int, chunksize: int): generate randomly an entire dataset using multiple thread
        generate_missing(): generate the missing sample in case there is a problem

    """

    def __init__(self, img_size, start_draw, interval, n_draw, parameter_data_file, parameters_of_interest, n_samples,
                 name, treatment=None):
        self.img_size = img_size
        self.start_draw = start_draw
        self.interval = interval
        self.n_draw = n_draw
        self.parameter_data = pd.read_csv(parameter_data_file, index_col=0)
        self.parameters_of_interest = parameters_of_interest
        self.n_samples = n_samples
        self.name = DATASET_FOLDER_NAME.format(name, self.start_draw, self.interval, self.n_draw, self.img_size[0],
                                               self.img_size[1])
        self.treatment = treatment

    def generate_sample(self, parameter, color_type=True):
        sample = {}
        simu = Simulation(self.img_size[0], self.img_size[1], parameter, self.treatment)
        simu.cycle(self.start_draw)
        for i in range(self.n_draw):
            sample[self.start_draw + i * self.interval] = {CELLS_TYPES: simu.get_cells_type(color=color_type),
                                                           CELLS_DENSITIES: simu.get_cells_density(),
                                                           OXYGEN: simu.get_oxygen(), GLUCOSE: simu.get_glucose()}
            simu.cycle(self.interval)
        return sample

    def plot_sample(self, parameter):
        sample = self.generate_sample(parameter)
        plt.axis("off")
        for time, draw in sample.items():
            for type, matrix in draw.items():
                path = os.path.join("pictures",
                                    "simu_{}x{}_t{}_{}.png".format(self.img_size[0], self.img_size[1], time, type))
                plt.imshow(matrix)
                plt.savefig(path, bbox_inches='tight')

    def generate_parameters(self):
        parameters = {}
        for nameRow, row in self.parameter_data.iterrows():
            if nameRow not in self.parameters_of_interest:
                if row["Type"] == "int":
                    parameters[nameRow] = np.full(self.n_samples, int(row["Default Value"]))
                else:
                    parameters[nameRow] = np.full(self.n_samples, float(row["Default Value"]))
            else:
                if row["Type"] == "int":
                    parameters[nameRow] = np.random.randint(low=int(row["Minimum"]), high=int(row["Maximum"]) + 1,
                                                            size=self.n_samples)
                else:
                    parameters[nameRow] = np.random.uniform(low=float(row["Minimum"]), high=float(row["Maximum"]),
                                                            size=self.n_samples)
        return parameters

    def generate_dataset(self):
        general_path = os.path.join(DATASET_FOLDER_PATH, self.name)
        if not os.path.exists(general_path):
            os.makedirs(general_path)

        df = pd.DataFrame(self.generate_parameters())
        df.to_csv(os.path.join(general_path, DATASET_FILE_NAME), index=True)

        times = []
        print("Starting for {}".format(self.n_samples), end='\r')
        for index, rows in df.iterrows():
            start = time.time()
            sample = self.generate_sample(rows, color_type=False)
            for t, draw in sample.items():
                for type, matrix in draw.items():
                    path = os.path.join(general_path, DATA_NAME.format(index, type, t))
                    np.save(path, matrix)
            end = time.time()
            times.append(end - start)
            print("{} out of {} done \t Expected time remaining = {} s".format(index + 1, self.n_samples,
                                                                               (self.n_samples - index - 1) * np.mean(
                                                                                   times)), end='\r')

    def generate_dataset_multi_process(self, process_number: int):
        general_path = os.path.join(DATASET_FOLDER_PATH, self.name)
        if not os.path.exists(general_path):
            os.makedirs(general_path)

        df = pd.DataFrame(self.generate_parameters())
        df.to_csv(os.path.join(general_path, DATASET_FILE_NAME), index=True)

        global generate

        def generate(i):
            row = df.iloc[i]
            sample = self.generate_sample(row, color_type=False)
            for t, draw in sample.items():
                for type, matrix in draw.items():
                    path = os.path.join(general_path, DATA_NAME.format(i, type, t))
                    np.save(path, matrix)
            print(f"Sample {i} done !")

        pool = Pool(process_number)
        pool.map(generate, range(df.shape[0]))

    def generate_missing_multi_process(self, process_number: int):
        general_path = os.path.join(DATASET_FOLDER_PATH, self.name)
        df = pd.read_csv(os.path.join(general_path, DATASET_FILE_NAME), index_col=0)
        all_files = os.listdir(general_path)
        all_files.remove(DATASET_FILE_NAME)
        pattern = r'image(\d+)_type=(\w+)_time=(\d+)\.npy'
        samples = Counter([re.findall(pattern, file)[0][0] for file in all_files])
        missing_samples = [sample for sample in range(self.n_samples) if samples.get(str(sample), 0) != self.n_draw * 4]

        global generate

        def generate(i):
            row = df.iloc[i]
            sample = self.generate_sample(row, color_type=False)
            for t, draw in sample.items():
                for type, matrix in draw.items():
                    path = os.path.join(general_path, DATA_NAME.format(i, type, t))
                    np.save(path, matrix)
            print(f"Sample {i} done !")

        pool = Pool(process_number)
        pool.map(generate, missing_samples)


if __name__ == '__main__':
    dose_hours = list(range(350, 1300, 24))
    default_treatment = np.zeros(1300)
    default_treatment[dose_hours] = 2

    parameter_data_file_path = os.path.join("simulation", "parameter_data.csv")
    param_interest = [
        "average_healthy_glucose_absorption",
        "average_cancer_glucose_absorption",
        "average_healthy_oxygen_consumption",
        "average_cancer_oxygen_consumption",
        "cell_cycle"
    ]
    dataset_generator = DatasetGenerator((64, 64), 350, 100, 8, parameter_data_file_path, param_interest, 3200,
                                         "full_treatment_dataset", treatment=default_treatment)

    dataset_generator.generate_missing_multi_process(12)
