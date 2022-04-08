import numpy as np
from time import sleep
from math import exp
shape=19.28
rate=1.61
#  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
sample=int(exp(np.random.gamma(shape, 1.0/rate, 1))) + 1200
if sample > 86400:
	print("Sleep for ", 86400)
	sleep(86400)
else:
	print("Sleep for ", sample)
	sleep(sample)
