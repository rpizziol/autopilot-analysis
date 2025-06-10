import time
from locust import HttpUser, task
import numpy as np
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class MyUser(HttpUser):

    @task
    def index_page(self):
        think_time = np.random.exponential(1000)  # in ms
        time.sleep(think_time / 1000)  # in s
        self.client.get("/")
