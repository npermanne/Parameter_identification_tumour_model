from skimage.metrics import structural_similarity
from enum import Enum
import math
import numpy as np
from scipy import signal
from sklearn.metrics import normalized_mutual_info_score
from sklearn.feature_selection import mutual_info_regression


def ssim_function(image1, image2):
    min_value, max_value = min(np.min(image1), np.min(image2)), max(np.max(image1), np.max(image2))
    return structural_similarity(image1, image2, full=True, data_range=max_value - min_value)[0]


def corr_hist_function(image1, image2):
    min_value, max_value = min(np.min(image1), np.min(image2)), max(np.max(image1), np.max(image2))
    hist1, bins1 = np.histogram(image1, bins=np.linspace(min_value, max_value + 1, 100))
    hist2, bins2 = np.histogram(image2, bins=np.linspace(min_value, max_value + 1, 100))
    return np.corrcoef(hist1, hist2)[0, 1]


def dice_function(image1, image2):
    flatten_image1 = image1.flatten()
    flatten_image2 = image2.flatten()
    number_of_equal = np.count_nonzero(flatten_image1 == flatten_image2)
    return 2 * number_of_equal / (len(flatten_image1) * len(flatten_image2))


class Metric(Enum):
    IMAGE_ABSOLUTE_DIFFERENCE = 0
    CORRELATION_HISTOGRAM = 1
    SSIM = 2
    MEAN_ABSOLUTE_ERROR = 3
    ROOT_MEAN_SQUARED_ERROR = 4
    MAX_ABSOLUTE_ERROR = 5
    CORRELATION = 6
    DICE = 7
    MUTUAL_INFORMATION = 8
    CONTINUOUS_MUTUAL_INFORMATION = 9

    def __str__(self):
        if self == Metric.IMAGE_ABSOLUTE_DIFFERENCE:
            return "image absolute difference"
        elif self == Metric.CORRELATION_HISTOGRAM:
            return "histogram correlation"
        elif self == Metric.SSIM:
            return "ssim index"
        elif self == Metric.MEAN_ABSOLUTE_ERROR:
            return "mean absolute error"
        elif self == Metric.ROOT_MEAN_SQUARED_ERROR:
            return "root mean squared error"
        elif self == Metric.MAX_ABSOLUTE_ERROR:
            return "max absolute error"
        elif self == Metric.CORRELATION:
            return "correlation"
        elif self == Metric.DICE:
            return "sørensen–Dice coefficient "
        elif self == Metric.MUTUAL_INFORMATION:
            return "mutual information"
        elif self == Metric.CONTINUOUS_MUTUAL_INFORMATION:
            return "continuous mutual information"

    def get_function(self):
        if self == Metric.IMAGE_ABSOLUTE_DIFFERENCE:
            return lambda a, b: np.absolute(a - b)
        elif self == Metric.CORRELATION_HISTOGRAM:
            return corr_hist_function
        elif self == Metric.SSIM:
            return ssim_function
        elif self == Metric.MEAN_ABSOLUTE_ERROR:
            return lambda a, b: np.abs(a - b).mean()
        elif self == Metric.ROOT_MEAN_SQUARED_ERROR:
            return lambda a, b: math.sqrt(np.square(a - b).mean())
        elif self == Metric.MAX_ABSOLUTE_ERROR:
            return lambda a, b: np.max(np.absolute(a - b))
        elif self == Metric.CORRELATION:
            return lambda a, b: np.corrcoef(a.flatten(), b.flatten())[0, 1]
        elif self == Metric.DICE:
            return dice_function
        elif self == Metric.MUTUAL_INFORMATION:
            return lambda a, b: normalized_mutual_info_score(a.flatten(), b.flatten())
        elif self == Metric.CONTINUOUS_MUTUAL_INFORMATION:
            return lambda a, b: mutual_info_regression(np.array([a.flatten()]).transpose(), b.flatten())[0]
