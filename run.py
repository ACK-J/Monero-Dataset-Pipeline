import numpy as np
from time import sleep, time
from math import exp
from datetime import datetime, timedelta
import subprocess
from sys import argv
import random
import string

NETWORK = "stagenet"


def get_new_wallet_id():
    """Generate a random string"""
    str = string.ascii_uppercase
    return "-" + ''.join(random.choice(str) for i in range(10))


def runcommand(cmd):
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True,
                            universal_newlines=True)
    std_out, std_err = proc.communicate()
    return proc.returncode, std_out, std_err


def main():
    # Error Checking
    if len(argv) != 2:
        print("Usage Error: ./run.py < Wallets Name >")
        exit(1)
    shape = 19.28
    rate = 1.61
    endtime_epoch = datetime.fromtimestamp(1656637261)  # June 30th
    current_wallet_id = ""
    oneliner = 'cd ../../; priority=$(python3 select_transaction_priority.py); cd -; ./' + argv[1] + """-spend.exp $(python3 -c 'import random;print(format(random.uniform(0.0001, 0.000000000001), ".12f"))') $(echo $priority) """ + '"' + current_wallet_id + '"' + '; date;'
    print(oneliner)

    print("Sleeping for 20 minutes for new coins to unlock.")
    sleep(1200)

    while True:
        #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
        sample = int(exp(np.random.gamma(shape, 1.0 / rate, 1))) + 1200
        sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=sample)
        print("Sleep until " + str(sleep_time))
        if sleep_time >= endtime_epoch:
            _, date, _ = runcommand("date")
            print("Current time " + date.strip())

            print("Making new Wallet...")
            current_wallet_id = get_new_wallet_id()
            # make new wallet
            returncode, std_out, std_err = runcommand("../MakeWallet.exp " + argv[1] + current_wallet_id)
            print("../MakeWallet.exp " + argv[1] + current_wallet_id)
            print(std_out)
            print(std_err)

            print("Checking if another program is using the funding wallet...")
            _, walletAddr, _ = runcommand("cat " + argv[1] + current_wallet_id + ".address.txt")
            # fund it
            sleep(random.randint(2, 20))
            _, num_open_files, _ = runcommand("lsof | grep -i " + NETWORK + "-Funding.keys | wc -l")
            while num_open_files.split()[0] != "0":
                sleep(random.randint(2, 20))
                _, num_open_files, _ = runcommand("lsof | grep -i " + NETWORK + "-Funding.keys | wc -l")

            print("Funding the new wallet")
            returncode, std_out, std_err = runcommand("../../" + NETWORK + "-FundWallet.exp " + walletAddr.strip())
            print("../../" + NETWORK + "-FundWallet.exp " + walletAddr.strip())
            print(std_out)
            print(std_err)

            print("Sleep for 20 mins to unlock new coins.")
            sleep(1200)

            print("Executing a transfer...")
            oneliner = 'cd ../../; priority=$(python3 select_transaction_priority.py); cd -; ./' + argv[1] + """-spend.exp $(python3 -c 'import random;print(format(random.uniform(0.0001, 0.000000000001), ".12f"))') $(echo $priority) """ + '"' + current_wallet_id + '"' + '; date;'
            print(oneliner)
            returncode, std_out, std_err = runcommand(oneliner)
            print(std_out)
            print(std_err)
            pass
        else:
            print("Executing a transfer...")
            returncode, std_out, std_err = runcommand(oneliner)
            print(std_out)
            print(std_err)

            _, date, _ = runcommand("date")
            print(date.strip())
            print("Sleep for", sample, "seconds")
            sleep(sample)


if __name__ == '__main__':
    main()
