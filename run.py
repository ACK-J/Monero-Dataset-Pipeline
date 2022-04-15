from numpy import random
from time import sleep, time
from math import exp
from datetime import datetime, timedelta
from subprocess import Popen, PIPE, TimeoutExpired
from sys import argv
from random import randint
from colorama import Fore, Style
from os import getenv, getcwd, remove
from uuid import uuid4

NETWORK = getenv('RUN_SH_NETWORK')


def get_new_wallet_id():
    """

    :return:
    """
    return str(uuid4()).replace("-", "")


def runcommand(cmd):
    """

    :param cmd:
    :return:
    """
    proc = None
    while proc is None:
        try:
            proc = Popen(cmd,
                        stdout=PIPE,
                        stderr=PIPE,
                        shell=True,
                        universal_newlines=True)
            std_out, std_err = proc.communicate(timeout=3600)
        except TimeoutExpired as e:
            print(Fore.RED + "Warning: Transaction timed out, restarting!" + Style.RESET_ALL)
    return proc.returncode, std_out, std_err


def delete_wallet(wallet_name):
    print(Fore.GREEN + "Deleting " + wallet_name + " since it never transacted!" + Style.RESET_ALL)
    remove("./" + wallet_name)
    print(Fore.GREEN + "Deleting " + wallet_name + ".adddress.txt since it never transacted!" + Style.RESET_ALL)
    remove("./" + wallet_name + ".adddress.txt")
    print(Fore.GREEN + "Deleting " + wallet_name + ".keys since it never transacted!" + Style.RESET_ALL)
    remove("./" + wallet_name + ".keys")


