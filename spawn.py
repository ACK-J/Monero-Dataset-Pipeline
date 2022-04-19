from numpy import random
from time import sleep, time
from math import exp
from datetime import datetime, timedelta
from subprocess import Popen, PIPE, TimeoutExpired
from sys import argv
from colorama import Fore, Style
from os import getenv, getcwd, system

NETWORK = getenv('RUN_SH_NETWORK')
END_COLLECTION_EPOCH_DATE = getenv('END_COLLECTION_EPOCH_DATE')


def runcommand(cmd):
    """

    :param cmd:
    :return:
    """
    std_out = None
    while std_out is None:
        try:
            proc = Popen(cmd,
                        stdout=PIPE,
                        stderr=PIPE,
                        shell=True,
                        universal_newlines=True)
            std_out, std_err = proc.communicate(timeout=400)
            return proc.returncode, std_out, std_err
        except TimeoutExpired:
            print(Fore.RED + "Warning: Transaction timed out!" + Style.RESET_ALL)
            # Send CTRL C to any processes with the keys file open
            # https://superuser.com/questions/97844/how-can-i-determine-what-process-has-a-file-open-in-linux
            system("fuser ./" + str(argv[1]) + ".keys  2> /dev/null | xargs -I{} kill -2 {} 2> /dev/null")
            sleep(1)


def main():
    # Error Checking
    if len(argv) != 2:
        print("Usage Error: ./spawn.py < Wallets Name >")
        exit(1)
    # Gamma Parameters
    shape = 19.28
    rate = 1.61

    # The time to stop collection in epoch
    endtime_epoch = datetime.fromtimestamp(int(END_COLLECTION_EPOCH_DATE))

    # A one line bash command that will call the spend Expect script with an amount, priority and wallet id
    oneliner = './' + argv[1] + """-spend.exp $(python3 -c 'import random;print(format(random.uniform(0.0001, 0.000000000001), ".12f"))') $(python3 -c 'import random;print(random.randint(1,4))') """ + ' | grep -v "Height*/*"'

    # When this script first runs the only funds in the wallet will be brand new so we must wait 20 mins
    print(Fore.BLUE + "Sleeping for 20 minutes for new coins to unlock." + Style.RESET_ALL)
    # 20 minute lockout delay
    lockout_delay = 1400
    sleep(lockout_delay)

    # Metrics
    total_transfers = 0         # Total transactions made for the current process

    while True:  # infinitely transact
        print(getcwd())
        print(Fore.BLUE + "Current Time: " + str(datetime.fromtimestamp(int(time()))) + Style.RESET_ALL)
        #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
        sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
        # Calculate the date + time when the sleeping will be done
        sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=sample)
        print(Fore.BLUE + "Delay chosen: " + str(sleep_time) + Style.RESET_ALL)

        if datetime.fromtimestamp(int(time())) > (endtime_epoch - timedelta(seconds=172800)):
            print(Fore.RED + "EXIT: End date less then 48 hours away." + Style.RESET_ALL)
            sleep(120)
            exit(1)
        if sleep_time >= endtime_epoch:
            print(Fore.RED + "Sleep time surpassed the end time. Choosing a Different Time!" + Style.RESET_ALL)
            new_sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
            new_sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=new_sample)
            while new_sleep_time >= endtime_epoch:
                #  Sleep a random value chosen at random from a gamma dist + 1200 seconds for the 20 min lockout
                new_sample = int(exp(random.gamma(shape, 1.0 / rate, 1))) + 1200
                # Calculate the date + time when the sleeping will be done
                new_sleep_time = datetime.fromtimestamp(int(time())) + timedelta(seconds=new_sample)
            print(Fore.BLUE + "Sleeping for " + Fore.GREEN + str(new_sample) + Fore.BLUE + " seconds until: " + Fore.GREEN + str(new_sleep_time) + Style.RESET_ALL)
            print()
            print(Fore.BLUE + "Executing a transfer..." + Style.RESET_ALL)
            # Send CTRL C to any processes with the keys file open
            # https://superuser.com/questions/97844/how-can-i-determine-what-process-has-a-file-open-in-linux
            system("fuser ./" + str(argv[1]) + ".keys  2> /dev/null | xargs -I{} kill -2 {} 2> /dev/null")
            system(oneliner)

            # Metrics
            total_transfers += 1
            print(Fore.BLUE + "Stats:")
            print("\tTotal Transfers: " + str(total_transfers))

            _, date, _ = runcommand("date")
            print("\t" + Fore.BLUE + "Current time: " + str(date.strip()) + Style.RESET_ALL)
            print("\t" + Fore.BLUE + "Sleeping for " + Fore.GREEN + str(new_sample) + Fore.BLUE + " seconds until: " + Fore.GREEN + str(new_sleep_time) + Style.RESET_ALL)
            print()

            sleep(new_sample)

        else:  # Sleep time is within the collection time... so transact as normal
            print(Fore.BLUE + "Sleep was less than the end time!" + Style.RESET_ALL)
            print(Fore.BLUE + "Executing a transfer..." + Style.RESET_ALL)
            # Send CTRL C to any processes with the keys file open
            # https://superuser.com/questions/97844/how-can-i-determine-what-process-has-a-file-open-in-linux
            system("fuser ./" + str(argv[1]) + ".keys  2> /dev/null | xargs -I{} kill -2 {} 2> /dev/null")
            system(oneliner)

            # Metrics
            total_transfers += 1
            print(Fore.BLUE + "Stats:")
            print("\tTotal Transfers: " + str(total_transfers))

            _, date, _ = runcommand("date")
            print("\t" + Fore.BLUE + "Current time: " + str(date.strip()) + Style.RESET_ALL)
            print("\t" + Fore.BLUE + "Sleeping for " + Fore.GREEN + str(sample) + Fore.BLUE + " seconds until: " + Fore.GREEN + str(sleep_time) + Style.RESET_ALL)
            print()

            sleep(sample)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(e)
        print(traceback.print_exc())
        sleep(1200)
