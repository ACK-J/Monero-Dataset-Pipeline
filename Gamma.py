import numpy as np
from time import sleep
from math import exp
shape=19.28
rate=1.61
#  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
sample=int(exp(np.random.gamma(shape, 1.0/rate, 1))) + 1200
print("Sleep for ", sample)
if sample > 43200:  # 12 hours
	sleep(43200)
else:
	sleep(sample)