def main():
    # Error Checking
    if len(argv) != 2:
        print("Usage Error: ./run.py < Wallets Name >")
        exit(1)
    # Gamma Parameters
    shape = 19.28
    rate = 1.61
    # The time to stop collection in epoch
    endtime_epoch = datetime.fromtimestamp(1656637261)  # June 30th
    # The wallet ID starts off blank but if a new wallet needs to be made it will be changed
    current_wallet_id = ""
    # A one line bash command that will call the spend Expect script with an amount, priority and wallet id
    oneliner = './' + argv[1] + """-spend.exp $(python3 -c 'import random;print(format(random.uniform(0.0001, 0.000000000001), ".12f"))') $(python3 -c 'import random;print(random.randint(1,4))') """ + '"' + current_wallet_id + '" ' + ' | grep -v "Height*/*"'

    # When this script first runs the only funds in the wallet will be brand new so we must wait 20 mins
    print(Fore.BLUE + "Sleeping for 20 minutes for new coins to unlock." + Style.RESET_ALL)
    sleep(1380)

    # Metrics
    total_transfers = 0
    curr_wallet_transfers = 0
    num_extra_wallets = 0

    # If the funding wallet is open send it CTRL-C
    _, num_open_files, _ = runcommand("lsof | grep -i " + NETWORK + "-Funding.keys | wc -l")
    if num_open_files.split()[0] != "0":
        _, _, _ = runcommand("ps aux | grep -i " + NETWORK + "-Funding.keys | awk '{print $2}' | xargs kill -2 ")
        sleep(3)

    while True:
        print(getcwd())
        #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
        sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
        # Calculate the date + time when the sleeping will be done
        sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=sample)
        print(Fore.BLUE + "Delay chosen: " + str(sleep_time) + Style.RESET_ALL)

        # Check if the sleep time passes the end time for collection
        if sleep_time >= endtime_epoch:
            # If there are no transactions in the old wallet, and it will never transact again, then delete it
            if curr_wallet_transfers == 0:
                delete_wallet(argv[1] + current_wallet_id)
            # Dont make any new wallets 2 days before the end date
            if datetime.fromtimestamp(int(time())) > (endtime_epoch - timedelta(seconds=172800)):
                print("EXIT: End date less then 48 hours away.")
                exit(1)
            # check if the process is making a ton of wallets
            if num_extra_wallets > 100:
                print("EXIT: Current process made more than 100 wallets.")
                exit(1)

            print(Fore.RED + "Sleep time surpassed the end time. Making a new wallet!" + Style.RESET_ALL)
            # Metrics
            num_extra_wallets += 1
            curr_wallet_transfers = 0

            # Print the current date and time
            _, date, _ = runcommand("date")
            print(Fore.BLUE + "Current time: " + date.strip() + Style.RESET_ALL)

            #  Make a new wallet id
            print(Fore.BLUE + "Making new Wallet..." + Style.RESET_ALL)
            current_wallet_id = get_new_wallet_id()
            # Call makewallet.exp and pass the wallet name with the wallet id
            returncode, std_out, std_err = runcommand("../MakeWallet.exp " + argv[1] + current_wallet_id)
            print(std_out)
            print(std_err)

            # Check to see if another process has the funding wallet open
            print(Fore.BLUE + "Checking if another program is using the funding wallet..." + Style.RESET_ALL)
            _, walletAddr, _ = runcommand("cat " + argv[1] + current_wallet_id + ".address.txt")
            sleep(randint(2, 20))
            _, num_open_files, _ = runcommand("lsof | grep -i " + NETWORK + "-Funding.keys | wc -l")
            while num_open_files.split()[0] != "0":
                sleep(randint(2, 20))
                _, num_open_files, _ = runcommand("lsof | grep -i " + NETWORK + "-Funding.keys | wc -l")

            #  Fund the new wallet
            print(Fore.BLUE + "Funding the new wallet..." + Style.RESET_ALL)
            returncode, std_out, std_err = runcommand("../../" + NETWORK + "-FundWallet.exp " + walletAddr.strip() + ' | grep -v "Height*/*" | grep -v "Height*txid*"')
            print(std_out)
            print(std_err)

            #  Wait 20 mins for the new coins to be usable
            print(Fore.BLUE + "Sleep for 20 mins to unlock new coins." + Style.RESET_ALL)
            sleep(1380)

            #  Transfer a random amount of coins to the other wallet
            print(Fore.BLUE + "Executing a transfer..." + Style.RESET_ALL)
            oneliner = './' + argv[1] + """-spend.exp $(python3 -c 'import random;print(format(random.uniform(0.0001, 0.000000000001), ".12f"))') $(python3 -c 'import random;print(random.randint(1,4))') """ + '"' + current_wallet_id + '" ' + ' | grep -v "Height*/*"'
            returncode, std_out, std_err = runcommand(oneliner)
            print(std_out)
            print(std_err)

            # Metrics
            curr_wallet_transfers += 1
            total_transfers += 1
            print(Fore.BLUE + "Stats:")
            print("\tTotal Transfers: " + str(total_transfers))
            print("\tCurrent Wallet Transfers: " + str(curr_wallet_transfers))
            print("\tNumber of Extra Wallets: " + str(num_extra_wallets) + Style.RESET_ALL)

            #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
            new_sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
            # Calculate the date + time when the sleeping will be done
            sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=new_sample)
            while sleep_time >= endtime_epoch:
                #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
                new_sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
                # Calculate the date + time when the sleeping will be done
                sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=new_sample)
            print(Fore.BLUE + date.strip() + Style.RESET_ALL)
            print(Fore.BLUE + "Sleeping for " + Fore.GREEN + str(new_sample) + Fore.BLUE + " seconds until: " + Fore.GREEN + str(sleep_time) + Style.RESET_ALL)
            print()

            sleep(new_sample)
        else:  # Sleep time is within the collection time
            print(Fore.BLUE + "Sleep was less than the end time!" + Style.RESET_ALL)
            print(Fore.BLUE + "Executing a transfer..." + Style.RESET_ALL)
            returncode, std_out, std_err = runcommand(oneliner)
            print(std_out)
            print(std_err)

            # Metrics
            curr_wallet_transfers += 1
            total_transfers += 1
            print(Fore.BLUE + "Stats:")
            print("\tTotal Transfers: " + str(total_transfers))
            print("\tCurrent Wallet Transfers: " + str(curr_wallet_transfers))
            print("\tNumber of Extra Wallets: " + str(num_extra_wallets) + Style.RESET_ALL)

            _, date, _ = runcommand("date")
            print(Fore.BLUE + "Current time: " + str(date.strip()) + Style.RESET_ALL)
            print(Fore.BLUE + "Sleeping for " + Fore.GREEN + str(sample) + Fore.BLUE + " seconds until: " + Fore.GREEN + str(sleep_time) + Style.RESET_ALL)
            print()

            sleep(sample)


if __name__ == '__main__':
    main()
