import os
from functools import wraps
import time
import pickle

def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(f'Function {func.__name__} Took: {total_time:.4f} seconds')
        return result
    return timeit_wrapper


def generate_logger(file_name:str):
    r"""generate logger config"""
    logger_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {"format" : "%(asctime)s %(levelname)s:%(message)s"}
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "formatter": "simple",
                "level": "DEBUG",
                "filename": f"./logs/{file_name}.log"
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": "ERROR"
            }
        },
        'loggers': {
            file_name: {
                'handlers': ['console', 'file'],
                'level': 'DEBUG',
                'propagate': True  
            },
        }
    }
    return logger_config


def load_data(pkl_path: str):
    r"""load data which cleaed after load.py"""
    assert os.path.isfile(pkl_path)
    with open(pkl_path, 'rb') as f:
        loadedData = pickle.load(f)
    return loadedData