import pickle
import random

"""
https://user-images.githubusercontent.com/60232273/155869893-2146401b-6cc6-4b41-be57-74b5e58624ed.png
"""

def main():
    with open("xmr_tx_fee_distribution.pkl", "rb") as fp:
        data = pickle.load(fp)
        # 1 0.00000002
        # 2 0.00000008
        # 3 0.0000004
        # 4 0.00000332
        Base_Ratio = 0.00000002
        rand_idx = random.randrange(0, len(data)-1)
        xmr_per_byte = (data[rand_idx]['tx_fee'] * 0.000000000001) / data[rand_idx]['tx_size']
        if xmr_per_byte <= Base_Ratio:
            print("1")
        elif xmr_per_byte <= (Base_Ratio * 4):
            print("2")
        elif xmr_per_byte <= (Base_Ratio * 20):
            print("3")
        else:
            print("4")


if __name__ == '__main__':
    main()
