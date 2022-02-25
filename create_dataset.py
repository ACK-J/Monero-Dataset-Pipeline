import os
import pickle
# find last directories
# Combine 5 files
# Enrich data
# Add to final dataset

# TODO add checkpoint saves

# Key = tx hash, val = dict(transaction metadata)
data = {}


def combine_files(Wallet_addrs):
    for addr in Wallet_addrs:
        with open("./cli_export_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                transaction = {}
                values = line.split(",")
                transaction['Tx_Hash'] = values[6].strip()
                transaction['Block_Number'] = int(values[0].strip())
                transaction['Direction'] = values[1].strip()
                transaction['Tx_Timestamp'] = values[3].strip()
                transaction['Amount'] = float(values[4].strip())
                transaction['Wallet_Balance'] = float(values[5].strip())
                transaction['Tx_Fee'] = values[8].strip()
                transaction['Destination_Address'] = values[9].strip()

                if transaction['Tx_Hash'] not in data:
                    data[transaction['Tx_Hash']] = transaction

        with open("./xmr_report_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                values = line.split(",")
                if values[2].strip() in data:
                    data[values[2].strip()]['Tx_Version'] = values[4].strip()
                    data[values[2].strip()]['Tx_Public_Key'] = values[3].strip()
                    data[values[2].strip()]['Output_Pub_Key'] = values[8].strip()
                    data[values[2].strip()]['Output_Key_Img'] = values[9].strip()
                    data[values[2].strip()]['Output_Number_Spent'] = values[10].strip()
                else:
                    transaction = {}
                    transaction['Tx_Hash'] = values[2].strip()
                    transaction['Tx_Version'] = values[4].strip()
                    transaction['Tx_Public_Key'] = values[3].strip()
                    transaction['Output_Pub_Key'] = values[8].strip()
                    transaction['Output_Key_Img'] = values[9].strip()
                    transaction['Output_Number_Spent'] = values[10].strip()
                    data[values[2].strip()] = transaction

        with open("./xmr_report_outgoing_txs_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                values = line.split(",")
                if values[2].strip() in data:
                    data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
                else:
                    transaction = {}
                    transaction['Tx_Hash'] = values[2].strip()
                    transaction['Tx_Timestamp'] = values[0].strip()
                    transaction['Block_Number'] = values[1].strip()
                    transaction['Output_Pub_Key'] = values[3].strip()
                    transaction['Output_Key_Img'] = values[4].strip()
                    transaction['Ring_no/Ring_size'] = values[5].strip()
                    data[values[2].strip()] = transaction

        # with open("./xmr_report_ring_members_" + addr + ".csv", "r") as fp:
        #     next(fp)  # Skip header of csv
        #     for line in fp:
        #         values = line.split(",")
        #         if values[2].strip() in data:
        #             data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
        #         else:
        #             transaction = {}
        #             transaction['Tx_Hash'] = values[2].strip()
        #             transaction['Tx_Timestamp'] = values[0].strip()
        #             transaction['Block_Number'] = values[1].strip()
        #             transaction['Output_Pub_Key'] = values[3].strip()
        #             transaction['Output_Key_Img'] = values[4].strip()
        #             transaction['Ring_no/Ring_size'] = values[5].strip()
        #             data[values[2].strip()] = transaction

        # with open("./xmr_report_ring_members_freq_" + addr + ".csv", "r") as fp:
        #     next(fp)  # Skip header of csv
        #     for line in fp:
        #         values = line.split(",")
        #         if values[2].strip() in data:
        #             data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
        #         else:
        #             transaction = {}
        #             transaction['Tx_Hash'] = values[2].strip()
        #             transaction['Tx_Timestamp'] = values[0].strip()
        #             transaction['Block_Number'] = values[1].strip()
        #             transaction['Output_Pub_Key'] = values[3].strip()
        #             transaction['Output_Key_Img'] = values[4].strip()
        #             transaction['Ring_no/Ring_size'] = values[5].strip()
        #             data[values[2].strip()] = transaction


def discover_wallet_directories():
    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in os.walk("./Wallets"):
        for name in files:
            if name.lower().endswith(".csv"):
                if root not in unique_directories:
                    unique_directories.append(root)
    print(unique_directories)
    cwd = os.getcwd()
    for dir in unique_directories:
        os.chdir(dir)
        Wallet_addrs = []
        for root, dirs, files in os.walk("."):
            for name in files:
                if name.lower().endswith(".csv"):
                    addr = name[::-1].split(".")[1].split("_")[0][::-1]
                    if addr not in Wallet_addrs:
                        Wallet_addrs.append(addr)
            combine_files(Wallet_addrs)
        print(Wallet_addrs)
        os.chdir(cwd)
    pass


def main():
    discover_wallet_directories()
    with open("data.pkl", "wb") as fp:
        pickle.dump(data, fp)

if __name__ == '__main__':
    main()
